"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import { DecisionBadge, StatusBadge } from "@/components/Badges";
import Loading from "@/components/Loading";
import RubricEditor from "@/components/RubricEditor";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DECISION_LABEL, fmtDate, fmtTime, PENDING } from "@/lib/format";
import type { InterviewDetail, Rubric, Status } from "@/lib/types";

const PIPELINE: { key: Status; label: string }[] = [
  { key: "agendada", label: "Bot agendado" },
  { key: "entrando", label: "Entrando na chamada" },
  { key: "gravando", label: "Gravando e transcrevendo" },
  { key: "processando", label: "Gerando rubrica" },
  { key: "concluida", label: "Pronta" },
];

const ACTION_LABEL: Record<string, string> = {
  visualizou: "visualizou",
  criou_entrevista: "criou a entrevista",
  editou_rubrica: "editou a rubrica",
  regerou_rubrica: "gerou a rubrica novamente",
};

/** Texto pronto para colar no ATS (Gupy, Kenoby, SOLIDES...) ou mandar ao gestor. */
function exportText(d: InterviewDetail): string {
  const r = d.rubric!;
  const out = [
    `AVALIAÇÃO DE ENTREVISTA — ${d.candidate_name}${d.job_title ? ` (${d.job_title})` : ""}`,
    `Data: ${fmtDate(d.processed_at || d.created_at)} · Entrevistador(a): ${d.created_by_name}`,
    "",
    `RECOMENDAÇÃO: ${DECISION_LABEL[r.recomendacao.decisao]}`,
    r.recomendacao.justificativa,
    r.recomendacao.proximo_passo ? `Próximo passo: ${r.recomendacao.proximo_passo}` : "",
    "",
    "RESUMO",
    r.resumo,
    "",
    "COMPETÊNCIAS",
    ...r.competencias.map((c) => `- ${c.nome}: ${c.nota}/5 — ${c.evidencia}`),
    "",
    "PONTOS FORTES",
    ...r.pontos_fortes.map((x) => `- ${x}`),
    "",
    "PONTOS DE ATENÇÃO",
    ...r.pontos_de_atencao.map((x) => `- ${x}`),
    "",
    "CITAÇÕES DO(A) CANDIDATO(A)",
    ...r.citacoes.map((q) => `- [${fmtTime(q.timestamp_segundos)}] "${q.texto}"${q.contexto ? ` — ${q.contexto}` : ""}`),
    "",
    "Gerado pela Rubrica e revisado pelo(a) recrutador(a).",
  ];
  return out.filter((l, i, a) => !(l === "" && a[i - 1] === "")).join("\n");
}

