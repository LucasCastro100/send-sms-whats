# 🌐 Deploy — API na VPS, painel na Vercel

Este é o caminho de produção: a **API** (FastAPI + Postgres) roda na VPS com
HTTPS, e o **painel** (Next.js) roda na Vercel. O envio diário dos
aniversariantes continua independente do painel — veja
[`04-DISPARO-PELO-GIT.md`](04-DISPARO-PELO-GIT.md).

```
navegador
   │  https://gestao-membros.vercel.app        (Next.js na Vercel)
   │        │ fetch para NEXT_PUBLIC_API_URL
   ▼        ▼
https://api.seudominio.com  ──►  Caddy (HTTPS)  ──►  api:8000  ──►  Postgres
        (VPS)                                              (volume na VPS)
```

O que muda em relação ao local: o banco deixa de ser SQLite e passa a ser
Postgres, e o front fala com a API por outro domínio (CORS + cookie
`SameSite=None; Secure`).

---

## 1. Antes de começar

- VPS com Docker e Docker Compose (`docker compose version`).
- Um domínio/subdomínio para a API (ex.: `api.seudominio.com`) com registro
  **A** apontando para o IP da VPS. O Caddy só emite o certificado depois que
  o DNS propaga.
- Portas 80 e 443 liberadas na VPS.
- Conta na Vercel com o repositório conectado.

---

## 2. API na VPS

```bash
# 1. clone o repositório na VPS
git clone https://github.com/LucasCastro100/send-sms-whats.git
cd send-sms-whats/deploy

# 2. configure o ambiente
cp .env.prod.example .env
nano .env        # API_DOMAIN, CORS_ORIGINS, POSTGRES_PASSWORD, APP_USERS, Evolution

# 3. suba Postgres + API + Caddy
docker compose -f docker-compose.prod.yml up -d --build

# 4. acompanhe
docker compose -f docker-compose.prod.yml logs -f api
```

Teste:

```bash
curl https://api.seudominio.com/api/health
```

O `deploy/docker-compose.prod.yml` já cuida de:

- **Postgres 17** com volume `cb-pg` (os dados ficam fora do container);
- **API** com `DATABASE_URL=postgresql+psycopg://...@db:5432/...`, `data/` do
  repositório montado **somente leitura** em `/dados` e uploads no volume
  `cb-uploads`;
- **Caddy** na frente, com certificado automático e a porta 8000 fechada para
  fora.

---

## 3. Levar os dados do SQLite para o Postgres

O banco local (`backend/data/app.db`) tem as vidas, presenças, eventos,
observações e usuários. Copie uma vez, depois de a API ter subido ao menos uma
vez (para as tabelas existirem):

### Opção A — túnel SSH (recomendada, não expõe o Postgres)

Na sua máquina, dentro de `backend/`:

```bash
ssh -L 5432:127.0.0.1:5432 usuario@ip-da-vps -N
```

Em outro terminal:

```bash
cd backend
.venv/bin/python scripts/migrar_para_postgres.py \
  --destino "postgresql+psycopg://checkbirthday:SENHA@127.0.0.1:5432/checkbirthday"
# confira o resumo e depois repita com --aplicar
```

### Opção B — rodar dentro da VPS

```bash
# na sua máquina
scp backend/data/app.db usuario@ip-da-vps:/tmp/app.db

# na VPS
docker compose -f deploy/docker-compose.prod.yml exec api \
  python scripts/migrar_para_postgres.py \
  --origem sqlite:////tmp/app.db --destino "$DATABASE_URL" --aplicar
```

> O `app.db` precisa estar visível dentro do container. Se não estiver, copie
> com `docker cp /tmp/app.db $(docker compose ... ps -q api):/tmp/app.db`.

O script preserva os ids e ajusta as sequências do Postgres. Rode sem
`--aplicar` primeiro: ele mostra quantos registros cada tabela tem.

Depois da cópia, reinicie a API:

```bash
docker compose -f docker-compose.prod.yml restart api
```

---

## 4. Painel na Vercel

1. **Add New → Project** e importe `LucasCastro100/send-sms-whats`.
2. **Root Directory**: `frontend`.
3. Framework: **Next.js** (a Vercel detecta sozinha; usa o `pnpm-lock.yaml`).
4. Em **Environment Variables**, adicione para Production (e Preview):

   | Nome | Valor |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://api.seudominio.com` (sem barra no fim) |

   É variável de **build**: se mudar depois, faça um novo deploy.
5. **Deploy**. Depois copie o domínio final e coloque em `CORS_ORIGINS` na VPS
   (`deploy/.env`) e reinicie a API:

   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

### Se o login não “pegar” no navegador

Com o front em outro domínio, o cookie de sessão é de terceiros. Safari e
Firefox podem bloqueá-lo por padrão. Duas saídas:

- **Recomendado:** use o proxy do Next (mesma origem). Na Vercel, deixe
  `NEXT_PUBLIC_API_URL` **vazio** e configure `API_INTERNAL_URL=https://api.seudominio.com`
  (o rewrite do `next.config.ts` encaminha `/api/*`). Nesse caso o cookie volta
  a ser de primeira parte e o CORS deixa de importar.
- Ou peça aos usuários para liberar cookies de terceiros para o site.

---

## 5. Atualizar depois

```bash
# API (na VPS)
cd send-sms-whats && git pull
docker compose -f deploy/docker-compose.prod.yml up -d --build

# Painel: a Vercel redeploya sozinha a cada push no main
```

O `deploy/` e o `backend/` não interferem no envio do GitHub
(`core/`, `scripts/`, `data/` na raiz).

---

## 6. Backup e diagnóstico

```bash
# backup do Postgres
docker compose -f deploy/docker-compose.prod.yml exec -T db \
  pg_dump -U checkbirthday checkbirthday | gzip > backup-$(date +%F).sql.gz

# restaurar
gunzip -c backup-2026-11-11.sql.gz | \
  docker compose -f deploy/docker-compose.prod.yml exec -T db \
  psql -U checkbirthday -d checkbirthday

# logs
docker compose -f deploy/docker-compose.prod.yml logs -f api
docker compose -f deploy/docker-compose.prod.yml logs -f caddy
```

---

## 7. Envio dos aniversariantes na VPS

Com a VPS ligada 24h, dá para a **própria API** enviar (lê o Postgres, sempre
atualizado) em vez do GitHub Actions:

1. no `deploy/.env`: `DISPARO_AUTOMATICO=true`;
2. **remova** o `schedule` do `.github/workflows/disparo-diario.yml` (senão a
   mensagem sai duas vezes);
3. `docker compose -f deploy/docker-compose.prod.yml up -d`.

Mantendo `DISPARO_AUTOMATICO=false` (padrão), quem envia é o GitHub Actions e
vale o que está em [`04-DISPARO-PELO-GIT.md`](04-DISPARO-PELO-GIT.md) — inclusive
o `scripts/publicar_dados.sh` depois de ajustar gênero ou “Não enviar SMS”.
