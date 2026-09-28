"""Testes do fluxo principal com Supabase, Recall.ai e IA simulados."""
from pathlib import Path

from app.services import llm, recall
from app.services.transcript import parse_manual_transcript

from .conftest import h

SAMPLE = (Path(__file__).resolve().parent.parent / "scripts" / "exemplo_transcricao.txt").read_text(encoding="utf-8")

FAKE_RUBRIC = {
    "resumo": "Candidato experiente em Python.",
    "competencias": [{"nome": "Python", "nota": "4", "evidencia": "FastAPI há 2 anos"}, {"nome": "Nuvem", "nota": 9}],
    "pontos_fortes": ["Performance"],
    "pontos_de_atencao": ["Pouco Terraform"],
    "citacoes": [{"texto": "a gente derrubou para uns quarenta minutos", "timestamp_segundos": "46"}],
    "recomendacao": {"decisao": "Avançar com ressalvas", "justificativa": "Bom técnico"},
}


def fake_llm(monkeypatch):
    calls = []

    def gen(segments, candidate, job):
        calls.append(len(segments))
        return llm.normalize_rubric(FAKE_RUBRIC)

    monkeypatch.setattr(llm, "generate_rubric", gen)
    return calls


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_requires_login(client):
    assert client.get("/api/interviews").status_code == 401
    assert client.get("/api/interviews", headers=h("tok-xxx")).status_code == 401


def test_first_login_creates_workspace_as_admin(client):
    r = client.get("/api/me", headers=h("tok-ana")).json()
    assert r["member"]["role"] == "admin"
    assert r["workspace"]["name"] == "Workspace de Ana"


def test_manual_flow_end_to_end(client, monkeypatch):
    calls = fake_llm(monkeypatch)
    r = client.post("/api/interviews/manual", headers=h("tok-ana"), json={
        "candidate_name": "Rafael Souza", "job_title": "Dev Back-end Pleno",
        "transcript": SAMPLE, "consent_ack": True,
    })
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    assert calls == [24]

    d = client.get(f"/api/interviews/{iid}", headers=h("tok-ana")).json()
    assert d["status"] == "concluida"
    assert d["rubric"]["recomendacao"]["decisao"] == "avancar_com_ressalvas"
    assert d["rubric"]["competencias"][1]["nota"] == 5  # nota limitada a 1..5
    assert d["rubric"]["citacoes"][0]["timestamp_segundos"] == 46
    assert d["segments"][0]["speaker"] == "Fernanda (Recrutadora)"
    assert any(a["action"] == "visualizou" for a in d["audit"])

    # Busca por palavra-chave retorna candidato + timestamp
    res = client.get("/api/search", params={"q": "terraform"}, headers=h("tok-ana")).json()
    assert len(res) == 1
    assert res[0]["candidate_name"] == "Rafael Souza"
    assert res[0]["start_seconds"] == 122

    # Lista
    lst = client.get("/api/interviews", headers=h("tok-ana")).json()
    assert lst[0]["decision"] == "avancar_com_ressalvas"

    # Edição da rubrica
    rub = d["rubric"]
    rub["pontos_fortes"].append("Mentoria")
    r = client.put(f"/api/interviews/{iid}/rubric", headers=h("tok-ana"), json={"rubric": rub})
    assert r.status_code == 200
    d = client.get(f"/api/interviews/{iid}", headers=h("tok-ana")).json()
    assert d["rubric_edited"] is True and "Mentoria" in d["rubric"]["pontos_fortes"]

    # Outro workspace não enxerga
    assert client.get(f"/api/interviews/{iid}", headers=h("tok-caio")).status_code == 404
    assert client.get("/api/search", params={"q": "terraform"}, headers=h("tok-caio")).json() == []

    # Exclusão (LGPD)
    assert client.delete(f"/api/interviews/{iid}", headers=h("tok-ana")).status_code == 204
    assert client.get("/api/search", params={"q": "terraform"}, headers=h("tok-ana")).json() == []


def test_consent_required(client, monkeypatch):
    fake_llm(monkeypatch)
    r = client.post("/api/interviews/manual", headers=h("tok-ana"), json={
        "candidate_name": "X Y", "transcript": SAMPLE, "consent_ack": False,
    })
    assert r.status_code == 400


def test_llm_failure_marks_error(client, monkeypatch):
    def boom(*a):
        raise llm.LLMError("sem cota")
    monkeypatch.setattr(llm, "generate_rubric", boom)
    iid = client.post("/api/interviews/manual", headers=h("tok-ana"), json={
        "candidate_name": "Rafael", "transcript": SAMPLE, "consent_ack": True,
    }).json()["id"]
    d = client.get(f"/api/interviews/{iid}", headers=h("tok-ana")).json()
    assert d["status"] == "erro" and "sem cota" in d["status_detail"]


def test_invite_and_roles(client, monkeypatch):
    fake_llm(monkeypatch)
    client.get("/api/me", headers=h("tok-ana"))
    r = client.post("/api/team/invites", headers=h("tok-ana"), json={"email": "BIA@empresa.com", "role": "gestor"})
    assert r.status_code == 201
    # Bia entra e cai no workspace da Ana como gestora
    me = client.get("/api/me", headers=h("tok-bia")).json()
    assert me["member"]["role"] == "gestor"
    assert me["workspace"]["name"] == "Workspace de Ana"
    team = client.get("/api/team", headers=h("tok-ana")).json()
    assert len(team["members"]) == 2 and team["invites"] == []
    # Gestor não cria entrevista nem convida, mas vê
    assert client.post("/api/interviews/manual", headers=h("tok-bia"), json={
        "candidate_name": "Rafael", "transcript": SAMPLE, "consent_ack": True}).status_code == 403
    assert client.post("/api/team/invites", headers=h("tok-bia"), json={"email": "z@z.com"}).status_code == 403
    client.post("/api/interviews/manual", headers=h("tok-ana"), json={
        "candidate_name": "Rafael", "transcript": SAMPLE, "consent_ack": True})
    assert len(client.get("/api/interviews", headers=h("tok-bia")).json()) == 1


