"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AuthShell } from "@/components/auth-shell";
import { PasswordInput } from "@/components/password-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch, ApiError } from "@/lib/api";
import { errosPorCampo, loginSchema } from "@/lib/schemas";

export default function LoginPage() {
  const router = useRouter();
  const [usuario, setUsuario] = useState("");
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [erros, setErros] = useState<Record<string, string>>({});

  function limparErro(campo: string) {
    setErros((atuais) => {
      if (!atuais[campo]) return atuais;
      const proximos = { ...atuais };
      delete proximos[campo];
      return proximos;
    });
  }

  async function entrar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);

    const validacao = loginSchema.safeParse({ usuario, senha });
    if (!validacao.success) {
      setErros(errosPorCampo(validacao.error));
      return;
    }

    setErros({});
    setEnviando(true);

    try {
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(validacao.data),
      });
      toast.success("Bem-vindo de volta!");
      router.replace("/dashboard");
      router.refresh();
    } catch (e) {
      const mensagem =
        e instanceof ApiError ? e.message : "Não foi possível entrar agora.";
      setErro(mensagem);
      toast.error(mensagem);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <AuthShell
      titulo="Entrar"
      descricao="Use o seu usuário para acessar o painel."
      rodape={
        <span className="text-muted-foreground">
          Não tem conta? Peça ao administrador para criar a sua.
        </span>
      }
    >
      <form onSubmit={entrar} noValidate className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="usuario">E-mail ou usuário</Label>
          <Input
            id="usuario"
            name="usuario"
            autoComplete="username"
            autoFocus
            value={usuario}
            aria-invalid={Boolean(erros.usuario)}
            onChange={(e) => {
              setUsuario(e.target.value);
              limparErro("usuario");
            }}
          />
          {erros.usuario ? (
            <p className="text-xs text-destructive">{erros.usuario}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="senha">Senha</Label>
          <PasswordInput
            id="senha"
            name="senha"
            autoComplete="current-password"
            value={senha}
            aria-invalid={Boolean(erros.senha)}
            onChange={(e) => {
              setSenha(e.target.value);
              limparErro("senha");
            }}
          />
          {erros.senha ? (
            <p className="text-xs text-destructive">{erros.senha}</p>
          ) : null}
        </div>

        {erro ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-destructive">
            {erro}
          </p>
        ) : null}

        <Button type="submit" className="h-10 w-full" disabled={enviando}>
          {enviando ? <Loader2 className="animate-spin" /> : null}
          {enviando ? "Entrando..." : "Entrar"}
        </Button>
      </form>
    </AuthShell>
  );
}
