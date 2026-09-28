"""Cadastro aberto: qualquer pessoa cria uma conta e já entra, sem e-mail de confirmação.

O usuário é criado no Supabase Auth já confirmado pela função
rubrica.create_confirmed_user (migração "cadastro_sem_confirmacao_email"), que só o
papel do backend pode executar. Depois o frontend faz login normal com e-mail e senha.
"""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..db import get_db

router = APIRouter(prefix="/api/auth", tags=["cadastro"])

# Limite simples por IP para evitar criação de contas em massa
_WINDOW = 600  # 10 minutos
_MAX_PER_WINDOW = 10
_hits: dict[str, deque] = defaultdict(deque)


class SignupIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def _check_rate(ip: str) -> None:
    now = time.time()
    q = _hits[ip]
    while q and q[0] < now - _WINDOW:
        q.popleft()
    if len(q) >= _MAX_PER_WINDOW:
        raise HTTPException(429, "Muitas contas criadas a partir desta rede. Aguarde alguns minutos.")
    q.append(now)
    if len(_hits) > 5000:
        _hits.clear()


@router.post("/signup", status_code=201)
def signup(body: SignupIn, request: Request, db: Session = Depends(get_db)):
    if db.get_bind().dialect.name != "postgresql":
        # Rodando local com SQLite: o frontend cai no cadastro padrão do Supabase
        raise HTTPException(501, "Cadastro direto disponível só com o banco do Supabase")
    _check_rate(_client_ip(request))
    try:
        user_id = db.execute(
            text("select rubrica.create_confirmed_user(:email, :password, :name)"),
            {"email": str(body.email), "password": body.password, "name": body.name.strip()},
        ).scalar_one()
        db.commit()
    except DBAPIError as e:
        db.rollback()
        msg = str(getattr(e, "orig", e))
        if "email_exists" in msg:
            raise HTTPException(409, "Este e-mail já tem conta. Use a opção Entrar.")
        if "weak_password" in msg:
            raise HTTPException(422, "A senha precisa ter pelo menos 6 caracteres.")
        if "invalid_email" in msg:
            raise HTTPException(422, "E-mail inválido.")
        raise HTTPException(500, "Não foi possível criar a conta agora. Tente de novo.")
    return {"id": str(user_id), "email": str(body.email).lower()}
