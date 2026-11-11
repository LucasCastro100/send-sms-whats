"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  RefreshCw,
  Upload,
  UserMinus,
  UserPlus,
  Users,
  X,
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
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
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
  type ConfirmacaoImportacao,
  type Fonte,
  type Igreja,
  type ImportacaoHistorico,
  type PreviewImportacao,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const FONTES: { valor: Fonte; rotulo: string; descricao: string }[] = [
  { valor: "icm", rotulo: "ICM", descricao: "Lista do data.pdf" },
  { valor: "zoom", rotulo: "Zoom", descricao: "Lista do Zoom" },
];

function Contador({
  rotulo,
  valor,
  tom,
}: {
  rotulo: string;
  valor: number;
  tom: "novo" | "alterado" | "igual" | "ausente" | "conflito";
}) {
  const cores: Record<string, string> = {
    novo: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    alterado: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    igual: "bg-muted text-muted-foreground",
    ausente: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
    conflito: "bg-destructive/10 text-destructive",
  };

  return (
    <div className={cn("rounded-xl px-3 py-2", cores[tom])}>
      <p className="text-xl font-semibold tabular-nums">{valor}</p>
      <p className="text-xs font-medium">{rotulo}</p>
    </div>
  );
}

export default function ImportarPage() {
  const { usuario } = useAuth();
  const [fonte, setFonte] = useState<Fonte>("icm");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewImportacao | null>(null);
  const [resultado, setResultado] = useState<ConfirmacaoImportacao | null>(null);
  const [analisando, setAnalisando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [historico, setHistorico] = useState<ImportacaoHistorico[] | null>(null);
  const [igrejas, setIgrejas] = useState<Igreja[]>([]);
  const [igrejaId, setIgrejaId] = useState("");

  const carregarHistorico = useCallback(async () => {
    try {
      const dados = await api.get<{ total: number; importacoes: ImportacaoHistorico[] }>(
        "/api/importar/historico?limite=10",
      );
      setHistorico(dados.importacoes);
    } catch {
      setHistorico([]);
    }
  }, []);

  useEffect(() => {
    if (usuario?.admin) void carregarHistorico();
  }, [carregarHistorico, usuario?.admin]);

  useEffect(() => {
    if (!usuario?.admin) return;
    api
      .get<Igreja[]>("/api/igrejas")
      .then(setIgrejas)
      .catch(() => setIgrejas([]));
  }, [usuario?.admin]);

  function escolher(novo: File | null) {
    setArquivo(novo);
    setPreview(null);
    setResultado(null);
  }

  async function analisar() {
    if (!arquivo) {
      toast.error("Escolha um arquivo PDF, XLSX ou CSV.");
      return;
    }

    setAnalisando(true);
    setResultado(null);

    try {
      const form = new FormData();
      form.append("arquivo", arquivo);
      form.append("fonte", fonte);
      if (fonte === "icm" && igrejaId) {
        form.append("igreja_id", igrejaId);
      }
      const dados = await api.postForm<PreviewImportacao>(
        "/api/importar/preview",
        form,
      );
      setPreview(dados);
      toast.success(
        `${dados.total_linhas} linha(s) lidas: ${dados.resumo.novos} nova(s), ` +
          `${dados.resumo.alterados} alterada(s).`,
      );
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Não foi possível ler o arquivo.");
    } finally {
      setAnalisando(false);
    }
  }

  async function confirmar() {
    if (!preview) return;

    setConfirmando(true);
    try {
      const dados = await api.post<ConfirmacaoImportacao>(
        `/api/importar/${preview.upload_id}/confirmar`,
      );
      setResultado(dados);
      setPreview(null);
      setArquivo(null);
      toast.success("Importação aplicada no banco.");
      await carregarHistorico();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Falha ao confirmar.");
    } finally {
      setConfirmando(false);
    }
  }

  if (!usuario?.admin) {
    return (
      <div className="space-y-6">
        <PageHeader
          sobretitulo="Dados"
          titulo="Importar planilhas"
          descricao="Envie o PDF do ICM ou uma planilha. O sistema compara com o banco e mostra o que vai mudar antes de gravar."
        />
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            Apenas administradores podem importar planilhas.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        sobretitulo="Dados"
        titulo="Importar planilhas"
        descricao="Envie o PDF do ICM ou uma planilha. O sistema compara com o banco e mostra o que vai mudar antes de gravar."
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileSpreadsheet className="size-4" />
            Novo arquivo
          </CardTitle>
          <CardDescription>
            PDF, XLSX, XLS, ODS ou CSV. Nada é gravado até você confirmar.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {FONTES.map((item) => (
              <Button
                key={item.valor}
                variant={fonte === item.valor ? "default" : "outline"}
                onClick={() => {
                  setFonte(item.valor);
                  setPreview(null);
                  setResultado(null);
                }}
              >
                {item.rotulo}
                <span className="text-xs opacity-70">{item.descricao}</span>
              </Button>
            ))}
          </div>

          {fonte === "icm" && igrejas.length > 0 ? (
            <div className="space-y-1.5">
              <Label htmlFor="igreja-importar">Igreja das vidas do arquivo</Label>
              <select
                id="igreja-importar"
                value={igrejaId}
                onChange={(e) => setIgrejaId(e.target.value)}
                className="h-9 max-w-96 rounded-lg border bg-background px-2 text-sm"
              >
                <option value="">Não vincular agora</option>
                {igrejas.map((igreja) => (
                  <option key={igreja.id} value={String(igreja.id)}>
                    {igreja.nome} ({igreja.total} vida(s))
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">
                As vidas novas do arquivo ficam vinculadas a esta igreja; vidas que
                já têm igreja não são alteradas.
              </p>
            </div>
          ) : null}

          <label
            htmlFor="arquivo"
            className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center transition-colors hover:bg-muted/40"
          >
            <Upload className="size-5 text-muted-foreground" />
            <span className="text-sm font-medium">
              {arquivo ? arquivo.name : "Clique para escolher o arquivo"}
            </span>
            <span className="text-xs text-muted-foreground">
              {arquivo
                ? `${(arquivo.size / 1024).toFixed(0)} KB`
                : "PDF do ICM, planilha do Zoom ou XLS"}
            </span>
            <input
              id="arquivo"
              type="file"
              accept=".pdf,.csv,.tsv,.txt,.xlsx,.xls,.ods"
              className="sr-only"
              onChange={(e) => escolher(e.target.files?.[0] ?? null)}
            />
          </label>

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void analisar()} disabled={analisando || !arquivo}>
              {analisando ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              {analisando ? "Analisando..." : "Analisar arquivo"}
            </Button>

            {arquivo ? (
              <Button variant="ghost" onClick={() => escolher(null)}>
                <X />
                Limpar
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {resultado ? (
        <Card className="border-emerald-500/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="size-4" />
              Importação concluída
            </CardTitle>
            <CardDescription>
              {resultado.arquivo} · fonte {resultado.fonte.toUpperCase()}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Contador rotulo="Novos" valor={resultado.novos} tom="novo" />
              <Contador rotulo="Alterados" valor={resultado.alterados} tom="alterado" />
              <Contador rotulo="Iguais" valor={resultado.iguais} tom="igual" />
              <Contador rotulo="Ausentes" valor={resultado.ausentes} tom="ausente" />
            </div>
          </CardContent>
        </Card>
      ) : null}

      {preview ? (
        <Card>
          <CardHeader>
            <CardTitle>Resultado da análise</CardTitle>
            <CardDescription>
              {preview.arquivo} · {preview.total_linhas} linha(s) · fonte{" "}
              {preview.fonte.toUpperCase()}
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-5">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <Contador rotulo="Novos" valor={preview.resumo.novos} tom="novo" />
              <Contador rotulo="Alterados" valor={preview.resumo.alterados} tom="alterado" />
              <Contador rotulo="Iguais" valor={preview.resumo.iguais} tom="igual" />
              <Contador rotulo="Ausentes" valor={preview.resumo.ausentes} tom="ausente" />
              <Contador rotulo="Conflitos" valor={preview.resumo.conflitos} tom="conflito" />
            </div>

            {preview.avisos.length > 0 ? (
              <div className="space-y-1 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-400">
                {preview.avisos.map((aviso) => (
                  <p key={aviso} className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                    {aviso}
                  </p>
                ))}
              </div>
            ) : null}

            <p className="text-xs text-muted-foreground">
              Colunas usadas:{" "}
              {Object.entries(preview.mapeamento)
                .map(([campo, coluna]) => `${campo} = “${coluna}”`)
                .join(" · ") || "formato fixo do PDF"}
            </p>

            {preview.novos.length > 0 ? (
              <div className="space-y-2">
                <p className="flex items-center gap-1.5 text-sm font-medium">
                  <UserPlus className="size-4 text-emerald-600 dark:text-emerald-400" />
                  Novos ({preview.novos.length})
                </p>
                <div className="max-h-56 overflow-y-auto rounded-lg border">
                  {preview.novos.map((pessoa) => (
                    <div
                      key={`${pessoa.nome}-${pessoa.data}`}
                      className="flex items-center justify-between gap-3 border-b px-3 py-2 text-sm last:border-b-0"
                    >
                      <span className="truncate">{pessoa.nome}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {pessoa.data}
                        {pessoa.grupo ? ` · ${pessoa.grupo}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {preview.alterados.length > 0 ? (
              <div className="space-y-2">
                <p className="flex items-center gap-1.5 text-sm font-medium">
                  <RefreshCw className="size-4 text-amber-600 dark:text-amber-400" />
                  Alterados ({preview.alterados.length})
                </p>
                <div className="max-h-56 overflow-y-auto rounded-lg border">
                  {preview.alterados.map((pessoa) => (
                    <div
                      key={pessoa.id}
                      className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2 text-sm last:border-b-0"
                    >
                      <span className="truncate font-medium">{pessoa.nome}</span>
                      <span className="text-xs text-muted-foreground">
                        {pessoa.mudancas
                          .map((mudanca) => `${mudanca.campo}: ${mudanca.de} → ${mudanca.para}`)
                          .join(" · ")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {preview.ausentes.length > 0 ? (
              <div className="space-y-2">
                <p className="flex items-center gap-1.5 text-sm font-medium">
                  <UserMinus className="size-4 text-sky-600 dark:text-sky-400" />
                  Ausentes no arquivo ({preview.ausentes.length})
                </p>
                <p className="text-xs text-muted-foreground">
                  Continuam ativos no banco — nada é apagado.
                </p>
                <div className="max-h-40 overflow-y-auto rounded-lg border">
                  {preview.ausentes.map((pessoa) => (
                    <div
                      key={pessoa.id}
                      className="flex items-center justify-between gap-3 border-b px-3 py-1.5 text-sm last:border-b-0"
                    >
                      <span className="truncate">{pessoa.nome}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {pessoa.data}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {preview.conflitos.length > 0 ? (
              <div className="space-y-2">
                <p className="flex items-center gap-1.5 text-sm font-medium">
                  <AlertTriangle className="size-4 text-destructive" />
                  Conflitos ({preview.conflitos.length})
                </p>
                <div className="max-h-40 overflow-y-auto rounded-lg border">
                  {preview.conflitos.map((conflito, indice) => (
                    <div
                      key={`${conflito.nome}-${indice}`}
                      className="flex items-center justify-between gap-3 border-b px-3 py-1.5 text-sm last:border-b-0"
                    >
                      <span className="truncate">{conflito.nome || "(sem nome)"}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {conflito.motivo}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <Separator />

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void confirmar()} disabled={confirmando}>
                {confirmando ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}
                {confirmando ? "Aplicando..." : "Confirmar importação"}
              </Button>
              <Button variant="outline" onClick={() => setPreview(null)}>
                Descartar
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="size-4" />
            Últimas importações
          </CardTitle>
          <CardDescription>Histórico do que já foi aplicado no banco.</CardDescription>
        </CardHeader>
        <CardContent>
          {historico === null ? (
            <div className="space-y-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : historico.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhuma importação registrada ainda.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Arquivo</TableHead>
                  <TableHead>Fonte</TableHead>
                  <TableHead>Quando</TableHead>
                  <TableHead className="text-right">Resultado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {historico.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="max-w-52 truncate">{item.arquivo}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{item.fonte.toUpperCase()}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {item.criado_em}
                      {item.usuario ? ` · ${item.usuario}` : ""}
                    </TableCell>
                    <TableCell className="text-right text-xs text-muted-foreground">
                      +{item.inseridos} · ~{item.atualizados} · ={item.iguais}
                      {item.ausentes ? ` · ${item.ausentes} ausentes` : ""}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
