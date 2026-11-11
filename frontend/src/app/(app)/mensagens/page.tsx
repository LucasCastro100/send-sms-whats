"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarClock,
  Check,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Trash2,
  Users,
  X,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

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
  type Agendamento,
  type AgendamentosResposta,
  type Contato,
  type ContatosResposta,
  type DestinoMensagem,
  type DisparoAutomatico,
  type Grupo,
  type GruposResposta,
  type ResultadoEnvio,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type Aba = "grupos" | "contatos" | "numero";

const ABAS: { valor: Aba; rotulo: string }[] = [
  { valor: "grupos", rotulo: "Grupos" },
  { valor: "contatos", rotulo: "Contatos" },
  { valor: "numero", rotulo: "Número" },
];

const STATUS: Record<string, string> = {
  pendente: "Pendente",
  enviado: "Enviado",
  erro: "Erro",
  cancelado: "Cancelado",
  vazio: "Sem aniversariantes",
};

function formatarNumero(valor: string): string {
  const numeros = valor.replace(/\D/g, "");
  if (numeros.length === 13) {
    return `+${numeros.slice(0, 2)} (${numeros.slice(2, 4)}) ${numeros.slice(4, 9)}-${numeros.slice(9)}`;
  }
  if (numeros.length === 12) {
    return `+${numeros.slice(0, 2)} (${numeros.slice(2, 4)}) ${numeros.slice(4, 8)}-${numeros.slice(8)}`;
  }
  return numeros ? `+${numeros}` : "";
}

function daquiUmaHora(): string {
  const data = new Date(Date.now() + 60 * 60 * 1000);
  data.setMinutes(0, 0, 0);
  const dois = (numero: number) => String(numero).padStart(2, "0");
  return `${data.getFullYear()}-${dois(data.getMonth() + 1)}-${dois(data.getDate())}T${dois(data.getHours())}:${dois(data.getMinutes())}`;
}

function cortar(texto: string, limite = 70): string {
  return texto.length > limite ? `${texto.slice(0, limite)}…` : texto;
}

