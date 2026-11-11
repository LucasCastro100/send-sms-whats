"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  CalendarHeart,
  MessageSquare,
  QrCode,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  UserCheck,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";
import { StatusWhatsApp } from "@/components/status-whatsapp";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, type Resumo } from "@/lib/api";
import { cn } from "@/lib/utils";

function IconeTile({
  children,
  tom = "brand",
}: {
  children: React.ReactNode;
  tom?: "brand" | "neutro";
}) {
  return (
    <span
      className={cn(
        "flex size-9 items-center justify-center rounded-xl ring-1",
        tom === "brand"
          ? "bg-brand-soft text-brand ring-brand/15 dark:bg-brand/15 dark:text-brand"
          : "bg-muted text-muted-foreground ring-border",
      )}
    >
      {children}
    </span>
  );
}

const ATALHOS = [
  {
    href: "/aniversariantes",
    icone: CalendarHeart,
    titulo: "Aniversariantes",
    texto: "Veja quem faz aniversário e dispare a mensagem do dia.",
  },
  {
    href: "/mensagens",
    icone: MessageSquare,
    titulo: "Mensagens",
    texto: "Envie um comunicado agora ou agende para mais tarde.",
  },
  {
    href: "/presenca",
    icone: UserCheck,
    titulo: "Presença",
    texto: "Registre faltas e acompanhe as visitas da semana.",
  },
  {
    href: "/conexao",
    icone: QrCode,
    titulo: "Conexão do WhatsApp",
    texto: "Gere o QR Code e conecte o número que vai enviar as mensagens.",
  },
];

export default function DashboardPage() {
  const { usuario } = useAuth();
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [carregando, setCarregando] = useState(true);

  const carregar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCarregando(true);
    try {
      setResumo(await api.get<Resumo>("/api/resumo"));
    } catch (e) {
      const mensagem =
        e instanceof ApiError ? e.message : "Falha ao carregar o resumo.";
      if (!silencioso) toast.error(mensagem);
    } finally {
      if (!silencioso) setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const whats = resumo?.whatsapp;

  return (
    <div className="space-y-7">
      <PageHeader
        sobretitulo="Visão geral"
        titulo={`Olá, ${usuario?.nome.split(" ")[0] ?? "usuário"}`}
        descricao="Acompanhe a automação do seu WhatsApp e o que precisa de atenção hoje."
      >
        <Button
          variant="outline"
          onClick={() => void carregar(true)}
          disabled={carregando}
        >
          <RefreshCw className={carregando ? "animate-spin" : ""} />
          Atualizar
        </Button>
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="gap-4">
          <CardHeader className="grid-cols-[auto_1fr] items-center gap-3">
            <IconeTile>
              <Smartphone className="size-4" />
            </IconeTile>
            <div className="space-y-0.5">
              <CardDescription>WhatsApp</CardDescription>
              <CardTitle>
                {carregando || !whats ? (
                  <Skeleton className="h-5 w-24" />
                ) : (
                  <StatusWhatsApp estado={whats.estado} />
                )}
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p className="font-medium">
              {whats?.perfil || "Sem perfil conectado"}
            </p>
            <p className="text-muted-foreground">
              {whats?.numero || "Nenhum número vinculado"}
            </p>
            <p className="pt-1 text-[0.7rem] text-muted-foreground">
              instância · {whats?.instancia ?? "—"}
            </p>
          </CardContent>
        </Card>

        {usuario?.admin ? (
          <Card className="gap-4">
            <CardHeader className="grid-cols-[auto_1fr] items-center gap-3">
              <IconeTile>
                <Users className="size-4" />
              </IconeTile>
              <div className="space-y-0.5">
                <CardDescription>Usuários</CardDescription>
                <CardTitle className="text-2xl leading-none">
                  {carregando || !resumo ? (
                    <Skeleton className="h-7 w-16" />
                  ) : (
                    resumo.usuarios?.total ?? 0
                  )}
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p className="flex items-center gap-1.5">
                <UserCheck className="size-4" />
                {resumo?.usuarios?.ativos ?? 0} ativos
              </p>
            </CardContent>
          </Card>
        ) : null}

        <Card className="gap-4">
          <CardHeader className="grid-cols-[auto_1fr] items-center gap-3">
            <IconeTile tom="neutro">
              <ShieldCheck className="size-4" />
            </IconeTile>
            <div className="space-y-0.5">
              <CardDescription>Sua sessão</CardDescription>
              <CardTitle>
                {usuario?.admin ? "Administrador" : "Usuário padrão"}
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <p>
              Conta <span className="font-medium text-foreground">@{usuario?.usuario}</span>
            </p>
          </CardContent>
        </Card>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight">Atalhos</h2>
          {usuario?.admin ? (
            <Link
              href="/usuarios"
              className="text-xs font-medium text-muted-foreground hover:text-brand"
            >
              Gerenciar usuários
            </Link>
          ) : null}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {ATALHOS.map(({ href, icone: Icone, titulo, texto }) => (
            <Link
              key={href}
              href={href}
              className="group rounded-xl border bg-card p-5 transition-colors hover:border-brand/30 hover:bg-brand-soft/40 dark:hover:bg-brand/5"
            >
              <div className="flex items-start justify-between gap-3">
                <IconeTile>
                  <Icone className="size-4" />
                </IconeTile>
                <ArrowRight className="size-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-brand" />
              </div>
              <p className="mt-3 font-heading text-sm font-semibold">{titulo}</p>
              <p className="mt-1 text-sm text-muted-foreground">{texto}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
