"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CalendarDays,
  ChartColumn,
  Download,
  Loader2,
  RefreshCw,
  UsersRound,
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
  type Igreja,
  type RelatorioPresenca,
  type TipoPresenca,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type FiltroTipo = TipoPresenca | "todos";

const TIPOS: { valor: FiltroTipo; rotulo: string }[] = [
  { valor: "todos", rotulo: "Culto e Escola Bíblica" },
  { valor: "culto", rotulo: "Culto" },
  { valor: "escola_biblica", rotulo: "Escola Bíblica" },
];

function doisDigitos(numero: number): string {
  return String(numero).padStart(2, "0");
}

function hojeLocal(): string {
  const data = new Date();
  return `${data.getFullYear()}-${doisDigitos(data.getMonth() + 1)}-${doisDigitos(data.getDate())}`;
}

function diasAtras(dias: number): string {
  const data = new Date();
  data.setDate(data.getDate() - dias);
  return `${data.getFullYear()}-${doisDigitos(data.getMonth() + 1)}-${doisDigitos(data.getDate())}`;
}

function campoCsv(valor: string | number): string {
  const texto = String(valor ?? "");
  return `"${texto.replace(/"/g, '""')}"`;
}

function baixarCsv(nomeArquivo: string, linhas: (string | number)[][]) {
  const conteudo = linhas.map((linha) => linha.map(campoCsv).join(";")).join("\r\n");
  // O BOM faz o Excel abrir o arquivo com os acentos corretos.
  const blob = new Blob([`\ufeff${conteudo}`], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function mensagemErro(erro: unknown, padrao: string): string {
  return erro instanceof ApiError ? erro.message : padrao;
}

export default function RelatoriosPage() {
  const { usuario } = useAuth();
  const [de, setDe] = useState(diasAtras(30));
  const [ate, setAte] = useState(hojeLocal());
  const [tipo, setTipo] = useState<FiltroTipo>("todos");
  const [grupo, setGrupo] = useState("");
  const [igrejaId, setIgrejaId] = useState("");
  const [igrejas, setIgrejas] = useState<Igreja[]>([]);
  const [dados, setDados] = useState<RelatorioPresenca | null>(null);
  const [grupos, setGrupos] = useState<string[]>([]);
  const [carregando, setCarregando] = useState(true);

  const carregar = useCallback(async () => {
    setCarregando(true);
    try {
      const parametros = new URLSearchParams({
        de,
        ate,
        tipo,
      });
      if (grupo) parametros.set("grupo", grupo);
      if (igrejaId) parametros.set("igreja_id", igrejaId);

      setDados(
        await api.get<RelatorioPresenca>(
          `/api/presenca/relatorio?${parametros.toString()}`,
        ),
      );
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao carregar o relatório."));
    } finally {
      setCarregando(false);
    }
  }, [de, ate, tipo, grupo, igrejaId]);

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

  function exportar() {
    if (!dados) return;

    const linhas: (string | number)[][] = [
      ["Relatório de presença"],
      ["Período", `${dados.de} a ${dados.ate}`],
      ["Tipo", dados.tipo_rotulo],
      ["Lançamentos", dados.resumo.lancamentos],
      ["Presenças", dados.resumo.presentes],
      ["Faltas", dados.resumo.faltas],
      ["Percentual geral", `${dados.resumo.percentual}%`],
      [],
      ["Lançamentos"],
      ["Data", "Tipo", "Total", "Presentes", "Faltas", "Percentual"],
      ...dados.lancamentos.map((item) => [
        item.data,
        item.tipo_rotulo,
        item.total,
        item.presentes,
        item.faltantes,
        `${item.percentual}%`,
      ]),
      [],
      ["Por vida"],
      ["Nome", "Grupo", "Igreja", "Presenças", "Faltas", "Total", "Percentual"],
      ...dados.pessoas.map((pessoa) => [
        pessoa.nome,
        pessoa.grupo,
        pessoa.igreja_nome,
        pessoa.presencas,
        pessoa.faltas,
        pessoa.total,
        `${pessoa.percentual}%`,
      ]),
    ];

    baixarCsv(`relatorio-presenca-${dados.de}-a-${dados.ate}.csv`, linhas);
    toast.success("Relatório exportado em CSV.");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        sobretitulo="Acompanhamento"
        titulo="Relatórios"
        descricao="Presença dos cultos e da Escola Bíblica por período, grupo e igreja. Exporte em CSV para compartilhar."
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
        <CardContent className="flex flex-wrap items-end gap-3 pt-6">
          <div className="space-y-1.5">
            <Label htmlFor="de" className="flex items-center gap-1.5">
              <CalendarDays className="size-3.5" />
              De
            </Label>
            <Input
              id="de"
              type="date"
              value={de}
              className="w-44"
              onChange={(e) => setDe(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ate">Até</Label>
            <Input
              id="ate"
              type="date"
              value={ate}
              className="w-44"
              onChange={(e) => setAte(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tipo-relatorio">Tipo</Label>
            <select
              id="tipo-relatorio"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as FiltroTipo)}
              className="h-9 w-52 rounded-lg border bg-background px-2 text-sm"
            >
              {TIPOS.map((item) => (
                <option key={item.valor} value={item.valor}>
                  {item.rotulo}
                </option>
              ))}
            </select>
          </div>

          {grupos.length > 0 ? (
            <div className="space-y-1.5">
              <Label htmlFor="grupo-relatorio">Grupo</Label>
              <select
                id="grupo-relatorio"
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
              <Label htmlFor="igreja-relatorio">Igreja</Label>
              <select
                id="igreja-relatorio"
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

          <Button onClick={exportar} disabled={!dados || carregando}>
            <Download />
            Exportar CSV
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Lançamentos</CardDescription>
            <CardTitle className="text-2xl">
              {dados?.resumo.lancamentos ?? "—"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Presenças</CardDescription>
            <CardTitle className="text-2xl text-emerald-600 dark:text-emerald-400">
              {dados?.resumo.presentes ?? "—"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Faltas</CardDescription>
            <CardTitle className="text-2xl text-destructive">
              {dados?.resumo.faltas ?? "—"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Percentual geral</CardDescription>
            <CardTitle className="text-2xl">
              {dados ? `${dados.resumo.percentual}%` : "—"}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {carregando && !dados ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ChartColumn className="size-4" />
                Lançamentos ({dados?.lancamentos.length ?? 0})
              </CardTitle>
              <CardDescription>
                {dados
                  ? `${dados.tipo_rotulo} · ${dados.de} a ${dados.ate}`
                  : "Carregando..."}
              </CardDescription>
            </CardHeader>

            <CardContent>
              <div className="max-h-96 overflow-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Data</TableHead>
                      <TableHead>Tipo</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                      <TableHead className="text-right">Presentes</TableHead>
                      <TableHead className="text-right">Faltas</TableHead>
                      <TableHead className="text-right">Percentual</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {!dados || dados.lancamentos.length === 0 ? (
                      <TableRow>
                        <TableCell
                          colSpan={6}
                          className="text-sm text-muted-foreground"
                        >
                          Nenhum lançamento no período.
                        </TableCell>
                      </TableRow>
                    ) : (
                      dados.lancamentos.map((item) => (
                        <TableRow key={`${item.dia}-${item.tipo}`}>
                          <TableCell className="font-medium">
                            {item.data}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                item.tipo === "escola_biblica"
                                  ? "secondary"
                                  : "outline"
                              }
                            >
                              {item.tipo_rotulo}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right text-xs">
                            {item.total}
                          </TableCell>
                          <TableCell className="text-right text-xs text-emerald-600 dark:text-emerald-400">
                            {item.presentes}
                          </TableCell>
                          <TableCell className="text-right text-xs text-destructive">
                            {item.faltantes}
                          </TableCell>
                          <TableCell className="text-right text-xs">
                            {item.percentual}%
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UsersRound className="size-4" />
                Por vida ({dados?.pessoas.length ?? 0})
              </CardTitle>
              <CardDescription>
                Presenças e faltas considerando os lançamentos do período.
              </CardDescription>
            </CardHeader>

            <CardContent>
              <div className="max-h-[32rem] overflow-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Nome</TableHead>
                      <TableHead>Grupo</TableHead>
                      <TableHead>Igreja</TableHead>
                      <TableHead className="text-right">Presenças</TableHead>
                      <TableHead className="text-right">Faltas</TableHead>
                      <TableHead className="text-right">Percentual</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {!dados || dados.pessoas.length === 0 ? (
                      <TableRow>
                        <TableCell
                          colSpan={6}
                          className="text-sm text-muted-foreground"
                        >
                          Nenhuma vida com esses filtros.
                        </TableCell>
                      </TableRow>
                    ) : (
                      dados.pessoas.map((pessoa) => (
                        <TableRow key={pessoa.nome_chave}>
                          <TableCell className="max-w-64 truncate font-medium">
                            {pessoa.nome}
                          </TableCell>
                          <TableCell className="max-w-56 truncate text-xs text-muted-foreground">
                            {pessoa.grupo || "—"}
                          </TableCell>
                          <TableCell className="max-w-52 truncate text-xs text-muted-foreground">
                            {pessoa.igreja_nome || "—"}
                          </TableCell>
                          <TableCell className="text-right text-xs text-emerald-600 dark:text-emerald-400">
                            {pessoa.presencas}
                          </TableCell>
                          <TableCell className="text-right text-xs text-destructive">
                            {pessoa.faltas}
                          </TableCell>
                          <TableCell className="text-right text-xs">
                            {pessoa.percentual}%
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>

              <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
                <Loader2 className={cn("size-3.5", !carregando && "hidden")} />
                {carregando
                  ? "Carregando o relatório..."
                  : "O CSV inclui o resumo, os lançamentos e a lista por vida."}
              </p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
