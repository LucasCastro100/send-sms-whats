# Check Birthday — painel web (FastAPI + Next.js)

Painel da igreja rodando com API FastAPI + SQLite e front em Next.js. O
Streamlit antigo foi removido; `core/` e `scripts/` continuam na raiz apenas
para o disparo manual de emergência do GitHub Actions.

- `backend/` — API FastAPI + SQLite (SQLModel), JWT em cookie `cb_session`
- `frontend/` — Next.js 15 (App Router) + Tailwind v4 + shadcn/ui
- `docker-compose.yml` — API + web no mesmo servidor, banco em volume

Telas: Painel, Aniversariantes, Membros, Mensagens, Presença, Relatórios,
Motivos de oração, Conexão WhatsApp, Grupos (admin), Importar planilhas
(admin), Igrejas (admin) e Usuários (admin).

## Rodar local (sem Docker)

### 1. API

```bash
cd backend
python3.9 -m venv .venv            # só na primeira vez
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

O banco fica em `backend/data/app.db` e é criado no primeiro start. Os
usuários iniciais vêm do `APP_USERS` do `.env` da raiz (mesmo formato do
Streamlit); sem ele, cria o admin `lucas` / `trocar123`.

### 2. Painel

```bash
cd frontend
pnpm install                       # só na primeira vez
echo "API_INTERNAL_URL=http://127.0.0.1:8000" > .env.local
pnpm dev
```

Abra <http://localhost:3000>. O Next faz proxy de `/api/*` para o FastAPI,
então não há CORS e o cookie funciona na mesma origem.

## Rodar com Docker

```bash
docker compose up --build
```

Sobe a API em `api:8000` e o painel em <http://localhost:3000>. O SQLite
fica no volume `cb-data` (`/data/app.db`). O `.env` da raiz é injetado nos
dois serviços.

Se a porta 3000 já estiver em uso, troque só a porta pública:

```bash
WEB_PORT=3100 docker compose up --build
```

> `API_INTERNAL_URL` é resolvido no build do Next (routes-manifest), por
> isso vai como build arg no `docker-compose.yml`.

## Endpoints principais

| Método | Rota | Quem pode |
| --- | --- | --- |
| POST | `/api/auth/login` | público |
| POST | `/api/auth/logout` | logado |
| GET | `/api/auth/me` | logado |
| GET | `/api/resumo` | logado |
| GET | `/api/whatsapp/estado` | logado |
| POST | `/api/whatsapp/conectar` | logado |
| POST | `/api/whatsapp/desconectar` | logado |
| GET/POST | `/api/whatsapp/grupos` e `/grupos/sincronizar` | logado |
| GET/POST | `/api/whatsapp/contatos` e `/contatos/sincronizar` | logado |
| GET/PATCH | `/api/pessoas`, `/api/pessoas/{id}` | logado (Zoom: admin) |
| POST | `/api/pessoas/{id}/visita` | logado (Zoom: admin) |
| GET | `/api/pessoas/resumo` | logado (Zoom: admin) |
| POST | `/api/importar/preview` e `/confirmar` | admin |
| GET | `/api/importar/historico` | admin |
| GET | `/api/aniversariantes/dia` | logado (Zoom: admin) |
| POST | `/api/aniversariantes/enviar` | logado (Zoom: admin) |
| POST | `/api/mensagens/enviar` e `/agendar` | logado |
| GET/DELETE | `/api/mensagens/agendamentos` | logado |
| GET | `/api/mensagens/automatico` | logado |
| POST | `/api/mensagens/automatico/disparar` | logado |
| GET/POST | `/api/presenca` e `/api/presenca/registrar` | logado |
| POST | `/api/presenca/faltas` | logado (compatibilidade) |
| POST | `/api/presenca/enviar` | logado |
| GET | `/api/presenca/relatorio` | logado |
| GET | `/api/presenca/pessoa/{id}` | logado (ICM) |
| GET/POST | `/api/presenca/numeros` e `/numeros/vincular` | logado |
| GET/PUT | `/api/presenca/mensagens` | logado |
| GET/POST | `/api/oracoes` | logado |
| PATCH/DELETE | `/api/oracoes/{id}` | logado |
| GET | `/api/grupos-assistencia` | logado |
| PATCH | `/api/grupos-assistencia/{id}` | admin |
| GET | `/api/igrejas` | logado |
| POST/PATCH/DELETE | `/api/igrejas` | admin |
| GET/POST | `/api/usuarios` | admin |
| PATCH | `/api/usuarios/{id}` | admin |

Documentação automática: <http://localhost:8000/docs>.

## Usuários, funções e grupos

Não existe cadastro público: o admin cria as contas em **Usuários** e define a
função de cada uma.

| Função | O que enxerga |
| --- | --- |
| `admin` | Todos os grupos, todas as telas e o cadastro de usuários |
| `lider` | Só o grupo de assistência vinculado (obrigatório no cadastro) |
| `frente` | Grupo de Senhoras: todas as mulheres, de todos os grupos |

Os grupos de assistência são sincronizados no start da API a partir do campo
`grupo` da tabela `icm` (`1- LUCAS / PAULO`, `2- VANDERLEY / JOSE ROBERTO`,
`3 - ANTONIO / FERNANDO`). Cada usuário tem no máximo um grupo (`users.grupo_id`).

O filtro por escopo vale para Aniversariantes, Membros, Presença, Relatórios
e Motivos de oração no ICM. A
lista do Zoom é exclusiva do admin (consulta, edição e disparo manual), assim
como as telas **Importar planilhas** e **Usuários**; o disparo diário e o envio
de mensagens seguem valendo para todos.

## Igrejas de origem das vidas

Cada vida da lista ICM pode ser vinculada a uma igreja (cadastro em
**Igrejas**, só admin; o primeiro start cria a `IGREJA BOA VISTA` e vincula a
ela as vidas que já estavam no banco). O vínculo é organizativo — não muda o
disparo, que segue mandando os aniversários do dia para o grupo configurado.

- A análise de cada vida tem o campo **Vincular a igreja** (troca e desvincula);
  a tela Aniversariantes tem filtro e coluna por igreja.
- Na importação dá para escolher a igreja do arquivo: vidas novas ficam
  vinculadas a ela e vidas que já têm igreja não são alteradas.
- Igreja com vidas vinculadas não pode ser excluída (realoque as vidas antes).
- O Zoom não tem vínculo com igreja.

Cada grupo de assistência tem um **responsável** (nome + WhatsApp) cadastrado
em **Grupos** (só admin). Cada igreja tem o **pastor** (nome + WhatsApp)
cadastrado em **Igrejas**. Esses contatos recebem os avisos de presença.

## Presença: culto e Escola Bíblica

A tela **Presença** lança a frequência em dois tipos: **Culto** e **Escola
Bíblica** (domingo). O tipo é escolhido no topo e cada dia fica registrado
separadamente por tipo.

- No culto, marca-se quem **faltou**.
- Na Escola Bíblica, marca-se quem **participou**; quem não for marcado entra
  como falta.
- A sequência de faltas que dispara o aviso de visita (`7` por padrão) conta
  **culto + Escola Bíblica**, em ordem cronológica.
- O dia fica registrado mesmo quando ninguém faltou (presença conferida).

Os avisos **não vão para a vida**: vão para o **responsável do grupo** e para
o **pastor da igreja**, em uma mensagem consolidada por grupo/igreja com a
lista de nomes. O envio usa os marcadores `{responsavel}`, `{nomes}`,
`{data}`, `{tipo}`, `{total}` e `{limite}`; os textos são editados na aba
**Mensagens** da própria tela. Destinos sem WhatsApp aparecem como aviso na
resposta.

## Membros, relatórios e motivos de oração

- **Membros** lista todas as vidas da fonte (ICM; Zoom só para admin) com
  filtros de busca, grupo, igreja e situação. Cada linha abre a **página da
  vida** em `/membros/{id}?fonte=icm|zoom` — sem drawer na tela Membros.
- A **página da vida** reúne contatos com link para o WhatsApp, aniversário e
  cadastro, visitação (dias sem visita, última visita e registrar), presença
  com resumo e gráfico de culto/Escola Bíblica, **faltas** (histórico e
  sequência atual unificada), **eventos** (Maanaim, encontros, retiros...),
  motivos de oração, **observações** e a marcação **Não enviar SMS**.
- **Eventos** têm nome, data própria (dois eventos nunca no mesmo dia), local e
  descrição. Só o admin cria/exclui eventos; qualquer usuário marca a
  participação das vidas do seu escopo na própria página da vida. As tabelas
  são `eventos` e `evento_participantes` (`/api/eventos`).
- **Observações** são anotações internas da ficha (`/api/observacoes`, tabela
  `observacoes`), visíveis para quem tem acesso à vida.
- **Relatórios** resume presença por tipo, período, grupo e igreja: totais,
  lançamentos do período e percentual por vida, com **exportar CSV** gerado no
  navegador.
- **Motivos de oração** lista os pedidos de todas as vidas no escopo do
  usuário (admin vê tudo; líder, o próprio grupo; frente, as mulheres). O
  lançamento é feito na página da vida; a lista permite marcar como
  atendido, reabrir e excluir.
- A tela **Aniversariantes** mostra apenas quem tem dia e mês de aniversário,
  com o card do dia e a lista do mês; a marcação **Não enviar SMS** (campo
  `excluido` no banco) vale para o disparo manual e para o automático.

A base agora tem o ano de nascimento (vindo da listagem do sistema da igreja),
então o corte de 15+ do Grupo de Senhoras pode ser aplicado; hoje a função
`frente` ainda filtra apenas pelo gênero `F`.

## Dados do sistema da igreja

As listagens exportadas do portal da igreja entram por
`backend/scripts/importar_dados_icm.py` (arquivos em
`data/entrada/dados_icm/`, que não vão para o Git por conterem dados pessoais):

```bash
cd backend
.venv/bin/python scripts/importar_dados_icm.py            # só simula
.venv/bin/python scripts/importar_dados_icm.py --aplicar  # grava no banco
```

- `listagem-geral.pdf` — cadastro: nome completo, situação, grupo, categoria e
  sexo. Não traz aniversário.
- `listagem-membros_gN_contato.pdf` — aniversário, telefones e `S/ Visitas`.
- `listagem-membros_gN_foto(s).pdf` — hoje vem como HTML do portal, sem dados.

A junção casa os nomes (a planilha abrevia os nomes do meio) e grava na tabela
`icm`. Campos manuais (`genero`, `excluido`) nunca são sobrescritos, e o nome
mais completo — o do banco ou o da planilha — é o que fica.

Cada pessoa passa a ter `situacao`, `categoria`, `tel_residencial`,
`tel_comercial`, `celular`, `ultima_visita`, `dias_sem_visita` e
`visitas_referencia`. `S/ Visitas` vira `ultima_visita = referência − N dias`;
`dias_sem_visita` é calculado a partir da data, então envelhece sozinho e serve
de fila de prioridade para a visitação. Registrar uma visita
(`POST /api/pessoas/{id}/visita`) zera o contador.

Telefones são normalizados para `55` + DDD + número; número com 8–9 dígitos
ganha o DDD `34`. Números fora do padrão (ex.: 12 dígitos sem `55`) não são
gravados e aparecem no relatório da importação.

Na tabela de Aniversariantes, o ícone de análise de cada linha abre o drawer
com aniversário, idade, telefones (com link para o WhatsApp), última visita,
dias sem visita, grupo, igreja, situação, histórico de presença, motivos de
oração e o botão **Registrar visita**. A ficha completa, com eventos,
faltas e observações, fica na página `/membros/{id}`.

## Cache de grupos e contatos

`/group/fetchAllGroups` da Evolution pode levar minutos. Por isso a busca
roda em segundo plano (`backend/app/services/cache.py`) e o resultado fica
em `backend/data/cache/*.json`. A tela consulta o progresso e mostra o
último resultado salvo.

## Disparo diário dos aniversariantes

Quem envia é o **GitHub Actions** (`.github/workflows/disparo-diario.yml`,
`cron: "0 3 * * *"` = 00:00 de Brasília; o GitHub às vezes atrasa e o job cai
de manhã). O job não enxerga o banco: ele lê os arquivos versionados em
`data/` — `data.pdf`, `aniversariantes_zoom.csv`, `generos.json` e
`exclusoes.json`.

- O painel espelha nesses JSON o **gênero** e a marcação **Não enviar SMS**
  salvos na ficha da vida. Como o workflow lê o repositório, depois de ajustar
  algo no painel rode:

  ```bash
  scripts/publicar_dados.sh
  ```

  Ele publica só `data/generos.json` e `data/exclusoes.json` pelo `gh` (sem
  mexer no resto do repositório) e avisa quando não há nada novo.
- A thread do backend (`services/disparo_automatico.py`) faz o mesmo envio às
  07:00 lendo o banco. Com o `.env` padrão (`DISPARO_AUTOMATICO=false`) ela
  fica desligada para não mandar a mensagem duas vezes; ligue só se o painel
  for o único responsável pelo envio.
- Disparo manual de emergência: **Actions** → *Disparo diário de
  aniversariantes* → *Run workflow* (`dry_run` monta a mensagem sem enviar).

Passo a passo completo em
[`docs/04-DISPARO-PELO-GIT.md`](docs/04-DISPARO-PELO-GIT.md).

