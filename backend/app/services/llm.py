"""Geração da rubrica estruturada por IA.

Usa qualquer API compatível com o formato da OpenAI (Groq, Google Gemini, OpenAI...),
configurada por LLM_BASE_URL / LLM_API_KEY / LLM_MODEL. Groq e Gemini têm plano gratuito.
"""
import json
import logging
import re

import httpx

from ..config import get_settings

log = logging.getLogger("rubrica.llm")

DECISIONS = {
    "avancar": "Avançar",
    "avancar_com_ressalvas": "Avançar com ressalvas",
    "nao_avancar": "Não avançar",
    "inconclusivo": "Inconclusivo",
}

SYSTEM_PROMPT = """Você é um especialista em recrutamento e seleção de profissionais de tecnologia.
Recebe a transcrição de uma entrevista de emprego (em português) e produz uma rubrica de
avaliação estruturada, objetiva e baseada SOMENTE em evidências do que foi dito.

Regras:
- Não invente fatos. Se algo não foi discutido, não avalie.
- Não considere idade, gênero, origem, aparência, sotaque, religião ou qualquer
  característica pessoal protegida. Avalie apenas competências e comportamento profissional.
- Identifique quem é o candidato e quem é o entrevistador pelo contexto.
- Citações devem ser trechos literais (ou quase) ditos pelo CANDIDATO, com o timestamp em
  segundos do trecho correspondente (o número entre colchetes [mm:ss] convertido em segundos).
- Escreva em português do Brasil.

Responda APENAS com um JSON válido neste formato:
{
  "resumo": "2 a 4 frases resumindo a entrevista e o perfil do candidato",
  "competencias": [
    {"nome": "ex.: Comunicação", "nota": 1-5, "evidencia": "o que foi observado que justifica a nota"}
  ],
  "pontos_fortes": ["..."],
  "pontos_de_atencao": ["..."],
  "citacoes": [
    {"texto": "trecho dito pelo candidato", "timestamp_segundos": 123, "contexto": "por que é relevante"}
  ],
  "recomendacao": {
    "decisao": "avancar | avancar_com_ressalvas | nao_avancar | inconclusivo",
    "justificativa": "1 a 3 frases",
    "proximo_passo": "sugestão concreta de próximo passo no processo"
  }
}
Inclua de 3 a 6 competências, de 2 a 5 itens em pontos fortes e em pontos de atenção,
e de 2 a 5 citações."""


class LLMError(Exception):
    pass


def fmt_ts(seconds: float) -> str:
    s = int(seconds or 0)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def transcript_as_text(segments: list[dict], max_chars: int) -> str:
    lines = [f"[{fmt_ts(s['start_seconds'])}] {s['speaker']}: {s['text']}" for s in segments]
    text = "\n".join(lines)
    if len(text) > max_chars:
        # Mantém começo e fim (onde costumam estar apresentação e perguntas finais)
        half = max_chars // 2
        text = text[:half] + "\n[... trecho do meio omitido por tamanho ...]\n" + text[-half:]
    return text


def _extract_json(content: str) -> dict:
    content = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.S)
    if fence:
        content = fence.group(1)
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("A IA não retornou um JSON")
    return json.loads(content[start:end + 1])


def _as_list(v) -> list:
    return v if isinstance(v, list) else ([] if v in (None, "") else [v])


def normalize_rubric(raw: dict) -> dict:
    """Garante que a rubrica tenha sempre o mesmo formato, mesmo se a IA variar."""
    comps = []
    for c in _as_list(raw.get("competencias")):
        if isinstance(c, dict) and c.get("nome"):
            try:
                nota = max(1, min(5, int(round(float(c.get("nota") or 3)))))
            except (TypeError, ValueError):
                nota = 3
            comps.append({"nome": str(c["nome"]), "nota": nota, "evidencia": str(c.get("evidencia") or "")})

    quotes = []
    for q in _as_list(raw.get("citacoes")):
        if isinstance(q, str):
            q = {"texto": q}
        if isinstance(q, dict) and q.get("texto"):
            try:
                ts = float(q.get("timestamp_segundos")) if q.get("timestamp_segundos") is not None else None
            except (TypeError, ValueError):
                ts = None
            quotes.append({"texto": str(q["texto"]), "timestamp_segundos": ts, "contexto": str(q.get("contexto") or "")})

    rec = raw.get("recomendacao") or {}
    if isinstance(rec, str):
        rec = {"decisao": rec}
    decisao = str(rec.get("decisao") or "inconclusivo").strip().lower()
    decisao = (decisao.replace("ã", "a").replace("ç", "c").replace(" ", "_").replace("-", "_"))
    if decisao not in DECISIONS:
        decisao = "inconclusivo"

    return {
        "resumo": str(raw.get("resumo") or ""),
        "competencias": comps,
        "pontos_fortes": [str(x) for x in _as_list(raw.get("pontos_fortes")) if x],
        "pontos_de_atencao": [str(x) for x in _as_list(raw.get("pontos_de_atencao")) if x],
        "citacoes": quotes,
        "recomendacao": {
            "decisao": decisao,
            "justificativa": str(rec.get("justificativa") or ""),
            "proximo_passo": str(rec.get("proximo_passo") or ""),
        },
    }


def generate_rubric(segments: list[dict], candidate_name: str, job_title: str) -> dict:
    s = get_settings()
    if not s.llm_api_key:
        raise LLMError("LLM_API_KEY não configurada no servidor")

    transcript = transcript_as_text(segments, s.max_transcript_chars)
    user_msg = (
        f"Candidato(a): {candidate_name}\nVaga: {job_title or 'não informada'}\n\n"
        f"Transcrição:\n{transcript}"
    )
    body = {
        "model": s.llm_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    }
    headers = {"Authorization": f"Bearer {s.llm_api_key}", "Content-Type": "application/json"}
    url = f"{s.llm_base_url.rstrip('/')}/chat/completions"

    last_err = None
    for _ in range(2):  # uma nova tentativa se vier JSON quebrado
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=120)
        except httpx.HTTPError as e:
            last_err = LLMError(f"Falha de conexão com a IA: {e}")
            continue
        if r.status_code >= 300:
            last_err = LLMError(f"A IA retornou erro {r.status_code}: {r.text[:300]}")
            if r.status_code in (400, 401, 403, 404):
                break
            continue
        try:
            content = r.json()["choices"][0]["message"]["content"]
            return normalize_rubric(_extract_json(content))
        except (KeyError, IndexError, ValueError, LLMError) as e:
            last_err = LLMError(f"Resposta da IA em formato inesperado: {e}")
    raise last_err or LLMError("Falha ao gerar rubrica")
