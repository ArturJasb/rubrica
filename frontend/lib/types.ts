export type Role = "admin" | "recrutador" | "gestor";

export type Status = "agendada" | "entrando" | "gravando" | "processando" | "concluida" | "erro";

export type Decision = "avancar" | "avancar_com_ressalvas" | "nao_avancar" | "inconclusivo";

export interface Competencia {
  nome: string;
  nota: number;
  evidencia: string;
}

export interface Citacao {
  texto: string;
  timestamp_segundos: number | null;
  contexto: string;
}

export interface Rubric {
  resumo: string;
  competencias: Competencia[];
  pontos_fortes: string[];
  pontos_de_atencao: string[];
  citacoes: Citacao[];
  recomendacao: { decisao: Decision; justificativa: string; proximo_passo: string };
}

export interface InterviewSummary {
  id: string;
  candidate_name: string;
  job_title: string;
  source: "bot" | "manual";
  status: Status;
  status_detail: string;
  meeting_url: string | null;
  scheduled_at: string | null;
  created_at: string;
  processed_at: string | null;
  created_by_name: string;
  decision: Decision | null;
}

export interface Segment {
  idx: number;
  speaker: string;
  text: string;
  start_seconds: number;
}

export interface InterviewDetail extends InterviewSummary {
  rubric: Rubric | null;
  rubric_edited: boolean;
  duration_seconds: number | null;
  segments: Segment[];
  audit?: { user_email: string; action: string; created_at: string }[];
}

export interface SearchHit {
  interview_id: string;
  candidate_name: string;
  job_title: string;
  speaker: string;
  text: string;
  start_seconds: number;
  idx: number;
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  name: string;
  role: Role;
  created_at: string;
}

export interface Me {
  member: Member;
  workspace: { id: string; name: string };
}
