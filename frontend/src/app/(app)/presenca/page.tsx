"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  CalendarDays,
  Check,
  ClipboardCheck,
  Link2,
  Loader2,
  MessageSquare,
  Phone,
  RefreshCw,
  Save,
  Send,
  Trash2,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
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
  type Contato,
  type ContatosResposta,
  type PresencaEnvio,
  type PresencaEstado,
  type PresencaMensagens,
  type PresencaNumeros,
  type TipoPresenca,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type Aba = "faltas" | "numeros" | "mensagens";

const ABAS: { valor: Aba; rotulo: string; icone: typeof ClipboardCheck }[] = [
  { valor: "faltas", rotulo: "Registrar presença", icone: ClipboardCheck },
  { valor: "numeros", rotulo: "Números", icone: Phone },
  { valor: "mensagens", rotulo: "Mensagens", icone: MessageSquare },
];

const TIPOS: { valor: TipoPresenca; rotulo: string; icone: typeof BookOpen }[] = [
  { valor: "culto", rotulo: "Culto", icone: Users },
  { valor: "escola_biblica", rotulo: "Escola Bíblica", icone: BookOpen },
];

function doisDigitos(numero: number): string {
  return String(numero).padStart(2, "0");
}

function hojeLocal(): string {
  const data = new Date();
  return `${data.getFullYear()}-${doisDigitos(data.getMonth() + 1)}-${doisDigitos(data.getDate())}`;
}

function mensagemErro(erro: unknown, padrao: string): string {
  return erro instanceof ApiError ? erro.message : padrao;
}

function montarExemplo(
  modelo: string,
  exemplo: { responsavel: string; nomes: string[]; data: string },
  tipo: TipoPresenca,
  limite: number,
): string {
  return modelo
    .replace(/\{responsavel\}/g, exemplo.responsavel)
    .replace(/\{nomes\}/g, exemplo.nomes.join(", "))
    .replace(/\{data\}/g, exemplo.data)
    .replace(
      /\{tipo\}/g,
      tipo === "escola_biblica" ? "Escola Bíblica" : "Culto",
    )
    .replace(/\{total\}/g, String(exemplo.nomes.length))
    .replace(/\{limite\}/g, String(limite));
}

