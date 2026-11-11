"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Loader2, Pencil, RefreshCw, UsersRound, X } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, ApiError, type GrupoAssistencia } from "@/lib/api";

type Edicao = { nome: string; whatsapp: string };

export default function GruposPage() {
  const { usuario } = useAuth();
  const [grupos, setGrupos] = useState<GrupoAssistencia[] | null>(null);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [edicao, setEdicao] = useState<Edicao>({ nome: "", whatsapp: "" });
  const [salvando, setSalvando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setGrupos(await api.get<GrupoAssistencia[]>("/api/grupos-assistencia"));
    } catch {
      setGrupos([]);
    }
  }, []);

  useEffect(() => {
    if (usuario?.admin) void carregar();
  }, [carregar, usuario?.admin]);

  function abrirEdicao(grupo: GrupoAssistencia) {
    setEditandoId(grupo.id);
    setEdicao({
      nome: grupo.responsavel_nome,
      whatsapp: grupo.responsavel_whatsapp,
    });
  }

  async function salvar(grupo: GrupoAssistencia) {
    setSalvando(true);
    try {
      const atualizado = await api.patch<GrupoAssistencia>(
        `/api/grupos-assistencia/${grupo.id}`,
        {
          responsavel_nome: edicao.nome.trim(),
          responsavel_whatsapp: edicao.whatsapp.trim(),
        },
      );
      setGrupos((atual) =>
        (atual ?? []).map((item) =>
          item.id === grupo.id ? atualizado : item,
        ),
      );
      setEditandoId(null);
      toast.success("Responsável atualizado.");
    } catch (e) {
      toast.error(
        e instanceof ApiError
          ? e.message
          : "Falha ao salvar o responsável do grupo.",
      );
    } finally {
      setSalvando(false);
    }
  }

  if (!usuario?.admin) {
    return (
      <div className="space-y-6">
        <PageHeader
          sobretitulo="Administração"
          titulo="Grupos"
          descricao="Apenas administradores podem gerenciar os responsáveis."
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
        titulo="Grupos"
        descricao="Cadastre quem recebe o resumo de faltas e os avisos de visita de cada grupo de assistência."
      >
        <Button variant="outline" onClick={() => void carregar()}>
          <RefreshCw />
          Atualizar
        </Button>
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UsersRound className="size-4" />
            Grupos de assistência
          </CardTitle>
          <CardDescription>
            Os grupos vêm da coluna <strong>grupo</strong> da lista ICM. Aqui
            você só define o responsável de cada um.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!grupos ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : grupos.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhum grupo encontrado. Importe a lista ICM para criá-los.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Grupo</TableHead>
                    <TableHead>Responsável</TableHead>
                    <TableHead>WhatsApp do responsável</TableHead>
                    <TableHead className="w-28 text-right">
                      <span className="sr-only">Ações</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {grupos.map((grupo) => (
                    <TableRow key={grupo.id}>
                      <TableCell className="font-medium">{grupo.nome}</TableCell>
                      <TableCell>
                        {editandoId === grupo.id ? (
                          <Input
                            value={edicao.nome}
                            autoFocus
                            placeholder="Nome do responsável"
                            className="max-w-56"
                            onChange={(e) =>
                              setEdicao((atual) => ({
                                ...atual,
                                nome: e.target.value,
                              }))
                            }
                            onKeyDown={(e) => {
                              if (e.key === "Enter") void salvar(grupo);
                              if (e.key === "Escape") setEditandoId(null);
                            }}
                          />
                        ) : (
                          (grupo.responsavel_nome || "—")
                        )}
                      </TableCell>
                      <TableCell>
                        {editandoId === grupo.id ? (
                          <Input
                            value={edicao.whatsapp}
                            placeholder="5534999998888"
                            className="max-w-48"
                            onChange={(e) =>
                              setEdicao((atual) => ({
                                ...atual,
                                whatsapp: e.target.value,
                              }))
                            }
                          />
                        ) : grupo.responsavel_whatsapp ? (
                          <span className="text-sm">
                            {grupo.responsavel_whatsapp}
                          </span>
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            sem contato
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {editandoId === grupo.id ? (
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label="Salvar"
                              disabled={salvando}
                              onClick={() => void salvar(grupo)}
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
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label="Editar responsável"
                            onClick={() => abrirEdicao(grupo)}
                          >
                            <Pencil />
                          </Button>
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

      <Card>
        <CardHeader>
          <CardTitle>Como os avisos funcionam</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            Ao enviar as faltas, o responsável de cada grupo recebe{" "}
            <strong>uma mensagem com a lista</strong> das vidas do grupo que
            faltaram — nunca uma mensagem por vida.
          </p>
          <p>
            O pastor da igreja recebe o mesmo resumo consolidado das vidas
            vinculadas à igreja dele.
          </p>
          <p>
            Sem WhatsApp cadastrado, o grupo aparece como{" "}
            <strong>sem contato</strong> e nada é enviado.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
