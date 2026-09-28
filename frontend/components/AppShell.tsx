"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL } from "@/lib/format";
import Loading from "./Loading";
import Logo from "./Logo";

const NAV = [
  { href: "/painel", label: "Painel" },
  { href: "/entrevistas/nova", label: "Nova entrevista" },
  { href: "/time", label: "Time" },
];

/** Layout das páginas logadas: exige sessão e mostra o menu. */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const { session, me, loading, meError, refreshMe, signOut } = useAuth();
  const router = useRouter();
  const path = usePathname();

  useEffect(() => {
    if (!loading && !session) {
      // Guarda caminho + query (ex.: /entrevistas/ver/?id=...) para voltar depois do login
      const here = window.location.pathname + window.location.search;
      router.replace(`/entrar/?next=${encodeURIComponent(here)}`);
    }
  }, [loading, session, router, path]);

  if (loading || !session) return <Loading full />;

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <Link href="/painel" className="brand">
            <Logo />
          </Link>
          <nav className="nav">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className={path.replace(/\/$/, "") === n.href ? "active" : ""}>
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="user">
            {me && (
              <span className="user-info" title={me.workspace.name}>
                {me.member.name} · <span className="muted">{ROLE_LABEL[me.member.role]}</span>
              </span>
            )}
            <button
              className="btn btn-ghost btn-sm"
              onClick={async () => {
                await signOut();
                router.replace("/entrar");
              }}
            >
              Sair
            </button>
          </div>
        </div>
      </header>
      <main className="container">
        {meError ? (
          <div className="card error-box">
            <p>{meError}</p>
            <button className="btn" onClick={refreshMe}>
              Tentar novamente
            </button>
          </div>
        ) : !me ? (
          <Loading />
        ) : (
          children
        )}
      </main>
    </div>
  );
}
