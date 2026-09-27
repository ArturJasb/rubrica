"use client";

import Link from "next/link";
import Logo from "@/components/Logo";
import { useAuth } from "@/lib/auth";

const STEPS = [
  { n: "1", t: "Cole o link da entrevista", d: "Google Meet ou Microsoft Teams, agora ou com horário marcado." },
  { n: "2", t: "O bot entra e avisa todos", d: "Aviso de gravação (LGPD) no vídeo e no chat antes de a conversa começar." },
  { n: "3", t: "Transcrição em português", d: "Cada fala com quem disse e em que minuto — pesquisável depois." },
  { n: "4", t: "Rubrica pronta em minutos", d: "Competências com nota, pontos fortes, pontos de atenção, citações e recomendação." },
];

export default function Home() {
  const { session } = useAuth();
  return (
    <div className="landing">
      <header className="landing-top">
        <Logo />
        <div className="row">
          {session ? (
            <Link href="/painel" className="btn">
              Ir para o painel
            </Link>
          ) : (
            <>
              <Link href="/entrar" className="btn btn-ghost">
                Entrar
              </Link>
              <Link href="/cadastro" className="btn">
                Criar conta grátis
              </Link>
            </>
          )}
        </div>
      </header>

      <section className="hero">
        <p className="eyebrow">Para times de recrutamento de tecnologia</p>
        <h1>Preste atenção no candidato. A Rubrica cuida das anotações.</h1>
        <p className="lead">
          A Rubrica entra na sua entrevista no Google Meet ou no Teams, transcreve a conversa em português e entrega
          uma rubrica de avaliação estruturada para você compartilhar com o gestor ou colar no ATS.
        </p>
        <div className="row center">
          <Link href={session ? "/entrevistas/nova" : "/cadastro"} className="btn btn-lg">
            {session ? "Nova entrevista" : "Começar agora"}
          </Link>
        </div>
      </section>

      <section className="steps">
        {STEPS.map((s) => (
          <div key={s.n} className="card step">
            <span className="step-n">{s.n}</span>
            <h3>{s.t}</h3>
            <p className="muted">{s.d}</p>
          </div>
        ))}
      </section>

      <footer className="landing-foot muted small">
        Rubrica · MVP acadêmico (SP2) · Dados tratados conforme a LGPD: mídia bruta apagada após a transcrição e
        exclusão sob demanda.
      </footer>
    </div>
  );
}
