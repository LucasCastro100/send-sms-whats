# Check Birthday — Painel de Automação do WhatsApp

Streamlit + Evolution API para disparar aniversariantes (ICM e Zoom), mensagens
para grupos/contatos e envios agendados.

- **Painel (Streamlit):** consulta das listas e disparo manual.
- **Disparo automático diário (GitHub Actions):** todo dia às **00:00 de
  Brasília** envia os aniversariantes do ICM e do Zoom, mesmo com o app do
  Streamlit hibernando.

---

## 1. Rodar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Crie o `.env` na raiz do projeto:

```env
EVOLUTION_BASE_URL=https://sua-evolution-api
EVOLUTION_INSTANCE=igreja-bot
EVOLUTION_APIKEY=sua-chave

JID_GRUPO_IGREJA_FIXO=000000000000000000@g.us
NOME_GRUPO_IGREJA_FIXO=ICM - IGREJA BOA VISTA

JID_GRUPO_ZOOM=000000000000000000@g.us
NOME_GRUPO_ZOOM=ZOOM MG VALE PEDAGOGICO
```

Rodar o painel:

```bash
streamlit run main.py
```

Testar o disparo **sem enviar nada** (imprime a mensagem no terminal):

```bash
python -m scripts.disparar_aniversariantes --dry-run
python -m scripts.disparar_aniversariantes --dry-run --data 30/10
```

Disparar de verdade pela linha de comando:

```bash
python -m scripts.disparar_aniversariantes            # ICM + Zoom
python -m scripts.disparar_aniversariantes --fonte icm
```

---

## 2. Deploy no Streamlit Cloud

1. Suba o projeto no GitHub.
2. Em <https://share.streamlit.io>, clique em **New app** e escolha o repositório,
   branch `main` e **Main file path**: `main.py`.
3. Em **Settings → Secrets**, cole as mesmas variáveis do `.env`:

```toml
EVOLUTION_BASE_URL = "https://sua-evolution-api"
EVOLUTION_INSTANCE = "igreja-bot"
EVOLUTION_APIKEY = "sua-chave"
JID_GRUPO_IGREJA_FIXO = "000000000000000000@g.us"
NOME_GRUPO_IGREJA_FIXO = "ICM - IGREJA BOA VISTA"
JID_GRUPO_ZOOM = "000000000000000000@g.us"
NOME_GRUPO_ZOOM = "ZOOM MG VALE PEDAGOGICO"
```

> O `data.pdf` e o `data/aniversariantes_zoom.csv` precisam estar no repositório,
> pois o app na nuvem não enxerga arquivos locais.

---

## 3. Disparo automático às 00:00 (GitHub Actions)

O workflow `.github/workflows/disparo-diario.yml` roda:

```yaml
schedule:
  - cron: "0 3 * * *"   # 03:00 UTC = 00:00 em America/Sao_Paulo
```

### Configurar os Secrets no GitHub

Em **Settings → Secrets and variables → Actions → New repository secret**,
cadastre:

| Secret | Exemplo |
|---|---|
| `EVOLUTION_BASE_URL` | `https://sua-evolution-api` |
| `EVOLUTION_INSTANCE` | `igreja-bot` |
| `EVOLUTION_APIKEY` | `sua-chave` |
| `JID_GRUPO_IGREJA_FIXO` | `...@g.us` |
| `NOME_GRUPO_IGREJA_FIXO` | `ICM - IGREJA BOA VISTA` |
| `JID_GRUPO_ZOOM` | `...@g.us` |
| `NOME_GRUPO_ZOOM` | `ZOOM MG VALE PEDAGOGICO` |

### Testar sem esperar a meia-noite

Aba **Actions → Disparo diário de aniversariantes → Run workflow**:

- `fonte`: `ambos`, `icm` ou `zoom`
- `dry_run`: marque para apenas montar a mensagem (não envia)

O resultado de cada execução fica no log do job.

> Observação: o cron do GitHub Actions pode atrasar alguns minutos em horários
> de pico. Para o disparo sair pontualmente às 00:00, a alternativa é rodar
> `python -m scripts.disparar_aniversariantes` num cron do próprio servidor
> (`0 0 * * *` com `TZ=America/Sao_Paulo`).

---

## 4. Estrutura

```
main.py                     painel inicial + agendador interno (reforço)
core/comum.py               leitura das listas, mensagens e envio (Evolution API)
core/agendamentos.py        envios avulsos agendados pela tela Mensagens
pages/aniversariantes_icm.py
pages/aniversariantes_zoom.py
pages/mensagens.py
scripts/disparar_aniversariantes.py   disparo via linha de comando / CI
data/data.pdf               lista do ICM
data/aniversariantes_zoom.csv
data/generos.json           gênero por nome (irmão/irmã)
runtime/                    logs e fila de agendamentos (não versionado)
```

## 5. Documentação

O funcionamento completo de cada página e módulo está em
[`docs/`](docs/).