export default function MensagensPage() {
  const [texto, setTexto] = useState("");
  const [aba, setAba] = useState<Aba>("grupos");
  const [selecionados, setSelecionados] = useState<Record<string, DestinoMensagem>>(
    {},
  );

  const [grupos, setGrupos] = useState<Grupo[]>([]);
  const [contatos, setContatos] = useState<Contato[]>([]);
  const [sincronizando, setSincronizando] = useState(false);
  const [carregandoDestinos, setCarregandoDestinos] = useState(true);
  const [busca, setBusca] = useState("");

  const [numero, setNumero] = useState("");
  const [nomeNumero, setNomeNumero] = useState("");

  const [enviando, setEnviando] = useState(false);
  const [confirmandoEnvio, setConfirmandoEnvio] = useState(false);
  const [agendando, setAgendando] = useState(false);
  const [quando, setQuando] = useState(daquiUmaHora());

  const [agendamentos, setAgendamentos] = useState<AgendamentosResposta | null>(
    null,
  );
  const [cancelando, setCancelando] = useState<number | null>(null);

  const [automatico, setAutomatico] = useState<DisparoAutomatico | null>(null);
  const [disparandoAgora, setDisparandoAgora] = useState(false);
  const [confirmandoAuto, setConfirmandoAuto] = useState(false);

  const carregarDestinos = useCallback(async (forcar = false) => {
    setCarregandoDestinos(true);
    try {
      if (forcar) {
        await Promise.all([
          api.post("/api/whatsapp/grupos/sincronizar"),
          api.post("/api/whatsapp/contatos/sincronizar"),
        ]);
      }

      const [respostaGrupos, respostaContatos] = await Promise.all([
        api.get<GruposResposta>("/api/whatsapp/grupos"),
        api.get<ContatosResposta>("/api/whatsapp/contatos"),
      ]);

      setGrupos(respostaGrupos.grupos);
      setContatos(respostaContatos.contatos);
      setSincronizando(respostaGrupos.sincronizando || respostaContatos.sincronizando);

      if (respostaGrupos.erro) toast.error(`Grupos: ${respostaGrupos.erro}`);
      if (respostaContatos.erro) toast.error(`Contatos: ${respostaContatos.erro}`);
    } catch (e) {
      toast.error(
        e instanceof ApiError
          ? e.message
          : "Falha ao carregar grupos e contatos do WhatsApp.",
      );
    } finally {
      setCarregandoDestinos(false);
    }
  }, []);

  const carregarAgendamentos = useCallback(async () => {
    try {
      const dados = await api.get<AgendamentosResposta>("/api/mensagens/agendamentos");
      setAgendamentos(dados);
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Falha ao carregar os agendamentos.",
      );
    }
  }, []);

  const carregarAutomatico = useCallback(async () => {
    try {
      const dados = await api.get<DisparoAutomatico>("/api/mensagens/automatico");
      setAutomatico(dados);
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Falha ao consultar o disparo automático.",
      );
    }
  }, []);

  useEffect(() => {
    void carregarDestinos();
    void carregarAgendamentos();
    void carregarAutomatico();
  }, [carregarDestinos, carregarAgendamentos, carregarAutomatico]);

  // Enquanto a Evolution estiver sincronizando, consulta de novo.
  useEffect(() => {
    if (!sincronizando) return;
    const timer = setInterval(() => void carregarDestinos(false), 5000);
    return () => clearInterval(timer);
  }, [sincronizando, carregarDestinos]);

  const destinos = useMemo(() => Object.values(selecionados), [selecionados]);

  const termo = busca.trim().toLowerCase();

  const gruposFiltrados = useMemo(
    () =>
      grupos.filter((grupo) =>
        termo ? grupo.nome.toLowerCase().includes(termo) : true,
      ),
    [grupos, termo],
  );

  const contatosFiltrados = useMemo(
    () =>
      contatos.filter((contato) =>
        termo
          ? contato.nome.toLowerCase().includes(termo) ||
            contato.numero.toLowerCase().includes(termo)
          : true,
      ),
    [contatos, termo],
  );

  function alternar(destino: DestinoMensagem) {
    setSelecionados((atual) => {
      const proximo = { ...atual };
      if (proximo[destino.jid]) delete proximo[destino.jid];
      else proximo[destino.jid] = destino;
      return proximo;
    });
  }

  function marcarVisiveis() {
    setSelecionados((atual) => {
      const proximo = { ...atual };
      const lista = aba === "contatos" ? contatosFiltrados : gruposFiltrados;
      for (const item of lista) {
        proximo[item.jid] = { jid: item.jid, nome: item.nome };
      }
      return proximo;
    });
  }

  function limparSelecao() {
    setSelecionados({});
  }

  function adicionarNumero() {
    const digitos = numero.replace(/\D/g, "");
    if (!digitos) {
      toast.error("Digite o número com DDI e DDD.");
      return;
    }
    if (digitos.length < 10 || digitos.length > 15) {
      toast.error("Número incompleto. Use DDI + DDD + número (ex.: 5534999998888).");
      return;
    }

    const nome = nomeNumero.trim() || formatarNumero(digitos);
    setSelecionados((atual) => ({ ...atual, [digitos]: { jid: digitos, nome } }));
    setNumero("");
    setNomeNumero("");
    toast.success(`${nome} adicionado aos destinos.`);
  }

  async function enviar() {
    if (!texto.trim()) {
      toast.error("Escreva o texto da mensagem.");
      return;
    }
    if (destinos.length === 0) {
      toast.error("Escolha pelo menos um destino.");
      return;
    }

    setEnviando(true);
    try {
      const resposta = await api.post<ResultadoEnvio>("/api/mensagens/enviar", {
        texto,
        destinos,
      });

      if (resposta.falhas === 0) {
        toast.success(`Mensagem enviada para ${resposta.enviados} destino(s).`);
      } else {
        toast.warning(
          `${resposta.enviados} enviado(s), ${resposta.falhas} falha(s).`,
        );
        resposta.resultados
          .filter((item) => !item.ok)
          .slice(0, 3)
          .forEach((item) => toast.error(`${item.nome}: ${item.mensagem}`));
      }
      setConfirmandoEnvio(false);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Falha ao enviar.");
    } finally {
      setEnviando(false);
    }
  }

  async function agendar() {
    if (!texto.trim()) {
      toast.error("Escreva o texto da mensagem.");
      return;
    }
    if (destinos.length === 0) {
      toast.error("Escolha pelo menos um destino.");
      return;
    }
    if (!quando) {
      toast.error("Escolha a data e a hora do envio.");
      return;
    }

    const data = new Date(quando);
    if (Number.isNaN(data.getTime()) || data.getTime() <= Date.now()) {
      toast.error("Escolha um horário no futuro.");
      return;
    }

    setAgendando(true);
    try {
      const resposta = await api.post<{ total: number }>("/api/mensagens/agendar", {
        texto,
        destinos,
        quando: data.toISOString(),
      });
      toast.success(`${resposta.total} envio(s) agendado(s).`);
      setQuando(daquiUmaHora());
      await carregarAgendamentos();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Falha ao agendar.");
    } finally {
      setAgendando(false);
    }
  }

  async function cancelar(item: Agendamento) {
    setCancelando(item.id);
    try {
      await api.delete(`/api/mensagens/agendamentos/${item.id}`);
      toast.success("Agendamento cancelado.");
      await carregarAgendamentos();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Falha ao cancelar.");
    } finally {
      setCancelando(null);
    }
  }

  async function dispararAutomatico() {
    setDisparandoAgora(true);
    try {
      const resposta = await api.post<{
        executado: boolean;
        status: string;
        citados?: number;
        motivo?: string;
      }>("/api/mensagens/automatico/disparar");

      if (resposta.status === "enviado") {
        toast.success(
          `Disparo feito para ${resposta.citados} aniversariante(s).`,
        );
      } else {
        toast.info(resposta.motivo || "Nada para disparar agora.");
      }
      setConfirmandoAuto(false);
      await carregarAutomatico();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Falha no disparo automático.");
    } finally {
      setDisparandoAgora(false);
    }
  }

  const pendentes = agendamentos?.pendentes ?? [];
  const historico = agendamentos?.historico ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        sobretitulo="Comunicação"
        titulo="Mensagens"
        descricao="Envie um comunicado para grupos, contatos ou um número avulso — agora ou agendado."
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="size-4" />
            Conteúdo da mensagem
          </CardTitle>
          <CardDescription>
            O mesmo texto vai para todos os destinos selecionados.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <textarea
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Escreva aqui o aviso, comunicado ou lembrete..."
            className="min-h-40 w-full resize-y rounded-lg border bg-background p-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
          <p className="text-right text-xs text-muted-foreground">
            {texto.length}/4000
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="size-4" />
            Destinos
          </CardTitle>
          <CardDescription>
            {destinos.length === 0
              ? "Nenhum destino selecionado."
              : `${destinos.length} destino(s) selecionado(s).`}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {ABAS.map((item) => (
              <Button
                key={item.valor}
                variant={aba === item.valor ? "default" : "outline"}
                size="sm"
                onClick={() => setAba(item.valor)}
              >
                {item.rotulo}
              </Button>
            ))}

            <Button
              variant="outline"
              size="sm"
              className="ml-auto"
              onClick={() => void carregarDestinos(true)}
              disabled={carregandoDestinos}
            >
              <RefreshCw className={cn(carregandoDestinos && "animate-spin")} />
              Sincronizar WhatsApp
            </Button>
          </div>

          {aba !== "numero" ? (
            <>
              <div className="flex flex-wrap items-end gap-2">
                <div className="space-y-1.5">
                  <Label htmlFor="busca-destino">Buscar</Label>
                  <Input
                    id="busca-destino"
                    value={busca}
                    placeholder={aba === "grupos" ? "Nome do grupo" : "Nome ou número"}
                    className="w-56"
                    onChange={(e) => setBusca(e.target.value)}
                  />
                </div>
                <Button variant="outline" size="sm" onClick={marcarVisiveis}>
                  <Check />
                  Marcar visíveis
                </Button>
                <Button variant="ghost" size="sm" onClick={limparSelecao}>
                  Limpar seleção
                </Button>
              </div>

              <div className="max-h-72 divide-y overflow-y-auto rounded-lg border">
                {carregandoDestinos && grupos.length === 0 && contatos.length === 0 ? (
                  <div className="space-y-2 p-3">
                    <Skeleton className="h-6 w-full" />
                    <Skeleton className="h-6 w-full" />
                    <Skeleton className="h-6 w-full" />
                  </div>
                ) : (aba === "grupos" ? gruposFiltrados : contatosFiltrados).length ===
                  0 ? (
                  <p className="p-3 text-sm text-muted-foreground">
                    {sincronizando
                      ? "Sincronizando com o WhatsApp..."
                      : "Nada encontrado. Clique em “Sincronizar WhatsApp”."}
                  </p>
                ) : aba === "grupos" ? (
                  gruposFiltrados.map((grupo) => (
                    <label
                      key={grupo.jid}
                      className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50"
                    >
                      <input
                        type="checkbox"
                        className="size-4 accent-primary"
                        checked={Boolean(selecionados[grupo.jid])}
                        onChange={() => alternar({ jid: grupo.jid, nome: grupo.nome })}
                      />
                      <span className="truncate">{grupo.nome}</span>
                    </label>
                  ))
                ) : (
                  contatosFiltrados.map((contato) => (
                    <label
                      key={contato.jid}
                      className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2 text-sm hover:bg-muted/50"
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        <input
                          type="checkbox"
                          className="size-4 accent-primary"
                          checked={Boolean(selecionados[contato.jid])}
                          onChange={() =>
                            alternar({ jid: contato.jid, nome: contato.nome })
                          }
                        />
                        <span className="truncate">{contato.nome}</span>
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {contato.numero}
                      </span>
                    </label>
                  ))
                )}
              </div>
            </>
          ) : (
            <div className="flex flex-wrap items-end gap-2">
              <div className="space-y-1.5">
                <Label htmlFor="numero">Número (DDI + DDD)</Label>
                <Input
                  id="numero"
                  value={numero}
                  placeholder="+55 34 99999-9999"
                  className="w-52"
                  onChange={(e) => setNumero(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") adicionarNumero();
                  }}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="nome-numero">Nome (opcional)</Label>
                <Input
                  id="nome-numero"
                  value={nomeNumero}
                  placeholder="Ex: João"
                  className="w-44"
                  onChange={(e) => setNomeNumero(e.target.value)}
                />
              </div>
              <Button variant="outline" onClick={adicionarNumero}>
                <Plus />
                Adicionar
              </Button>
            </div>
          )}

          {destinos.length > 0 ? (
            <div className="space-y-2">
              <Separator />
              <p className="text-sm font-medium">Selecionados</p>
              <div className="flex flex-wrap gap-2">
                {destinos.map((destino) => (
                  <span
                    key={destino.jid}
                    className="flex items-center gap-1 rounded-lg border bg-muted/40 px-2 py-1 text-xs"
                  >
                    {destino.nome}
                    <button
                      type="button"
                      aria-label={`Remover ${destino.nome}`}
                      className="text-muted-foreground hover:text-foreground"
                      onClick={() => alternar(destino)}
                    >
                      <X className="size-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Send className="size-4" />
            Enviar
          </CardTitle>
          <CardDescription>
            Envie agora ou escolha data e hora (horário de Brasília).
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {confirmandoEnvio ? (
              <>
                <Button onClick={() => void enviar()} disabled={enviando}>
                  {enviando ? <Loader2 className="animate-spin" /> : <Send />}
                  {enviando ? "Enviando..." : `Confirmar envio (${destinos.length})`}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => setConfirmandoEnvio(false)}
                  disabled={enviando}
                >
                  Cancelar
                </Button>
              </>
            ) : (
              <Button
                onClick={() => setConfirmandoEnvio(true)}
                disabled={!texto.trim() || destinos.length === 0}
              >
                <Send />
                Enviar agora
              </Button>
            )}
          </div>

          <Separator />

          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1.5">
              <Label htmlFor="quando">Data e hora</Label>
              <Input
                id="quando"
                type="datetime-local"
                value={quando}
                className="w-56"
                onChange={(e) => setQuando(e.target.value)}
              />
            </div>
            <Button
              variant="outline"
              onClick={() => void agendar()}
              disabled={agendando || !texto.trim() || destinos.length === 0}
            >
              {agendando ? <Loader2 className="animate-spin" /> : <CalendarClock />}
              {agendando ? "Agendando..." : "Agendar envio"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock className="size-4" />
            Agendamentos
          </CardTitle>
          <CardDescription>
            {pendentes.length === 0
              ? "Nenhum envio pendente."
              : `${pendentes.length} envio(s) pendente(s).`}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Destino</TableHead>
                  <TableHead>Quando</TableHead>
                  <TableHead>Mensagem</TableHead>
                  <TableHead className="text-right">Ação</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendentes.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={4}
                      className="text-sm text-muted-foreground"
                    >
                      Nada agendado no momento.
                    </TableCell>
                  </TableRow>
                ) : (
                  pendentes.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="max-w-56 truncate font-medium">
                        {item.nome}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {item.quando}
                      </TableCell>
                      <TableCell className="max-w-72 truncate text-xs text-muted-foreground">
                        {cortar(item.texto)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void cancelar(item)}
                          disabled={cancelando === item.id}
                        >
                          {cancelando === item.id ? (
                            <Loader2 className="animate-spin" />
                          ) : (
                            <Trash2 />
                          )}
                          Cancelar
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {historico.length > 0 ? (
            <details className="rounded-lg border">
              <summary className="cursor-pointer px-3 py-2 text-sm font-medium">
                Histórico ({historico.length})
              </summary>
              <div className="overflow-x-auto border-t">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Destino</TableHead>
                      <TableHead>Quando</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Resultado</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {historico.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="max-w-56 truncate">
                          {item.nome}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {item.quando}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {STATUS[item.status] ?? item.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-72 truncate text-xs text-muted-foreground">
                          {item.resultado || "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </details>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="size-4" />
            Disparo automático dos aniversariantes
          </CardTitle>
          <CardDescription>
            {automatico
              ? automatico.ativo
                ? `Todos os dias às ${String(automatico.hora).padStart(2, "0")}:${String(automatico.minuto).padStart(2, "0")} (Brasília), a partir da tabela ${automatico.fonte.toUpperCase()}, pela instância ${automatico.instancia}.`
                : "Desativado. Defina DISPARO_AUTOMATICO=true no backend."
              : "Consultando..."}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {automatico ? (
            <>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-muted-foreground">Destino:</span>
                <span className="font-medium">
                  {automatico.destino.nome || "não configurado"}
                </span>
                {automatico.destino.jid ? (
                  <span className="text-xs text-muted-foreground">
                    {automatico.destino.jid}
                  </span>
                ) : null}
              </div>

              {confirmandoAuto ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    onClick={() => void dispararAutomatico()}
                    disabled={disparandoAgora}
                  >
                    {disparandoAgora ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Zap />
                    )}
                    {disparandoAgora ? "Disparando..." : "Confirmar disparo"}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => setConfirmandoAuto(false)}
                    disabled={disparandoAgora}
                  >
                    Cancelar
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  onClick={() => setConfirmandoAuto(true)}
                  disabled={!automatico.ativo}
                >
                  <Zap />
                  Disparar os aniversariantes de hoje agora
                </Button>
              )}

              <div className="overflow-x-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Dia</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Citados</TableHead>
                      <TableHead>Resultado</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {automatico.ultimos.length === 0 ? (
                      <TableRow>
                        <TableCell
                          colSpan={4}
                          className="text-sm text-muted-foreground"
                        >
                          Nenhum disparo registrado ainda.
                        </TableCell>
                      </TableRow>
                    ) : (
                      automatico.ultimos.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell className="text-xs text-muted-foreground">
                            {item.data}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {STATUS[item.status] ?? item.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs">{item.citados}</TableCell>
                          <TableCell className="max-w-72 truncate text-xs text-muted-foreground">
                            {item.resultado || "—"}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </>
          ) : (
            <Skeleton className="h-20 w-full" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
