"use client";

import { useEffect, useState } from "react";

/** Indicador de carregamento; após alguns segundos explica que o servidor gratuito pode estar "acordando". */
export default function Loading({ full = false, label = "Carregando" }: { full?: boolean; label?: string }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 4000);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className={full ? "loading loading-full" : "loading"}>
      <span className="spinner" aria-hidden />
      <span>{label}…</span>
      {slow && (
        <p className="muted small">
          O servidor gratuito pode levar até 1 minuto para acordar na primeira visita. Obrigado pela paciência!
        </p>
      )}
    </div>
  );
}