function Detail() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const router = useRouter();
  const { me } = useAuth();
  const [d, setD] = useState<InterviewDetail | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [filter, setFilter] = useState("");
  const [focusIdx, setFocusIdx] = useState<number | null>(params.get("t") ? Number(params.get("t")) : null);
  const segRefs = useRef<Record<number, HTMLLIElement | null>>({});

  const load = useCallback(async () => {
    try {
      setD(await api<InterviewDetail>(`/api/interviews/${id}`));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Enquanto não termina: consulta o status do bot (fallback do webhook) e recarrega
  const pending = d ? PENDING.includes(d.status) : false;
  const source = d?.source;
  useEffect(() => {
    if (!pending) return;
    const tick = async () => {
      if (source === "bot") {
        try {
          await api(`/api/interviews/${id}/sync`, { method: "POST" });
        } catch {
          /* tenta de novo no próximo ciclo */
        }
      }
      load();
    };
    const t = setInterval(tick, source === "bot" ? 10000 : 3000);
    return () => clearInterval(t);
  }, [pending, source, id, load]);

  // Rola até o trecho vindo da busca ou de uma citação
  useEffect(() => {
    if (focusIdx !== null && d?.segments.length) {
      segRefs.current[focusIdx]?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [focusIdx, d?.segments.length]);

  function jumpTo(seconds: number | null) {
    if (seconds === null || !d) return;
    let best = 0;
    d.segments.forEach((s, i) => {
      if (s.start_seconds <= seconds + 1) best = i;
    });
    setFilter("");
    setFocusIdx(d.segments[best]?.idx ?? null);
  }

  async function saveRubric(r: Rubric) {
    await api(`/api/interviews/${id}/rubric`, { method: "PUT", body: JSON.stringify({ rubric: r }) });
    setEditing(false);
    await load();
  }

  async function regenerate() {
    if (!confirm("Gerar a rubrica novamente com IA? As edições manuais serão substituídas.")) return;
    try {
      await api(`/api/interviews/${id}/regenerate`, { method: "POST" });
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove() {
    if (!confirm("Excluir esta entrevista? Transcrição, rubrica e gravação serão apagadas definitivamente.")) return;
    try {
      await api(`/api/interviews/${id}`, { method: "DELETE" });
      router.replace("/painel");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function copy() {
    if (!d?.rubric) return;
    await navigator.clipboard.writeText(exportText(d));
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  if (error && !d)
    return (
      <div className="card error-box">
        <p>{error}</p>
        <Link href="/painel" className="btn">
          Voltar ao painel
        </Link>
      </div>
    );
  if (!d) return <Loading />;

  const canWrite = me?.member.role !== "gestor";
  const r = d.rubric;
  const stepIdx = PIPELINE.findIndex((p) => p.key === d.status);
  const segments = filter
    ? d.segments.filter((s) => (s.text + " " + s.speaker).toLowerCase().includes(filter.toLowerCase()))
    : d.segments;

  return (
    <>
      <Link href="/painel" className="back">
        ← Entrevistas
      </Link>
      <div className="page-head">
        <div>
          <h1>{d.candidate_name}</h1>
          <p className="muted">
            {d.job_title || "Vaga não informada"} · {fmtDate(d.scheduled_at || d.created_at)} · por {d.created_by_name}
            {d.duration_seconds ? ` · ${fmtTime(d.duration_seconds)} de conversa` : ""}
          </p>
          <div className="row">
            <StatusBadge status={d.status} />
            {r && <DecisionBadge decision={r.recomendacao.decisao} />}
            {d.rubric_edited && <span className="badge">Revisada pelo recrutador</span>}
          </div>
        </div>
        <div className="row wrap">
          {r && !editing && (
            <button className="btn" onClick={copy}>
              {copied ? "Copiado ✓" : "Copiar para o ATS"}
            </button>
          )}
          {canWrite && r && !editing && (
            <button className="btn btn-ghost" onClick={() => setEditing(true)}>
              Editar
            </button>
          )}
          {canWrite && d.segments.length > 0 && !pending && !editing && (
            <button className="btn btn-ghost" onClick={regenerate}>
              Gerar de novo
            </button>
          )}
          {canWrite && (
            <button className="btn btn-danger-ghost" onClick={remove}>
              Excluir
            </button>
          )}
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {pending && (
        <section className="card progress">
          <ol className="pipeline">
            {PIPELINE.filter((p) => d.source === "bot" || p.key === "processando" || p.key === "concluida").map((p) => {
              const idx = PIPELINE.findIndex((x) => x.key === p.key);
              return (
                <li key={p.key} className={idx < stepIdx ? "done" : idx === stepIdx ? "current" : ""}>
                  {p.label}
                </li>
              );
            })}
          </ol>
          <p className="muted">
            {d.status_detail ||
              (d.status === "agendada"
                ? d.scheduled_at
                  ? `O bot entrará na reunião em ${fmtDate(d.scheduled_at)}.`
                  : "O bot está a caminho da reunião."
                : d.status === "gravando"
                  ? "O bot está na chamada. A rubrica será gerada automaticamente quando a reunião terminar."
                  : "Gerando a rubrica com IA — normalmente leva menos de 1 minuto.")}
          </p>
          {d.meeting_url && (
            <p className="small">
              Reunião:{" "}
              <a href={d.meeting_url} target="_blank" rel="noreferrer">
                {d.meeting_url}
              </a>
            </p>
          )}
        </section>
      )}

      {d.status === "erro" && (
        <section className="card error-box">
          <strong>Não foi possível concluir esta entrevista.</strong>
          <p>{d.status_detail}</p>
          {canWrite && d.segments.length > 0 && (
            <button className="btn" onClick={regenerate}>
              Tentar gerar a rubrica novamente
            </button>
          )}
        </section>
      )}

      <div className="detail-grid">
        <div>
          {editing && r ? (
            <RubricEditor initial={r} onSave={saveRubric} onCancel={() => setEditing(false)} />
          ) : r ? (
            <section className="card rubric">
              <div className={`reco decision-${r.recomendacao.decisao}`}>
                <span className="small">Recomendação</span>
                <strong>{DECISION_LABEL[r.recomendacao.decisao]}</strong>
                <p>{r.recomendacao.justificativa}</p>
                {r.recomendacao.proximo_passo && (
                  <p className="small">
                    <strong>Próximo passo:</strong> {r.recomendacao.proximo_passo}
                  </p>
                )}
              </div>

              <h2>Resumo</h2>
              <p>{r.resumo}</p>

              <h2>Competências</h2>
              <ul className="comps">
                {r.competencias.map((c) => (
                  <li key={c.nome}>
                    <div className="comp-head">
                      <strong>{c.nome}</strong>
                      <span className="score" aria-label={`Nota ${c.nota} de 5`}>
                        {[1, 2, 3, 4, 5].map((n) => (
                          <span key={n} className={n <= c.nota ? "on" : ""} />
                        ))}
                        <em>{c.nota}/5</em>
                      </span>
                    </div>
                    <p className="muted">{c.evidencia}</p>
                  </li>
                ))}
              </ul>

              <div className="grid-2">
                <div>
                  <h2>Pontos fortes</h2>
                  <ul className="bullets good">
                    {r.pontos_fortes.map((x, i) => (
                      <li key={i}>{x}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h2>Pontos de atenção</h2>
                  <ul className="bullets warn">
                    {r.pontos_de_atencao.map((x, i) => (
                      <li key={i}>{x}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {r.citacoes.length > 0 && (
                <>
                  <h2>Citações relevantes</h2>
                  <ul className="quotes">
                    {r.citacoes.map((q, i) => (
                      <li key={i}>
                        <blockquote>“{q.texto}”</blockquote>
                        <div className="small muted">
                          {q.timestamp_segundos !== null && (
                            <button className="ts-link" onClick={() => jumpTo(q.timestamp_segundos)}>
                              {fmtTime(q.timestamp_segundos)}
                            </button>
                          )}{" "}
                          {q.contexto}
                        </div>
                      </li>
                    ))}
                  </ul>
                </>
              )}
              <p className="small muted disclaimer">
                Rubrica gerada por IA a partir da transcrição. Revise antes de tomar decisões — a avaliação final é sempre
                de uma pessoa.
              </p>
            </section>
          ) : (
            !pending &&
            d.status !== "erro" && (
              <section className="card">
                <p className="muted">A rubrica ainda não foi gerada.</p>
              </section>
            )
          )}

          {me?.member.role === "admin" && d.audit && d.audit.length > 0 && (
            <details className="card audit">
              <summary>Registro de acessos (LGPD)</summary>
              <ul>
                {d.audit.map((a, i) => (
                  <li key={i} className="small">
                    {fmtDate(a.created_at)} — {a.user_email} {ACTION_LABEL[a.action] || a.action}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>

        <aside className="card transcript">
          <div className="section-head">
            <h2>Transcrição</h2>
            <span className="muted small">{d.segments.length} falas</span>
          </div>
          {d.segments.length === 0 ? (
            <p className="muted small">A transcrição aparece aqui quando a chamada terminar.</p>
          ) : (
            <>
              <input
                type="search"
                placeholder="Filtrar nesta entrevista…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
              <ul className="segments">
                {segments.map((s) => (
                  <li
                    key={s.idx}
                    ref={(el) => {
                      segRefs.current[s.idx] = el;
                    }}
                    className={focusIdx === s.idx ? "focus" : ""}
                  >
                    <div className="seg-head">
                      <span className="ts">{fmtTime(s.start_seconds)}</span>
                      <strong>{s.speaker}</strong>
                    </div>
                    <p>{s.text}</p>
                  </li>
                ))}
                {segments.length === 0 && <li className="muted small">Nenhuma fala contém “{filter}”.</li>}
              </ul>
            </>
          )}
        </aside>
      </div>
    </>
  );
}

export default function Page() {
  return (
    <AppShell>
      <Suspense fallback={<Loading />}>
        <Detail />
      </Suspense>
    </AppShell>
  );
}
