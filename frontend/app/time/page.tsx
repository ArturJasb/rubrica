"use client";

import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import Loading from "@/components/Loading";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, ROLE_HELP, ROLE_LABEL } from "@/lib/format";
import type { Member, Role } from "@/lib/types";

interface Invite {
  id: string;
  email: string;
  role: Role;
  created_at: string;
}

function inviteLink(email: string) {
  return `${window.location.origin}/cadastro/?email=${encodeURIComponent(email)}`;
}

function Team() {
  const { me, refreshMe } = useAuth();
  const [data, setData] = useState<{ members: Member[]; invites: Invite[] } | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("recrutador");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [wsName, setWsName] = useState(me?.workspace.name || "");
  const isAdmin = me?.member.role === "admin";

  const load = useCallback(async () => {
    try {
      setData(await api("/api/team"));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      const inv = await api<Invite>("/api/team/invites", { method: "POST", body: JSON.stringify({ email, role }) });
      await navigator.clipboard.writeText(inviteLink(inv.email)).catch(() => {});
      setMsg(`Convite criado para ${inv.email}. O link de cadastro foi copiado — envie para a pessoa.`);
      setEmail("");
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function act(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!data) return <Loading />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Time</h1>
          <p className="muted">Todos os membros veem as entrevistas do workspace, conforme seu papel.</p>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {msg && <p className="success">{msg}</p>}

      {isAdmin && (
        <section className="card">
          <h2>Workspace</h2>
          <form
            className="row"
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                await api("/api/workspace", { method: "PATCH", body: JSON.stringify({ name: wsName }) });
                await refreshMe();
                setMsg("Nome do workspace atualizado.");
              });
            }}
          >
            <input value={wsName} onChange={(e) => setWsName(e.target.value)} minLength={2} required aria-label="Nome do workspace" />
            <button className="btn btn-ghost">Salvar nome</button>
          </form>
        </section>
      )}

      {isAdmin && (
        <section className="card">
          <h2>Convidar pessoa</h2>
          <form className="invite-form" onSubmit={invite}>
            <input type="email" placeholder="email@empresa.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <select value={role} onChange={(e) => setRole(e.target.value as Role)} aria-label="Papel">
              {(Object.keys(ROLE_LABEL) as Role[]).map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r]}
                </option>
              ))}
            </select>
            <button className="btn">Convidar</button>
          </form>
          <p className="muted small">{ROLE_HELP[role]}. A pessoa entra no time ao criar a conta com este e-mail.</p>
        </section>
      )}

      <section className="card no-pad">
        <div className="section-head pad">
          <h2>Membros ({data.members.length})</h2>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>E-mail</th>
                <th>Papel</th>
                <th>Desde</th>
                {isAdmin && <th />}
              </tr>
            </thead>
            <tbody>
              {data.members.map((m) => (
                <tr key={m.id}>
                  <td>
                    {m.name}
                    {m.id === me?.member.id && <span className="muted"> (você)</span>}
                  </td>
                  <td>{m.email}</td>
                  <td>
                    {isAdmin && m.id !== me?.member.id ? (
                      <select
                        value={m.role}
                        onChange={(e) =>
                          act(() => api(`/api/team/members/${m.id}`, { method: "PATCH", body: JSON.stringify({ role: e.target.value }) }))
                        }
                        aria-label={`Papel de ${m.name}`}
                      >
                        {(Object.keys(ROLE_LABEL) as Role[]).map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABEL[r]}
                          </option>
                        ))}
                      </select>
                    ) : (
                      ROLE_LABEL[m.role]
                    )}
                  </td>
                  <td className="nowrap">{fmtDate(m.created_at)}</td>
                  {isAdmin && (
                    <td>
                      {m.id !== me?.member.id && (
                        <button
                          className="btn btn-danger-ghost btn-sm"
                          onClick={() =>
                            confirm(`Remover ${m.name} do time?`) &&
                            act(() => api(`/api/team/members/${m.id}`, { method: "DELETE" }))
                          }
                        >
                          Remover
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {data.invites.length > 0 && (
        <section className="card no-pad">
          <div className="section-head pad">
            <h2>Convites pendentes</h2>
          </div>
          <div className="table-wrap">
            <table className="table">
              <tbody>
                {data.invites.map((i) => (
                  <tr key={i.id}>
                    <td>{i.email}</td>
                    <td>{ROLE_LABEL[i.role]}</td>
                    <td className="nowrap">{fmtDate(i.created_at)}</td>
                    {isAdmin && (
                      <td className="row end">
                        <a
                          className="btn btn-ghost btn-sm"
                          href={`mailto:${i.email}?subject=${encodeURIComponent("Convite para a Rubrica")}&body=${encodeURIComponent(
                            `Olá! Você foi convidado(a) para o workspace "${me?.workspace.name}" na Rubrica. Crie sua conta com este e-mail: ${inviteLink(i.email)}`,
                          )}`}
                        >
                          Enviar por e-mail
                        </a>
                        <button className="btn btn-ghost btn-sm" onClick={() => navigator.clipboard.writeText(inviteLink(i.email))}>
                          Copiar link
                        </button>
                        <button
                          className="btn btn-danger-ghost btn-sm"
                          onClick={() => act(() => api(`/api/team/invites/${i.id}`, { method: "DELETE" }))}
                        >
                          Cancelar
                        </button>
                      </td>
                    )}
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
      <Team />
    </AppShell>
  );
}
