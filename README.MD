# Check Birthday — painel de automação do WhatsApp

Painel da igreja para aniversariantes, mensagens e presença, com envio pelo
WhatsApp (Evolution API).

- **API** — FastAPI + SQLite/SQLModel (`backend/`). Só API, sem telas.
- **Painel** — Next.js 15 + Tailwind v4 + shadcn/ui (`frontend/`).
- **Disparo diário** — thread do backend às 07:00 de Brasília, com base na
  lista **ICM** do banco.

O Streamlit antigo foi aposentado. Ficaram na raiz apenas `core/` e `scripts/`,
usados pelo disparo manual de emergência do GitHub Actions.

---

## 1. Rodar local

### API

```bash
cd backend
python3.9 -m venv .venv            # só na primeira vez
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

O banco fica em `backend/data/app.db` e é criado no primeiro start. Os
usuários iniciais vêm do `APP_USERS` do `.env` da raiz; sem ele, cria o admin
`lucas` / `trocar123`.

### Painel

```bash
cd frontend
pnpm install                       # só na primeira vez
echo "API_INTERNAL_URL=http://127.0.0.1:8000" > .env.local
pnpm dev
```

Abra <http://localhost:3000>. O Next faz proxy de `/api/*` para o FastAPI,
então não há CORS e o cookie de sessão funciona na mesma origem.

### Docker

```bash
docker compose up --build
```

Sobe a API em `api:8000` e o painel em <http://localhost:3000>. O SQLite fica
no volume `cb-data` (`/data/app.db`). Se a porta 3000 estiver ocupada:
`WEB_PORT=3100 docker compose up --build`.

## 2. Variáveis de ambiente

Crie o `.env` na raiz (o mesmo arquivo alimenta API, painel e scripts):

```env
EVOLUTION_BASE_URL=https://sua-evolution-api
EVOLUTION_INSTANCE=igreja-bot
EVOLUTION_APIKEY=sua-chave

# Opcional: chave global (AUTHENTICATION_API_KEY) para criar instância por usuário
EVOLUTION_GLOBAL_APIKEY=
EVOLUTION_INSTANCE_PREFIX=cb-

# Login inicial do painel (JSON). Sem isso, o admin é lucas / trocar123.
APP_USERS={"lucas": {"senha": "troque-esta-senha", "nome": "Lucas", "instancia": "igreja-bot"}}

JID_GRUPO_IGREJA_FIXO=000000000000000000@g.us
NOME_GRUPO_IGREJA_FIXO=ICM - IGREJA BOA VISTA

JID_GRUPO_ZOOM=000000000000000000@g.us
NOME_GRUPO_ZOOM=ZOOM MG VALE PEDAGOGICO
```

Cada usuário pode ter a própria instância (`cb-<usuario>`) ou usar uma
existente (ex.: `"instancia": "igreja-bot"`). Sem
`EVOLUTION_GLOBAL_APIKEY` a API só reconecta a instância padrão; com ela, o
admin cria a conta e cada usuário conecta o próprio WhatsApp pelo QR Code.

## 3. Disparo automático

O backend envia os aniversariantes do dia sozinho, todos os dias às **07:00 de
Brasília** (thread `services/disparo_automatico.py`), lendo a tabela `icm` —
com gêneros e exclusões ajustados no painel. A idempotência fica na tabela
`disparos`: cada dia/fonte é enviado uma única vez.

O workflow `.github/workflows/disparo-diario.yml` é **somente manual**
(`workflow_dispatch`) e serve como plano B:

```bash
python -m scripts.disparar_aniversariantes --dry-run
python -m scripts.disparar_aniversariantes --fonte icm
```

> Não agende o workflow no GitHub enquanto o backend estiver no ar, ou a
> mensagem sai duas vezes.

## 4. Estrutura

```
backend/        API FastAPI (rotas, serviços, SQLite em backend/data/)
frontend/       Painel Next.js (src/app, src/components, src/lib)
core/           Regras antigas reaproveitadas pelo script de disparo manual
scripts/        Disparo manual de aniversariantes
data/           Arquivos de entrada/legado (PDF do ICM, CSVs, exclusões)
docs/           Documentação e imagens
docker-compose.yml
```

## 5. Telas

Painel, Aniversariantes, Mensagens (com agendamento), Presença, Conexão
WhatsApp, Importar planilhas e Usuários (admin).

Não há cadastro público: o admin cria as contas e define a função de cada
usuário — `admin` (tudo), `lider` (só o grupo de assistência vinculado) ou
`frente` (Grupo de Senhoras: todas as mulheres).

Detalhes das rotas da API, funções, grupos, cache de grupos/contatos e
importação estão em [`README-web.md`](README-web.md).
