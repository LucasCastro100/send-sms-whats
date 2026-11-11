# Check Birthday — frontend

Painel Next.js 15 (App Router) + Tailwind v4 + shadcn/ui.

```bash
pnpm install
echo "API_INTERNAL_URL=http://127.0.0.1:8000" > .env.local
pnpm dev
```

O Next faz proxy de `/api/*` para o FastAPI definido em `API_INTERNAL_URL`.
Instruções completas (API, Docker, endpoints): veja `../README-web.md`.
