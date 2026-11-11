"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Cake,
  Check,
  Copy,
  Loader2,
  MessageCircle,
  RefreshCw,
  ScanEye,
  Send,
  UserRoundX,
  UsersRound,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { PessoaDrawer } from "@/components/pessoa-drawer";
import { useAuth } from "@/components/auth-provider";
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
  type AniversariantesDia,
  type Fonte,
  type Igreja,
  type Pessoa,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const FONTES: { valor: Fonte; rotulo: string }[] = [
  { valor: "icm", rotulo: "ICM" },
  { valor: "zoom", rotulo: "Zoom" },
];

const MESES = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

function hojeComoData(): string {
  const agora = new Date();
  const mes = String(agora.getMonth() + 1).padStart(2, "0");
  const dia = String(agora.getDate()).padStart(2, "0");
  return `${agora.getFullYear()}-${mes}-${dia}`;
}

function partes(data: string): { dia: number; mes: number } {
  const [, mes, dia] = data.split("-");
  return { dia: Number(dia), mes: Number(mes) };
}

export default function AniversariantesPage() {
  const { usuario } = useAuth();
  const [fonte, setFonte] = useState<Fonte>("icm");
  const [data, setData] = useState(hojeComoData());
  const [dados, setDados] = useState<AniversariantesDia | null>(null);
  const [pessoas, setPessoas] = useState<Pessoa[] | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [busca, setBusca] = useState("");
  const [filtroMes, setFiltroMes] = useState(String(new Date().getMonth() + 1));
  const [filtroGrupo, setFiltroGrupo] = useState("todos");
  const [filtroIgreja, setFiltroIgreja] = useState("todas");
  const [igrejas, setIgrejas] = useState<Igreja[]>([]);
  const [selecionada, setSelecionada] = useState<Pessoa | null>(null);

  // A lista do Zoom é restrita ao administrador.
  const fontesDisponiveis = useMemo(
    () => FONTES.filter((item) => item.valor === "icm" || usuario?.admin),
    [usuario?.admin],
  );

  useEffect(() => {
    if (!usuario?.admin && fonte === "zoom") setFonte("icm");
  }, [usuario?.admin, fonte]);

  const carregar = useCallback(
    async (silencioso = false) => {
      if (!silencioso) setCarregando(true);
      const { dia, mes } = partes(data);

      try {
        const [doDia, lista] = await Promise.all([
          api.get<AniversariantesDia>(
            `/api/aniversariantes/dia?fonte=${fonte}&dia=${dia}&mes=${mes}`,
          ),
          api.get<Pessoa[]>(`/api/pessoas?fonte=${fonte}`),
        ]);
        setDados(doDia);
        setPessoas(lista);
      } catch (e) {
        toast.error(
          e instanceof ApiError ? e.message : "Falha ao carregar a lista.",
        );
      } finally {
        setCarregando(false);
      }
    },
    [data, fonte],
  );

  useEffect(() => {
    void carregar();
  }, [carregar]);

  // Igrejas para o filtro (e o drawer) — só a lista ICM tem o vínculo.
  useEffect(() => {
    api
      .get<Igreja[]>("/api/igrejas")
      .then(setIgrejas)
      .catch(() => setIgrejas([]));
  }, []);

  // Trocou a fonte: o filtro de igreja não se aplica ao Zoom.
  useEffect(() => {
    setFiltroIgreja("todas");
  }, [fonte]);

  async function atualizar(pessoa: Pessoa, mudancas: Record<string, unknown>) {
    try {
      await api.patch<Pessoa>(`/api/pessoas/${pessoa.id}`, {
        ...mudancas,
        fonte: pessoa.fonte,
      });
      await carregar(true);
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível salvar a mudança.",
      );
    }
  }

  function pessoaAtualizada(atualizada: Pessoa) {
    setPessoas((lista) =>
      lista
        ? lista.map((pessoa) =>
            pessoa.id === atualizada.id && pessoa.fonte === atualizada.fonte
              ? atualizada
              : pessoa,
          )
        : lista,
    );
    setSelecionada((atual) =>
      atual && atual.id === atualizada.id && atual.fonte === atualizada.fonte
        ? atualizada
        : atual,
    );
  }

  async function copiar() {
    if (!dados?.mensagem) return;
    try {
      await navigator.clipboard.writeText(dados.mensagem);
      toast.success("Mensagem copiada.");
    } catch {
      toast.error("O navegador bloqueou a cópia. Selecione o texto manualmente.");
    }
  }

  function abrirWhatsApp() {
    if (!dados?.mensagem) return;
    window.open(
      `https://web.whatsapp.com/send?text=${encodeURIComponent(dados.mensagem)}`,
      "_blank",
      "noopener",
    );
  }

  async function disparar() {
    const { dia, mes } = partes(data);
    setEnviando(true);
    try {
      const resposta = await api.post<{ grupo: string; citados: number }>(
        "/api/aniversariantes/enviar",
        { fonte, dia, mes },
      );
      toast.success(
        `Mensagem enviada para ${resposta.grupo} (${resposta.citados} pessoa(s)).`,
      );
      setConfirmando(false);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Falha ao enviar.");
    } finally {
      setEnviando(false);
    }
  }

  const grupos = useMemo(() => {
    const valores = new Set(
      (pessoas ?? []).map((pessoa) => pessoa.grupo).filter(Boolean),
    );
    return Array.from(valores).sort((a, b) => a.localeCompare(b, "pt-BR"));
  }, [pessoas]);

  const filtradas = useMemo(() => {
    const termo = busca.trim().toUpperCase();
    return (pessoas ?? []).filter((pessoa) => {
      // A tela de aniversariantes só lista quem faz aniversário; a ficha
      // completa de cada vida fica na tela Membros.
      if (!pessoa.dia || !pessoa.mes) return false;
      if (termo && !pessoa.nome.toUpperCase().includes(termo)) return false;
      if (filtroMes !== "todos" && pessoa.mes !== Number(filtroMes)) return false;
      if (filtroGrupo !== "todos" && pessoa.grupo !== filtroGrupo) return false;
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
  }, [pessoas, busca, filtroMes, filtroGrupo, filtroIgreja]);

  const temAniversariante = (dados?.pessoas.length ?? 0) > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        sobretitulo="Listas"
        titulo="Aniversariantes"
        descricao="Confira quem faz aniversário, ajuste quem não deve ser citado e dispare a mensagem para o grupo."
      >
        {usuario && !usuario.admin ? (
          <Badge variant="outline" className="border-brand/30 bg-brand-soft text-brand">
            {usuario.funcao === "frente"
              ? "Grupo de Senhoras"
              : usuario.grupo_nome || "Sem grupo"}
          </Badge>
        ) : null}
      </PageHeader>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 pt-6">
          <div className="flex gap-2">
            {fontesDisponiveis.map((item) => (
              <Button
                key={item.valor}
                variant={fonte === item.valor ? "default" : "outline"}
                onClick={() => setFonte(item.valor)}
              >
                {item.rotulo}
              </Button>
            ))}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="data">Data</Label>
            <Input
              id="data"
              type="date"
              value={data}
              className="w-44"
              onChange={(e) => setData(e.target.value || hojeComoData())}
            />
          </div>

          <Button variant="outline" onClick={() => void carregar()}>
            <RefreshCw className={cn(carregando && "animate-spin")} />
            Atualizar
          </Button>

          <div className="ml-auto text-right text-sm text-muted-foreground">
            <p>
              Destino:{" "}
              <span className="font-medium text-foreground">
                {dados?.destino.nome || "—"}
              </span>
            </p>
            <p className="text-xs">{dados?.destino.jid || "JID não configurado"}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cake className="size-4" />
            {carregando && !dados
              ? "Carregando..."
              : `Aniversariantes de ${dados?.data ?? "—"}`}
          </CardTitle>
          <CardDescription>
            {temAniversariante
              ? `${dados?.citados} para citar` +
                (dados?.nao_citados
                  ? ` · ${dados.nao_citados} marcado(s) sem SMS`
                  : "")
              : "Ninguém faz aniversário nesta data."}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {carregando && !dados ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : !temAniversariante ? (
            <p className="text-sm text-muted-foreground">
              Escolha outra data ou importe a planilha atualizada.
            </p>
          ) : (
            <>
              <div className="divide-y rounded-lg border">
                {dados?.pessoas.map((pessoa) => (
                  <div
                    key={pessoa.id}
                    className="flex flex-wrap items-center justify-between gap-3 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p
                        className={cn(
                          "truncate text-sm font-medium",
                          pessoa.excluido && "text-muted-foreground line-through",
                        )}
                      >
                        {pessoa.nome}
                      </p>
                      {pessoa.grupo ? (
                        <p className="truncate text-xs text-muted-foreground">
                          {pessoa.grupo}
                        </p>
                      ) : null}
                    </div>

                    <div className="flex items-center gap-2">
                      <select
                        aria-label={`Gênero de ${pessoa.nome}`}
                        value={pessoa.genero ?? ""}
                        onChange={(e) =>
                          void atualizar(pessoa, {
                            genero: e.target.value,
                          })
                        }
                        className="h-8 rounded-lg border bg-background px-2 text-xs"
                      >
                        <option value="">gênero?</option>
                        <option value="F">Irmã</option>
                        <option value="M">Irmão</option>
                      </select>

                      <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border px-2 py-1 text-xs">
                        <input
                          type="checkbox"
                          className="size-3.5 accent-primary"
                          checked={pessoa.excluido}
                          onChange={(e) =>
                            void atualizar(pessoa, {
                              excluido: e.target.checked,
                            })
                          }
                        />
                        Não enviar SMS
                      </label>
                    </div>
                  </div>
                ))}
              </div>

              {dados?.mensagem ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">Mensagem</p>
                    <Button variant="ghost" size="sm" onClick={() => void copiar()}>
                      <Copy />
                      Copiar
                    </Button>
                  </div>
                  <pre className="max-h-72 overflow-auto rounded-lg border bg-muted/40 p-3 text-sm whitespace-pre-wrap">
                    {dados.mensagem}
                  </pre>
                </div>
              ) : (
                <p className="rounded-lg bg-sky-500/10 px-3 py-2 text-sm text-sky-700 dark:text-sky-400">
                  Todos os aniversariantes desta data estão marcados para não
                  citar.
                </p>
              )}

              <Separator />

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  onClick={abrirWhatsApp}
                  disabled={!dados?.mensagem}
                >
                  <MessageCircle />
                  Abrir no WhatsApp Web
                </Button>

                {confirmando ? (
                  <>
                    <Button onClick={() => void disparar()} disabled={enviando}>
                      {enviando ? <Loader2 className="animate-spin" /> : <Send />}
                      {enviando ? "Enviando..." : "Confirmar envio"}
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => setConfirmando(false)}
                      disabled={enviando}
                    >
                      Cancelar
                    </Button>
                  </>
                ) : (
                  <Button
                    onClick={() => setConfirmando(true)}
                    disabled={!dados?.mensagem}
                  >
                    <Send />
                    Disparar para {dados?.destino.nome || "o grupo"}
                  </Button>
                )}

                {dados?.nao_citados ? (
                  <Badge variant="outline" className="gap-1">
                    <UserRoundX className="size-3" />
                    {dados.nao_citados} sem SMS
                  </Badge>
                ) : null}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1.5">
              <CardTitle>Aniversariantes do mês</CardTitle>
              <CardDescription>
                {filtradas.length} pessoa(s) na fonte {fonte.toUpperCase()}. A
                ficha completa de cada vida fica em Membros.
              </CardDescription>
            </div>
            <Link href="/membros">
              <Button variant="outline" size="sm">
                <UsersRound />
                Ver todos os membros
              </Button>
            </Link>
          </div>
        </CardHeader>

        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1.5">
              <Label htmlFor="busca">Buscar</Label>
              <Input
                id="busca"
                value={busca}
                placeholder="Nome"
                className="w-48"
                onChange={(e) => setBusca(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="mes">Mês</Label>
              <select
                id="mes"
                value={filtroMes}
                onChange={(e) => setFiltroMes(e.target.value)}
                className="h-9 rounded-lg border bg-background px-2 text-sm"
              >
                <option value="todos">Todos</option>
                {MESES.map((nome, indice) => (
                  <option key={nome} value={indice + 1}>
                    {nome}
                  </option>
                ))}
              </select>
            </div>

            {grupos.length > 0 ? (
              <div className="space-y-1.5">
                <Label htmlFor="grupo">Grupo</Label>
                <select
                  id="grupo"
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
                <Label htmlFor="igreja">Igreja</Label>
                <select
                  id="igreja"
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
          </div>

          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nome</TableHead>
                  <TableHead>Data</TableHead>
                  <TableHead>Grupo</TableHead>
                  <TableHead>Igreja</TableHead>
                  <TableHead>Gênero</TableHead>
                  <TableHead className="text-right">Não enviar SMS</TableHead>
                  <TableHead className="w-10 text-right">
                    <span className="sr-only">Análise</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtradas.map((pessoa) => (
                  <TableRow key={`${pessoa.fonte}-${pessoa.id}`}>
                    <TableCell className="max-w-64 truncate font-medium">
                      {pessoa.nome}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {pessoa.data}
                    </TableCell>
                    <TableCell className="max-w-56 truncate text-xs text-muted-foreground">
                      {pessoa.grupo || "—"}
                    </TableCell>
                    <TableCell className="max-w-52 truncate text-xs text-muted-foreground">
                      {pessoa.igreja_nome || "—"}
                    </TableCell>
                    <TableCell>
                      <select
                        aria-label={`Gênero de ${pessoa.nome}`}
                        value={pessoa.genero ?? ""}
                        onChange={(e) =>
                          void atualizar(pessoa, {
                            genero: e.target.value,
                          })
                        }
                        className="h-7 rounded-md border bg-background px-1.5 text-xs"
                      >
                        <option value="">—</option>
                        <option value="F">F</option>
                        <option value="M">M</option>
                      </select>
                    </TableCell>
                    <TableCell className="text-right">
                      <input
                        type="checkbox"
                        aria-label={`Não enviar SMS para ${pessoa.nome}`}
                        className="size-4 accent-primary"
                        checked={pessoa.excluido}
                        onChange={(e) =>
                          void atualizar(pessoa, {
                            excluido: e.target.checked,
                          })
                        }
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        aria-label={`Abrir ficha de ${pessoa.nome}`}
                        title="Abrir ficha"
                        onClick={() => setSelecionada(pessoa)}
                      >
                        <ScanEye />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {filtradas.length === 0 && !carregando ? (
            <p className="text-sm text-muted-foreground">
              Nenhuma pessoa com esses filtros.
            </p>
          ) : null}
        </CardContent>
      </Card>

      {dados?.citados ? (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Check className="size-3.5" />
          As marcações de gênero e “não enviar SMS” valem para o disparo manual e
          para o envio automático.
        </p>
      ) : null}

      <PessoaDrawer
        pessoa={selecionada}
        igrejas={igrejas}
        onFechar={() => setSelecionada(null)}
        onAtualizada={pessoaAtualizada}
      />
    </div>
  );
}
