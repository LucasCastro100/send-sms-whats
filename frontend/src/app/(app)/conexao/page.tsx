"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Loader2,
  LogOut,
  MessageSquare,
  QrCode,
  RefreshCw,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { StatusWhatsApp } from "@/components/status-whatsapp";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  api,
  ApiError,
  type Contato,
  type ContatosResposta,
  type EstadoWhatsApp,
  type Grupo,
  type GruposResposta,
  type QrResposta,
} from "@/lib/api";

type Lista = "grupos" | "contatos";

export default function ConexaoPage() {
  const [estado, setEstado] = useState<EstadoWhatsApp | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [codigo, setCodigo] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [conectando, setConectando] = useState(false);
  const [desconectando, setDesconectando] = useState(false);

  const [grupos, setGrupos] = useState<Grupo[] | null>(null);
  const [contatos, setContatos] = useState<Contato[] | null>(null);
  const [gruposEm, setGruposEm] = useState<number | null>(null);
  const [contatosEm, setContatosEm] = useState<number | null>(null);
  const [carregandoLista, setCarregandoLista] = useState<Lista | null>(null);
  const [busca, setBusca] = useState("");

  const estadoAnterior = useRef<string | null>(null);

  const atualizar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCarregando(true);
    try {
      const dados = await api.get<EstadoWhatsApp>("/api/whatsapp/estado");
      setEstado(dados);

      if (dados.estado === "open") {
        setQr(null);
        setCodigo(null);
        if (estadoAnterior.current === "connecting") {
          toast.success("WhatsApp conectado!");
        }
      }
      estadoAnterior.current = dados.estado;
    } catch (e) {
      if (!silencioso) {
        toast.error(e instanceof ApiError ? e.message : "Falha ao consultar o estado.");
      }
    } finally {
      if (!silencioso) setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void atualizar();
  }, [atualizar]);

  // Enquanto houver QR na tela, verifica o estado a cada 4 segundos.
  useEffect(() => {
    if (!qr) return;

    const timer = setInterval(() => void atualizar(true), 4000);
    return () => clearInterval(timer);
  }, [qr, atualizar]);

  async function conectar() {
    setConectando(true);
    try {
      const dados = await api.post<QrResposta>("/api/whatsapp/conectar");
      setQr(dados.qr);
      setCodigo(dados.codigo);

      if (dados.qr) {
        toast.info("Escaneie o QR Code no WhatsApp do seu celular.");
      } else if (dados.estado === "open") {
        toast.success("WhatsApp já está conectado.");
      } else {
        toast.warning("A Evolution não retornou um QR Code. Tente novamente.");
      }
      await atualizar(true);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Não foi possível conectar.");
    } finally {
      setConectando(false);
    }
  }

  async function desconectar() {
    setDesconectando(true);
    try {
      await api.post("/api/whatsapp/desconectar");
      toast.success("WhatsApp desconectado.");
      setQr(null);
      setCodigo(null);
      await atualizar(true);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Não foi possível desconectar.");
    } finally {
      setDesconectando(false);
    }
  }

  async function carregarLista(tipo: Lista, forcar = true) {
    setCarregandoLista(tipo);
    try {
      if (forcar) {
        await api.post(`/api/whatsapp/${tipo}/sincronizar`);
      }

      // A Evolution pode demorar; consultamos o progresso até terminar.
      for (let tentativa = 0; tentativa < 60; tentativa += 1) {
        const dados =
          tipo === "grupos"
            ? await api.get<GruposResposta>("/api/whatsapp/grupos")
            : await api.get<ContatosResposta>("/api/whatsapp/contatos");

        if (tipo === "grupos") {
          const resposta = dados as GruposResposta;
          if (resposta.grupos.length > 0) {
            setGrupos(resposta.grupos);
            setGruposEm(resposta.atualizado_em);
          }
          if (resposta.erro) {
            toast.error(resposta.erro);
            return;
          }
          if (!resposta.sincronizando) {
            toast.success(`${resposta.total} grupos carregados.`);
            return;
          }
        } else {
          const resposta = dados as ContatosResposta;
          if (resposta.contatos.length > 0) {
            setContatos(resposta.contatos);
            setContatosEm(resposta.atualizado_em);
          }
          if (resposta.erro) {
            toast.error(resposta.erro);
            return;
          }
          if (!resposta.sincronizando) {
            toast.success(`${resposta.total} contatos carregados.`);
            return;
          }
        }

        await new Promise((resolver) => setTimeout(resolver, 3000));
      }

      toast.warning(
        "A Evolution ainda está processando. Tente novamente em alguns instantes.",
      );
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Falha ao carregar a lista do WhatsApp.",
      );
    } finally {
      setCarregandoLista(null);
    }
  }

  const conectado = estado?.estado === "open";
  const termo = busca.trim().toLowerCase();

  const gruposFiltrados = (grupos ?? []).filter((grupo) =>
    termo ? grupo.nome.toLowerCase().includes(termo) : true,
  );
  const contatosFiltrados = (contatos ?? []).filter((contato) =>
    termo
      ? contato.nome.toLowerCase().includes(termo) ||
        contato.numero.toLowerCase().includes(termo)
      : true,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        sobretitulo="Integração"
        titulo="Conexão WhatsApp"
        descricao="Cada usuário conecta o seu próprio número."
      >
        <Button
          variant="outline"
          onClick={() => void atualizar()}
          disabled={carregando}
        >
          <RefreshCw className={carregando ? "animate-spin" : ""} />
          Atualizar
        </Button>
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <QrCode className="size-4" />
            Sessão atual
          </CardTitle>
          <CardDescription>
            {carregando || !estado ? (
              <Skeleton className="h-4 w-40" />
            ) : (
              <span className="flex flex-wrap items-center gap-2">
                <StatusWhatsApp estado={estado.estado} />
                <span>Instância {estado.instancia}</span>
              </span>
            )}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-5">
          <div className="grid gap-1 text-sm">
            <p>
              <span className="text-muted-foreground">Perfil: </span>
              {estado?.perfil || "—"}
            </p>
            <p>
              <span className="text-muted-foreground">Número: </span>
              {estado?.numero || "—"}
            </p>
          </div>

          <Separator />

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void conectar()} disabled={conectando || conectado}>
              {conectando ? <Loader2 className="animate-spin" /> : <QrCode />}
              {conectado ? "Já conectado" : "Conectar / gerar QR"}
            </Button>
            <Button
              variant="outline"
              onClick={() => void desconectar()}
              disabled={desconectando || !conectado}
            >
              {desconectando ? <Loader2 className="animate-spin" /> : <LogOut />}
              Desconectar
            </Button>
          </div>

          {qr ? (
            <div className="flex flex-col items-center gap-3 rounded-xl bg-muted/50 p-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={qr}
                alt="QR Code para conectar o WhatsApp"
                className="size-56 rounded-lg bg-white p-2"
              />
              <p className="text-center text-sm text-muted-foreground">
                Abra o WhatsApp → Aparelhos conectados → Conectar aparelho.
              </p>
              {codigo ? (
                <p className="text-xs text-muted-foreground">
                  Código de pareamento:{" "}
                  <span className="font-medium text-foreground">
                    {codigo}
                  </span>
                </p>
              ) : null}
              <p className="text-xs text-muted-foreground">
                O QR expira rápido. Se não funcionar, clique em “Conectar” de novo.
              </p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="size-4" />
            Grupos e contatos
          </CardTitle>
          <CardDescription>
            Puxados da sessão conectada da Evolution API. A busca roda em segundo
            plano, porque pode demorar.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() => void carregarLista("grupos")}
              disabled={!conectado || carregandoLista !== null}
            >
              {carregandoLista === "grupos" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Users />
              )}
              Carregar grupos
              {grupos ? (
                <span className="text-xs text-muted-foreground">({grupos.length})</span>
              ) : null}
            </Button>

            <Button
              variant="outline"
              onClick={() => void carregarLista("contatos")}
              disabled={!conectado || carregandoLista !== null}
            >
              {carregandoLista === "contatos" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <MessageSquare />
              )}
              Carregar contatos
              {contatos ? (
                <span className="text-xs text-muted-foreground">
                  ({contatos.length})
                </span>
              ) : null}
            </Button>
          </div>

          {!conectado ? (
            <p className="text-sm text-muted-foreground">
              Conecte o WhatsApp para listar grupos e contatos.
            </p>
          ) : null}

          {grupos || contatos ? (
            <Input
              placeholder="Filtrar por nome ou número..."
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
          ) : null}

          {grupos ? (
            <div className="space-y-1">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Grupos ({gruposFiltrados.length})
                {gruposEm ? (
                  <span className="ml-2 font-normal normal-case">
                    atualizado em{" "}
                    {new Date(gruposEm * 1000).toLocaleString("pt-BR")}
                  </span>
                ) : null}
              </p>
              <div className="max-h-64 overflow-y-auto rounded-lg border">
                {gruposFiltrados.length === 0 ? (
                  <p className="p-3 text-sm text-muted-foreground">
                    Nenhum grupo encontrado.
                  </p>
                ) : (
                  gruposFiltrados.map((grupo) => (
                    <div
                      key={grupo.jid}
                      className="flex items-center justify-between gap-3 border-b px-3 py-2 text-sm last:border-b-0"
                    >
                      <span className="truncate">{grupo.nome}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {grupo.jid}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : null}

          {contatos ? (
            <div className="space-y-1">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Contatos ({contatosFiltrados.length})
                {contatosEm ? (
                  <span className="ml-2 font-normal normal-case">
                    atualizado em{" "}
                    {new Date(contatosEm * 1000).toLocaleString("pt-BR")}
                  </span>
                ) : null}
              </p>
              <div className="max-h-64 overflow-y-auto rounded-lg border">
                {contatosFiltrados.length === 0 ? (
                  <p className="p-3 text-sm text-muted-foreground">
                    Nenhum contato encontrado.
                  </p>
                ) : (
                  contatosFiltrados.map((contato) => (
                    <div
                      key={contato.jid}
                      className="flex items-center justify-between gap-3 border-b px-3 py-2 text-sm last:border-b-0"
                    >
                      <span className="truncate">{contato.nome}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {contato.numero}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
