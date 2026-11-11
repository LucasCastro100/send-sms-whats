export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const resposta = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });

  const texto = await resposta.text();
  let dados: unknown = null;
  if (texto) {
    try {
      dados = JSON.parse(texto);
    } catch {
      dados = null;
    }
  }

  if (!resposta.ok) {
    const detalhe =
      dados && typeof dados === "object" && "detail" in dados
        ? String((dados as { detail: unknown }).detail)
        : `Erro ${resposta.status}`;
    throw new ApiError(detalhe, resposta.status);
  }

  return dados as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: "PATCH",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: "PUT",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
  postForm: <T>(path: string, form: FormData) =>
    apiFetch<T>(path, { method: "POST", body: form }),
};

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------
export type Funcao = "admin" | "lider" | "frente";

export type GrupoAssistencia = {
  id: number;
  nome: string;
  responsavel_nome: string;
  responsavel_whatsapp: string;
};

export type Usuario = {
  id: number;
  nome: string;
  usuario: string;
  admin: boolean;
  funcao: Funcao;
  ativo: boolean;
  instancia: string;
  grupo_id: number | null;
  grupo_nome: string;
};

export type Resumo = {
  usuario: { nome: string; usuario: string; admin: boolean };
  usuarios?: { total: number; ativos: number };
  whatsapp: {
    instancia: string;
    estado: string;
    perfil: string;
    numero: string;
  };
};

export type EstadoWhatsApp = {
  instancia: string;
  estado: string;
  perfil: string;
  numero: string;
  jid?: string;
};

export type QrResposta = {
  instancia: string;
  estado: string;
  qr: string | null;
  codigo: string | null;
  perfil?: string;
  numero?: string;
};

export type Grupo = { nome: string; jid: string };
export type Contato = { jid: string; nome: string; numero: string };

export type GruposResposta = {
  total: number;
  grupos: Grupo[];
  sincronizando: boolean;
  erro: string | null;
  atualizado_em: number | null;
};

export type ContatosResposta = {
  total: number;
  contatos: Contato[];
  sincronizando: boolean;
  erro: string | null;
  atualizado_em: number | null;
};

export type UsuarioLista = Usuario & {
  criado_em: string;
  whatsapp: { estado: string; perfil: string; numero: string; jid: string };
};

// ---------------------------------------------------------------------------
// Pessoas e importação
// ---------------------------------------------------------------------------
export type Fonte = "icm" | "zoom";

export type Igreja = {
  id: number;
  nome: string;
  total: number;
  pastor_nome: string;
  pastor_whatsapp: string;
};

export type Pessoa = {
  id: number;
  fonte: string;
  nome: string;
  nome_chave: string;
  dia: number | null;
  mes: number | null;
  ano: number | null;
  data: string;
  mes_nome: string;
  idade: number | null;
  grupo: string;
  telefone: string;
  tel_residencial: string;
  tel_comercial: string;
  celular: string;
  situacao: string;
  categoria: string;
  genero: string | null;
  excluido: boolean;
  ativo: boolean;
  igreja_id: number | null;
  igreja_nome: string;
  visto_em: string | null;
  ultima_visita: string | null;
  dias_sem_visita: number | null;
};

export type Mudanca = { campo: string; de: string | number; para: string | number };

export type PreviewImportacao = {
  upload_id: string;
  arquivo: string;
  formato: string;
  fonte: string;
  mapeamento: Record<string, string>;
  avisos: string[];
  total_linhas: number;
  novos: {
    nome: string;
    data: string;
    grupo: string;
    telefone: string;
  }[];
  alterados: { id: number; nome: string; mudancas: Mudanca[] }[];
  iguais: { id: number; nome: string }[];
  ausentes: { id: number; nome: string; data: string; visto_em: string }[];
  conflitos: { nome: string; motivo: string }[];
  resumo: {
    novos: number;
    alterados: number;
    iguais: number;
    ausentes: number;
    conflitos: number;
  };
};

