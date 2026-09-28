"""Cria o usuário de teste do avaliador e uma entrevista de exemplo JÁ PROCESSADA em produção.

Usa o caminho real do produto: cadastro no Supabase Auth -> API da Rubrica -> IA.
Rode do seu computador, depois do deploy:

    cd backend
    python scripts/criar_usuario_teste.py \
        --supabase-url https://SEU_REF.supabase.co --anon-key SUA_ANON_KEY \
        --api-url https://rubrica-api.onrender.com

Hoje a conta do avaliador já existe em produção; o script é só para recriar o ambiente.
"""
import argparse
import sys
import time
from pathlib import Path

import httpx

EMAIL = "avaliador@rubrica.app"
PASSWORD = "Rubrica@2026"
NAME = "Avaliador(a) SP2"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--supabase-url", required=True)
    ap.add_argument("--anon-key", required=True)
    ap.add_argument("--api-url", required=True)
    ap.add_argument("--email", default=EMAIL)
    ap.add_argument("--password", default=PASSWORD)
    a = ap.parse_args()

    auth = a.supabase_url.rstrip("/") + "/auth/v1"
    h = {"apikey": a.anon_key, "Content-Type": "application/json"}

    r = httpx.post(f"{auth}/signup", headers=h, json={"email": a.email, "password": a.password, "data": {"full_name": NAME}})
    print("cadastro:", r.status_code, "(422/400 = já existia, tudo bem)")
    r = httpx.post(f"{auth}/token?grant_type=password", headers=h, json={"email": a.email, "password": a.password})
    if r.status_code != 200:
        sys.exit(f"Falha no login: {r.text}\nDesative 'Confirm email' no Supabase ou confirme o e-mail.")
    token = r.json()["access_token"]

    api = a.api_url.rstrip("/")
    ah = {"Authorization": f"Bearer {token}"}
    print("acordando a API (pode levar ~1 min no Render Free)...")
    httpx.get(f"{api}/health", timeout=120)

    existing = httpx.get(f"{api}/api/interviews", headers=ah, timeout=60).json()
    if any(i["status"] == "concluida" for i in existing):
        print("Já existe entrevista processada para este usuário. Nada a fazer.")
    else:
        transcript = (Path(__file__).parent / "exemplo_transcricao.txt").read_text(encoding="utf-8")
        r = httpx.post(f"{api}/api/interviews/manual", headers=ah, timeout=60, json={
            "candidate_name": "Rafael Souza (exemplo)", "job_title": "Desenvolvedor(a) Back-end Pleno",
            "transcript": transcript, "consent_ack": True,
        })
        r.raise_for_status()
        iid = r.json()["id"]
        for _ in range(30):
            d = httpx.get(f"{api}/api/interviews/{iid}", headers=ah, timeout=60).json()
            if d["status"] in ("concluida", "erro"):
                break
            time.sleep(3)
        print("entrevista de exemplo:", d["status"], d.get("status_detail", ""))

    print(f"\nPronto! Usuário de teste:\n  e-mail: {a.email}\n  senha:  {a.password}")


if __name__ == "__main__":
    main()
