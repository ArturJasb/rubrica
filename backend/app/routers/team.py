"""Usuário atual, workspace compartilhado e convites do time."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..auth import audit, get_member, require_roles
from ..db import get_db
from ..schemas import InviteIn, RoleIn, WorkspaceIn

router = APIRouter(prefix="/api", tags=["time"])

admin_only = require_roles(m.ROLE_ADMIN)


def member_out(x: m.Member) -> dict:
    return {"id": x.id, "user_id": x.user_id, "email": x.email, "name": x.name, "role": x.role, "created_at": x.created_at}


@router.get("/me")
def me(db: Session = Depends(get_db), member: m.Member = Depends(get_member)):
    ws = db.get(m.Workspace, member.workspace_id)
    return {"member": member_out(member), "workspace": {"id": ws.id, "name": ws.name}}


@router.patch("/workspace")
def rename_workspace(body: WorkspaceIn, db: Session = Depends(get_db), member: m.Member = Depends(admin_only)):
    ws = db.get(m.Workspace, member.workspace_id)
    ws.name = body.name.strip()
    db.commit()
    return {"id": ws.id, "name": ws.name}


@router.get("/team")
def team(db: Session = Depends(get_db), member: m.Member = Depends(get_member)):
    members = db.scalars(
        select(m.Member).where(m.Member.workspace_id == member.workspace_id).order_by(m.Member.created_at)
    ).all()
    invites = db.scalars(
        select(m.Invite)
        .where(m.Invite.workspace_id == member.workspace_id, m.Invite.accepted_at.is_(None))
        .order_by(m.Invite.created_at.desc())
    ).all()
    return {
        "members": [member_out(x) for x in members],
        "invites": [{"id": v.id, "email": v.email, "role": v.role, "created_at": v.created_at} for v in invites],
    }


@router.post("/team/invites", status_code=201)
def invite(body: InviteIn, db: Session = Depends(get_db), member: m.Member = Depends(admin_only)):
    email = body.email.lower()
    existing = db.scalar(select(m.Member).where(func.lower(m.Member.email) == email))
    if existing:
        if existing.workspace_id == member.workspace_id:
            raise HTTPException(409, "Essa pessoa já faz parte do time")
        raise HTTPException(409, "Esse e-mail já usa a Rubrica em outro workspace")
    pending = db.scalar(select(m.Invite).where(
        m.Invite.workspace_id == member.workspace_id, func.lower(m.Invite.email) == email, m.Invite.accepted_at.is_(None)
    ))
    if pending:
        pending.role = body.role
        inv = pending
    else:
        inv = m.Invite(workspace_id=member.workspace_id, email=email, role=body.role, invited_by=member.user_id)
        db.add(inv)
    audit(db, member, f"convidou:{email}")
    db.commit()
    return {"id": inv.id, "email": inv.email, "role": inv.role, "created_at": inv.created_at}


@router.delete("/team/invites/{invite_id}", status_code=204)
def cancel_invite(invite_id: str, db: Session = Depends(get_db), member: m.Member = Depends(admin_only)):
    inv = db.get(m.Invite, invite_id)
    if not inv or inv.workspace_id != member.workspace_id:
        raise HTTPException(404, "Convite não encontrado")
    db.delete(inv)
    db.commit()


@router.patch("/team/members/{member_id}")
def change_role(member_id: str, body: RoleIn, db: Session = Depends(get_db), member: m.Member = Depends(admin_only)):
    target = db.get(m.Member, member_id)
    if not target or target.workspace_id != member.workspace_id:
        raise HTTPException(404, "Membro não encontrado")
    if target.id == member.id and body.role != m.ROLE_ADMIN:
        raise HTTPException(400, "Você não pode remover seu próprio acesso de admin")
    target.role = body.role
    db.commit()
    return member_out(target)


@router.delete("/team/members/{member_id}", status_code=204)
def remove_member(member_id: str, db: Session = Depends(get_db), member: m.Member = Depends(admin_only)):
    target = db.get(m.Member, member_id)
    if not target or target.workspace_id != member.workspace_id:
        raise HTTPException(404, "Membro não encontrado")
    if target.id == member.id:
        raise HTTPException(400, "Você não pode remover a si mesmo")
    db.delete(target)
    db.commit()
