"""Configurações da aplicação, lidas de variáveis de ambiente (ou do arquivo .env).

Nenhum segredo fica no código: tudo vem do ambiente. Veja o .env.example.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Banco de dados (Supabase Postgres em produção; SQLite para rodar local/testes)
    database_url: str = "sqlite:///./rubrica.db"

    # Supabase Auth — usado para validar o token JWT enviado pelo frontend
    supabase_url: str = ""
    supabase_anon_key: str = ""

    # Origens liberadas no CORS (URL do frontend na Vercel), separadas por vírgula
    cors_origins: str = "http://localhost:3000"

    # Recall.ai — bot que entra no Google Meet / Microsoft Teams
    recall_api_key: str = ""
    recall_region: str = "us-east-1"
    recall_transcript_language: str = "pt"
    # Após salvar a transcrição, apaga áudio/vídeo brutos no Recall (LGPD: minimização)
    recall_delete_media: bool = True
    # Token secreto que precisa estar na URL do webhook (?token=...)
    webhook_token: str = ""

    # Modelo de linguagem (qualquer API compatível com OpenAI: Groq, Gemini, OpenAI...)
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    max_transcript_chars: int = 40000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