export type ConfirmacaoImportacao = {
  arquivo: string;
  fonte: string;
  importacao_id: number;
  novos: number;
  alterados: number;
  iguais: number;
  ausentes: number;
  conflitos: number;
};

export type ImportacaoHistorico = {
  id: number;
  arquivo: string;
  formato: string;
  fonte: string;
  usuario: string;
  inseridos: number;
  atualizados: number;
  iguais: number;
  ausentes: number;
  conflitos: number;
  criado_em: string;
};

export type AniversariantesDia = {
  fonte: string;
  dia: number;
  mes: number;
  data: string;
  mes_nome: string;
  destino: { jid: string; nome: string };
  pessoas: Pessoa[];
  citados: number;
  nao_citados: number;
  mensagem: string;
};

export type ResumoPessoas = Record<
  string,
  { total: number; ativos: number; excluidos: number; sem_genero: number }
>;

// ---------------------------------------------------------------------------
// Mensagens e agendamentos
// ---------------------------------------------------------------------------
export type DestinoMensagem = { jid: string; nome: string };

export type ResultadoEnvio = {
  enviados: number;
  falhas: number;
  resultados: { nome: string; jid: string; ok: boolean; mensagem: string }[];
};

export type Agendamento = {
  id: number;
  texto: string;
  destino: string;
  nome: string;
  quando: string;
  quando_iso: string;
  status: string;
  resultado: string;
  criado_em: string;
  executado_em: string;
};

export type AgendamentosResposta = {
  pendentes: Agendamento[];
  historico: Agendamento[];
};

export type DisparoAutomatico = {
  ativo: boolean;
  hora: number;
  minuto: number;
  fonte: string;
  instancia: string;
  destino: { jid: string; nome: string };
  ultimos: {
    id: number;
    data: string;
    fonte: string;
    destino: string;
    nome: string;
    citados: number;
    status: string;
    resultado: string;
    executado_em: string;
  }[];
};

// ---------------------------------------------------------------------------
// Presença
// ---------------------------------------------------------------------------
export type TipoPresenca = "culto" | "escola_biblica";

export type PresencaPessoa = {
  id: number;
  nome: string;
  nome_chave: string;
  grupo: string;
  igreja_id: number | null;
  igreja_nome: string;
  telefone: string;
  numero: string;
  numero_formatado: string;
  vinculado: boolean;
  falta: boolean;
  presente: boolean;
  participou: boolean;
  faltas_consecutivas: number;
  precisa_visita: boolean;
  contato_grupo: boolean;
  contato_igreja: boolean;
};

export type PresencaHistoricoDia = {
  dia: string;
  data: string;
  faltantes: number;
  participantes: number;
};

export type PresencaEstado = {
  dia: string;
  data: string;
  tipo: TipoPresenca;
  tipo_rotulo: string;
  conferido: boolean;
  limite_visita: number;
  mensagens: { falta: string; visita: string };
  grupos: string[];
  total: number;
  presentes: number;
  faltantes: number;
  participantes: number;
  com_numero: number;
  sem_numero: number;
  visitas_pendentes: number;
  pessoas: PresencaPessoa[];
  historico: PresencaHistoricoDia[];
  salvos?: number;
};

export type PresencaNumeroPessoa = {
  id: number;
  nome: string;
  nome_chave: string;
  grupo: string;
  telefone: string;
  numero: string;
  numero_formatado: string;
  vinculado: boolean;
};

export type PresencaNumeros = {
  total: number;
  com_numero: number;
  sem_numero: number;
  contatos_whats: number;
  sincronizando: boolean;
  erro: string | null;
  pessoas: PresencaNumeroPessoa[];
};

export type PresencaMensagens = {
  mensagens: { falta: string; visita: string };
  limite_visita: number;
  exemplo: {
    responsavel: string;
    nomes: string[];
    data: string;
    falta: string;
    visita: string;
  };
};

