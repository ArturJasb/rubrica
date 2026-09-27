"""Leitura de transcrições coladas manualmente (entrevistas gravadas fora do bot).

Formatos aceitos por linha (o timestamp é opcional):
    [00:05] Fernanda: Bom dia, tudo bem?
    00:12 - Carlos: Tudo ótimo!
    Carlos: Tudo ótimo!
Linhas sem "Nome:" são anexadas à fala anterior.
"""
import re

LINE_RE = re.compile(
    r"^\s*(?:\[?(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\]?\s*[-–—]?\s*)?"
    r"(?P<speaker>[^:\n]{1,60}?):\s*(?P<text>.+)$"
)


def _ts_to_seconds(ts: str) -> float:
    parts = [int(p) for p in ts.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def parse_manual_transcript(raw: str) -> list[dict]:
    segments: list[dict] = []
    last_ts = 0.0
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        # Evita tratar "Obs: ..." longo ou URLs como falante; falante deve ter até 5 palavras
        if m and len(m.group("speaker").split()) <= 5 and "http" not in m.group("speaker"):
            ts = m.group("ts")
            if ts:
                last_ts = float(_ts_to_seconds(ts))
            elif segments:
                # Sem timestamp: estima ~15s por fala para manter a ordem na busca
                last_ts = segments[-1]["start_seconds"] + 15
            segments.append({
                "speaker": m.group("speaker").strip(),
                "text": m.group("text").strip(),
                "start_seconds": last_ts,
            })
        elif segments:
            segments[-1]["text"] += " " + line
        else:
            segments.append({"speaker": "Participante", "text": line, "start_seconds": 0.0})
    return segments
