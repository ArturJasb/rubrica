"""Entrevistas: criar (bot ou transcrição colada), listar, ver, editar rubrica, excluir, buscar."""
from datetime import timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import models as m
from ..auth import audit, get_member, require_roles
from ..db import get_db
from ..schemas import BotInterviewIn, ManualInterviewIn, RubricIn
from ..services import llm, pipeline, recall
from ..services.transcript import parse_manual_transcript

router = APIRouter(prefix="/api", tags=["entrevistas"])

can_write = require_roles(m.ROLE_ADMIN, m.ROLE_RECRUITER)


def interview_summary(i: m.Interview) -> dict:
    rec = (i.rubric or {}).get("recomendacao") or {}
    return {
        "id": i.id,
        "candidate_name": i.candidate_name,
        "job_title": i.job_title,
        "source": i.source,
        "status": i.status,
        "status_detail": i.status_detail,
        "meeting_url": i.meeting_url,
        "scheduled_at": i.scheduled_at,
        "created_at": i.created_at,
        "processed_at": i.processed_at,
        "created_by_name": i.created_by_name,
        "decision": rec.get("decisao"),
    }


def get_interview_or_404(db: Session, member: m.Member, interview_id: str) -> m.Interview:
    i = db.get(m.Interview, interview_id)
    if not i or i.workspace_id != member.workspace_id:
        raise HTTPException(404, "Entrevista não encontrada")
    return i


@router.get("/interviews")
def list_interviews(q: str = "", db: Session = Depends(get_db), member: m.Member = Depends(get_member)):
    stmt = select(m.Interview).where(m.Interview.workspace_id == member.workspace_id)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(m.Interview.candidate_name).like(like), func.lower(m.Interview.job_title).like(like)))
    items = db.scalars(stmt.order_by(m.Interview.created_at.desc()).limit(200)).all()
    return [interview_summary(i) for i in items]


@router.post("/interviews", status_code=201)
def create_bot_interview(
    body: BotInterviewIn, bg: BackgroundTasks,
    db: Session = Depends(get_db), member: m.Member = Depends(can_write),
):
    if not body.consent_ack:
        raise HTTPException(400, "Confirme que o candidato foi informado sobre a gravação (LGPD)")
    sched = body.scheduled_at
    if sched and sched.tzinfo is None:
        sched = sched.replace(tzinfo=timezone.utc)

    i = m.Interview(
        workspace_id=member.workspace_id, created_by=member.user_id, created_by_name=member.name,
        candidate_name=body.candidate_name.strip(), job_title=body.job_title.strip(),
        source="bot", meeting_url=body.meeting_url, scheduled_at=sched, consent_ack=True,
        status=m.ST_SCHEDULED,
    )
    db.add(i)
    db.flush()
    try:
        bot = recall.create_bot(body.meeting_url, sched, i.id)
    except recall.RecallError as e:
        db.rollback()
        raise HTTPException(502, str(e))
    except Exception:  # noqa: BLE001
        db.rollback()
        raise HTTPException(502, "Não foi possível falar com o Recall.ai agora. Tente novamente.")
    i.bot_id = bot.get("id")
    audit(db, member, "criou_entrevista", i.id)
    db.commit()
    return interview_summary(i)


@router.post("/interviews/manual", status_code=201)
def create_manual_interview(
    body: ManualInterviewIn, bg: BackgroundTasks,
    db: Session = Depends(get_db), member: m.Member = Depends(can_write),
):
    if not body.consent_ack:
        raise HTTPException(400, "Confirme que o candidato autorizou a gravação/transcrição (LGPD)")
    segments = parse_manual_transcript(body.transcript)
    if len(segments) < 2:
        raise HTTPException(400, "Não consegui identificar as falas. Use uma linha por fala no formato 'Nome: texto'.")
    i = m.Interview(
        workspace_id=member.workspace_id, created_by=member.user_id, created_by_name=member.name,
        candidate_name=body.candidate_name.strip(), job_title=body.job_title.strip(),
        source="manual", consent_ack=True, status=m.ST_PROCESSING,
        status_detail="Gerando a rubrica com IA...",
    )
    db.add(i)
    db.flush()
    pipeline.save_segments(db, i, segments)
    audit(db, member, "criou_entrevista", i.id)
    db.commit()
    bg.add_task(pipeline.process_interview_bg, i.id)
    return interview_summary(i)


