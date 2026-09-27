"""Formatos de entrada e saída da API (validação com Pydantic)."""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from .models import ROLES


class BotInterviewIn(BaseModel):
    candidate_name: str = Field(min_length=2, max_length=200)
    job_title: str = Field(default="", max_length=200)
    meeting_url: str = Field(min_length=10, max_length=2000)
    scheduled_at: datetime | None = None
    consent_ack: bool

    @field_validator("meeting_url")
    @classmethod
    def valid_meeting(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("https://"):
            raise ValueError("Use o link completo da reunião (https://...)")
        if not any(d in v for d in ("meet.google.com", "teams.microsoft.com", "teams.live.com", "zoom.us")):
            raise ValueError("Link precisa ser do Google Meet ou Microsoft Teams")
        return v


class ManualInterviewIn(BaseModel):
    candidate_name: str = Field(min_length=2, max_length=200)
    job_title: str = Field(default="", max_length=200)
    transcript: str = Field(min_length=50, max_length=200_000)
    consent_ack: bool


class RubricIn(BaseModel):
    rubric: dict


class InviteIn(BaseModel):
    email: EmailStr
    role: str = "recrutador"

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError("Papel inválido")
        return v


class RoleIn(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError("Papel inválido")
        return v


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
