"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Check,
  HeartHandshake,
  Loader2,
  RefreshCw,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, type Igreja, type Oracao } from "@/lib/api";
import { cn } from "@/lib/utils";

type FiltroStatus = "aberto" | "atendido" | "todos";

const STATUS: { valor: FiltroStatus; rotulo: string }[] = [
  { valor: "aberto", rotulo: "Abertos" },
  { valor: "atendido", rotulo: "Atendidos" },
  { valor: "todos", rotulo: "Todos" },
];

function mensagemErro(erro: unknown, padrao: string): string {
  return erro instanceof ApiError ? erro.message : padrao;
}

export default function OracoesPage() {
  const { usuario } = useAuth();
  const [status, setStatus] = useState<FiltroStatus>("aberto");
  const [busca, setBusca] = useState("");
  const [grupo, setGrupo] = useState("");
  const [igrejaId, setIgrejaId] = useState("");
  const [igrejas, setIgrejas] = useState<Igreja[]>([]);
  const [oracoes, setOracoes] = useState<Oracao[] | null>(null);
  const [grupos, setGrupos] = useState<string[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [processando, setProcessando] = useState<number | null>(null);

  const carregar = useCallback(async () => {
    setCarregando(true);
    try {
      const parametros = new URLSearchParams({ status });
      if (busca.trim()) parametros.set("busca", busca.trim());
      if (grupo) parametros.set("grupo", grupo);
      if (igrejaId) parametros.set("igreja_id", igrejaId);

      setOracoes(
        await api.get<Oracao[]>(`/api/oracoes?${parametros.toString()}`),
      );
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao carregar os motivos de oração."));
    } finally {
      setCarregando(false);
    }
  }, [status, busca, grupo, igrejaId]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  useEffect(() => {
    api
      .get<Igreja[]>("/api/igrejas")
      .then(setIgrejas)
      .catch(() => setIgrejas([]));

    api
      .get<{ grupo: string }[]>("/api/pessoas?fonte=icm")
      .then((pessoas) => {
        const valores = new Set(
          pessoas.map((pessoa) => pessoa.grupo).filter(Boolean),
        );
        setGrupos(
          Array.from(valores).sort((a, b) => a.localeCompare(b, "pt-BR")),
        );
      })
      .catch(() => setGrupos([]));
  }, []);

  const abertos = useMemo(
    () => (oracoes ?? []).filter((motivo) => motivo.status === "aberto").length,
    [oracoes],
  );

  async function alternar(motivo: Oracao) {
    const novo = motivo.status === "aberto" ? "atendido" : "aberto";
    setProcessando(motivo.id);
    try {
      const atualizado = await api.patch<Oracao>(`/api/oracoes/${motivo.id}`, {
        status: novo,
      });
      setOracoes((atual) =>
        atual
          ? status === "todos"
            ? atual.map((item) =>
                item.id === atualizado.id ? atualizado : item,
              )
            : atual.filter((item) => item.id !== atualizado.id)
          : atual,
      );
      toast.success(
        novo === "atendido" ? "Marcado como atendido." : "Motivo reaberto.",
      );
    } catch (e) {
      toast.error(
        mensagemErro(e, "Não foi possível atualizar o motivo."),
      );
    } finally {
      setProcessando(null);
    }
  }

  async function excluir(motivo: Oracao) {
    if (!window.confirm(`Excluir o motivo de ${motivo.nome}?`)) return;
    setProcessando(motivo.id);
    try {
      await api.delete(`/api/oracoes/${motivo.id}`);
      setOracoes((atual) =>
        atual ? atual.filter((item) => item.id !== motivo.id) : atual,
      );
      toast.success("Motivo excluído.");
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível excluir o motivo."));
    } finally {
      setProcessando(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        sobretitulo="Cuidado"
        titulo="Motivos de oração"
        descricao="Todos os pedidos lançados na ficha das vidas. Marque como atendido quando a oração for respondida. Para lançar um novo, abra a ficha em Membros."
      >
        {usuario && !usuario.admin ? (
          <Badge
            variant="outline"
            className="border-brand/30 bg-brand-soft text-brand"
          >
            {usuario.funcao === "frente"
              ? "Grupo de Senhoras"
              : usuario.grupo_nome || "Sem grupo"}
          </Badge>
        ) : null}
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HeartHandshake className="size-4" />
            Pedidos ({oracoes?.length ?? 0})
          </CardTitle>
          <CardDescription>
            {carregando
              ? "Carregando..."
              : status === "aberto"
                ? `${abertos} motivo(s) em aberto nessa visão.`
                : `${oracoes?.length ?? 0} motivo(s) nessa visão.`}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1.5">
              <Label>Status</Label>
              <div className="flex gap-2">
                {STATUS.map((item) => (
                  <Button
                    key={item.valor}
                    variant={status === item.valor ? "default" : "outline"}
                    size="sm"
                    onClick={() => setStatus(item.valor)}
                  >
                    {item.rotulo}
                  </Button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="busca-oracoes">Buscar pessoa</Label>
              <Input
                id="busca-oracoes"
                value={busca}
                placeholder="Parte do nome"
                className="w-56"
                onChange={(e) => setBusca(e.target.value)}
              />
            </div>

            {grupos.length > 0 ? (
              <div className="space-y-1.5">
                <Label htmlFor="grupo-oracoes">Grupo</Label>
                <select
                  id="grupo-oracoes"
                  value={grupo}
                  onChange={(e) => setGrupo(e.target.value)}
                  className="h-9 max-w-56 rounded-lg border bg-background px-2 text-sm"
                >
                  <option value="">Todos</option>
                  {grupos.map((nome) => (
                    <option key={nome} value={nome}>
                      {nome}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            {igrejas.length > 0 ? (
              <div className="space-y-1.5">
                <Label htmlFor="igreja-oracoes">Igreja</Label>
                <select
                  id="igreja-oracoes"
                  value={igrejaId}
                  onChange={(e) => setIgrejaId(e.target.value)}
                  className="h-9 max-w-56 rounded-lg border bg-background px-2 text-sm"
                >
                  <option value="">Todas</option>
                  {igrejas.map((igreja) => (
                    <option key={igreja.id} value={String(igreja.id)}>
                      {igreja.nome}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            <Button variant="outline" onClick={() => void carregar()}>
              <RefreshCw className={cn(carregando && "animate-spin")} />
              Atualizar
            </Button>
          </div>

          {carregando && !oracoes ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : (oracoes ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhum motivo de oração nessa visão.
            </p>
          ) : (
            <ul className="space-y-2">
              {(oracoes ?? []).map((motivo) => (
                <li
                  key={motivo.id}
                  className={cn(
                    "space-y-2 rounded-lg border p-3",
                    motivo.status === "atendido" && "bg-muted/30",
                  )}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-medium">{motivo.nome}</span>
                        {motivo.grupo ? (
                          <Badge variant="outline">{motivo.grupo}</Badge>
                        ) : null}
                        {motivo.igreja_nome ? (
                          <Badge variant="outline">{motivo.igreja_nome}</Badge>
                        ) : null}
                        <Badge
                          variant={
                            motivo.status === "aberto"
                              ? "secondary"
                              : "outline"
                          }
                        >
                          {motivo.status === "aberto" ? "aberto" : "atendido"}
                        </Badge>
                      </div>
                      <p
                        className={cn(
                          "text-sm",
                          motivo.status === "atendido" &&
                            "text-muted-foreground line-through",
                        )}
                      >
                        {motivo.texto}
                      </p>
                    </div>

                    <div className="flex shrink-0 items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void alternar(motivo)}
                        disabled={processando === motivo.id}
                      >
                        {processando === motivo.id ? (
                          <Loader2 className="animate-spin" />
                        ) : motivo.status === "aberto" ? (
                          <Check />
                        ) : (
                          <RotateCcw />
                        )}
                        {motivo.status === "aberto"
                          ? "Atendido"
                          : "Reabrir"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Excluir motivo"
                        className="text-muted-foreground hover:text-destructive"
                        onClick={() => void excluir(motivo)}
                        disabled={processando === motivo.id}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  </div>

                  <p className="text-[0.65rem] text-muted-foreground">
                    {motivo.criado_por ? `${motivo.criado_por} · ` : ""}
                    {motivo.criado_em}
                    {motivo.atendido_em
                      ? ` · atendido em ${motivo.atendido_em}`
                      : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
