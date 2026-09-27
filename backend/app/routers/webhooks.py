"""Webhook do Recall.ai: avisa quando o status do bot muda (ex.: chamada terminou).

O handler só dispara uma nova consulta ao Recall (idempotente), então mesmo um
evento repetido ou fora de ordem não corrompe nada. A URL precisa conter ?token=WEBHOOK_TOKEN.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from ..config import get_settings
from ..services import pipeline

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/recall")
async def recall_webhook(request: Request, bg: BackgroundTasks, token: str = ""):
    expected = get_settings().webhook_token
    if not expected or token != expected:
        raise HTTPException(401, "token inválido")
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "JSON inválido")

    data = payload.get("data") or {}
    bot = data.get("bot") or {}
    bot_id = bot.get("id") or data.get("bot_id")
    if bot_id:
        bg.add_task(pipeline.process_by_bot_id_bg, bot_id)
    return {"ok": True}