export type PresencaEnvioResultado = {
  destino: "grupo" | "igreja";
  referencia: string;
  responsavel: string;
  numero: string;
  ok: boolean;
  mensagem: string;
  nomes: string[];
  total: number;
};

export type PresencaEnvioSemContato = {
  destino: "grupo" | "igreja";
  referencia: string;
  responsavel: string;
  nomes: string[];
};

export type PresencaEnvio = {
  tipo: string;
  tipo_presenca: TipoPresenca;
  dia: string;
  enviados: number;
  falhas: number;
  sem_contato: PresencaEnvioSemContato[];
  resultados: PresencaEnvioResultado[];
};

// ---------------------------------------------------------------------------
// Histórico por vida
// ---------------------------------------------------------------------------
export type PresencaEvento = {
  dia: string;
  data: string;
  tipo: TipoPresenca;
  tipo_rotulo: string;
  presente: boolean;
  falta: boolean;
};

export type PresencaResumo = {
  total: number;
  presencas: number;
  faltas: number;
  percentual: number;
};

export type PresencaHistorico = {
  pessoa: {
    id: number;
    nome: string;
    grupo: string;
    igreja_id: number | null;
    igreja_nome: string;
  };
  limite: number;
  eventos: PresencaEvento[];
  resumo: {
    culto: PresencaResumo;
    escola_biblica: PresencaResumo;
    geral: PresencaResumo;
  };
  faltas: PresencaFalta[];
  sequencia: PresencaSequencia;
};

export type PresencaFalta = {
  dia: string;
  data: string;
  tipo: TipoPresenca;
  tipo_rotulo: string;
};

export type PresencaSequencia = {
  atual: number;
  inicio: string | null;
  inicio_data: string | null;
  limite: number;
  precisa_visita: boolean;
  visita_avisada_em: string | null;
};

// ---------------------------------------------------------------------------
// Relatório
// ---------------------------------------------------------------------------
export type RelatorioLancamento = {
  dia: string;
  data: string;
  tipo: TipoPresenca;
  tipo_rotulo: string;
  total: number;
  presentes: number;
  faltantes: number;
  percentual: number;
};

export type RelatorioPessoa = {
  id: number;
  nome: string;
  nome_chave: string;
  grupo: string;
  igreja_id: number | null;
  igreja_nome: string;
  presencas: number;
  faltas: number;
  total: number;
  percentual: number;
};

export type RelatorioPresenca = {
  de: string;
  ate: string;
  tipo: string;
  tipo_rotulo: string;
  resumo: {
    lancamentos: number;
    presentes: number;
    faltas: number;
    percentual: number;
  };
  lancamentos: RelatorioLancamento[];
  pessoas: RelatorioPessoa[];
};

// ---------------------------------------------------------------------------
// Motivos de oração
// ---------------------------------------------------------------------------
export type StatusOracao = "aberto" | "atendido";

export type Oracao = {
  id: number;
  pessoa_id: number;
  nome: string;
  nome_chave: string;
  texto: string;
  status: StatusOracao;
  criado_por: string;
  criado_em: string;
  atendido_em: string | null;
  grupo: string;
  igreja_id: number | null;
  igreja_nome: string;
};

// ---------------------------------------------------------------------------
// Eventos (Maanaim, encontros...) e observações da vida
// ---------------------------------------------------------------------------
export type Evento = {
  id: number;
  nome: string;
  data: string;
  data_iso: string;
  local: string;
  descricao: string;
  participantes: number;
  criado_por: string;
  criado_em: string;
  participa: boolean;
};

export type EventoParticipante = {
  pessoa_id: number;
  nome: string;
  nome_chave: string;
};

export type Observacao = {
  id: number;
  pessoa_id: number;
  nome: string;
  nome_chave: string;
  texto: string;
  criado_por: string;
  criado_em: string;
};
