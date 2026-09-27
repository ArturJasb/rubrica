"""Pipeline de processamento: status do bot -> transcrição -> rubrica por IA.

É chamado em segundo plano (BackgroundTasks) pelo webhook do Recall, pelo botão
"Atualizar" e pelo polling do painel — assim funciona mesmo que o servidor gratuito
tenha "dormido" e perdido um webhook.
"""
import logging

from sqlalchemy.orm import Session

from .. import models as m
from ..db import SessionLocal
from . import llm, recall

log = logging.getLogger("rubrica.pipeline")

FINAL = (m.ST_DONE, m.ST_FAILED)


def save_segments(db: Session, interview: m.Interview, segments: list[dict]) -> None:
    interview.segments.clear()
    db.flush()
    for i, s in enumerate(segments):
        interview.segments.append(m.TranscriptSegment(
            idx=i, speaker=s["speaker"][:200], text=s["text"], start_seconds=s["start_seconds"],
        ))
    if segments:
        interview.duration_seconds = segments[-1]["start_seconds"]


def run_rubric(db: Session, interview: m.Interview) -> None:
    segments = [{"speaker": s.speaker, "text": s.text, "start_seconds": s.start_seconds} for s in interview.segments]
    if not segments:
        interview.status, interview.status_detail = m.ST_FAILED, "A transcrição está vazia — ninguém falou ou o áudio não foi captado."
        return
    try:
        interview.rubric = llm.generate_rubric(segments, interview.candidate_name, interview.job_title)
        interview.rubric_edited = False
        interview.status, interview.status_detail = m.ST_DONE, ""
        interview.processed_at = m.now()
    except llm.LLMError as e:
        log.exception("Falha na IA")
        interview.status, interview.status_detail = m.ST_FAILED, f"Falha ao gerar a rubrica: {e}"


def sync_bot_interview(db: Session, interview: m.Interview) -> None:
    """Consulta o Recall e avança o status da entrevista."""
    if interview.source != "bot" or not interview.bot_id or interview.status in FINAL:
        return
    try:
        bot = recall.get_bot(interview.bot_id)
    except recall.RecallError as e:
        interview.status_detail = str(e)
        db.commit()
        return

    code = recall.last_status(bot)
    new_status = recall.STATUS_MAP.get(code, interview.status)

    if code == "fatal":
        sub = recall.last_sub_code(bot)
        interview.status = m.ST_FAILED
        interview.status_detail = recall.FATAL_MESSAGES.get(sub, f"O bot não conseguiu gravar ({sub or 'erro'}).")
        db.commit()
        return

    if code not in ("done", "analysis_done"):
        interview.status = new_status
        interview.status_detail = {"in_waiting_room": "Bot na sala de espera — admita-o na chamada."}.get(code, "")
        db.commit()
        return

    # Chamada terminou: busca a transcrição
    interview.status = m.ST_PROCESSING
    url, tr_status = recall.transcript_download_url(bot)
    if tr_status == "failed":
        interview.status, interview.status_detail = m.ST_FAILED, "O Recall não conseguiu transcrever o áudio."
        db.commit()
        return
    if not url:
        interview.status_detail = "Transcrição sendo finalizada..."
        db.commit()
        return

    try:
        segments = recall.parse_transcript(recall.download_transcript(url))
    except Exception as e:  # noqa: BLE001
        interview.status_detail = f"Erro ao baixar transcrição: {e}"
        db.commit()
        return

    save_segments(db, interview, segments)
    db.commit()
    run_rubric(db, interview)
    db.commit()

    if interview.status == m.ST_DONE and recall.get_settings().recall_delete_media:
        recall.delete_bot_or_media(bot)


def process_interview_bg(interview_id: str) -> None:
    """Ponto de entrada das tarefas em segundo plano (abre a própria sessão do banco)."""
    db = SessionLocal()
    try:
        interview = db.get(m.Interview, interview_id)
        if not interview:
            return
        if interview.source == "bot":
            sync_bot_interview(db, interview)
        elif interview.status == m.ST_PROCESSING:
            run_rubric(db, interview)
            db.commit()
    except Exception:  # noqa: BLE001
        log.exception("Erro processando entrevista %s", interview_id)
        db.rollback()
    finally:
        db.close()


def process_by_bot_id_bg(bot_id: str) -> None:
    db = SessionLocal()
    try:
        interview = db.query(m.Interview).filter(m.Interview.bot_id == bot_id).first()
        interview_id = interview.id if interview else None
    finally:
        db.close()
    if interview_id:
        process_interview_bg(interview_id)
