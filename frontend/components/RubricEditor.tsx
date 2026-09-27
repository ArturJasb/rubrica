"use client";

import { useState } from "react";
import { DECISION_LABEL } from "@/lib/format";
import type { Decision, Rubric } from "@/lib/types";

const lines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

/** Formulário para o recrutador revisar e ajustar a rubrica gerada pela IA. */
export default function RubricEditor({
  initial,
  onSave,
  onCancel,
}: {
  initial: Rubric;
  onSave: (r: Rubric) => Promise<void>;
  onCancel: () => void;
}) {
  const [r, setR] = useState<Rubric>(structuredClone(initial));
  const [strong, setStrong] = useState(initial.pontos_fortes.join("\n"));
  const [attention, setAttention] = useState(initial.pontos_de_atencao.join("\n"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const setComp = (i: number, patch: Partial<Rubric["competencias"][number]>) =>
    setR({ ...r, competencias: r.competencias.map((c, j) => (j === i ? { ...c, ...patch } : c)) });

  async function save() {
    setBusy(true);
    setError("");
    try {
      await onSave({
        ...r,
        competencias: r.competencias.filter((c) => c.nome.trim()),
        pontos_fortes: lines(strong),
        pontos_de_atencao: lines(attention),
      });
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="card form editor">
      <h2>Editar rubrica</h2>
      <label>
        Resumo
        <textarea rows={3} value={r.resumo} onChange={(e) => setR({ ...r, resumo: e.target.value })} />
      </label>

      <fieldset>
        <legend>Competências</legend>
        {r.competencias.map((c, i) => (
          <div key={i} className="comp-edit">
            <input value={c.nome} onChange={(e) => setComp(i, { nome: e.target.value })} placeholder="Competência" />
            <select value={c.nota} onChange={(e) => setComp(i, { nota: Number(e.target.value) })} aria-label="Nota">
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n}/5
                </option>
              ))}
            </select>
            <textarea rows={2} value={c.evidencia} onChange={(e) => setComp(i, { evidencia: e.target.value })} placeholder="Evidência" />
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setR({ ...r, competencias: r.competencias.filter((_, j) => j !== i) })}
            >
              Remover
            </button>
          </div>
        ))}
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => setR({ ...r, competencias: [...r.competencias, { nome: "", nota: 3, evidencia: "" }] })}
        >
          + Adicionar competência
        </button>
      </fieldset>

      <div className="grid-2">
        <label>
          Pontos fortes (um por linha)
          <textarea rows={5} value={strong} onChange={(e) => setStrong(e.target.value)} />
        </label>
        <label>
          Pontos de atenção (um por linha)
          <textarea rows={5} value={attention} onChange={(e) => setAttention(e.target.value)} />
        </label>
      </div>

      <div className="grid-2">
        <label>
          Recomendação
          <select
            value={r.recomendacao.decisao}
            onChange={(e) => setR({ ...r, recomendacao: { ...r.recomendacao, decisao: e.target.value as Decision } })}
          >
            {Object.entries(DECISION_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Próximo passo
          <input
            value={r.recomendacao.proximo_passo}
            onChange={(e) => setR({ ...r, recomendacao: { ...r.recomendacao, proximo_passo: e.target.value } })}
          />
        </label>
      </div>
      <label>
        Justificativa
        <textarea
          rows={2}
          value={r.recomendacao.justificativa}
          onChange={(e) => setR({ ...r, recomendacao: { ...r.recomendacao, justificativa: e.target.value } })}
        />
      </label>

      {r.citacoes.length > 0 && (
        <fieldset>
          <legend>Citações</legend>
          {r.citacoes.map((q, i) => (
            <div key={i} className="quote-edit">
              <span>“{q.texto}”</span>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setR({ ...r, citacoes: r.citacoes.filter((_, j) => j !== i) })}
              >
                Remover
              </button>
            </div>
          ))}
        </fieldset>
      )}

      {error && <p className="error">{error}</p>}
      <div className="row end">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
          Cancelar
        </button>
        <button type="button" className="btn" onClick={save} disabled={busy}>
          {busy ? "Salvando…" : "Salvar alterações"}
        </button>
      </div>
    </div>
  );
}
