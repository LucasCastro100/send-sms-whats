"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  CalendarDays,
  Check,
  ChevronDown,
  Loader2,
  Pencil,
  RefreshCw,
  Trash2,
  UsersRound,
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
  type Evento,
  type EventoParticipante,
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

const FORMULARIO_VAZIO = {
  nome: "",
  data: hojeIso(),
  local: "",
  descricao: "",
};

export default function EventosPage() {
  const { usuario } = useAuth();
  const [eventos, setEventos] = useState<Evento[] | null>(null);
  const [formulario, setFormulario] = useState(FORMULARIO_VAZIO);
  const [editando, setEditando] = useState<Evento | null>(null);
  const [salvando, setSalvando] = useState(false);

  const [expandido, setExpandido] = useState<number | null>(null);
  const [participantes, setParticipantes] = useState<
    Record<number, EventoParticipante[]>
  >({});
  const [carregandoParticipantes, setCarregandoParticipantes] = useState<
    number | null
  >(null);

  const carregar = useCallback(async () => {
    try {
      setEventos(await api.get<Evento[]>("/api/eventos"));
    } catch {
      setEventos([]);
    }
  }, []);

  useEffect(() => {
    if (usuario?.admin) void carregar();
  }, [carregar, usuario?.admin]);

  function limparFormulario() {
    setFormulario(FORMULARIO_VAZIO);
    setEditando(null);
  }

  function abrirEdicao(evento: Evento) {
    setEditando(evento);
    setFormulario({
      nome: evento.nome,
      data: evento.data_iso,
      local: evento.local,
      descricao: evento.descricao,
    });
  }

  async function salvar(eventoForm: React.FormEvent) {
    eventoForm.preventDefault();
    const nome = formulario.nome.trim();
    if (nome.length < 2) {
      toast.error("Dê um nome ao evento.");
      return;
    }
    if (!formulario.data) {
      toast.error("Informe a data do evento.");
      return;
    }

    setSalvando(true);
    try {
      const dados = {
        nome,
        data: formulario.data,
        local: formulario.local.trim(),
        descricao: formulario.descricao.trim(),
      };

      if (editando) {
        const atualizado = await api.patch<Evento>(
          `/api/eventos/${editando.id}`,
          dados,
        );
        setEventos((atual) =>
          (atual ?? [])
            .map((item) => (item.id === atualizado.id ? atualizado : item))
            .sort((a, b) => b.data_iso.localeCompare(a.data_iso)),
        );
        toast.success("Evento atualizado.");
      } else {
        const criado = await api.post<Evento>("/api/eventos", dados);
        setEventos((atual) =>
          [criado, ...(atual ?? [])].sort((a, b) =>
            b.data_iso.localeCompare(a.data_iso),
          ),
        );
        toast.success("Evento criado. Marque a participação na ficha da vida.");
      }
      limparFormulario();
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível salvar o evento."));
    } finally {
      setSalvando(false);
    }
  }

  async function excluir(evento: Evento) {
    if (
      !window.confirm(
        `Excluir o evento "${evento.nome}" e as participações dele?`,
      )
    ) {
      return;
    }
    try {
      await api.delete(`/api/eventos/${evento.id}`);
      setEventos((atual) =>
        (atual ?? []).filter((item) => item.id !== evento.id),
      );
      if (expandido === evento.id) setExpandido(null);
      toast.success("Evento excluído.");
    } catch (e) {
      toast.error(mensagemErro(e, "Não foi possível excluir o evento."));
    }
  }

  async function alternarParticipantes(evento: Evento) {
    if (expandido === evento.id) {
      setExpandido(null);
      return;
    }
    setExpandido(evento.id);
    if (participantes[evento.id]) return;

    setCarregandoParticipantes(evento.id);
    try {
      const lista = await api.get<EventoParticipante[]>(
        `/api/eventos/${evento.id}/participantes`,
      );
      setParticipantes((atual) => ({ ...atual, [evento.id]: lista }));
    } catch (e) {
      toast.error(
        mensagemErro(e, "Não foi possível carregar os participantes."),
      );
    } finally {
      setCarregandoParticipantes(null);
    }
  }

  if (!usuario?.admin) {
    return (
      <div className="space-y-6">
        <PageHeader
          sobretitulo="Administração"
          titulo="Eventos"
          descricao="Apenas administradores podem gerenciar os eventos."
        />
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            Você não tem permissão para acessar esta tela.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        sobretitulo="Administração"
        titulo="Eventos"
        descricao="Maanaim, encontros, retiros e outros eventos da igreja. Cada evento tem a sua data; a participação é marcada na ficha de cada vida."
      >
        <Button variant="outline" onClick={() => void carregar()}>
          <RefreshCw />
          Atualizar
        </Button>
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle>
            {editando ? `Editar ${editando.nome}` : "Novo evento"}
          </CardTitle>
          <CardDescription>
            {editando
              ? "Altere os dados e salve."
              : "Depois de criar, abra a ficha de cada vida em Membros para marcar quem participou."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={salvar} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-1.5">
                <Label htmlFor="evento-nome">Nome</Label>
                <Input
                  id="evento-nome"
                  value={formulario.nome}
                  placeholder="Ex.: Maanaim 2026"
                  maxLength={120}
                  onChange={(e) =>
                    setFormulario((atual) => ({
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
                  value={formulario.data}
                  onChange={(e) =>
                    setFormulario((atual) => ({
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
                  value={formulario.local}
                  placeholder="Opcional"
                  maxLength={160}
                  onChange={(e) =>
                    setFormulario((atual) => ({
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
                  value={formulario.descricao}
                  placeholder="Opcional"
                  maxLength={1000}
                  onChange={(e) =>
                    setFormulario((atual) => ({
                      ...atual,
                      descricao: e.target.value,
                    }))
                  }
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={salvando}>
                {salvando ? <Loader2 className="animate-spin" /> : <Check />}
                {editando ? "Salvar alterações" : "Criar evento"}
              </Button>
              {editando ? (
                <Button type="button" variant="ghost" onClick={limparFormulario}>
                  <X />
                  Cancelar
                </Button>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Eventos cadastrados</CardTitle>
          <CardDescription>
            Clique em participantes para ver quem foi e abrir a ficha da vida.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!eventos ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : eventos.length === 0 ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <CalendarDays className="size-4" />
              Nenhum evento cadastrado ainda.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Evento</TableHead>
                    <TableHead>Data</TableHead>
                    <TableHead>Local</TableHead>
                    <TableHead>Participantes</TableHead>
                    <TableHead className="w-28 text-right">
                      <span className="sr-only">Ações</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {eventos.map((evento) => (
                    <Fragment key={evento.id}>
                      <TableRow>
                        <TableCell className="max-w-72">
                          <p className="font-medium">{evento.nome}</p>
                          {evento.descricao ? (
                            <p className="truncate text-xs text-muted-foreground">
                              {evento.descricao}
                            </p>
                          ) : null}
                        </TableCell>
                        <TableCell>{evento.data}</TableCell>
                        <TableCell>
                          {evento.local || (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="gap-1.5"
                            onClick={() => void alternarParticipantes(evento)}
                          >
                            <UsersRound />
                            {evento.participantes}
                            <ChevronDown
                              className={cn(
                                "size-3.5 transition-transform",
                                expandido === evento.id && "rotate-180",
                              )}
                            />
                          </Button>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label={`Editar ${evento.nome}`}
                              onClick={() => abrirEdicao(evento)}
                            >
                              <Pencil />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label={`Excluir ${evento.nome}`}
                              className="text-muted-foreground hover:text-destructive"
                              onClick={() => void excluir(evento)}
                            >
                              <Trash2 />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>

                      {expandido === evento.id ? (
                        <TableRow>
                          <TableCell colSpan={5} className="bg-muted/30">
                            {carregandoParticipantes === evento.id ? (
                              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="size-4 animate-spin" />
                                Carregando participantes...
                              </p>
                            ) : (participantes[evento.id] ?? []).length === 0 ? (
                              <p className="text-sm text-muted-foreground">
                                Nenhuma vida marcada neste evento ainda.
                              </p>
                            ) : (
                              <div className="flex flex-wrap gap-1.5">
                                {(participantes[evento.id] ?? []).map(
                                  (participante) =>
                                    participante.pessoa_id > 0 ? (
                                      <Link
                                        key={participante.nome_chave}
                                        href={`/membros/${participante.pessoa_id}?fonte=icm`}
                                      >
                                        <Badge
                                          variant="outline"
                                          className="hover:border-brand/40 hover:text-brand"
                                        >
                                          {participante.nome}
                                        </Badge>
                                      </Link>
                                    ) : (
                                      <Badge
                                        key={participante.nome_chave}
                                        variant="outline"
                                      >
                                        {participante.nome}
                                      </Badge>
                                    ),
                                )}
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </Fragment>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
