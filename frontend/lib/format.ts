import type { Decision, Role, Status } from "./types";

export function fmtTime(seconds: number | null | undefined): string {
  const s = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(sec).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  // O backend pode devolver data sem fuso (SQLite local); tratamos como UTC
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z");
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export const STATUS_LABEL: Record<Status, string> = {
  agendada: "Bot agendado",
  entrando: "Bot entrando",
  gravando: "Gravando",
  processando: "Gerando rubrica",
  concluida: "Rubrica pronta",
  erro: "Erro",
};

export const DECISION_LABEL: Record<Decision, string> = {
  avancar: "Avançar",
  avancar_com_ressalvas: "Avançar com ressalvas",
  nao_avancar: "Não avançar",
  inconclusivo: "Inconclusivo",
};

export const ROLE_LABEL: Record<Role, string> = {
  admin: "Admin",
  recrutador: "Recrutador(a)",
  gestor: "Gestor(a)",
};

export const ROLE_HELP: Record<Role, string> = {
  admin: "Tudo, inclusive gerenciar o time e ver o registro de acessos",
  recrutador: "Cria entrevistas, edita e exclui rubricas",
  gestor: "Vê e busca as entrevistas do time (somente leitura)",
};

export const PENDING: Status[] = ["agendada", "entrando", "gravando", "processando"];