export default function PresencaPage() {
  const { usuario } = useAuth();
  const [aba, setAba] = useState<Aba>("faltas");
  const [dia, setDia] = useState(hojeLocal());
  const [tipo, setTipo] = useState<TipoPresenca>("culto");
  const [estado, setEstado] = useState<PresencaEstado | null>(null);
  const [carregando, setCarregando] = useState(true);

  const [marcados, setMarcados] = useState<Record<string, boolean>>({});
  const [busca, setBusca] = useState("");
  const [grupo, setGrupo] = useState("");
  const [salvando, setSalvando] = useState(false);

  const [confirmandoFalta, setConfirmandoFalta] = useState(false);
  const [confirmandoVisita, setConfirmandoVisita] = useState(false);
  const [enviando, setEnviando] = useState<"falta" | "visita" | null>(null);

  const [numeros, setNumeros] = useState<PresencaNumeros | null>(null);
  const [buscaNumero, setBuscaNumero] = useState("");
  const [pessoaSel, setPessoaSel] = useState("");
  const [contatoSel, setContatoSel] = useState("");
  const [numeroManual, setNumeroManual] = useState("");
  const [contatosWhats, setContatosWhats] = useState<Contato[]>([]);
  const [salvandoNumero, setSalvandoNumero] = useState(false);
  const [vinculando, setVinculando] = useState(false);
  const [sincronizando, setSincronizando] = useState(false);

  const [mensagens, setMensagens] = useState<PresencaMensagens | null>(null);
  const [textoFalta, setTextoFalta] = useState("");
  const [textoVisita, setTextoVisita] = useState("");
  const [salvandoMensagens, setSalvandoMensagens] = useState(false);

  const carregarEstado = useCallback(
    async (diaAtual: string, tipoAtual: TipoPresenca) => {
      setCarregando(true);
      try {
        const dados = await api.get<PresencaEstado>(
          `/api/presenca?dia=${encodeURIComponent(diaAtual)}&tipo=${tipoAtual}`,
        );
        setEstado(dados);
        setMarcados(
          Object.fromEntries(
            dados.pessoas.map((pessoa) => [
              pessoa.nome_chave,
              tipoAtual === "escola_biblica"
                ? pessoa.participou
                : pessoa.falta,
            ]),
          ),
        );
      } catch (e) {
        toast.error(mensagemErro(e, "Falha ao carregar a presença do dia."));
      } finally {
        setCarregando(false);
      }
    },
    [],
  );

  const carregarNumeros = useCallback(async () => {
    try {
      setNumeros(await api.get<PresencaNumeros>("/api/presenca/numeros"));
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao carregar os números."));
    }
  }, []);

  const carregarMensagens = useCallback(async () => {
    try {
      const dados = await api.get<PresencaMensagens>("/api/presenca/mensagens");
      setMensagens(dados);
      setTextoFalta((atual) => atual || dados.mensagens.falta);
      setTextoVisita((atual) => atual || dados.mensagens.visita);
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao carregar as mensagens."));
    }
  }, []);

  const carregarContatosWhats = useCallback(async () => {
    try {
      const dados = await api.get<ContatosResposta>("/api/whatsapp/contatos");
      setContatosWhats(dados.contatos);
      setSincronizando(dados.sincronizando);
    } catch {
      // O cache de contatos pode ainda não existir; a tela continua utilizável.
    }
  }, []);

  useEffect(() => {
    void carregarEstado(dia, tipo);
  }, [carregarEstado, dia, tipo]);

  useEffect(() => {
    void carregarNumeros();
    void carregarMensagens();
    void carregarContatosWhats();
  }, [carregarNumeros, carregarMensagens, carregarContatosWhats]);

  const filtradas = useMemo(() => {
    const termo = busca.trim().toUpperCase();
    return (estado?.pessoas ?? []).filter((pessoa) => {
      if (grupo && pessoa.grupo !== grupo) return false;
      if (termo && !pessoa.nome_chave.includes(termo)) return false;
      return true;
    });
  }, [estado, busca, grupo]);

  const marcadosVisiveis = useMemo(
    () => filtradas.filter((pessoa) => marcados[pessoa.nome_chave]).length,
    [filtradas, marcados],
  );

  const totalMarcados = useMemo(
    () => Object.values(marcados).filter(Boolean).length,
    [marcados],
  );

  const faltantes = useMemo(
    () => (estado?.pessoas ?? []).filter((pessoa) => pessoa.falta),
    [estado],
  );

  const participantes = useMemo(
    () => (estado?.pessoas ?? []).filter((pessoa) => pessoa.participou),
    [estado],
  );

  const visitasPendentes = useMemo(
    () => (estado?.pessoas ?? []).filter((pessoa) => pessoa.precisa_visita),
    [estado],
  );

  const numerosFiltrados = useMemo(() => {
    const termo = buscaNumero.trim().toUpperCase();
    if (!termo) return numeros?.pessoas ?? [];
    return (numeros?.pessoas ?? []).filter((pessoa) =>
      pessoa.nome_chave.includes(termo),
    );
  }, [numeros, buscaNumero]);

  const contatosOrdenados = useMemo(
    () =>
      [...contatosWhats].sort((a, b) =>
        a.nome.localeCompare(b.nome, "pt-BR"),
      ),
    [contatosWhats],
  );

  function alternar(nomeChave: string) {
    setMarcados((atual) => ({ ...atual, [nomeChave]: !atual[nomeChave] }));
  }

  function marcarVisiveis() {
    setMarcados((atual) => {
      const proximo = { ...atual };
      for (const pessoa of filtradas) proximo[pessoa.nome_chave] = true;
      return proximo;
    });
  }

  function limparMarcacoes() {
    setMarcados({});
  }

  async function salvarPresenca() {
    if (!estado) return;

    setSalvando(true);
    try {
      const nomes = Object.entries(marcados)
        .filter(([, marcado]) => marcado)
        .map(([nomeChave]) => nomeChave);

      const dados = await api.post<PresencaEstado>("/api/presenca/registrar", {
        dia,
        tipo,
        nomes_chave: nomes,
      });
      setEstado(dados);
      setMarcados(
        Object.fromEntries(
          dados.pessoas.map((pessoa) => [
            pessoa.nome_chave,
            tipo === "escola_biblica" ? pessoa.participou : pessoa.falta,
          ]),
        ),
      );
      toast.success(
        tipo === "escola_biblica"
          ? `Escola Bíblica de ${dados.data} salva: ${dados.participantes} participante(s).`
          : `Faltas do culto de ${dados.data} salvas: ${dados.faltantes}.`,
      );
      await carregarNumeros();
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao salvar a presença."));
    } finally {
      setSalvando(false);
    }
  }

  async function enviar(tipoAviso: "falta" | "visita") {
    const alvos =
      tipoAviso === "visita"
        ? visitasPendentes.map((pessoa) => pessoa.nome_chave)
        : faltantes.map((pessoa) => pessoa.nome_chave);

    if (alvos.length === 0) {
      toast.error(
        tipoAviso === "visita"
          ? "Ninguém atingiu o limite de faltas seguidas."
          : "Nenhuma falta marcada para esse dia.",
      );
      return;
    }

    setEnviando(tipoAviso);
    try {
      const resposta = await api.post<PresencaEnvio>("/api/presenca/enviar", {
        dia,
        tipo: tipoAviso,
        tipo_presenca: tipo,
        nomes_chave: alvos,
      });

      const rotulo = tipoAviso === "falta" ? "falta" : "visita";
      if (resposta.falhas === 0) {
        toast.success(
          `${resposta.enviados} resumo(s) de ${rotulo} enviado(s) ao responsável e ao pastor.`,
        );
      } else {
        toast.warning(
          `${resposta.enviados} enviado(s), ${resposta.falhas} falha(s).`,
        );
        resposta.resultados
          .filter((item) => !item.ok)
          .slice(0, 3)
          .forEach((item) =>
            toast.error(`${item.referencia}: ${item.mensagem}`),
          );
      }

      if (resposta.sem_contato.length > 0) {
        toast.warning(
          `${resposta.sem_contato.length} destino(s) sem WhatsApp cadastrado: ${resposta.sem_contato
            .map((item) => item.referencia)
            .join(", ")}.`,
        );
      }

      setConfirmandoFalta(false);
      setConfirmandoVisita(false);
      await carregarEstado(dia, tipo);
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao enviar as mensagens."));
    } finally {
      setEnviando(null);
    }
  }

  async function sincronizarContatos() {
    setSincronizando(true);
    try {
      await api.post("/api/whatsapp/contatos/sincronizar");

      for (let tentativa = 0; tentativa < 60; tentativa += 1) {
        const dados = await api.get<ContatosResposta>("/api/whatsapp/contatos");
        setContatosWhats(dados.contatos);
        if (!dados.sincronizando) {
          if (dados.erro) toast.error(dados.erro);
          break;
        }
        await new Promise((resolver) => setTimeout(resolver, 5000));
      }

      await carregarNumeros();
      toast.success("Contatos do WhatsApp atualizados.");
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao sincronizar os contatos."));
    } finally {
      setSincronizando(false);
    }
  }

  async function vincularAutomaticamente() {
    setVinculando(true);
    try {
      const resposta = await api.post<{
        novos: number;
        sincronizando: boolean;
        erro: string | null;
      }>("/api/presenca/numeros/vincular");

      if (resposta.sincronizando) {
        toast.info(
          "Os contatos do WhatsApp ainda estão sincronizando. Tente de novo em instantes.",
        );
      } else if (resposta.erro) {
        toast.error(resposta.erro);
      } else {
        toast.success(
          resposta.novos === 0
            ? "Nenhum vínculo novo encontrado pelo nome."
            : `${resposta.novos} vínculo(s) criado(s) pelo nome.`,
        );
      }

      await carregarNumeros();
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao vincular automaticamente."));
    } finally {
      setVinculando(false);
    }
  }

  async function salvarNumero() {
    if (!pessoaSel) {
      toast.error("Escolha a pessoa.");
      return;
    }

    const jid = numeroManual.trim() || contatoSel;
    if (!jid) {
      toast.error("Escolha um contato do WhatsApp ou digite o número.");
      return;
    }

    const pessoa = numeros?.pessoas.find((item) => item.nome_chave === pessoaSel);

    setSalvandoNumero(true);
    try {
      await api.post("/api/presenca/numeros", {
        nome_chave: pessoaSel,
        nome: pessoa?.nome ?? "",
        jid,
      });
      toast.success(`Número de ${pessoa?.nome ?? pessoaSel} salvo.`);
      setNumeroManual("");
      setContatoSel("");
      await Promise.all([carregarNumeros(), carregarEstado(dia, tipo)]);
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao salvar o número."));
    } finally {
      setSalvandoNumero(false);
    }
  }

  async function removerNumero(nomeChave: string, nome: string) {
    try {
      await api.post("/api/presenca/numeros", { nome_chave: nomeChave, jid: "" });
      toast.success(`Número de ${nome} removido.`);
      await Promise.all([carregarNumeros(), carregarEstado(dia, tipo)]);
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao remover o número."));
    }
  }

  async function salvarMensagens() {
    setSalvandoMensagens(true);
    try {
      const resposta = await api.put<{
        ok: boolean;
        mensagens: { falta: string; visita: string };
      }>("/api/presenca/mensagens", {
        falta: textoFalta,
        visita: textoVisita,
      });
      setTextoFalta(resposta.mensagens.falta);
      setTextoVisita(resposta.mensagens.visita);
      toast.success("Mensagens salvas.");
      await carregarMensagens();
    } catch (e) {
      toast.error(mensagemErro(e, "Falha ao salvar as mensagens."));
    } finally {
      setSalvandoMensagens(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        sobretitulo="Acompanhamento"
        titulo="Presença"
        descricao="Lance a presença do culto e da Escola Bíblica. Os avisos de falta e de visita vão para o responsável do grupo e o pastor da igreja, com a lista de nomes."
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
          <div className="space-y-1.5">
            <Label htmlFor="dia" className="flex items-center gap-1.5">
              <CalendarDays className="size-3.5" />
              Dia
            </Label>
            <Input
              id="dia"
              type="date"
              value={dia}
              className="w-44"
              onChange={(e) => {
                setDia(e.target.value);
                setConfirmandoFalta(false);
                setConfirmandoVisita(false);
              }}
            />
          </div>

          <div className="space-y-1.5">
            <Label>Tipo</Label>
            <div className="flex gap-2">
              {TIPOS.map((item) => {
                const Icone = item.icone;
                return (
                  <Button
                    key={item.valor}
                    variant={tipo === item.valor ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      setTipo(item.valor);
                      setConfirmandoFalta(false);
                      setConfirmandoVisita(false);
                    }}
                  >
                    <Icone />
                    {item.rotulo}
                  </Button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {ABAS.map((item) => {
              const Icone = item.icone;
              return (
                <Button
                  key={item.valor}
                  variant={aba === item.valor ? "default" : "outline"}
                  size="sm"
                  onClick={() => setAba(item.valor)}
                >
                  <Icone />
                  {item.rotulo}
                </Button>
              );
            })}
          </div>

          {estado ? (
            <div className="ml-auto flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline">{estado.total} pessoas</Badge>
              {estado.tipo === "escola_biblica" ? (
                <Badge variant="outline">
                  {estado.participantes} participante(s)
                </Badge>
              ) : (
                <Badge variant="outline">{estado.faltantes} faltantes</Badge>
              )}
              <Badge variant="outline">{estado.com_numero} com número</Badge>
              {estado.visitas_pendentes > 0 ? (
                <Badge>{estado.visitas_pendentes} visita(s)</Badge>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {aba === "faltas" ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ClipboardCheck className="size-4" />
                {tipo === "escola_biblica"
                  ? `Participantes da Escola Bíblica de ${estado?.data ?? "..."}`
                  : `Faltas do culto de ${estado?.data ?? "..."}`}
              </CardTitle>
              <CardDescription>
                {tipo === "escola_biblica" ? (
                  <>
                    Marque quem <strong>participou</strong> da Escola Bíblica e
                    clique em salvar. Quem não for marcado entra como falta.
                  </>
                ) : (
                  <>
                    Marque quem <strong>faltou</strong> ao culto e clique em
                    salvar. O dia fica registrado mesmo quando ninguém faltou.
                  </>
                )}
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-end gap-2">
                <div className="space-y-1.5">
                  <Label htmlFor="busca-presenca">Buscar</Label>
                  <Input
                    id="busca-presenca"
                    value={busca}
                    placeholder="Parte do nome"
                    className="w-56"
                    onChange={(e) => setBusca(e.target.value)}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="grupo-presenca">Grupo de assistência</Label>
                  <select
                    id="grupo-presenca"
                    value={grupo}
                    onChange={(e) => setGrupo(e.target.value)}
                    className="h-9 w-60 rounded-lg border bg-background px-3 text-sm"
                  >
                    <option value="">Todos os grupos</option>
                    {(estado?.grupos ?? []).map((nome) => (
                      <option key={nome} value={nome}>
                        {nome}
                      </option>
                    ))}
                  </select>
                </div>

                <Button variant="outline" size="sm" onClick={marcarVisiveis}>
                  <Check />
                  Marcar visíveis
                </Button>
                <Button variant="ghost" size="sm" onClick={limparMarcacoes}>
                  Limpar
                </Button>
              </div>

              {carregando && !estado ? (
                <div className="space-y-2">
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                </div>
              ) : (
                <div className="max-h-96 divide-y overflow-y-auto rounded-lg border">
                  {filtradas.length === 0 ? (
                    <p className="p-3 text-sm text-muted-foreground">
                      Nenhuma pessoa encontrada com esse filtro.
                    </p>
                  ) : (
                    filtradas.map((pessoa) => (
                      <label
                        key={pessoa.nome_chave}
                        className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2 text-sm hover:bg-muted/50"
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          <input
                            type="checkbox"
                            className="size-4 accent-primary"
                            checked={Boolean(marcados[pessoa.nome_chave])}
                            onChange={() => alternar(pessoa.nome_chave)}
                          />
                          <span className="truncate">{pessoa.nome}</span>
                        </span>
                        <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                          {pessoa.grupo ? <span>{pessoa.grupo}</span> : null}
                          {pessoa.faltas_consecutivas > 0 ? (
                            <Badge variant="outline">
                              {pessoa.faltas_consecutivas} seguida(s)
                            </Badge>
                          ) : null}
                        </span>
                      </label>
                    ))
                  )}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2">
                <Button onClick={() => void salvarPresenca()} disabled={salvando}>
                  {salvando ? <Loader2 className="animate-spin" /> : <Save />}
                  {salvando
                    ? "Salvando..."
                    : tipo === "escola_biblica"
                      ? "Salvar participantes"
                      : "Salvar faltas do dia"}
                </Button>
                <span className="text-xs text-muted-foreground">
                  {totalMarcados} marcado(s) · {marcadosVisiveis} visível(is)
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="size-4" />
                {tipo === "escola_biblica"
                  ? `Participantes de ${estado?.data ?? "..."}: ${participantes.length}`
                  : `Faltantes de ${estado?.data ?? "..."}: ${faltantes.length}`}
              </CardTitle>
              <CardDescription>
                {estado?.conferido
                  ? `${estado.com_numero} pessoa(s) na lista com número cadastrado.`
                  : "Esse dia ainda não foi conferido."}
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="overflow-x-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Pessoa</TableHead>
                      <TableHead>Grupo</TableHead>
                      <TableHead>Igreja</TableHead>
                      <TableHead>Número</TableHead>
                      {tipo === "escola_biblica" ? (
                        <TableHead>Presença</TableHead>
                      ) : (
                        <>
                          <TableHead>Faltas seguidas</TableHead>
                          <TableHead>Visita</TableHead>
                        </>
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(tipo === "escola_biblica"
                      ? participantes
                      : faltantes
                    ).length === 0 ? (
                      <TableRow>
                        <TableCell
                          colSpan={tipo === "escola_biblica" ? 5 : 6}
                          className="text-sm text-muted-foreground"
                        >
                          {tipo === "escola_biblica"
                            ? "Nenhum participante marcado para este dia."
                            : "Nenhuma falta marcada para este dia."}
                        </TableCell>
                      </TableRow>
                    ) : tipo === "escola_biblica" ? (
                      participantes.map((pessoa) => (
                        <TableRow key={pessoa.nome_chave}>
                          <TableCell className="font-medium">
                            {pessoa.nome}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {pessoa.grupo || "—"}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {pessoa.igreja_nome || "—"}
                          </TableCell>
                          <TableCell className="text-xs">
                            {pessoa.numero_formatado || "—"}
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary">participou</Badge>
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      faltantes.map((pessoa) => (
                        <TableRow key={pessoa.nome_chave}>
                          <TableCell className="font-medium">
                            {pessoa.nome}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {pessoa.grupo || "—"}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {pessoa.igreja_nome || "—"}
                          </TableCell>
                          <TableCell className="text-xs">
                            {pessoa.numero_formatado || (
                              <span className="text-amber-600">
                                sem número
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-xs">
                            {pessoa.faltas_consecutivas}
                          </TableCell>
                          <TableCell>
                            {pessoa.precisa_visita ? (
                              <Badge>avisar</Badge>
                            ) : (
                              <span className="text-xs text-muted-foreground">
                                —
                              </span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>

              <Separator />

              <div className="flex flex-wrap items-center gap-2">
                {confirmandoFalta ? (
                  <>
                    <Button
                      onClick={() => void enviar("falta")}
                      disabled={enviando !== null}
                    >
                      {enviando === "falta" ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <Send />
                      )}
                      {enviando === "falta"
                        ? "Enviando..."
                        : `Confirmar envio (${faltantes.length})`}
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => setConfirmandoFalta(false)}
                      disabled={enviando !== null}
                    >
                      Cancelar
                    </Button>
                  </>
                ) : (
                  <Button
                    onClick={() => setConfirmandoFalta(true)}
                    disabled={faltantes.length === 0}
                  >
                    <Send />
                    Enviar resumo de faltas
                  </Button>
                )}
                <span className="text-xs text-muted-foreground">
                  Vai para o responsável do grupo e o pastor da igreja, com a
                  lista de nomes.
                </span>
              </div>

              <Separator />

              <div className="space-y-2">
                <p className="flex items-center gap-2 text-sm font-medium">
                  <Phone className="size-4" />
                  Visitas ({estado?.limite_visita ?? 7}+ faltas seguidas,
                  contando culto e Escola Bíblica)
                </p>

                {visitasPendentes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Ninguém atingiu o limite nesta sequência (ou a visita já foi
                    avisada).
                  </p>
                ) : (
                  <>
                    <ul className="space-y-1 text-sm">
                      {visitasPendentes.map((pessoa) => (
                        <li key={pessoa.nome_chave}>
                          <strong>{pessoa.nome}</strong> —{" "}
                          {pessoa.faltas_consecutivas} faltas seguidas
                        </li>
                      ))}
                    </ul>

                    {confirmandoVisita ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          onClick={() => void enviar("visita")}
                          disabled={enviando !== null}
                        >
                          {enviando === "visita" ? (
                            <Loader2 className="animate-spin" />
                          ) : (
                            <Send />
                          )}
                          {enviando === "visita"
                            ? "Enviando..."
                            : `Confirmar visita (${visitasPendentes.length})`}
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => setConfirmandoVisita(false)}
                          disabled={enviando !== null}
                        >
                          Cancelar
                        </Button>
                      </div>
                    ) : (
                      <Button
                        variant="outline"
                        onClick={() => setConfirmandoVisita(true)}
                      >
                        <Send />
                        Enviar mensagem de visita
                      </Button>
                    )}
                  </>
                )}
              </div>

              {(estado?.historico.length ?? 0) > 0 ? (
                <details className="rounded-lg border">
                  <summary className="cursor-pointer px-3 py-2 text-sm font-medium">
                    Dias conferidos ({estado?.historico.length})
                  </summary>
                  <div className="max-h-56 divide-y overflow-y-auto border-t">
                    {estado?.historico.map((item) => (
                      <button
                        key={item.dia}
                        type="button"
                        className={cn(
                          "flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-muted/50",
                          item.dia === dia && "bg-muted/40",
                        )}
                        onClick={() => setDia(item.dia)}
                      >
                        <span>{item.data}</span>
                        <span className="text-xs text-muted-foreground">
                          {tipo === "escola_biblica"
                            ? `${item.participantes} participante(s)`
                            : `${item.faltantes} falta(s)`}
                        </span>
                      </button>
                    ))}
                  </div>
                </details>
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {aba === "numeros" ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Phone className="size-4" />
                Números das pessoas
              </CardTitle>
              <CardDescription>
                O número é usado nas mensagens de falta e de visita. Você pode
                escolher um contato do WhatsApp conectado ou digitar o número.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void sincronizarContatos()}
                  disabled={sincronizando}
                >
                  <RefreshCw className={cn(sincronizando && "animate-spin")} />
                  Sincronizar WhatsApp
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void vincularAutomaticamente()}
                  disabled={vinculando}
                >
                  {vinculando ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <Link2 />
                  )}
                  Vincular automaticamente pelo nome
                </Button>
                <span className="ml-auto self-center text-xs text-muted-foreground">
                  {numeros
                    ? `${numeros.com_numero} com número · ${numeros.sem_numero} sem número · ${numeros.contatos_whats} contato(s) do WhatsApp`
                    : "Carregando..."}
                </span>
              </div>

              <div className="flex flex-wrap items-end gap-2 rounded-lg border p-3">
                <div className="space-y-1.5">
                  <Label htmlFor="pessoa-numero">Pessoa</Label>
                  <select
                    id="pessoa-numero"
                    value={pessoaSel}
                    onChange={(e) => setPessoaSel(e.target.value)}
                    className="h-9 w-64 rounded-lg border bg-background px-3 text-sm"
                  >
                    <option value="">— escolher —</option>
                    {(numeros?.pessoas ?? []).map((pessoa) => (
                      <option key={pessoa.nome_chave} value={pessoa.nome_chave}>
                        {pessoa.nome}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="contato-numero">Contato do WhatsApp</Label>
                  <select
                    id="contato-numero"
                    value={contatoSel}
                    onChange={(e) => setContatoSel(e.target.value)}
                    className="h-9 w-64 rounded-lg border bg-background px-3 text-sm"
                  >
                    <option value="">— escolher da lista —</option>
                    {contatosOrdenados.map((contato) => (
                      <option key={contato.jid} value={contato.jid}>
                        {contato.nome} — {contato.numero}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="numero-manual">... ou o número</Label>
                  <Input
                    id="numero-manual"
                    value={numeroManual}
                    placeholder="5534999998888"
                    className="w-44"
                    onChange={(e) => setNumeroManual(e.target.value)}
                  />
                </div>

                <Button
                  onClick={() => void salvarNumero()}
                  disabled={salvandoNumero}
                >
                  {salvandoNumero ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <Save />
                  )}
                  Salvar vínculo
                </Button>
              </div>

              <div className="flex flex-wrap items-end gap-2">
                <div className="space-y-1.5">
                  <Label htmlFor="busca-numero">Buscar pessoa</Label>
                  <Input
                    id="busca-numero"
                    value={buscaNumero}
                    placeholder="Parte do nome"
                    className="w-56"
                    onChange={(e) => setBuscaNumero(e.target.value)}
                  />
                </div>
              </div>

              <div className="max-h-96 overflow-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Pessoa</TableHead>
                      <TableHead>Grupo</TableHead>
                      <TableHead>Número</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Ação</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {numerosFiltrados.length === 0 ? (
                      <TableRow>
                        <TableCell
                          colSpan={5}
                          className="text-sm text-muted-foreground"
                        >
                          Nenhuma pessoa encontrada.
                        </TableCell>
                      </TableRow>
                    ) : (
                      numerosFiltrados.map((pessoa) => (
                        <TableRow key={pessoa.nome_chave}>
                          <TableCell className="font-medium">
                            {pessoa.nome}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {pessoa.grupo || "—"}
                          </TableCell>
                          <TableCell className="text-xs">
                            {pessoa.numero_formatado || "—"}
                          </TableCell>
                          <TableCell>
                            {pessoa.vinculado ? (
                              <Badge variant="outline">vinculado</Badge>
                            ) : (
                              <span className="text-xs text-muted-foreground">
                                sem número
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            {pessoa.vinculado ? (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  void removerNumero(pessoa.nome_chave, pessoa.nome)
                                }
                              >
                                <Trash2 />
                                Remover
                              </Button>
                            ) : (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  setPessoaSel(pessoa.nome_chave);
                                  setContatoSel("");
                                  setNumeroManual("");
                                }}
                              >
                                <Link2 />
                                Vincular
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {aba === "mensagens" ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="size-4" />
                Textos das mensagens
              </CardTitle>
              <CardDescription>
                Use <code>{"{responsavel}"}</code>, <code>{"{nomes}"}</code>,{" "}
                <code>{"{data}"}</code>, <code>{"{tipo}"}</code>,{" "}
                <code>{"{total}"}</code> e <code>{"{limite}"}</code> — eles são
                trocados automaticamente. O aviso vai para o responsável do
                grupo e o pastor da igreja.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="texto-falta">Mensagem de falta</Label>
                <textarea
                  id="texto-falta"
                  value={textoFalta}
                  onChange={(e) => setTextoFalta(e.target.value)}
                  className="min-h-32 w-full resize-y rounded-lg border bg-background p-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="texto-visita">
                  Mensagem de visita (após {mensagens?.limite_visita ?? 7} faltas
                  seguidas)
                </Label>
                <textarea
                  id="texto-visita"
                  value={textoVisita}
                  onChange={(e) => setTextoVisita(e.target.value)}
                  className="min-h-32 w-full resize-y rounded-lg border bg-background p-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                />
              </div>

              <Button
                onClick={() => void salvarMensagens()}
                disabled={salvandoMensagens}
              >
                {salvandoMensagens ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <Save />
                )}
                {salvandoMensagens ? "Salvando..." : "Salvar mensagens"}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Prévia com dados de exemplo</CardTitle>
              <CardDescription>
                {mensagens
                  ? `${mensagens.exemplo.responsavel} · ${mensagens.exemplo.data}`
                  : "Carregando..."}
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4 text-sm">
              <div className="space-y-1">
                <p className="font-medium">Falta</p>
                <p className="rounded-lg border bg-muted/30 p-3">
                  {mensagens
                    ? montarExemplo(
                        textoFalta,
                        mensagens.exemplo,
                        tipo,
                        mensagens.limite_visita,
                      )
                    : "—"}
                </p>
              </div>

              <div className="space-y-1">
                <p className="font-medium">Visita</p>
                <p className="rounded-lg border bg-muted/30 p-3">
                  {mensagens
                    ? montarExemplo(
                        textoVisita,
                        mensagens.exemplo,
                        tipo,
                        mensagens.limite_visita,
                      )
                    : "—"}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
