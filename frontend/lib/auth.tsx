"use client";

import type { Session } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { supabase } from "./supabase";
import type { Me } from "./types";

interface AuthState {
  session: Session | null;
  me: Me | null;
  loading: boolean;
  meError: string;
  refreshMe: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  session: null,
  me: null,
  loading: true,
  meError: "",
  refreshMe: async () => {},
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [meError, setMeError] = useState("");

  const refreshMe = useCallback(async () => {
    try {
      setMeError("");
      setMe(await api<Me>("/api/me"));
    } catch (e) {
      setMeError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    const sb = supabase();
    sb.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: sub } = sb.auth.onAuthStateChange((_evt, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  const userId = session?.user.id;
  useEffect(() => {
    if (userId) refreshMe();
    else setMe(null);
  }, [userId, refreshMe]);

  const signOut = useCallback(async () => {
    await supabase().auth.signOut();
    setMe(null);
  }, []);

  return (
    <AuthContext.Provider value={{ session, me, loading, meError, refreshMe, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
