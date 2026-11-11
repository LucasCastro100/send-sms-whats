"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Check,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";
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
import { api, ApiError, type Igreja } from "@/lib/api";

type Edicao = {
  nome: string;
  pastor_nome: string;
  pastor_whatsapp: string;
};

export default function IgrejasPage() {
  const { usuario } = useAuth();
  const [igrejas, setIgrejas] = useState<Igreja[] | null>(null);
  const [nome, setNome] = useState("");
  const [pastorNome, setPastorNome] = useState("");
  const [pastorWhatsapp, setPastorWhatsapp] = useState("");
  const [criando, setCriando] = useState(false);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [edicao, setEdicao] = useState<Edicao>({
    nome: "",
    pastor_nome: "",
    pastor_whatsapp: "",
  });
  const [salvando, setSalvando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setIgrejas(await api.get<Igreja[]>("/api/igrejas"));
    } catch {
      setIgrejas([]);
    }
  }, []);

  useEffect(() => {
    if (usuario?.admin) void carregar();
  }, [carregar, usuario?.admin]);

  async function criar(evento: React.FormEvent) {
    evento.preventDefault();
    const limpo = nome.trim();
    if (limpo.length < 2) {
      toast.error("O nome da igreja precisa ter pelo menos 2 letras.");
      return;
    }

    setCriando(true);
    try {
      const criada = await api.post<Igreja>("/api/igrejas", {
        nome: limpo,
        pastor_nome: pastorNome.trim(),
        pastor_whatsapp: pastorWhatsapp.trim(),
      });
      setIgrejas((atual) =>
        [...(atual ?? []), criada].sort((a, b) =>
          a.nome.localeCompare(b.nome, "pt-BR"),
        ),
      );
      setNome("");
      setPastorNome("");
      setPastorWhatsapp("");
      toast.success(`Igreja ${criada.nome} cadastrada.`);
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Falha ao cadastrar a igreja.",
      );
    } finally {
      setCriando(false);
    }
  }

  function abrirEdicao(igreja: Igreja) {
    setEditandoId(igreja.id);
    setEdicao({
      nome: igreja.nome,
      pastor_nome: igreja.pastor_nome,
      pastor_whatsapp: igreja.pastor_whatsapp,
    });
  }

  async function salvar(igreja: Igreja) {
    const limpo = edicao.nome.trim();
    if (limpo.length < 2) {
      toast.error("O nome da igreja precisa ter pelo menos 2 letras.");
      return;
    }

    setSalvando(true);
    try {
      const atualizada = await api.patch<Igreja>(
        `/api/igrejas/${igreja.id}`,
        {
          nome: limpo,
          pastor_nome: edicao.pastor_nome.trim(),
          pastor_whatsapp: edicao.pastor_whatsapp.trim(),
        },
      );
      setIgrejas((atual) =>
        (atual ?? [])
          .map((item) => (item.id === igreja.id ? atualizada : item))
          .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR")),
      );
      setEditandoId(null);
      toast.success("Igreja atualizada.");
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Falha ao atualizar a igreja.",
      );
    } finally {
      setSalvando(false);
    }
  }

  async function excluir(igreja: Igreja) {
    if (
      !window.confirm(
        `Excluir a igreja ${igreja.nome}? As vidas vinculadas precisam ser realocadas antes.`,
      )
    ) {
      return;
    }

    try {
      await api.delete(`/api/igrejas/${igreja.id}`);
      setIgrejas((atual) =>
        (atual ?? []).filter((item) => item.id !== igreja.id),
      );
      toast.success(`Igreja ${igreja.nome} excluída.`);
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Falha ao excluir a igreja.",
      );
    }
  }

  if (!usuario?.admin) {
    return (
      <div className="space-y-6">
        <PageHeader
          sobretitulo="Administração"
          titulo="Igrejas"
          descricao="Apenas administradores podem gerenciar o cadastro."
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
        titulo="Igrejas"
        descricao="Cadastre as igrejas, o pastor de cada uma e vincule as vidas na análise da pessoa."
      >
        <Button variant="outline" onClick={() => void carregar()}>
          <RefreshCw />
          Atualizar
        </Button>
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle>Nova igreja</CardTitle>
          <CardDescription>
            O pastor recebe o resumo de faltas das vidas vinculadas à igreja.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={criar} className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="nome">Nome</Label>
              <Input
                id="nome"
                value={nome}
                placeholder="Ex.: IGREJA BOA VISTA - ICM"
                className="w-72"
                onChange={(e) => setNome(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pastor-nome">Pastor</Label>
              <Input
                id="pastor-nome"
                value={pastorNome}
                placeholder="Nome do pastor"
                className="w-56"
                onChange={(e) => setPastorNome(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pastor-whatsapp">WhatsApp do pastor</Label>
              <Input
                id="pastor-whatsapp"
                value={pastorWhatsapp}
                placeholder="5534999998888"
                className="w-48"
                onChange={(e) => setPastorWhatsapp(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={criando}>
              {criando ? <Loader2 className="animate-spin" /> : <Plus />}
              Cadastrar
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Igrejas cadastradas</CardTitle>
          <CardDescription>
            Quantas vidas da lista ICM estão vinculadas a cada igreja.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!igrejas ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : igrejas.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhuma igreja cadastrada ainda.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nome</TableHead>
                    <TableHead>Pastor</TableHead>
                    <TableHead>WhatsApp do pastor</TableHead>
                    <TableHead>Vidas vinculadas</TableHead>
                    <TableHead className="w-28 text-right">
                      <span className="sr-only">Ações</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {igrejas.map((igreja) => (
                    <TableRow key={igreja.id}>
                      <TableCell className="font-medium">
                        {editandoId === igreja.id ? (
                          <Input
                            value={edicao.nome}
                            autoFocus
                            className="max-w-72"
                            onChange={(e) =>
                              setEdicao((atual) => ({
                                ...atual,
                                nome: e.target.value,
                              }))
                            }
                            onKeyDown={(e) => {
                              if (e.key === "Enter") void salvar(igreja);
                              if (e.key === "Escape") setEditandoId(null);
                            }}
                          />
                        ) : (
                          igreja.nome
                        )}
                      </TableCell>
                      <TableCell>
                        {editandoId === igreja.id ? (
                          <Input
                            value={edicao.pastor_nome}
                            placeholder="Nome do pastor"
                            className="max-w-56"
                            onChange={(e) =>
                              setEdicao((atual) => ({
                                ...atual,
                                pastor_nome: e.target.value,
                              }))
                            }
                          />
                        ) : (
                          (igreja.pastor_nome || "—")
                        )}
                      </TableCell>
                      <TableCell>
                        {editandoId === igreja.id ? (
                          <Input
                            value={edicao.pastor_whatsapp}
                            placeholder="5534999998888"
                            className="max-w-48"
                            onChange={(e) =>
                              setEdicao((atual) => ({
                                ...atual,
                                pastor_whatsapp: e.target.value,
                              }))
                            }
                          />
                        ) : igreja.pastor_whatsapp ? (
                          <span className="text-sm">
                            {igreja.pastor_whatsapp}
                          </span>
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            sem contato
                          </span>
                        )}
                      </TableCell>
                      <TableCell>{igreja.total}</TableCell>
                      <TableCell className="text-right">
                        {editandoId === igreja.id ? (
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label="Salvar"
                              disabled={salvando}
                              onClick={() => void salvar(igreja)}
                            >
                              {salvando ? (
                                <Loader2 className="animate-spin" />
                              ) : (
                                <Check />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label="Cancelar"
                              onClick={() => setEditandoId(null)}
                            >
                              <X />
                            </Button>
                          </div>
                        ) : (
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label="Editar"
                              onClick={() => abrirEdicao(igreja)}
                            >
                              <Pencil />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label="Excluir"
                              className="text-muted-foreground hover:text-destructive"
                              disabled={igreja.total > 0}
                              onClick={() => void excluir(igreja)}
                            >
                              <Trash2 />
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
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