@router.get("/interviews/{interview_id}")
def get_interview(interview_id: str, db: Session = Depends(get_db), member: m.Member = Depends(get_member)):
    i = get_interview_or_404(db, member, interview_id)
    audit(db, member, "visualizou", i.id)
    db.commit()
    data = interview_summary(i)
    data.update({
        "rubric": i.rubric,
        "rubric_edited": i.rubric_edited,
        "duration_seconds": i.duration_seconds,
        "bot_id": i.bot_id,
        "segments": [
            {"idx": s.idx, "speaker": s.speaker, "text": s.text, "start_seconds": s.start_seconds}
            for s in i.segments
        ],
    })
    if member.role == m.ROLE_ADMIN:
        logs = db.scalars(
            select(m.AuditLog).where(m.AuditLog.interview_id == i.id).order_by(m.AuditLog.created_at.desc()).limit(20)
        ).all()
        data["audit"] = [{"user_email": a.user_email, "action": a.action, "created_at": a.created_at} for a in logs]
    return data


@router.post("/interviews/{interview_id}/sync")
def sync_interview(interview_id: str, db: Session = Depends(get_db), member: m.Member = Depends(get_member)):
    """Consulta o status do bot no Recall (fallback caso o webhook não chegue)."""
    i = get_interview_or_404(db, member, interview_id)
    if i.source == "bot" and i.status not in pipeline.FINAL:
        pipeline.sync_bot_interview(db, i)
        db.refresh(i)
    return interview_summary(i)


@router.put("/interviews/{interview_id}/rubric")
def update_rubric(
    interview_id: str, body: RubricIn,
    db: Session = Depends(get_db), member: m.Member = Depends(can_write),
):
    i = get_interview_or_404(db, member, interview_id)
    i.rubric = llm.normalize_rubric(body.rubric)
    i.rubric_edited = True
    if i.status != m.ST_DONE and i.segments:
        i.status, i.status_detail = m.ST_DONE, ""
    audit(db, member, "editou_rubrica", i.id)
    db.commit()
    return {"ok": True, "rubric": i.rubric}


@router.post("/interviews/{interview_id}/regenerate")
def regenerate(
    interview_id: str, bg: BackgroundTasks,
    db: Session = Depends(get_db), member: m.Member = Depends(can_write),
):
    i = get_interview_or_404(db, member, interview_id)
    if not i.segments:
        raise HTTPException(400, "Esta entrevista ainda não tem transcrição")
    i.status, i.status_detail = m.ST_PROCESSING, "Gerando a rubrica novamente..."
    audit(db, member, "regerou_rubrica", i.id)
    db.commit()
    # Roda direto a etapa da IA (vale para entrevistas do bot e manuais)
    bg.add_task(_regen_bg, i.id)
    return interview_summary(i)


def _regen_bg(interview_id: str) -> None:
    from ..db import SessionLocal
    db = SessionLocal()
    try:
        i = db.get(m.Interview, interview_id)
        if i:
            pipeline.run_rubric(db, i)
            db.commit()
    finally:
        db.close()


@router.delete("/interviews/{interview_id}", status_code=204)
def delete_interview(interview_id: str, db: Session = Depends(get_db), member: m.Member = Depends(can_write)):
    """Exclusão sob demanda (LGPD): apaga transcrição, rubrica e mídia no Recall."""
    i = get_interview_or_404(db, member, interview_id)
    if i.bot_id:
        try:
            recall.delete_bot_or_media(recall.get_bot(i.bot_id))
        except Exception:  # noqa: BLE001
            pass
    audit(db, member, "excluiu_entrevista", i.id)
    db.delete(i)
    db.commit()


@router.get("/search")
def search(q: str, db: Session = Depends(get_db), member: m.Member = Depends(get_member)):
    """Busca por palavra-chave em todas as transcrições do workspace, com timestamp."""
    term = q.strip().lower()
    if len(term) < 2:
        return []
    rows = db.execute(
        select(m.TranscriptSegment, m.Interview)
        .join(m.Interview, m.Interview.id == m.TranscriptSegment.interview_id)
        .where(m.Interview.workspace_id == member.workspace_id)
        .where(func.lower(m.TranscriptSegment.text).like(f"%{term}%"))
        .order_by(m.Interview.created_at.desc(), m.TranscriptSegment.idx)
        .limit(100)
    ).all()
    return [
        {
            "interview_id": iv.id, "candidate_name": iv.candidate_name, "job_title": iv.job_title,
            "speaker": seg.speaker, "text": seg.text, "start_seconds": seg.start_seconds, "idx": seg.idx,
        }
        for seg, iv in rows
    ]
