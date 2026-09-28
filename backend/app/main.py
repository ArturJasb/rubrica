"""API da Rubrica (FastAPI).

Rodar localmente:  uvicorn app.main:app --reload
Documentação interativa: http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, engine
from .routers import interviews, signup, team, webhooks

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MVP: cria as tabelas se não existirem (sem migrations por enquanto)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Rubrica API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app",  # previews da Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signup.router)
app.include_router(team.router)
app.include_router(interviews.router)
app.include_router(webhooks.router)


@app.get("/")
@app.get("/health")
def health():
    return {"status": "ok", "service": "rubrica-api"}
