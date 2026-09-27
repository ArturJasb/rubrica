"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { DecisionBadge, StatusBadge } from "@/components/Badges";
import Loading from "@/components/Loading";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, fmtTime, PENDING } from "@/lib/format";
import type { InterviewSummary, SearchHit } from "@/lib/types";

function Highlight({ text, term }: { text: string; term: string }) {
  if (!term) return <>{text}</>;
  const i = text.toLowerCase().indexOf(term.toLowerCase());
  if (i < 0) return <>{text}</>;
  // Mostra um recorte ao redor do termo encontrado
  let start = Math.max(0, i - 90);
  if (start > 0) start = text.indexOf(" ", start) + 1 || start; // não corta palavra no meio
  let end = Math.min(text.length, i + term.length + 120);
  if (end < text.length) end = text.lastIndexOf(" ", end) > i ? text.lastIndexOf(" ", end) : end;
  return (
    <>
      {start > 0 && "…"}
      {text.slice(start, i)}
      <mark>{text.slice(i, i + term.length)}</mark>
      {text.slice(i + term.length, end)}
      {end < text.length && "…"}
    </>
  );
}

function Dashboard() {
  const { me } = useAuth();
  const [items, setItems] = useState<InterviewSummary[] | null>(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await api<InterviewSummary[]>("/api/interviews"));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Atualiza sozinho enquanto houver entrevista em andamento
  const hasPending = items?.some((i) => PENDING.includes(i.status));
  useEffect(() => {
    if (!hasPending) return;
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [hasPending, load]);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    const t = q.trim();
    if (t.length < 2) {
      setHits(null);
      setTerm("");
      return;
    }
    setSearching(true);
    try {
      setHits(await api<SearchHit[]>(`/api/search?q=${encodeURIComponent(t)}`));
      setTerm(t);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSearching(false);
    }
  }

  const canWrite = me?.member.role !== "gestor";
  const done = items?.filter((i) => i.status === "concluida").length ?? 0;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Entrevistas</h1>
          <p className="muted">{me?.workspace.name}</p>
        </div>
        {canWrite && (
          <Link href="/entrevistas/nova" className="btn">
            + Nova entrevista
          </Link>
        )}
      </div>

      <form className="search" onSubmit={search}>
        <input
          type="search"
          placeholder="Buscar em todas as transcrições (ex.: Kubernetes, liderança, Terraform)"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            if (!e.target.value) {
              setHits(null);
              setTerm("");
            }
          }}
        />
        <button className="btn" disabled={searching}>
          {searching ? "Buscando…" : "Buscar"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {hits && (
        <section className="card">
          <div className="section-head">
            <h2>
              {hits.length} {hits.length === 1 ? "trecho encontrado" : "trechos encontrados"} para “{term}”
            </h2>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setHits(null);
                setQ("");
                setTerm("");
              }}
            >
              Limpar busca
            </button>
          </div>
          {hits.length === 0 && <p className="muted">Nenhuma entrevista menciona esse termo.</p>}
          <ul className="hits">
            {hits.map((h) => (
              <li key={`${h.interview_id}-${h.idx}`}>
                <Link href={`/entrevistas/${h.interview_id}?t=${h.idx}`}>
                  <div className="hit-meta">
                    <strong>{h.candidate_name}</strong>
                    {h.job_title && <span className="muted"> · {h.job_title}</span>}
                    <span className="ts">{fmtTime(h.start_seconds)}</span>
                    <span className="muted small">{h.speaker}</span>
                  </div>
                  <p>
                    <Highlight text={h.text} term={term} />
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!items ? (
        <Loading />
      ) : items.length === 0 ? (
        <div className="card empty">
          <h2>Nenhuma entrevista ainda</h2>
          <p className="muted">
            Cole o link de uma entrevista no Meet ou Teams para o bot gravar, ou teste agora com uma transcrição de
            exemplo — a rubrica fica pronta em segundos.
          </p>
          {canWrite && (
            <Link href="/entrevistas/nova" className="btn">
              Criar primeira entrevista
            </Link>
          )}
        </div>
      ) : (
        <section className="card no-pad">
          <div className="section-head pad">
            <h2>Todas as entrevistas</h2>
            <span className="muted small">
              {items.length} no total · {done} com rubrica pronta
            </span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Candidato(a)</th>
                  <th>Vaga</th>
                  <th>Status</th>
                  <th>Recomendação</th>
                  <th>Data</th>
                </tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.id}>
                    <td>
                      <Link href={`/entrevistas/${i.id}`} className="strong-link">
                        {i.candidate_name}
                      </Link>
                      <div className="muted small">{i.source === "bot" ? "Bot na reunião" : "Transcrição enviada"}</div>
                    </td>
                    <td>{i.job_title || <span className="muted">—</span>}</td>
                    <td>
                      <StatusBadge status={i.status} />
                    </td>
                    <td>
                      <DecisionBadge decision={i.decision} />
                    </td>
                    <td className="nowrap">{fmtDate(i.scheduled_at || i.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

export default function Page() {
  return (
    <AppShell>
      <Dashboard />
    </AppShell>
  );
}
