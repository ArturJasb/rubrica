"""Integração com o Recall.ai, a API que coloca um bot dentro do Google Meet / Teams.

Documentação: https://docs.recall.ai
"""
import base64
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import httpx

from ..config import get_settings

log = logging.getLogger("rubrica.recall")

BOT_NAME = "Rubrica | Gravando esta entrevista"

CONSENT_MESSAGE = (
    "Aviso de privacidade (LGPD): esta entrevista está sendo GRAVADA e TRANSCRITA pela "
    "Rubrica para apoiar a avaliação do processo seletivo. Os dados são usados apenas pela "
    "empresa contratante, o áudio/vídeo bruto é apagado após a transcrição e você pode pedir "
    "a exclusão a qualquer momento. Se não concordar, avise o(a) entrevistador(a) agora, "
    "antes de a conversa começar."
)

# Códigos de status do bot no Recall -> status da entrevista na Rubrica
STATUS_MAP = {
    "ready": "agendada",
    "joining_call": "entrando",
    "in_waiting_room": "entrando",
    "in_call_not_recording": "gravando",
    "recording_permission_allowed": "gravando",
    "recording_permission_denied": "gravando",
    "in_call_recording": "gravando",
    "call_ended": "processando",
    "done": "processando",
    "analysis_done": "processando",
    "fatal": "erro",
    "media_expired": "erro",
}

FATAL_MESSAGES = {
    "bot_kicked_from_waiting_room": "O bot não foi admitido na chamada (removido da sala de espera).",
    "timeout_exceeded_waiting_room": "O bot ficou tempo demais na sala de espera sem ser admitido.",
    "meeting_not_found": "Reunião não encontrada. Confira o link.",
    "meeting_requires_sign_in": "A reunião exige login; ajuste as permissões para convidados.",
}


class RecallError(Exception):
    pass


def _base() -> str:
    return f"https://{get_settings().recall_region}.recall.ai/api/v1"


def _headers() -> dict:
    key = get_settings().recall_api_key
    if not key:
        raise RecallError("RECALL_API_KEY não configurada no servidor")
    return {"Authorization": f"Token {key}", "Content-Type": "application/json"}


@lru_cache
def _consent_image_b64() -> str | None:
    p = Path(__file__).resolve().parent.parent / "assets" / "aviso-lgpd.jpg"
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else None


def build_bot_payload(meeting_url: str, join_at: datetime | None, interview_id: str, full: bool = True) -> dict:
    s = get_settings()
    payload: dict = {
        "meeting_url": meeting_url,
        "bot_name": BOT_NAME,
        "metadata": {"interview_id": interview_id},
        "recording_config": {
            "transcript": {
                "provider": {
                    "recallai_streaming": {
                        "mode": "prioritize_accuracy",
                        "language_code": s.recall_transcript_language,
                    }
                }
            }
        },
    }
    # O Recall só garante o horário se o bot for agendado com antecedência (>10 min).
    # Para reuniões "agora" ou em breve, mandamos entrar imediatamente.
    if join_at and join_at > datetime.now(timezone.utc) + timedelta(minutes=10):
        payload["join_at"] = join_at.astimezone(timezone.utc).isoformat()

    if full:
        # Aviso de consentimento: mensagem no chat para todos + imagem do bot com o aviso
        payload["chat"] = {"on_bot_join": {"send_to": "everyone", "message": CONSENT_MESSAGE}}
        img = _consent_image_b64()
        if img:
            payload["automatic_video_output"] = {"in_call_recording": {"kind": "jpeg", "b64_data": img}}
    return payload


def create_bot(meeting_url: str, join_at: datetime | None, interview_id: str) -> dict:
    payload = build_bot_payload(meeting_url, join_at, interview_id, full=True)
    r = httpx.post(f"{_base()}/bot/", json=payload, headers=_headers(), timeout=30)
    if r.status_code == 400:
        # Se algum campo opcional (imagem/chat) for rejeitado, tenta com o mínimo
        log.warning("Recall recusou payload completo: %s", r.text[:500])
        payload = build_bot_payload(meeting_url, join_at, interview_id, full=False)
        payload["bot_name"] = "Rubrica | GRAVANDO - aviso LGPD no chat"
        r = httpx.post(f"{_base()}/bot/", json=payload, headers=_headers(), timeout=30)
    if r.status_code >= 300:
        raise RecallError(f"Recall.ai recusou a criação do bot ({r.status_code}): {r.text[:300]}")
    return r.json()


def get_bot(bot_id: str) -> dict:
    r = httpx.get(f"{_base()}/bot/{bot_id}/", headers=_headers(), timeout=30)
    if r.status_code >= 300:
        raise RecallError(f"Erro ao consultar bot ({r.status_code}): {r.text[:300]}")
    return r.json()


def delete_bot_or_media(bot: dict) -> None:
    """Cancela um bot agendado ou apaga a mídia bruta de um bot finalizado (melhor esforço)."""
    bot_id = bot.get("id")
    if not bot_id:
        return
    try:
        code = last_status(bot)
        if code in ("ready", "", None):
            httpx.delete(f"{_base()}/bot/{bot_id}/", headers=_headers(), timeout=20)
        else:
            httpx.post(f"{_base()}/bot/{bot_id}/delete_media/", headers=_headers(), timeout=20)
    except Exception as e:  # noqa: BLE001 — limpeza não pode quebrar o fluxo principal
        log.warning("Falha ao limpar bot %s: %s", bot_id, e)


def last_status(bot: dict) -> str:
    changes = bot.get("status_changes") or []
    if changes:
        return changes[-1].get("code") or ""
    status = bot.get("status") or {}
    return status.get("code", "") if isinstance(status, dict) else str(status)


def last_sub_code(bot: dict) -> str:
    changes = bot.get("status_changes") or []
    return (changes[-1].get("sub_code") or "") if changes else ""


def transcript_download_url(bot: dict) -> tuple[str | None, str]:
    """Retorna (url, status) da transcrição da primeira gravação do bot."""
    for rec in bot.get("recordings") or []:
        tr = (rec.get("media_shortcuts") or {}).get("transcript")
        if not tr:
            continue
        st = ((tr.get("status") or {}).get("code")) or ""
        url = (tr.get("data") or {}).get("download_url")
        return url, st
    return None, ""


def download_transcript(url: str) -> list:
    r = httpx.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def parse_transcript(data: list) -> list[dict]:
    """Converte o JSON do Recall em falas: [{speaker, text, start_seconds}].

    Formato do Recall: lista de blocos {participant: {name}, words: [{text, start_timestamp: {relative}}]}.
    """
    segments = []
    for block in data or []:
        words = block.get("words") or []
        text = " ".join((w.get("text") or "").strip() for w in words).strip()
        if not text:
            continue
        participant = block.get("participant") or {}
        speaker = participant.get("name") or block.get("speaker") or "Participante"
        ts = (words[0].get("start_timestamp") or {}) if words else {}
        start = ts.get("relative") if isinstance(ts, dict) else ts
        segments.append({"speaker": speaker, "text": text, "start_seconds": float(start or 0)})
    return segments
