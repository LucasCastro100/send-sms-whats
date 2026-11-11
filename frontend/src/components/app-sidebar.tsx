"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Cake,
  CalendarDays,
  ChartColumn,
  Church,
  ClipboardCheck,
  HeartHandshake,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  QrCode,
  Upload,
  Users,
  UsersRound,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

const ITENS = [
  { href: "/dashboard", rotulo: "Painel", icone: LayoutDashboard },
  { href: "/aniversariantes", rotulo: "Aniversariantes", icone: Cake },
  { href: "/membros", rotulo: "Membros", icone: UsersRound },
  { href: "/mensagens", rotulo: "Mensagens", icone: MessageSquare },
  { href: "/presenca", rotulo: "Presença", icone: ClipboardCheck },
  { href: "/eventos", rotulo: "Eventos", icone: CalendarDays, soAdmin: true },
  { href: "/relatorios", rotulo: "Relatórios", icone: ChartColumn },
  { href: "/oracoes", rotulo: "Motivos de oração", icone: HeartHandshake },
  { href: "/conexao", rotulo: "Conexão WhatsApp", icone: QrCode },
  { href: "/grupos", rotulo: "Grupos", icone: UsersRound, soAdmin: true },
  { href: "/importar", rotulo: "Importar planilhas", icone: Upload, soAdmin: true },
  { href: "/igrejas", rotulo: "Igrejas", icone: Church, soAdmin: true },
  { href: "/usuarios", rotulo: "Usuários", icone: Users, soAdmin: true },
];

function iniciais(nome?: string) {
  if (!nome) return "?";
  const partes = nome.trim().split(/\s+/);
  return ((partes[0]?.[0] ?? "") + (partes[1]?.[0] ?? "")).toUpperCase();
}

function useItens() {
  const { usuario } = useAuth();
  return ITENS.filter((item) => !item.soAdmin || usuario?.admin);
}

function Navegacao({ aoNavegar }: { aoNavegar?: () => void }) {
  const caminho = usePathname();
  const itens = useItens();

  return (
    <nav className="flex flex-col gap-1">
      <p className="px-3 pb-2 text-[0.65rem] font-semibold tracking-[0.14em] text-muted-foreground/70 uppercase">
        Navegação
      </p>
      {itens.map((item) => {
        const Icone = item.icone;
        const ativo = caminho.startsWith(item.href);

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={aoNavegar}
            aria-current={ativo ? "page" : undefined}
            className={cn(
              "group relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
              ativo
                ? "bg-brand-soft text-brand-strong dark:bg-brand/15 dark:text-brand"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <span
              className={cn(
                "absolute top-1/2 left-0 h-5 w-[3px] -translate-y-1/2 rounded-full bg-brand transition-opacity",
                ativo ? "opacity-100" : "opacity-0",
              )}
            />
            <Icone
              className={cn(
                "size-4 transition-colors",
                ativo ? "text-brand" : "text-muted-foreground/80",
              )}
            />
            {item.rotulo}
          </Link>
        );
      })}
    </nav>
  );
}

function UsuarioRodape() {
  const { usuario, sair } = useAuth();

  return (
    <div className="flex items-center gap-2 rounded-xl border bg-muted/40 p-2">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand text-[0.7rem] font-bold text-brand-foreground">
        {iniciais(usuario?.nome)}
      </span>
      <div className="min-w-0 flex-1 leading-tight">
        <p className="truncate text-[0.8rem] font-semibold">{usuario?.nome}</p>
        <p className="truncate text-[0.7rem] text-muted-foreground">
          @{usuario?.usuario}
          {usuario?.admin ? " · admin" : ""}
        </p>
      </div>
      <div className="flex items-center">
        <ThemeToggle />
        <Button
          variant="ghost"
          size="icon"
          aria-label="Sair"
          className="text-muted-foreground hover:text-destructive"
          onClick={() => void sair()}
        >
          <LogOut />
        </Button>
      </div>
    </div>
  );
}

export function AppSidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 hidden w-[17rem] flex-col border-r border-sidebar-border bg-sidebar md:flex">
      <div className="px-5 py-5">
        <Brand />
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3">
        <Navegacao />
      </div>

      <div className="border-t border-sidebar-border p-3">
        <UsuarioRodape />
      </div>
    </aside>
  );
}

export function AppMobileHeader() {
  const { usuario, sair } = useAuth();
  const itens = useItens();

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-2 border-b bg-background/85 px-4 py-2.5 backdrop-blur-md md:hidden">
      <Brand />

      <div className="flex items-center gap-1">
        <ThemeToggle />
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" size="icon" aria-label="Abrir menu">
                <Menu />
              </Button>
            }
          />
          <DropdownMenuContent align="end" className="w-56">
            <div className="flex items-center gap-2 px-1.5 py-1.5">
              <span className="flex size-8 items-center justify-center rounded-lg bg-brand text-[0.7rem] font-bold text-brand-foreground">
                {iniciais(usuario?.nome)}
              </span>
              <div className="min-w-0 leading-tight">
                <p className="truncate text-sm font-medium">{usuario?.nome}</p>
                <p className="truncate text-xs text-muted-foreground">
                  @{usuario?.usuario}
                </p>
              </div>
            </div>
            <DropdownMenuSeparator />
            {itens.map((item) => {
              const Icone = item.icone;
              return (
                <DropdownMenuItem
                  key={item.href}
                  render={
                    <Link href={item.href}>
                      <Icone />
                      {item.rotulo}
                    </Link>
                  }
                />
              );
            })}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => void sair()}>
              <LogOut />
              Sair
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
