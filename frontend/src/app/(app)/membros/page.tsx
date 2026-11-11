"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RefreshCw, ScanEye, UserRoundX, UsersRound } from "lucide-react";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  api,
  ApiError,
  type Fonte,
  type Igreja,
  type Pessoa,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const FONTES: { valor: Fonte; rotulo: string }[] = [
  { valor: "icm", rotulo: "ICM" },
  { valor: "zoom", rotulo: "Zoom" },
];

export default function MembrosPage() {
  const { usuario } = useAuth();
  const [fonte, setFonte] = useState<Fonte>("icm");
  const [pessoas, setPessoas] = useState<Pessoa[] | null>(null);
  const [igrejas, setIgrejas] = useState<Igreja[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [busca, setBusca] = useState("");
  const [filtroGrupo, setFiltroGrupo] = useState("todos");
  const [filtroIgreja, setFiltroIgreja] = useState("todas");
  const [filtroSituacao, setFiltroSituacao] = useState("todos");

  const fontesDisponiveis = useMemo(
    () => FONTES.filter((item) => item.valor === "icm" || usuario?.admin),
    [usuario?.admin],
  );

  useEffect(() => {
    if (!usuario?.admin && fonte === "zoom") setFonte("icm");
  }, [usuario?.admin, fonte]);

  const carregar = useCallback(async () => {
    setCarregando(true);
    try {
      setPessoas(await api.get<Pessoa[]>(`/api/pessoas?fonte=${fonte}`));
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Falha ao carregar os membros.",
      );
    } finally {
      setCarregando(false);
    }
  }, [fonte]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  useEffect(() => {
    api
      .get<Igreja[]>("/api/igrejas")
      .then(setIgrejas)
      .catch(() => setIgrejas([]));
  }, []);

  useEffect(() => {
    setFiltroIgreja("todas");
  }, [fonte]);

  const grupos = useMemo(() => {
    const valores = new Set(
      (pessoas ?? []).map((pessoa) => pessoa.grupo).filter(Boolean),
    );
    return Array.from(valores).sort((a, b) => a.localeCompare(b, "pt-BR"));
  }, [pessoas]);

  const situacoes = useMemo(() => {
    const valores = new Set(
      (pessoas ?? []).map((pessoa) => pessoa.situacao).filter(Boolean),
    );
    return Array.from(valores).sort((a, b) => a.localeCompare(b, "pt-BR"));
  }, [pessoas]);

  const filtradas = useMemo(() => {
    const termo = busca.trim().toUpperCase();
    return (pessoas ?? []).filter((pessoa) => {
      if (termo && !pessoa.nome_chave.includes(termo)) return false;
      if (filtroGrupo !== "todos" && pessoa.grupo !== filtroGrupo) return false;
      if (filtroSituacao !== "todos" && pessoa.situacao !== filtroSituacao) {
        return false;
      }
      if (filtroIgreja === "sem" && pessoa.igreja_id !== null) return false;
      if (
        filtroIgreja !== "todas" &&
        filtroIgreja !== "sem" &&
        String(pessoa.igreja_id) !== filtroIgreja
      ) {
        return false;
      }
      return true;
    });
  }, [pessoas, busca, filtroGrupo, filtroSituacao, filtroIgreja]);

  return (
    <div className="space-y-6">
      <PageHeader
        sobretitulo="Listas"
        titulo="Membros"
        descricao="Consulte a ficha de cada vida: contatos, visitação, histórico de presença e motivos de oração."
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
            <UsersRound className="size-4" />
            Vidas cadastradas
          </CardTitle>
          <CardDescription>
            {carregando
              ? "Carregando..."
              : `${filtradas.length} de ${pessoas?.length ?? 0} pessoa(s) na fonte ${fonte.toUpperCase()}.`}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-end gap-2">
            {fontesDisponiveis.length > 1 ? (
              <div className="flex gap-2">
                {fontesDisponiveis.map((item) => (
                  <Button
                    key={item.valor}
                    variant={fonte === item.valor ? "default" : "outline"}
                    size="sm"
                    onClick={() => setFonte(item.valor)}
                  >
                    {item.rotulo}
                  </Button>
                ))}
              </div>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="busca-membros">Buscar</Label>
              <Input
                id="busca-membros"
                value={busca}
                placeholder="Nome"
                className="w-56"
                onChange={(e) => setBusca(e.target.value)}
              />
            </div>

            {grupos.length > 0 ? (
              <div className="space-y-1.5">
                <Label htmlFor="grupo-membros">Grupo</Label>
                <select
                  id="grupo-membros"
                  value={filtroGrupo}
                  onChange={(e) => setFiltroGrupo(e.target.value)}
                  className="h-9 max-w-56 rounded-lg border bg-background px-2 text-sm"
                >
                  <option value="todos">Todos</option>
                  {grupos.map((grupo) => (
                    <option key={grupo} value={grupo}>
                      {grupo}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            {fonte === "icm" && igrejas.length > 0 ? (
              <div className="space-y-1.5">
                <Label htmlFor="igreja-membros">Igreja</Label>
                <select
                  id="igreja-membros"
                  value={filtroIgreja}
                  onChange={(e) => setFiltroIgreja(e.target.value)}
                  className="h-9 max-w-56 rounded-lg border bg-background px-2 text-sm"
                >
                  <option value="todas">Todas</option>
                  <option value="sem">Sem igreja</option>
                  {igrejas.map((igreja) => (
                    <option key={igreja.id} value={String(igreja.id)}>
                      {igreja.nome}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            {situacoes.length > 0 ? (
              <div className="space-y-1.5">
                <Label htmlFor="situacao-membros">Situação</Label>
                <select
                  id="situacao-membros"
                  value={filtroSituacao}
                  onChange={(e) => setFiltroSituacao(e.target.value)}
                  className="h-9 max-w-44 rounded-lg border bg-background px-2 text-sm"
                >
                  <option value="todos">Todas</option>
                  {situacoes.map((situacao) => (
                    <option key={situacao} value={situacao}>
                      {situacao}
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

          {carregando && !pessoas ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : filtradas.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhuma pessoa com esses filtros.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nome</TableHead>
                    <TableHead>Aniversário</TableHead>
                    <TableHead>Grupo</TableHead>
                    <TableHead>Igreja</TableHead>
                    <TableHead>Situação</TableHead>
                    <TableHead>Categoria</TableHead>
                    <TableHead>Última visita</TableHead>
                    <TableHead className="text-right">Dias</TableHead>
                    <TableHead className="w-10 text-right">
                      <span className="sr-only">Ficha</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtradas.map((pessoa) => (
                    <TableRow key={`${pessoa.fonte}-${pessoa.id}`}>
                      <TableCell className="max-w-64 truncate font-medium">
                        <Link
                          href={`/membros/${pessoa.id}?fonte=${pessoa.fonte}`}
                          className="flex items-center gap-1.5 hover:text-brand hover:underline"
                        >
                          {pessoa.nome}
                          {pessoa.excluido ? (
                            <UserRoundX
                              className="size-3.5 shrink-0 text-muted-foreground"
                              aria-label="Não recebe SMS"
                            />
                          ) : null}
                          {!pessoa.ativo ? (
                            <Badge variant="outline" className="h-5">
                              ausente
                            </Badge>
                          ) : null}
                        </Link>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {pessoa.data || "—"}
                      </TableCell>
                      <TableCell className="max-w-56 truncate text-xs text-muted-foreground">
                        {pessoa.grupo || "—"}
                      </TableCell>
                      <TableCell className="max-w-52 truncate text-xs text-muted-foreground">
                        {pessoa.fonte === "icm"
                          ? pessoa.igreja_nome || "—"
                          : "—"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {pessoa.situacao || "—"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {pessoa.categoria || "—"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {pessoa.ultima_visita ?? "—"}
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">
                        {pessoa.dias_sem_visita ?? "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          aria-label={`Abrir ficha de ${pessoa.nome}`}
                          title="Abrir ficha"
                          render={
                            <Link
                              href={`/membros/${pessoa.id}?fonte=${pessoa.fonte}`}
                            />
                          }
                        >
                          <ScanEye />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          <p className="text-xs text-muted-foreground">
            Abra a ficha para ver o histórico de presença (culto e Escola
            Bíblica), as faltas, os eventos, os motivos de oração e as
            observações. Para aniversariantes e envio de SMS, use a tela{" "}
            <strong>Aniversariantes</strong>.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
