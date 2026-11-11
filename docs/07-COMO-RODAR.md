# 🏃 Como rodar o back e o front

Guia prático para subir o painel na sua máquina: a **API** em FastAPI
(`backend/`) e o **painel** em Next.js (`frontend/`), com ou sem Docker.

---

## 1. O que sobe e onde

| Peça | Tecnologia | Porta | URL |
|---|---|---|---|
| Back (API) | FastAPI + SQLite | `8000` | <http://localhost:8000> |
| Front (painel) | Next.js 15 | `3000` | <http://localhost:3000> |

O front faz **proxy** de `/api/*` para o back (configurado no
`frontend/next.config.ts`). Por isso não existe CORS e o login funciona na
mesma origem — mas os **dois processos precisam estar rodando**.

---

## 2. Pré-requisitos (uma vez por máquina)

- **Python 3.9+** (o Docker usa 3.12)
- **Node.js 18+** e **pnpm** (`npm install -g pnpm`)
- Arquivo **`.env` na raiz** do projeto (veja o `README.MD`, seção 2), com
  `EVOLUTION_*` e, se quiser, `APP_USERS`

---

## 3. Primeira vez em cada pasta

### Back

```bash
cd backend
python3.9 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Front

```bash
cd frontend
pnpm install
echo "API_INTERNAL_URL=http://127.0.0.1:8000" > .env.local
```

O `.env.local` só é preciso criar uma vez — é ele que diz ao Next para onde
ir o proxy de `/api`.

---

## 4. Rodar no dia a dia (dois terminais)

### Terminal 1 — back

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

No primeiro start o back faz tudo sozinho:

- cria o banco em `backend/data/app.db` (SQLite);
- importa `data.pdf`, CSVs e JSONs antigos de `data/` para o banco;
- sincroniza os grupos de assistência;
- liga o agendador de envios e o disparo diário (07:00, horário de Brasília).

### Terminal 2 — front

```bash
cd frontend
pnpm dev
```

Abra <http://localhost:3000>.

### Login

- Se a raiz tem `APP_USERS` no `.env`: usa esses usuários.
- Sem `APP_USERS`: admin padrão **`lucas` / `trocar123`**.

### Parar

`Ctrl+C` em cada terminal.

---

## 5. Rodar tudo com Docker (alternativa)

```bash
docker compose up --build
```

Sobe a API (`api:8000`) e o painel em <http://localhost:3000>. O SQLite fica
no volume `cb-data`. Se a porta 3000 estiver ocupada:

```bash
WEB_PORT=3100 docker compose up --build
```

Para parar: `docker compose down`.

> Com Docker não é preciso venv nem `pnpm install` — as imagens instalam
> tudo (`backend/Dockerfile` e `frontend/Dockerfile`).

---

## 6. Variáveis de ambiente

O back lê **dois** `.env` (o da raiz e o de `backend/`); em chave repetida,
o de `backend/` vence.

| Arquivo | O que carrega |
|---|---|
| `.env` (raiz) | `EVOLUTION_*`, `APP_USERS`, JIDs dos grupos |
| `backend/.env` | `SECRET_KEY`, `DATABASE_URL`, `COOKIE_SECURE`, `CORS_ORIGINS` |
| `frontend/.env.local` | `API_INTERNAL_URL` (para onde vai o proxy `/api`) |

---

## 7. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Front abre mas login/dados falham | Back não está rodando | suba o Terminal 1 primeiro |
| Erro de módulo no back | dependências novas no repo | `.venv/bin/pip install -r requirements.txt` |
| Erro de build no front | dependências novas no repo | `pnpm install` |
| Porta 3000 ocupada | outro processo nela | `pnpm dev -p 3100` |
| Reset do banco | apagar `backend/data/app.db` | o back recria e reimporta no próximo start |

Checagem rápida do back: <http://localhost:8000/api/health> deve responder
`{"ok": true, ...}`. A documentação automática das rotas fica em
<http://localhost:8000/docs>.
