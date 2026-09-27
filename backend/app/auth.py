"""Autenticação: o frontend faz login no Supabase Auth e envia o access token
no header Authorization. Aqui validamos esse token perguntando ao próprio
Supabase quem é o usuário (funciona com qualquer tipo de chave JWT do projeto).
"""
import time
from dataclasses import dataclass

import httpx
from fastapi import Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import ROLE_ADMIN, AuditLog, Invite, Member, Workspace, now


@dataclass
class AuthUser:
    id: str
    email: str
    name: str


# Cache curto (token -> usuário) para não chamar o Supabase a cada requisição
_cache: dict[str, tuple[float, AuthUser]] = {}
_CACHE_TTL = 60


def verify_token(token: str) -> AuthUser:
    hit = _cache.get(token)
    if hit and hit[0] > time.time():
        return hit[1]

    s = get_settings()
    if not s.supabase_url or not s.supabase_anon_key:
        raise HTTPException(500, "Supabase não configurado no servidor")
    try:
        r = httpx.get(
            f"{s.supabase_url.rstrip('/')}/auth/v1/user",
            headers={"apikey": s.supabase_anon_key, "Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except httpx.HTTPError:
        raise HTTPException(503, "Não foi possível validar a sessão agora")
    if r.status_code != 200:
        raise HTTPException(401, "Sessão inválida ou expirada. Entre novamente.")

    data = r.json()
    meta = data.get("user_metadata") or {}
    email = (data.get("email") or "").lower()
    user = AuthUser(id=data["id"], email=email, name=meta.get("full_name") or email.split("@")[0])

    if len(_cache) > 1000:
        _cache.clear()
    _cache[token] = (time.time() + _CACHE_TTL, user)
    return user


def get_current_user(authorization: str = Header(default="")) -> AuthUser:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Faça login para continuar")
    return verify_token(authorization.split(" ", 1)[1].strip())


def ensure_member(db: Session, user: AuthUser) -> Member:
    """Garante que o usuário pertença a um workspace.

    - Se já é membro, retorna.
    - Se existe convite pendente para o e-mail dele, entra no workspace de quem convidou.
    - Senão, cria um workspace novo com ele como admin.
    """
    member = db.scalar(select(Member).where(Member.user_id == user.id))
    if member:
        return member

    invite = db.scalar(
        select(Invite)
        .where(func.lower(Invite.email) == user.email, Invite.accepted_at.is_(None))
        .order_by(Invite.created_at.desc())
    )
    if invite:
        member = Member(
            workspace_id=invite.workspace_id, user_id=user.id, email=user.email,
            name=user.name, role=invite.role,
        )
        invite.accepted_at = now()
    else:
        ws = Workspace(name=f"Workspace de {user.name}")
        db.add(ws)
        db.flush()
        member = Member(workspace_id=ws.id, user_id=user.id, email=user.email, name=user.name, role=ROLE_ADMIN)
    db.add(member)
    db.commit()
    return member


def get_member(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> Member:
    return ensure_member(db, user)


def require_roles(*roles: str):
    def dep(member: Member = Depends(get_member)) -> Member:
        if member.role not in roles:
            raise HTTPException(403, "Seu perfil não tem permissão para esta ação")
        return member

    return dep


def audit(db: Session, member: Member, action: str, interview_id: str | None = None) -> None:
    db.add(AuditLog(
        workspace_id=member.workspace_id, interview_id=interview_id,
        user_id=member.user_id, user_email=member.email, action=action,
    ))
