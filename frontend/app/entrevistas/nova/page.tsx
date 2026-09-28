"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { SAMPLE_CANDIDATE, SAMPLE_JOB, SAMPLE_TRANSCRIPT } from "@/lib/sample";
import type { InterviewSummary } from "@/lib/types";

type Tab = "bot" | "manual";

function NewInterview() {
  const router = useRouter();
  const { me } = useAuth();
  const [tab, setTab] = useState<Tab>("bot");
  const [candidate, setCandidate] = useState("");
  const [job, setJob] = useState("");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [when, setWhen] = useState<"now" | "later">("now");
  const [scheduledAt, setScheduledAt] = useState("");
  const [transcript, setTranscript] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (me?.member.role === "gestor") {
    return (
      <div className="card">
        <h1>Nova entrevista</h1>
        <p className="muted">Seu perfil é de gestor(a), com acesso somente de leitura. Peça a um admin para mudar seu papel.</p>
      </div>
    );
  }

  function fillSample() {
    setCandidate(SAMPLE_CANDIDATE);
    setJob(SAMPLE_JOB);
    setTranscript(SAMPLE_TRANSCRIPT);
    setConsent(true);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      let created: InterviewSummary;
      if (tab === "bot") {
        let iso: string | null = null;
        if (when === "later") {
          if (!scheduledAt) throw new Error("Informe a data e hora da entrevista");
          const d = new Date(scheduledAt);
          if (d.getTime() < Date.now() - 60_000) throw new Error("O horário escolhido já passou");
          iso = d.toISOString();
        }
        created = await api<InterviewSummary>("/api/interviews", {
          method: "POST",
          body: JSON.stringify({
            candidate_name: candidate,
            job_title: job,
            meeting_url: meetingUrl,
            scheduled_at: iso,
            consent_ack: consent,
          }),
        });
      } else {
        created = await api<InterviewSummary>("/api/interviews/manual", {
          method: "POST",
          body: JSON.stringify({ candidate_name: candidate, job_title: job, transcript, consent_ack: consent }),
        });
      }
      router.push(`/entrevistas/ver/?id=${created.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="narrow">
      <h1>Nova entrevista</h1>
      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "bot"} className={tab === "bot" ? "active" : ""} onClick={() => setTab("bot")}>
          Enviar bot para a reunião
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "manual"}
          className={tab === "manual" ? "active" : ""}
          onClick={() => setTab("manual")}
        >
          Colar transcrição
        </button>
      </div>

      <form className="card form" onSubmit={submit}>
        {tab === "bot" ? (
          <p className="muted">
            O bot da Rubrica entra na chamada, exibe o aviso de gravação (LGPD) para todos e transcreve a conversa. Quando
            a chamada terminar, a rubrica fica pronta em poucos minutos. <strong>Lembre-se de admitir o bot</strong> se ele
            ficar na sala de espera.
          </p>
        ) : (
          <div className="hint">
            <p>
              Já tem a transcrição (ex.: da gravação nativa do Meet/Teams)? Cole abaixo, uma fala por linha, no formato{" "}
              <code>[mm:ss] Nome: texto</code>. O horário é opcional.
            </p>
            <button type="button" className="btn btn-ghost btn-sm" onClick={fillSample}>
              Preencher com entrevista de exemplo
            </button>
          </div>
        )}

        <div className="grid-2">
          <label>
            Nome do(a) candidato(a)
            <input value={candidate} onChange={(e) => setCandidate(e.target.value)} required minLength={2} placeholder="Ex.: Rafael Souza" />
          </label>
          <label>
            Vaga
            <input value={job} onChange={(e) => setJob(e.target.value)} placeholder="Ex.: Dev Back-end Pleno" />
          </label>
        </div>

        {tab === "bot" ? (
          <>
            <label>
              Link da reunião (Google Meet ou Microsoft Teams)
              <input
                type="url"
                value={meetingUrl}
                onChange={(e) => setMeetingUrl(e.target.value)}
                required
                placeholder="https://meet.google.com/abc-defg-hij"
              />
            </label>
            <fieldset className="radio-row">
              <legend>Quando o bot deve entrar?</legend>
              <label className="radio">
                <input type="radio" checked={when === "now"} onChange={() => setWhen("now")} /> Agora
              </label>
              <label className="radio">
                <input type="radio" checked={when === "later"} onChange={() => setWhen("later")} /> No horário marcado
              </label>
              {when === "later" && (
                <input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} required />
              )}
            </fieldset>
          </>
        ) : (
          <label>
            Transcrição
            <textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              required
              minLength={50}
              rows={12}
              placeholder={"[00:00] Fernanda: Oi, tudo bem? Pode se apresentar?\n[00:08] Rafael: Claro! Sou desenvolvedor há 4 anos..."}
            />
          </label>
        )}

        <label className="check">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} required />
          <span>
            Confirmo que o(a) candidato(a) foi informado(a) de que a entrevista será gravada e transcrita para fins do
            processo seletivo, conforme a LGPD.
          </span>
        </label>

        {error && <p className="error">{error}</p>}
        <button className="btn btn-block" disabled={busy}>
          {busy ? "Enviando…" : tab === "bot" ? "Enviar bot para a reunião" : "Gerar rubrica"}
        </button>
      </form>
    </div>
  );
}

export default function Page() {
  return (
    <AppShell>
      <NewInterview />
    </AppShell>
  );
}
