"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  BookOpen,
  CalendarDays,
  CalendarPlus,
  Cake,
  Check,
  ClipboardList,
  HeartHandshake,
  Home,
  Loader2,
  MailQuestion,
  MapPin,
  NotebookPen,
  PartyPopper,
  Phone,
  Plus,
  RefreshCw,
  Smartphone,
  Trash2,
  UserRoundX,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";
import {
  classeDias,
  formatarTelefone,
  GraficoPresenca,
  ResumoPresenca,
  rotuloDias,
} from "@/components/pessoa-comum";
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
  api,
  ApiError,
  type Evento,
  type Igreja,
  type Observacao,
  type Oracao,
  type Pessoa,
  type PresencaHistorico,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function hojeIso(): string {
  const data = new Date();
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${data.getFullYear()}-${mes}-${dia}`;
}

function mensagemErro(e: unknown, padrao: string): string {
  return e instanceof ApiError ? e.message : padrao;
}

function MembroConteudo() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const { usuario } = useAuth();

  const pessoaId = Number(params?.id);
  const fonte = (search.get("fonte") ?? "icm").toLowerCase();
  const ehIcm = fonte === "icm";

  const [pessoa, setPessoa] = useState<Pessoa | null>(null);
  const [igrejas, setIgrejas] = useState<Igreja[]>([]);
  const [historico, setHistorico] = useState<PresencaHistorico | null>(null);
  const [oracoes, setOracoes] = useState<Oracao[]>([]);
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [observacoes, setObservacoes] = useState<Observacao[]>([]);

  const [carregando, setCarregando] = useState(true);
  const [carregandoExtras, setCarregandoExtras] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const [registrando, setRegistrando] = useState(false);
  const [salvandoIgreja, setSalvandoIgreja] = useState(false);
  const [salvandoSms, setSalvandoSms] = useState(false);

  const [textoOracao, setTextoOracao] = useState("");
  const [salvandoOracao, setSalvandoOracao] = useState(false);

  const [textoObservacao, setTextoObservacao] = useState("");
  const [salvandoObservacao, setSalvandoObservacao] = useState(false);

  const [mostrarFormularioEvento, setMostrarFormularioEvento] = useState(false);
  const [novoEvento, setNovoEvento] = useState({
    nome: "",
    data: hojeIso(),
    local: "",
    descricao: "",
  });
  const [salvandoEvento, setSalvandoEvento] = useState(false);

  const carregarPessoa = useCallback(async () => {
    if (!Number.isFinite(pessoaId)) {
      setErro("Membro inválido.");
      setCarregando(false);
      return;
    }
    setCarregando(true);
    setErro(null);
    try {
      setPessoa(
        await api.get<Pessoa>(`/api/pessoas/${pessoaId}?fonte=${fonte}`),
      );
    } catch (e) {
      setPessoa(null);
      setErro(mensagemErro(e, "Não foi possível carregar esta vida."));
    } finally {
      setCarregando(false);
    }
  }, [pessoaId, fonte]);

  const carregarExtras = useCallback(async () => {
    if (!ehIcm || !Number.isFinite(pessoaId)) return;
    setCarregandoExtras(true);

    const [hist, orac, ev, obs] = await Promise.allSettled([
      api.get<PresencaHistorico>(
        `/api/presenca/pessoa/${pessoaId}?fonte=icm&limite=60`,
      ),
      api.get<Oracao[]>(`/api/oracoes?pessoa_id=${pessoaId}&fonte=icm`),
      api.get<Evento[]>(`/api/eventos?pessoa_id=${pessoaId}&fonte=icm`),
      api.get<Observacao[]>(`/api/observacoes?pessoa_id=${pessoaId}&fonte=icm`),
    ]);

    setHistorico(hist.status === "fulfilled" ? hist.value : null);
    setOracoes(orac.status === "fulfilled" ? orac.value : []);
    setEventos(ev.status === "fulfilled" ? ev.value : []);
    setObservacoes(obs.status === "fulfilled" ? obs.value : []);
    setCarregandoExtras(false);
  }, [ehIcm, pessoaId]);

  useEffect(() => {
    void carregarPessoa();
  }, [carregarPessoa]);

  useEffect(() => {
    void carregarExtras();
  }, [carregarExtras]);

  useEffect(() => {
    if (!ehIcm) {
      setIgrejas([]);
      return;
    }
    api
      .get<Igreja[]>("/api/igrejas")
      .then(setIgrejas)
      .catch(() => setIgrejas([]));
  }, [ehIcm]);

  const telefones = useMemo(
    () =>
      pessoa
        ? [
            { rotulo: "Celular", valor: pessoa.celular, Icone: Smartphone },
            { rotulo: "Residencial", valor: pessoa.tel_residencial, Icone: Home },
            { rotulo: "Comercial", valor: pessoa.tel_comercial, Icone: Phone },
          ].filter((telefone) => telefone.valor)
        : [],
    [pessoa],
  );

  async function registrarVisita() {
    if (!pessoa) return;
    setRegistrando(true);
    try {
      const atualizada = await api.post<Pessoa>(
        `/api/pessoas/${pessoa.id}/visita`,
        { fonte: pessoa.fonte },
      );
      setPessoa(atualizada);
      toast.success(`Visita de ${atualizada.nome.split(" ")[0]} registrada.`);
    } catch (e) {
      toast.error(
        mensagemErro(e, "Não foi possível registrar a visita."),
      );
    } finally {
      setRegistrando(false);
    }
  }

  async function trocarIgreja(valor: string) {
    if (!pessoa) return;
    setSalvandoIgreja(true);
    try {
      const atualizada = await api.patch<Pessoa>(`/api/pessoas/${pessoa.id}`, {
        fonte: pessoa.fonte,
        igreja_id: valor === "" ? null : Number(valor),
      });
      setPessoa(atualizada);
      toast.success("Igreja atualizada.");
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível salvar a igreja."));
    } finally {
      setSalvandoIgreja(false);
    }
  }

  async function alternarSms() {
    if (!pessoa) return;
    setSalvandoSms(true);
    try {
      const atualizada = await api.patch<Pessoa>(`/api/pessoas/${pessoa.id}`, {
        fonte: pessoa.fonte,
        excluido: !pessoa.excluido,
      });
      setPessoa(atualizada);
      toast.success(
        atualizada.excluido
          ? "Esta vida não receberá mais SMS de aniversário."
          : "Esta vida voltará a receber SMS de aniversário.",
      );
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível salvar a preferência."));
    } finally {
      setSalvandoSms(false);
    }
  }

  async function criarOracao() {
    if (!pessoa) return;
    const texto = textoOracao.trim();
    if (texto.length < 2) {
      toast.error("Escreva o motivo de oração.");
      return;
    }
    setSalvandoOracao(true);
    try {
      const criado = await api.post<Oracao>("/api/oracoes", {
        pessoa_id: pessoa.id,
        fonte: "icm",
        texto,
      });
      setOracoes((atual) => [criado, ...atual]);
      setTextoOracao("");
      toast.success("Motivo de oração salvo.");
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível salvar o motivo."));
    } finally {
      setSalvandoOracao(false);
    }
  }

  async function alternarOracao(motivo: Oracao) {
    const novo = motivo.status === "aberto" ? "atendido" : "aberto";
    try {
      const atualizado = await api.patch<Oracao>(`/api/oracoes/${motivo.id}`, {
        status: novo,
      });
      setOracoes((atual) =>
        atual.map((item) => (item.id === atualizado.id ? atualizado : item)),
      );
    } catch (e) {
      toast.error(
        mensagemErro(e, "Não foi possível atualizar o motivo."),
      );
    }
  }

  async function excluirOracao(motivo: Oracao) {
    if (!window.confirm("Excluir este motivo de oração?")) return;
    try {
      await api.delete(`/api/oracoes/${motivo.id}`);
      setOracoes((atual) => atual.filter((item) => item.id !== motivo.id));
      toast.success("Motivo excluído.");
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível excluir o motivo."));
    }
  }

  async function criarObservacao() {
    if (!pessoa) return;
    const texto = textoObservacao.trim();
    if (texto.length < 2) {
      toast.error("Escreva a observação.");
      return;
    }
    setSalvandoObservacao(true);
    try {
      const criada = await api.post<Observacao>("/api/observacoes", {
        pessoa_id: pessoa.id,
        fonte: "icm",
        texto,
      });
      setObservacoes((atual) => [criada, ...atual]);
      setTextoObservacao("");
      toast.success("Observação salva.");
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível salvar a observação."));
    } finally {
      setSalvandoObservacao(false);
    }
  }

  async function excluirObservacao(observacao: Observacao) {
    if (!window.confirm("Excluir esta observação?")) return;
    try {
      await api.delete(`/api/observacoes/${observacao.id}`);
      setObservacoes((atual) =>
        atual.filter((item) => item.id !== observacao.id),
      );
      toast.success("Observação excluída.");
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível excluir a observação."));
    }
  }

  async function alternarParticipacao(evento: Evento) {
    if (!pessoa) return;
    try {
      if (evento.participa) {
        await api.delete(
          `/api/eventos/${evento.id}/participantes/${pessoa.id}?fonte=icm`,
        );
        setEventos((atual) =>
          atual.map((item) =>
            item.id === evento.id
              ? {
                  ...item,
                  participa: false,
                  participantes: Math.max(0, item.participantes - 1),
                }
              : item,
          ),
        );
      } else {
        const atualizado = await api.post<Evento>(
          `/api/eventos/${evento.id}/participantes`,
          { pessoa_id: pessoa.id, fonte: "icm" },
        );
        setEventos((atual) =>
          atual.map((item) => (item.id === evento.id ? atualizado : item)),
        );
      }
    } catch (e) {
      toast.error(
        mensagemErro(e, "Não foi possível salvar a participação."),
      );
    }
  }

  async function criarEvento() {
    const nome = novoEvento.nome.trim();
    if (nome.length < 2) {
      toast.error("Dê um nome ao evento.");
      return;
    }
    if (!novoEvento.data) {
      toast.error("Informe a data do evento.");
      return;
    }
    setSalvandoEvento(true);
    try {
      const criado = await api.post<Evento>("/api/eventos", {
        nome,
        data: novoEvento.data,
        local: novoEvento.local.trim(),
        descricao: novoEvento.descricao.trim(),
      });
      setEventos((atual) =>
        [criado, ...atual].sort((a, b) =>
          b.data_iso.localeCompare(a.data_iso),
        ),
      );
      setNovoEvento({
        nome: "",
        data: hojeIso(),
        local: "",
        descricao: "",
      });
      setMostrarFormularioEvento(false);
      toast.success("Evento criado. Marque quem participou.");
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível criar o evento."));
    } finally {
      setSalvandoEvento(false);
    }
  }

  async function excluirEvento(evento: Evento) {
    if (
      !window.confirm(
        `Excluir o evento "${evento.nome}" e as participações dele?`,
      )
    ) {
      return;
    }
    try {
      await api.delete(`/api/eventos/${evento.id}`);
      setEventos((atual) => atual.filter((item) => item.id !== evento.id));
      toast.success("Evento excluído.");
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível excluir o evento."));
    }
  }

  if (carregando && !pessoa) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-52" />
        <Skeleton className="h-28 w-full" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (!pessoa) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" render={<Link href="/membros" />}>
          <ArrowLeft />
          Voltar para Membros
        </Button>
        <Card>
          <CardHeader>
            <CardTitle>Não foi possível abrir esta vida</CardTitle>
            <CardDescription>
              {erro ?? "Membro não encontrado."}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const aniversario = pessoa.data
    ? `${pessoa.data}${pessoa.ano ? `/${pessoa.ano}` : ""}`
    : "Não informado";
  const sequencia = historico?.sequencia;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="ghost" size="sm" render={<Link href="/membros" />}>
          <ArrowLeft />
          Voltar para Membros
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            void carregarPessoa();
            void carregarExtras();
          }}
          disabled={carregando || carregandoExtras}
        >
          <RefreshCw
            className={cn(
              (carregando || carregandoExtras) && "animate-spin",
            )}
          />
          Atualizar
        </Button>
      </div>

      <PageHeader
        sobretitulo="Ficha da vida"
        titulo={pessoa.nome}
        descricao={
          [
            pessoa.grupo ? `Grupo ${pessoa.grupo}` : null,
            pessoa.fonte === "icm" && pessoa.igreja_nome
              ? pessoa.igreja_nome
              : null,
            aniversario !== "Não informado"
              ? `Aniversário ${aniversario}`
              : null,
          ]
            .filter(Boolean)
            .join(" · ") || "Sem grupo ou igreja definidos."
        }
      >
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline">{pessoa.fonte.toUpperCase()}</Badge>
          {pessoa.situacao ? (
            <Badge variant="secondary">{pessoa.situacao}</Badge>
          ) : null}
          {pessoa.categoria ? (
            <Badge variant="outline">{pessoa.categoria}</Badge>
          ) : null}
          {pessoa.excluido ? (
            <Badge variant="destructive" className="gap-1">
              <UserRoundX className="size-3" />
              Não recebe SMS
            </Badge>
          ) : null}
          {!pessoa.ativo ? (
            <Badge variant="destructive">Ausente</Badge>
          ) : null}
        </div>
      </PageHeader>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_23rem]">
        <div className="space-y-6">
          {ehIcm ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="size-4 text-brand" />
                  Presença
                </CardTitle>
                <CardDescription>
                  Histórico de culto e Escola Bíblica desta vida.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {carregandoExtras && !historico ? (
                  <Skeleton className="h-40 w-full" />
                ) : !historico || historico.eventos.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Ainda não há presença lançada para esta vida.
                  </p>
                ) : (
                  <>
                    <div className="grid grid-cols-3 gap-2">
                      <ResumoPresenca
                        rotulo="Culto"
                        resumo={historico.resumo.culto}
                      />
                      <ResumoPresenca
                        rotulo="Escola Bíblica"
                        resumo={historico.resumo.escola_biblica}
                      />
                      <ResumoPresenca
                        rotulo="Geral"
                        resumo={historico.resumo.geral}
                      />
                    </div>
                    <GraficoPresenca
                      eventos={historico.eventos}
                      altura="h-32"
                    />
                    <details className="rounded-lg border">
                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium">
                        Últimos lançamentos ({historico.eventos.length})
                      </summary>
                      <ul className="max-h-64 divide-y overflow-y-auto border-t text-xs">
                        {historico.eventos.map((evento) => (
                          <li
                            key={`${evento.dia}-${evento.tipo}`}
                            className="flex items-center justify-between gap-2 px-3 py-1.5"
                          >
                            <span>
                              {evento.data} · {evento.tipo_rotulo}
                            </span>
                            <Badge
                              variant={evento.presente ? "secondary" : "outline"}
                              className={cn(
                                "h-5",
                                !evento.presente && "text-destructive",
                              )}
                            >
                              {evento.presente ? "presente" : "falta"}
                            </Badge>
                          </li>
                        ))}
                      </ul>
                    </details>
                  </>
                )}
              </CardContent>
            </Card>
          ) : null}

          {ehIcm ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ClipboardList className="size-4 text-brand" />
                  Faltas
                </CardTitle>
                <CardDescription>
                  Culto e Escola Bíblica contam na mesma sequência. O aviso de
                  visita vai para o responsável do grupo e para o pastor.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {carregandoExtras && !historico ? (
                  <Skeleton className="h-28 w-full" />
                ) : (
                  <>
                    <div className="grid gap-2 sm:grid-cols-3">
                      <div className="rounded-lg border bg-muted/20 p-3">
                        <p className="text-[0.7rem] text-muted-foreground">
                          Faltas seguidas
                        </p>
                        <p className="text-2xl leading-tight font-semibold">
                          {sequencia?.atual ?? 0}
                        </p>
                        <p className="text-[0.65rem] text-muted-foreground">
                          limite de {sequencia?.limite ?? 7}
                        </p>
                      </div>
                      <div className="rounded-lg border bg-muted/20 p-3">
                        <p className="text-[0.7rem] text-muted-foreground">
                          Início da sequência
                        </p>
                        <p className="text-sm font-medium">
                          {sequencia?.inicio_data ?? "—"}
                        </p>
                      </div>
                      <div className="rounded-lg border bg-muted/20 p-3">
                        <p className="text-[0.7rem] text-muted-foreground">
                          Aviso de visita
                        </p>
                        <Badge
                          variant={
                            sequencia?.precisa_visita ? "destructive" : "outline"
                          }
                          className="mt-1"
                        >
                          {sequencia?.precisa_visita
                            ? "pendente"
                            : sequencia?.visita_avisada_em
                              ? `avisado em ${sequencia.visita_avisada_em}`
                              : "em dia"}
                        </Badge>
                      </div>
                    </div>

                    {!historico || historico.faltas.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        Nenhuma falta registrada.
                      </p>
                    ) : (
                      <details className="rounded-lg border" open>
                        <summary className="cursor-pointer px-3 py-2 text-xs font-medium">
                          Histórico de faltas ({historico.faltas.length})
                        </summary>
                        <ul className="max-h-64 divide-y overflow-y-auto border-t text-xs">
                          {historico.faltas.map((falta) => (
                            <li
                              key={`${falta.dia}-${falta.tipo}`}
                              className="flex items-center justify-between gap-2 px-3 py-1.5"
                            >
                              <span>
                                {falta.data} · {falta.tipo_rotulo}
                              </span>
                              <Badge variant="outline" className="h-5 text-destructive">
                                falta
                              </Badge>
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          ) : null}

          {ehIcm ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CalendarDays className="size-4 text-brand" />
                  Eventos
                </CardTitle>
                <CardDescription>
                  Maanaim, encontros, retiros e outros eventos. Cada evento tem
                  a sua data e a vida pode participar de vários.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {usuario?.admin ? (
                  mostrarFormularioEvento ? (
                    <div className="space-y-3 rounded-lg border bg-muted/20 p-3">
                      <div className="grid gap-2 sm:grid-cols-2">
                        <div className="space-y-1.5">
                          <Label htmlFor="evento-nome">Nome</Label>
                          <Input
                            id="evento-nome"
                            value={novoEvento.nome}
                            placeholder="Ex.: Maanaim 2026"
                            maxLength={120}
                            onChange={(e) =>
                              setNovoEvento((atual) => ({
                                ...atual,
                                nome: e.target.value,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor="evento-data">Data</Label>
                          <Input
                            id="evento-data"
                            type="date"
                            value={novoEvento.data}
                            onChange={(e) =>
                              setNovoEvento((atual) => ({
                                ...atual,
                                data: e.target.value,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor="evento-local">Local</Label>
                          <Input
                            id="evento-local"
                            value={novoEvento.local}
                            placeholder="Opcional"
                            maxLength={160}
                            onChange={(e) =>
                              setNovoEvento((atual) => ({
                                ...atual,
                                local: e.target.value,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor="evento-descricao">Descrição</Label>
                          <Input
                            id="evento-descricao"
                            value={novoEvento.descricao}
                            placeholder="Opcional"
                            maxLength={1000}
                            onChange={(e) =>
                              setNovoEvento((atual) => ({
                                ...atual,
                                descricao: e.target.value,
                              }))
                            }
                          />
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => void criarEvento()}
                          disabled={salvandoEvento}
                        >
                          {salvandoEvento ? (
                            <Loader2 className="animate-spin" />
                          ) : (
                            <Check />
                          )}
                          Salvar evento
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setMostrarFormularioEvento(false)}
                        >
                          Cancelar
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setMostrarFormularioEvento(true)}
                    >
                      <CalendarPlus />
                      Novo evento
                    </Button>
                  )
                ) : null}

                {carregandoExtras && eventos.length === 0 ? (
                  <Skeleton className="h-20 w-full" />
                ) : eventos.length === 0 ? (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    <PartyPopper className="size-4" />
                    Nenhum evento cadastrado ainda.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {eventos.map((evento) => (
                      <li
                        key={evento.id}
                        className={cn(
                          "flex flex-wrap items-start justify-between gap-3 rounded-lg border p-3",
                          evento.participa && "border-brand/40 bg-brand-soft/40",
                        )}
                      >
                        <div className="min-w-0 space-y-0.5">
                          <p className="text-sm font-medium">{evento.nome}</p>
                          <p className="text-xs text-muted-foreground">
                            {evento.data}
                            {evento.local ? ` · ${evento.local}` : ""}
                            {` · ${evento.participantes} participante(s)`}
                          </p>
                          {evento.descricao ? (
                            <p className="text-xs text-muted-foreground">
                              {evento.descricao}
                            </p>
                          ) : null}
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant={evento.participa ? "default" : "outline"}
                            size="sm"
                            onClick={() => void alternarParticipacao(evento)}
                          >
                            {evento.participa ? <Check /> : <Plus />}
                            {evento.participa ? "Participou" : "Marcar"}
                          </Button>
                          {usuario?.admin ? (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label={`Excluir evento ${evento.nome}`}
                              className="text-muted-foreground hover:text-destructive"
                              onClick={() => void excluirEvento(evento)}
                            >
                              <Trash2 />
                            </Button>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ) : null}

          {ehIcm ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <HeartHandshake className="size-4 text-brand" />
                  Motivos de oração
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <textarea
                    value={textoOracao}
                    onChange={(e) => setTextoOracao(e.target.value)}
                    placeholder="Escreva o motivo de oração..."
                    rows={2}
                    maxLength={1000}
                    className="w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <Button
                    size="sm"
                    onClick={() => void criarOracao()}
                    disabled={salvandoOracao}
                  >
                    {salvandoOracao ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Plus />
                    )}
                    Adicionar motivo
                  </Button>
                </div>

                {carregandoExtras && oracoes.length === 0 ? (
                  <Skeleton className="h-16 w-full" />
                ) : oracoes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Nenhum motivo de oração registrado.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {oracoes.map((motivo) => (
                      <li
                        key={motivo.id}
                        className={cn(
                          "space-y-1.5 rounded-lg border p-3",
                          motivo.status === "atendido" && "bg-muted/30",
                        )}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p
                            className={cn(
                              "text-sm",
                              motivo.status === "atendido" &&
                                "text-muted-foreground line-through",
                            )}
                          >
                            {motivo.texto}
                          </p>
                          <div className="flex shrink-0 items-center">
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label={
                                motivo.status === "aberto"
                                  ? "Marcar como atendido"
                                  : "Reabrir motivo"
                              }
                              title={
                                motivo.status === "aberto"
                                  ? "Marcar como atendido"
                                  : "Reabrir motivo"
                              }
                              onClick={() => void alternarOracao(motivo)}
                            >
                              <Check
                                className={cn(
                                  motivo.status === "atendido" && "text-brand",
                                )}
                              />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label="Excluir motivo"
                              className="text-muted-foreground hover:text-destructive"
                              onClick={() => void excluirOracao(motivo)}
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
          ) : null}

          {ehIcm ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <NotebookPen className="size-4 text-brand" />
                  Observações
                </CardTitle>
                <CardDescription>
                  Anotações internas do líder/pastor sobre esta vida.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <textarea
                    value={textoObservacao}
                    onChange={(e) => setTextoObservacao(e.target.value)}
                    placeholder="Ex.: mudou de endereço, pediu oração pela família..."
                    rows={2}
                    maxLength={2000}
                    className="w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <Button
                    size="sm"
                    onClick={() => void criarObservacao()}
                    disabled={salvandoObservacao}
                  >
                    {salvandoObservacao ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Plus />
                    )}
                    Adicionar observação
                  </Button>
                </div>

                {carregandoExtras && observacoes.length === 0 ? (
                  <Skeleton className="h-16 w-full" />
                ) : observacoes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Nenhuma observação registrada.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {observacoes.map((observacao) => (
                      <li
                        key={observacao.id}
                        className="space-y-1 rounded-lg border p-3"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm whitespace-pre-wrap">
                            {observacao.texto}
                          </p>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label="Excluir observação"
                            className="shrink-0 text-muted-foreground hover:text-destructive"
                            onClick={() => void excluirObservacao(observacao)}
                          >
                            <Trash2 />
                          </Button>
                        </div>
                        <p className="text-[0.65rem] text-muted-foreground">
                          {observacao.criado_por
                            ? `${observacao.criado_por} · `
                            : ""}
                          {observacao.criado_em}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ) : null}

          {!ehIcm ? (
            <Card>
              <CardHeader>
                <CardTitle>Lista Zoom</CardTitle>
                <CardDescription>
                  Presença, eventos, motivos de oração e observações existem
                  apenas para as vidas do ICM.
                </CardDescription>
              </CardHeader>
            </Card>
          ) : null}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Phone className="size-4 text-brand" />
                Contatos
              </CardTitle>
            </CardHeader>
            <CardContent>
              {telefones.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nenhum telefone cadastrado.
                </p>
              ) : (
                <ul className="space-y-2">
                  {telefones.map(({ rotulo, valor, Icone }) => (
                    <li key={rotulo} className="flex items-center gap-3 text-sm">
                      <Icone className="size-4 shrink-0 text-muted-foreground" />
                      <span className="w-20 shrink-0 text-xs text-muted-foreground">
                        {rotulo}
                      </span>
                      <a
                        href={`https://wa.me/${valor.replace(/\D/g, "")}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium hover:text-brand hover:underline"
                      >
                        {formatarTelefone(valor)}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
              {!pessoa.telefone && telefones.length === 0 ? (
                <p className="mt-3 flex items-start gap-2 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
                  <MailQuestion className="mt-0.5 size-4 shrink-0" />
                  Sem telefone válido: o disparo automático não alcança esta
                  pessoa.
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="size-4 text-brand" />
                Visitação
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-lg border bg-muted/30 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs text-muted-foreground">
                      Dias sem visita
                    </p>
                    <p className="text-2xl font-semibold">
                      {pessoa.dias_sem_visita ?? "—"}
                    </p>
                  </div>
                  <Badge
                    variant="outline"
                    className={cn("h-6", classeDias(pessoa.dias_sem_visita))}
                  >
                    {rotuloDias(pessoa.dias_sem_visita)}
                  </Badge>
                </div>
                <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <CalendarDays className="size-3.5" />
                  Última visita:{" "}
                  <span className="font-medium text-foreground">
                    {pessoa.ultima_visita ?? "nunca registrada"}
                  </span>
                </p>
              </div>

              <Button
                className="w-full"
                onClick={() => void registrarVisita()}
                disabled={registrando}
              >
                {registrando ? <Loader2 className="animate-spin" /> : <Check />}
                {registrando ? "Registrando..." : "Registrar visita hoje"}
              </Button>
              <p className="text-xs text-muted-foreground">
                Registrar a visita zera o contador e a pessoa sai da frente da
                fila de visitação.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Cake className="size-4 text-brand" />
                Aniversário e cadastro
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
                <div>
                  <dt className="text-xs text-muted-foreground">Data</dt>
                  <dd className="font-medium">{aniversario}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Idade</dt>
                  <dd className="font-medium">
                    {pessoa.idade !== null ? `${pessoa.idade} anos` : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Grupo</dt>
                  <dd className="font-medium">{pessoa.grupo || "—"}</dd>
                </div>
                {pessoa.fonte === "icm" ? (
                  <div>
                    <dt className="text-xs text-muted-foreground">Igreja</dt>
                    <dd className="font-medium">
                      {pessoa.igreja_nome || "—"}
                    </dd>
                  </div>
                ) : null}
                <div>
                  <dt className="text-xs text-muted-foreground">Sexo</dt>
                  <dd className="font-medium">
                    {pessoa.genero === "F"
                      ? "Irmã"
                      : pessoa.genero === "M"
                        ? "Irmão"
                        : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Situação</dt>
                  <dd className="font-medium">{pessoa.situacao || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Categoria</dt>
                  <dd className="font-medium">{pessoa.categoria || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Fonte</dt>
                  <dd className="font-medium">{pessoa.fonte.toUpperCase()}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Visto em</dt>
                  <dd className="font-medium">{pessoa.visto_em ?? "—"}</dd>
                </div>
              </dl>

              {pessoa.fonte === "icm" && igrejas.length > 0 ? (
                <>
                  <Separator />
                  <div className="space-y-1.5">
                    <Label htmlFor="igreja-pessoa">Vincular a igreja</Label>
                    <select
                      id="igreja-pessoa"
                      value={
                        pessoa.igreja_id === null
                          ? ""
                          : String(pessoa.igreja_id)
                      }
                      disabled={salvandoIgreja}
                      onChange={(e) => void trocarIgreja(e.target.value)}
                      className="h-9 w-full rounded-lg border bg-background px-2 text-sm"
                    >
                      <option value="">Sem igreja</option>
                      {igrejas.map((igreja) => (
                        <option key={igreja.id} value={String(igreja.id)}>
                          {igreja.nome}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs text-muted-foreground">
                      {salvandoIgreja
                        ? "Salvando..."
                        : "A igreja serve para organizar as vidas; não muda o disparo."}
                    </p>
                  </div>
                </>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MailQuestion className="size-4 text-brand" />
                SMS de aniversário
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {pessoa.excluido
                  ? "Esta vida não recebe o SMS de aniversário no grupo da Boa Vista."
                  : "Esta vida recebe o SMS de aniversário no grupo da Boa Vista."}
              </p>
              <Button
                variant={pessoa.excluido ? "default" : "outline"}
                className="w-full"
                onClick={() => void alternarSms()}
                disabled={salvandoSms}
              >
                {salvandoSms ? (
                  <Loader2 className="animate-spin" />
                ) : pessoa.excluido ? (
                  <Check />
                ) : (
                  <UserRoundX />
                )}
                {pessoa.excluido ? "Voltar a receber SMS" : "Não enviar SMS"}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function MembroPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          <Skeleton className="h-9 w-52" />
          <Skeleton className="h-28 w-full" />
        </div>
      }
    >
      <MembroConteudo />
    </Suspense>
  );
}
