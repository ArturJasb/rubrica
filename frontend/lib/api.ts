import { supabase } from "./supabase";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    // Erros de validação do FastAPI (422) vêm como lista
    if (Array.isArray(d)) {
      return d
        .map((e) => String((e as { msg?: string }).msg || "").replace(/^Value error, /, ""))
        .filter(Boolean)
        .join(" · ");
    }
  }
  if (status >= 500) return "O servidor encontrou um erro. Tente novamente em instantes.";
  return `Erro ${status}`;
}

/** Chama a API da Rubrica enviando o token de sessão do Supabase. */
export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await supabase().auth.getSession();
  const token = data.session?.access_token;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers || {}),
      },
    });
  } catch {
    throw new ApiError(0, "Não foi possível conectar ao servidor. Verifique sua internet e tente de novo.");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, errorMessage(body, res.status));
  return body as T;
}
