"""Tabelas do banco de dados."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


# Papéis de acesso (controle por papel exigido no PRD, seção 6.1)
ROLE_ADMIN = "admin"
ROLE_RECRUITER = "recrutador"
ROLE_MANAGER = "gestor"
ROLES = (ROLE_ADMIN, ROLE_RECRUITER, ROLE_MANAGER)

# Status de uma entrevista ao longo do fluxo
ST_SCHEDULED = "agendada"        # bot criado, aguardando o horário
ST_JOINING = "entrando"          # bot entrando / na sala de espera
ST_IN_CALL = "gravando"          # bot na chamada, gravando e transcrevendo
ST_PROCESSING = "processando"    # chamada encerrada, gerando transcrição/rubrica
ST_DONE = "concluida"            # rubrica pronta
ST_FAILED = "erro"


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Member(Base):
    __tablename__ = "members"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # id do Supabase Auth
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(20), default=ROLE_ADMIN)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    workspace: Mapped[Workspace] = relationship()


class Invite(Base):
    __tablename__ = "invites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str] = mapped_column(String(20), default=ROLE_RECRUITER)
    invited_by: Mapped[str] = mapped_column(String(64))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_by_name: Mapped[str] = mapped_column(String(200), default="")
    candidate_name: Mapped[str] = mapped_column(String(200))
    job_title: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(20), default="bot")  # "bot" ou "manual"
    meeting_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bot_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=ST_SCHEDULED)
    status_detail: Mapped[str] = mapped_column(Text, default="")
    consent_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    rubric: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rubric_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="interview",
        order_by="TranscriptSegment.idx",
        cascade="all, delete-orphan",
    )


class TranscriptSegment(Base):
    """Uma fala da transcrição: quem falou, o quê e em que segundo da chamada."""

    __tablename__ = "transcript_segments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[str] = mapped_column(Text)
    start_seconds: Mapped[float] = mapped_column(Float, default=0)

    interview: Mapped[Interview] = relationship(back_populates="segments")


class AuditLog(Base):
    """Registro de quem acessou/alterou cada entrevista (PRD 6.1)."""

    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    interview_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    user_id: Mapped[str] = mapped_column(String(64))
    user_email: Mapped[str] = mapped_column(String(320), default="")
    action: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
