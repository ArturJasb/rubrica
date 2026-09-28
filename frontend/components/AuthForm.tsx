"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import Logo from "./Logo";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase";

function translate(msg: string): string {
  const m = msg.toLowerCase();
  if (m.includes("invalid login")) return "E-mail ou senha incorretos.";
  if (m.includes("already registered")) return "Este e-mail já tem conta. Use a opção Entrar.";
  if (m.includes("password should be")) return "A senha precisa ter pelo menos 6 caracteres.";
  if (m.includes("email not confirmed")) return "Confirme seu e-mail pelo link que enviamos antes de entrar.";
  if (m.includes("rate limit")) return "Muitas tentativas. Aguarde um minuto e tente de novo.";
  return msg;
}

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const params = useSearchParams();
  const { session } = useAuth();
  const next = params.get("next") || "/painel";
  const [name, setName] = useState("");
  const [email, setEmail] = useState(params.get("email") || "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (session) router.replace(next);
  }, [session, router, next]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);
    try {
      const sb = supabase();
      if (mode === "signup") {
        // Cadastro aberto: a API cria a conta já confirmada e entramos em seguida
        let created = false;
        try {
          await api("/api/auth/signup", { method: "POST", body: JSON.stringify({ name, email, password }) });
          created = true;
        } catch (err) {
          // 501 = backend local sem Supabase: usa o cadastro padrão do Supabase
          if (!(err instanceof ApiError && err.status === 501)) throw err;
        }
        if (created) {
          const { error } = await sb.auth.signInWithPassword({ email, password });
          if (error) throw error;
        } else {
          const { data, error } = await sb.auth.signUp({
            email,
            password,
            options: { data: { full_name: name }, emailRedirectTo: `${window.location.origin}/painel` },
          });
          if (error) throw error;
          if (!data.session) {
            setInfo("Conta criada! Enviamos um link de confirmação para o seu e-mail.");
            return;
          }
        }
      } else {
        const { error } = await sb.auth.signInWithPassword({ email, password });
        if (error) throw error;
      }
      router.replace(next);
    } catch (err) {
      setError(translate((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  const isSignup = mode === "signup";
  return (
    <div className="auth-page">
      <Link href="/" className="brand">
        <Logo />
      </Link>
      <form className="card auth-card" onSubmit={submit}>
        <h1>{isSignup ? "Criar sua conta" : "Entrar na Rubrica"}</h1>
        <p className="muted">
          {isSignup
            ? "Grátis para testar. Se você recebeu um convite, use o mesmo e-mail para entrar no time."
            : "Bem-vindo(a) de volta."}
        </p>
        {isSignup && (
          <label>
            Seu nome
            <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} autoComplete="name" />
          </label>
        )}
        <label>
          E-mail
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </label>
        <label>
          Senha
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            autoComplete={isSignup ? "new-password" : "current-password"}
          />
        </label>
        {error && <p className="error">{error}</p>}
        {info && <p className="success">{info}</p>}
        <button className="btn btn-block" disabled={busy}>
          {busy ? "Aguarde…" : isSignup ? "Criar conta" : "Entrar"}
        </button>
        <p className="muted small center">
          {isSignup ? (
            <>
              Já tem conta? <Link href="/entrar">Entrar</Link>
            </>
          ) : (
            <>
              Ainda não tem conta? <Link href="/cadastro">Criar conta</Link>
            </>
          )}
        </p>
      </form>
    </div>
  );
}
