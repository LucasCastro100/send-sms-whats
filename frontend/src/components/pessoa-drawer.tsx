"use client";

import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  CalendarDays,
  Cake,
  Check,
  HeartHandshake,
  Home,
  Loader2,
  MailQuestion,
  MapPin,
  Phone,
  Plus,
  Smartphone,
  Trash2,
  UserRoundX,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  classeDias,
  formatarTelefone,
  GraficoPresenca,
  ResumoPresenca,
  rotuloDias,
} from "@/components/pessoa-comum";
import {
  api,
  ApiError,
  type Igreja,
  type Oracao,
  type Pessoa,
  type PresencaHistorico,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  pessoa: Pessoa | null;
  igrejas?: Igreja[];
  onFechar: () => void;
  onAtualizada: (pessoa: Pessoa) => void;
};

export function PessoaDrawer({
  pessoa,
  igrejas = [],
  onFechar,
  onAtualizada,
}: Props) {
  const [registrando, setRegistrando] = useState(false);
  const [salvandoIgreja, setSalvandoIgreja] = useState(false);
  const [historico, setHistorico] = useState<PresencaHistorico | null>(null);
  const [carregandoHistorico, setCarregandoHistorico] = useState(false);
  const [oracoes, setOracoes] = useState<Oracao[]>([]);
  const [carregandoOracoes, setCarregandoOracoes] = useState(false);
  const [textoOracao, setTextoOracao] = useState("");
  const [salvandoOracao, setSalvandoOracao] = useState(false);
  const fecharRef = useRef<HTMLButtonElement>(null);
  const aberto = pessoa !== null;
  const pessoaId = pessoa?.id;
  const fonte = pessoa?.fonte;

  useEffect(() => {
    if (!aberto) return;

    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key === "Escape") onFechar();
    }

    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", aoTeclar);
    fecharRef.current?.focus();

    return () => {
      document.body.style.overflow = overflowAnterior;
      document.removeEventListener("keydown", aoTeclar);
    };
  }, [aberto, onFechar]);

  useEffect(() => {
    if (!pessoaId || fonte !== "icm") {
      setHistorico(null);
      setOracoes([]);
      return;
    }

    let ativo = true;
    setCarregandoHistorico(true);
    setCarregandoOracoes(true);

    api
      .get<PresencaHistorico>(`/api/presenca/pessoa/${pessoaId}?fonte=icm`)
      .then((dados) => {
        if (ativo) setHistorico(dados);
      })
      .catch(() => {
        if (ativo) setHistorico(null);
      })
      .finally(() => {
        if (ativo) setCarregandoHistorico(false);
      });

    api
      .get<Oracao[]>(`/api/oracoes?pessoa_id=${pessoaId}&fonte=icm`)
      .then((dados) => {
        if (ativo) setOracoes(dados);
      })
      .catch(() => {
        if (ativo) setOracoes([]);
      })
      .finally(() => {
        if (ativo) setCarregandoOracoes(false);
      });

    return () => {
      ativo = false;
    };
  }, [pessoaId, fonte]);

  if (!pessoa) return null;

  async function registrarVisita() {
    if (!pessoa) return;
    setRegistrando(true);
    try {
      const atualizada = await api.post<Pessoa>(
        `/api/pessoas/${pessoa.id}/visita`,
        { fonte: pessoa.fonte },
      );
      onAtualizada(atualizada);
      toast.success(`Visita de ${atualizada.nome.split(" ")[0]} registrada.`);
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível registrar a visita.",
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
      onAtualizada(atualizada);
      toast.success("Igreja atualizada.");
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível salvar a igreja.",
      );
    } finally {
      setSalvandoIgreja(false);
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
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível salvar o motivo.",
      );
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
        e instanceof ApiError ? e.message : "Não foi possível atualizar o motivo.",
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
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível excluir o motivo.",
      );
    }
  }

  const telefones = [
    { rotulo: "Celular", valor: pessoa.celular, Icone: Smartphone },
    { rotulo: "Residencial", valor: pessoa.tel_residencial, Icone: Home },
    { rotulo: "Comercial", valor: pessoa.tel_comercial, Icone: Phone },
  ].filter((telefone) => telefone.valor);

  const aniversario = pessoa.data
    ? `${pessoa.data}${pessoa.ano ? `/${pessoa.ano}` : ""}`
    : "Não informado";

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label={`Ficha de ${pessoa.nome}`}
    >
      <button
        type="button"
        aria-label="Fechar análise"
        onClick={onFechar}
        className="absolute inset-0 cursor-default bg-black/40 backdrop-blur-[2px] animate-in fade-in-0"
      />

      <aside className="relative flex h-full w-full max-w-md flex-col border-l bg-background shadow-2xl animate-in slide-in-from-right duration-200">
        <header className="flex items-start justify-between gap-3 border-b p-5">
          <div className="min-w-0 space-y-1">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Ficha da vida
            </p>
            <h2 className="truncate text-lg font-semibold">{pessoa.nome}</h2>
            <div className="flex flex-wrap gap-1.5 pt-1">
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
          </div>

          <Button
            ref={fecharRef}
            variant="ghost"
            size="icon-sm"
            onClick={onFechar}
            aria-label="Fechar"
          >
            <X />
          </Button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          <section className="space-y-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <Cake className="size-4 text-brand" />
              Aniversário
            </h3>
            <dl className="grid grid-cols-2 gap-3 text-sm">
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
            </dl>
          </section>

          <Separator />

          <section className="space-y-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <Phone className="size-4 text-brand" />
              Telefones
            </h3>
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
          </section>

          <Separator />

          <section className="space-y-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <MapPin className="size-4 text-brand" />
              Visitação
            </h3>
            <div className="rounded-lg border bg-muted/30 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs text-muted-foreground">Dias sem visita</p>
                  <p className="text-2xl font-semibold">
                    {pessoa.dias_sem_visita ?? "—"}
                  </p>
                </div>
                <Badge variant="outline" className={cn("h-6", classeDias(pessoa.dias_sem_visita))}>
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
              Registrar a visita zera o contador e a pessoa sai da frente da fila
              de visitação.
            </p>
          </section>

          {pessoa.fonte === "icm" ? (
            <>
              <Separator />

              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  <BookOpen className="size-4 text-brand" />
                  Presença
                </h3>

                {carregandoHistorico ? (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="size-4 animate-spin" />
                    Carregando o histórico...
                  </p>
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
                    <GraficoPresenca eventos={historico.eventos} />
                    <details className="rounded-lg border">
                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium">
                        Últimos lançamentos ({historico.eventos.length})
                      </summary>
                      <ul className="max-h-48 divide-y overflow-y-auto border-t text-xs">
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
              </section>

              <Separator />

              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  <HeartHandshake className="size-4 text-brand" />
                  Motivos de oração
                </h3>

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

                {carregandoOracoes ? (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="size-4 animate-spin" />
                    Carregando...
                  </p>
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
              </section>
            </>
          ) : null}

          <Separator />

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Cadastro</h3>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
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
              <div className="space-y-1.5">
                <Label htmlFor="igreja-pessoa">Vincular a igreja</Label>
                <select
                  id="igreja-pessoa"
                  value={pessoa.igreja_id === null ? "" : String(pessoa.igreja_id)}
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
            ) : null}
          </section>

          {!pessoa.telefone && !telefones.length ? (
            <p className="flex items-start gap-2 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
              <MailQuestion className="mt-0.5 size-4 shrink-0" />
              Sem telefone válido: o disparo automático não alcança esta pessoa.
            </p>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
