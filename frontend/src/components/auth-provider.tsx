"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import { apiFetch, type Usuario } from "@/lib/api";

type ContextoAuth = {
  usuario: Usuario | null;
  carregando: boolean;
  recarregar: () => Promise<void>;
  sair: () => Promise<void>;
};

const AuthContext = createContext<ContextoAuth | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);
  const router = useRouter();

  const recarregar = useCallback(async () => {
    try {
      const dados = await apiFetch<Usuario>("/api/auth/me");
      setUsuario(dados);
    } catch {
      setUsuario(null);
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  const sair = useCallback(async () => {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } catch {
      // ignora: o cookie será descartado de qualquer forma
    }
    setUsuario(null);
    router.replace("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ usuario, carregando, recarregar, sair }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): ContextoAuth {
  const contexto = useContext(AuthContext);
  if (!contexto) {
    throw new Error("useAuth precisa estar dentro de <AuthProvider>.");
  }
  return contexto;
}
