"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Check,
  KeyRound,
  Loader2,
  Plus,
  RefreshCw,
  UserCheck,
  UserX,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";
import { PasswordInput } from "@/components/password-input";
import { StatusWhatsApp } from "@/components/status-whatsapp";
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
  type Funcao,
  type GrupoAssistencia,
  type UsuarioLista,
} from "@/lib/api";
import {
  errosPorCampo,
  senhaSchema,
  usuarioNovoSchema,
} from "@/lib/schemas";

const ROTULO_FUNCAO: Record<Funcao, string> = {
  admin: "Administrador",
  lider: "Líder de grupo",
  frente: "Senhora de frente",
};

const AJUDA_FUNCAO: Record<Funcao, string> = {
  admin: "Vê todos os grupos e gerencia os usuários.",
  lider: "Vê apenas o grupo de assistência vinculado.",
  frente:
    "Grupo de Senhoras: vê todas as mulheres. O corte de 15+ entra quando a idade estiver na base.",
};

const FUNCOES: Funcao[] = ["admin", "lider", "frente"];

export default function UsuariosPage() {
  const { usuario } = useAuth();
  const [usuarios, setUsuarios] = useState<UsuarioLista[] | null>(null);
  const [grupos, setGrupos] = useState<GrupoAssistencia[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState<number | null>(null);

  // Formulário de novo usuário
  const [nome, setNome] = useState("");
  const [usuarioNovo, setUsuarioNovo] = useState("");
  const [senha, setSenha] = useState("");
  const [funcao, setFuncao] = useState<Funcao>("lider");
  const [grupoId, setGrupoId] = useState("");
  const [criando, setCriando] = useState(false);
  const [erros, setErros] = useState<Record<string, string>>({});

  // Redefinição de senha na própria linha
  const [senhaDe, setSenhaDe] = useState<number | null>(null);
  const [senhaNova, setSenhaNova] = useState("");
  const [salvandoSenha, setSalvandoSenha] = useState(false);

  const carregar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCarregando(true);
    try {
      const [lista, gruposApi] = await Promise.all([
        api.get<UsuarioLista[]>("/api/usuarios"),
        api.get<GrupoAssistencia[]>("/api/grupos-assistencia"),
      ]);
      setUsuarios(lista);
      setGrupos(gruposApi);
    } catch (e) {
      if (!silencioso) {
        toast.error(
          e instanceof ApiError ? e.message : "Falha ao carregar os usuários.",
        );
      }
    } finally {
      if (!silencioso) setCarregando(false);
    }
  }, []);

  useEffect(() => {
    if (usuario?.admin) void carregar();
  }, [carregar, usuario?.admin]);

  function limparErro(campo: string) {
    setErros((atuais) => {
      if (!atuais[campo]) return atuais;
      const proximos = { ...atuais };
      delete proximos[campo];
      return proximos;
    });
  }

  async function criar(evento: React.FormEvent) {
    evento.preventDefault();

    const validacao = usuarioNovoSchema.safeParse({
      nome,
      usuario: usuarioNovo,
      senha,
      funcao,
      grupo_id: grupoId ? Number(grupoId) : null,
    });
    if (!validacao.success) {
      setErros(errosPorCampo(validacao.error));
      return;
    }

    setErros({});
    setCriando(true);
    try {
      const criado = await api.post<UsuarioLista>(
        "/api/usuarios",
        validacao.data,
      );
      setUsuarios((atual) =>
        [...(atual ?? []), criado].sort((a, b) =>
          a.nome.localeCompare(b.nome, "pt-BR"),
        ),
      );
      setNome("");
      setUsuarioNovo("");
      setSenha("");
      setFuncao("lider");
      setGrupoId("");
      toast.success(`Usuário ${criado.nome} criado.`);
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Falha ao criar o usuário.",
      );
    } finally {
      setCriando(false);
    }
  }

  async function alterar(
    alvo: UsuarioLista,
    dados: { funcao?: Funcao; grupo_id?: number | null; ativo?: boolean },
  ) {
    setSalvando(alvo.id);
    try {
      const atualizado = await api.patch<UsuarioLista>(
        `/api/usuarios/${alvo.id}`,
        dados,
      );
      setUsuarios((atual) =>
        (atual ?? []).map((item) =>
          item.id === atualizado.id ? atualizado : item,
        ),
      );
      toast.success("Usuário atualizado.");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Falha ao atualizar.");
    } finally {
      setSalvando(null);
    }
  }

  async function salvarSenha(alvo: UsuarioLista) {
    const validacao = senhaSchema.safeParse({ senha: senhaNova });
    if (!validacao.success) {
      toast.error(validacao.error.issues[0]?.message ?? "Senha inválida.");
      return;
    }

    setSalvandoSenha(true);
    try {
      await api.patch<UsuarioLista>(`/api/usuarios/${alvo.id}`, validacao.data);
      setSenhaDe(null);
      setSenhaNova("");
      toast.success(`Senha de ${alvo.nome} atualizada.`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Falha ao salvar a senha.");
    } finally {
      setSalvandoSenha(false);
    }
  }

  const grupoSelecionado = grupos.find((grupo) => String(grupo.id) === grupoId);

  if (!usuario?.admin) {
    return (
      <div className="space-y-6">
        <PageHeader
          sobretitulo="Administração"
          titulo="Usuários"
          descricao="Apenas administradores podem gerenciar as contas."
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
        titulo="Usuários"
        descricao="Cadastre as pessoas, defina a função e o grupo de assistência de cada uma."
      >
        <Button
          variant="outline"
          onClick={() => void carregar()}
          disabled={carregando}
        >
          <RefreshCw className={carregando ? "animate-spin" : ""} />
          Atualizar
        </Button>
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle>Novo usuário</CardTitle>
          <CardDescription>
            O admin cria a conta; a pessoa entra com o e-mail/usuário e a senha
            definidos aqui.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={criar} noValidate className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="novo-nome">Nome</Label>
                <Input
                  id="novo-nome"
                  autoComplete="off"
                  value={nome}
                  aria-invalid={Boolean(erros.nome)}
                  onChange={(e) => {
                    setNome(e.target.value);
                    limparErro("nome");
                  }}
                  placeholder="Maria da Silva"
                />
                {erros.nome ? (
                  <p className="text-xs text-destructive">{erros.nome}</p>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label htmlFor="novo-usuario">E-mail ou usuário</Label>
                <Input
                  id="novo-usuario"
                  autoComplete="off"
                  value={usuarioNovo}
                  aria-invalid={Boolean(erros.usuario)}
                  onChange={(e) => {
                    setUsuarioNovo(e.target.value);
                    limparErro("usuario");
                  }}
                  placeholder="maria@email.com"
                />
                {erros.usuario ? (
                  <p className="text-xs text-destructive">{erros.usuario}</p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Letras, números, ponto, hífen, underline e @.
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="novo-senha">Senha inicial</Label>
                <PasswordInput
                  id="novo-senha"
                  autoComplete="new-password"
                  value={senha}
                  aria-invalid={Boolean(erros.senha)}
                  onChange={(e) => {
                    setSenha(e.target.value);
                    limparErro("senha");
                  }}
                  placeholder="mínimo 6 caracteres"
                />
                {erros.senha ? (
                  <p className="text-xs text-destructive">{erros.senha}</p>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label htmlFor="novo-funcao">Função</Label>
                <select
                  id="novo-funcao"
                  value={funcao}
                  onChange={(e) => {
                    setFuncao(e.target.value as Funcao);
                    limparErro("funcao");
                  }}
                  className="h-9 w-full rounded-xl border border-input bg-background px-3 text-sm"
                >
                  {FUNCOES.map((valor) => (
                    <option key={valor} value={valor}>
                      {ROTULO_FUNCAO[valor]}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">
                  {AJUDA_FUNCAO[funcao]}
                </p>
              </div>

              {funcao === "lider" ? (
                <div className="space-y-2">
                  <Label htmlFor="novo-grupo">Grupo de assistência</Label>
                  <select
                    id="novo-grupo"
                    value={grupoId}
                    aria-invalid={Boolean(erros.grupo_id)}
                    onChange={(e) => {
                      setGrupoId(e.target.value);
                      limparErro("grupo_id");
                    }}
                    className="h-9 w-full rounded-xl border border-input bg-background px-3 text-sm"
                  >
                    <option value="">Escolha o grupo</option>
                    {grupos.map((grupo) => (
                      <option key={grupo.id} value={grupo.id}>
                        {grupo.nome}
                      </option>
                    ))}
                  </select>
                  {erros.grupo_id ? (
                    <p className="text-xs text-destructive">{erros.grupo_id}</p>
                  ) : null}
                </div>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={criando}>
                {criando ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <Plus />
                )}
                {criando ? "Criando..." : "Criar usuário"}
              </Button>
              {funcao === "lider" && grupoSelecionado ? (
                <span className="text-xs text-muted-foreground">
                  O líder verá apenas as pessoas de{" "}
                  <strong>{grupoSelecionado.nome}</strong>.
                </span>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Contas cadastradas</CardTitle>
          <CardDescription>
            {usuarios ? `${usuarios.length} usuário(s)` : "Carregando..."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {carregando && !usuarios ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Usuário</TableHead>
                    <TableHead>Instância</TableHead>
                    <TableHead>WhatsApp</TableHead>
                    <TableHead>Função</TableHead>
                    <TableHead>Grupo</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(usuarios ?? []).map((item) => {
                    const eu = item.id === usuario?.id;
                    const ocupado = salvando === item.id;
                    const editandoSenha = senhaDe === item.id;

                    return (
                      <TableRow key={item.id}>
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="font-medium">
                              {item.nome}
                              {eu ? (
                                <span className="ml-1 text-xs text-muted-foreground">
                                  (você)
                                </span>
                              ) : null}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {item.usuario} · desde {item.criado_em}
                            </span>
                            <div className="mt-1 flex gap-1">
                              {!item.ativo ? (
                                <Badge variant="outline">inativo</Badge>
                              ) : null}
                              <Badge variant="outline">
                                {ROTULO_FUNCAO[item.funcao]}
                              </Badge>
                            </div>
                          </div>
                        </TableCell>

                        <TableCell className="text-xs">
                          {item.instancia}
                        </TableCell>

                        <TableCell>
                          <div className="flex flex-col gap-1 text-xs">
                            <StatusWhatsApp estado={item.whatsapp.estado} />
                            <span>{item.whatsapp.perfil || "—"}</span>
                            <span className="text-muted-foreground">
                              {item.whatsapp.numero || "—"}
                            </span>
                          </div>
                        </TableCell>

                        <TableCell>
                          <select
                            value={item.funcao}
                            disabled={ocupado || eu}
                            onChange={(e) =>
                              void alterar(item, {
                                funcao: e.target.value as Funcao,
                              })
                            }
                            className="h-8 rounded-lg border border-input bg-background px-2 text-xs"
                            aria-label={`Função de ${item.nome}`}
                          >
                            {FUNCOES.map((valor) => (
                              <option key={valor} value={valor}>
                                {ROTULO_FUNCAO[valor]}
                              </option>
                            ))}
                          </select>
                        </TableCell>

                        <TableCell>
                          {item.funcao === "lider" ? (
                            <select
                              value={item.grupo_id ?? ""}
                              disabled={ocupado}
                              onChange={(e) =>
                                void alterar(item, {
                                  grupo_id: e.target.value
                                    ? Number(e.target.value)
                                    : null,
                                })
                              }
                              className="h-8 max-w-52 rounded-lg border border-input bg-background px-2 text-xs"
                              aria-label={`Grupo de ${item.nome}`}
                            >
                              <option value="">Sem grupo</option>
                              {grupos.map((grupo) => (
                                <option key={grupo.id} value={grupo.id}>
                                  {grupo.nome}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              {item.funcao === "admin"
                                ? "Todos os grupos"
                                : "Grupo de Senhoras"}
                            </span>
                          )}
                        </TableCell>

                        <TableCell>
                          {editandoSenha ? (
                            <div className="flex items-center justify-end gap-1">
                              <PasswordInput
                                autoFocus
                                value={senhaNova}
                                onChange={(e) => setSenhaNova(e.target.value)}
                                placeholder="Nova senha"
                                className="h-8 w-40 text-xs"
                              />
                              <Button
                                size="icon-sm"
                                variant="outline"
                                disabled={salvandoSenha}
                                onClick={() => void salvarSenha(item)}
                                aria-label="Salvar senha"
                              >
                                {salvandoSenha ? (
                                  <Loader2 className="animate-spin" />
                                ) : (
                                  <Check />
                                )}
                              </Button>
                              <Button
                                size="icon-sm"
                                variant="ghost"
                                onClick={() => {
                                  setSenhaDe(null);
                                  setSenhaNova("");
                                }}
                                aria-label="Cancelar"
                              >
                                <X />
                              </Button>
                            </div>
                          ) : (
                            <div className="flex flex-wrap justify-end gap-1">
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={ocupado}
                                onClick={() => {
                                  setSenhaDe(item.id);
                                  setSenhaNova("");
                                }}
                              >
                                <KeyRound />
                                Senha
                              </Button>

                              <Button
                                variant={item.ativo ? "outline" : "default"}
                                size="sm"
                                disabled={ocupado || eu}
                                onClick={() =>
                                  void alterar(item, { ativo: !item.ativo })
                                }
                              >
                                {item.ativo ? <UserX /> : <UserCheck />}
                                {item.ativo ? "Desativar" : "Ativar"}
                              </Button>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