def test_bot_flow(client, monkeypatch):
    fake_llm(monkeypatch)
    created = {}

    def create_bot(url, join_at, iid):
        created["payload"] = recall.build_bot_payload(url, join_at, iid)
        return {"id": "bot-1"}

    state = {"code": "joining_call"}
    transcript = [
        {"participant": {"name": "Fernanda"}, "words": [{"text": "Olá,", "start_timestamp": {"relative": 1.0}}, {"text": "tudo bem?"}]},
        {"participant": {"name": "Rafael"}, "words": [{"text": "Trabalho com Kubernetes", "start_timestamp": {"relative": 5.5}}]},
    ]

    def get_bot(bot_id):
        bot = {"id": bot_id, "status_changes": [{"code": state["code"]}], "recordings": []}
        if state["code"] == "done":
            bot["recordings"] = [{"media_shortcuts": {"transcript": {"status": {"code": "done"}, "data": {"download_url": "https://x"}}}}]
        return bot

    deleted = []
    monkeypatch.setattr(recall, "create_bot", create_bot)
    monkeypatch.setattr(recall, "get_bot", get_bot)
    monkeypatch.setattr(recall, "download_transcript", lambda url: transcript)
    monkeypatch.setattr(recall, "delete_bot_or_media", lambda bot: deleted.append(bot["id"]))

    r = client.post("/api/interviews", headers=h("tok-ana"), json={
        "candidate_name": "Rafael", "job_title": "Dev", "meeting_url": "https://meet.google.com/abc-defg-hij",
        "consent_ack": True,
    })
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    p = created["payload"]
    assert "join_at" not in p  # sem horário -> entra agora
    assert p["chat"]["on_bot_join"]["send_to"] == "everyone"
    assert "LGPD" in p["chat"]["on_bot_join"]["message"]
    assert p["recording_config"]["transcript"]["provider"]["recallai_streaming"]["language_code"] == "pt"
    assert p["automatic_video_output"]["in_call_recording"]["kind"] == "jpeg"

    assert client.post(f"/api/interviews/{iid}/sync", headers=h("tok-ana")).json()["status"] == "entrando"
    state["code"] = "in_call_recording"
    assert client.post(f"/api/interviews/{iid}/sync", headers=h("tok-ana")).json()["status"] == "gravando"

    # Webhook de fim de chamada
    state["code"] = "done"
    assert client.post("/api/webhooks/recall?token=errado", json={}).status_code == 401
    r = client.post("/api/webhooks/recall?token=segredo", json={"event": "bot.done", "data": {"bot": {"id": "bot-1"}}})
    assert r.status_code == 200
    d = client.get(f"/api/interviews/{iid}", headers=h("tok-ana")).json()
    assert d["status"] == "concluida"
    assert [s["speaker"] for s in d["segments"]] == ["Fernanda", "Rafael"]
    assert d["segments"][0]["text"] == "Olá, tudo bem?"
    assert deleted == ["bot-1"]  # mídia bruta apagada


def test_bot_fatal(client, monkeypatch):
    monkeypatch.setattr(recall, "create_bot", lambda *a: {"id": "bot-2"})
    monkeypatch.setattr(recall, "get_bot", lambda b: {"status_changes": [{"code": "fatal", "sub_code": "bot_kicked_from_waiting_room"}]})
    iid = client.post("/api/interviews", headers=h("tok-ana"), json={
        "candidate_name": "Rafael", "meeting_url": "https://teams.microsoft.com/l/meetup-join/xyz", "consent_ack": True,
    }).json()["id"]
    r = client.post(f"/api/interviews/{iid}/sync", headers=h("tok-ana")).json()
    assert r["status"] == "erro" and "sala de espera" in r["status_detail"]


def test_invalid_meeting_link(client):
    r = client.post("/api/interviews", headers=h("tok-ana"), json={
        "candidate_name": "Rafael", "meeting_url": "https://example.com/x", "consent_ack": True})
    assert r.status_code == 422


def test_parse_manual_formats():
    segs = parse_manual_transcript("Ana: oi\ncontinuação\n01:02 - Beto: olá\nBeto: tudo")
    assert segs[0]["text"] == "oi continuação"
    assert segs[1]["start_seconds"] == 62
    assert segs[2]["start_seconds"] == 77


def test_llm_json_extraction():
    raw = 'Aqui está:\n```json\n{"resumo": "ok", "recomendacao": "não avançar"}\n```'
    r = llm.normalize_rubric(llm._extract_json(raw))
    assert r["resumo"] == "ok" and r["recomendacao"]["decisao"] == "nao_avancar"


def test_signup_requires_postgres_locally(client):
    # Com SQLite (local/testes) o cadastro direto responde 501 e o frontend usa o Supabase
    r = client.post("/api/auth/signup", json={"name": "Ana", "email": "ana@empresa.com", "password": "segredo1"})
    assert r.status_code == 501


def test_signup_validates_input(client):
    r = client.post("/api/auth/signup", json={"name": "A", "email": "nao-e-email", "password": "123"})
    assert r.status_code == 422
