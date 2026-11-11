"use client";

import Link from "next/link";
import { CalendarHeart, MessageCircle, ShieldCheck } from "lucide-react";

import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";

const DESTAQUES = [
  {
    icone: CalendarHeart,
    titulo: "Aniversariantes em dia",
    texto: "Ninguém do grupo é esquecido na data certa.",
  },
  {
    icone: MessageCircle,
    titulo: "Mensagens no WhatsApp",
    texto: "Envio manual ou agendado, direto para o grupo.",
  },
  {
    icone: ShieldCheck,
    titulo: "Cada líder com seu número",
    texto: "Conexão própria por usuário, com segurança.",
  },
];

export function AuthShell({
  titulo,
  descricao,
  children,
  rodape,
}: {
  titulo: string;
  descricao: string;
  children: React.ReactNode;
  rodape: React.ReactNode;
}) {
  return (
    <div className="grid min-h-svh lg:grid-cols-[1.05fr_1fr]">
      {/* Painel institucional */}
      <aside className="brand-gradient relative hidden overflow-hidden p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="bg-grid-light absolute inset-0 opacity-60" />
        <div className="absolute -top-32 -right-24 size-96 rounded-full bg-white/10 blur-3xl" />
        <div className="absolute -bottom-40 -left-24 size-[28rem] rounded-full bg-black/20 blur-3xl" />

        <div className="relative">
          <Brand tom="claro" />
        </div>

        <div className="relative max-w-md space-y-5">
          <p className="text-xs font-semibold tracking-[0.18em] text-white/60 uppercase">
            Cuidado que se lembra
          </p>
          <h2 className="font-heading text-3xl leading-[1.15] font-semibold tracking-tight">
            Cada aniversário importa. Cada pessoa tem nome.
          </h2>
          <p className="text-sm leading-relaxed text-white/75">
            Um painel único para lembrar aniversariantes, enviar mensagens e
            acompanhar a presença — sem depender de planilhas soltas.
          </p>

          <ul className="space-y-3 pt-2">
            {DESTAQUES.map(({ icone: Icone, titulo: t, texto }) => (
              <li key={t} className="flex items-start gap-3">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/12 ring-1 ring-white/20">
                  <Icone className="size-4" />
                </span>
                <div className="leading-tight">
                  <p className="text-sm font-medium">{t}</p>
                  <p className="text-xs text-white/65">{texto}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-white/50">
          Gestão de membros
        </p>
      </aside>

      {/* Formulário */}
      <main className="relative flex flex-col justify-center px-5 py-10 sm:px-10 lg:px-14">
        <div className="absolute top-4 right-4">
          <ThemeToggle />
        </div>

        <div className="mx-auto w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <Brand />
          </div>

          <div className="mb-7 space-y-1.5">
            <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
            <p className="text-sm text-muted-foreground">{descricao}</p>
          </div>

          {children}

          <div className="mt-7 text-center text-sm text-muted-foreground">
            {rodape}
          </div>

          <div className="mt-10 flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <span className="h-px w-8 bg-border" />
            <Link href="/dashboard" className="hover:text-foreground">
              Ir para o painel
            </Link>
            <span className="h-px w-8 bg-border" />
          </div>
        </div>
      </main>
    </div>
  );
}
