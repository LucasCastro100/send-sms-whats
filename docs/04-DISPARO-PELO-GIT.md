# 🚀 Disparo pelo Git — como o aniversário sai sozinho

O envio diário dos aniversariantes **não depende do painel estar aberto**: quem
manda a mensagem é o **GitHub Actions**. O painel serve para consultar e ajustar
os dados; o Git é quem envia.

---

## 1. Quem envia e quando

| Item | Valor |
|---|---|
| Workflow | `.github/workflows/disparo-diario.yml` |
| Horário agendado | `cron: "0 3 * * *"` = **00:00** de Brasília |
| Horário real | o GitHub costuma atrasar; nas últimas execuções caiu entre **06:30 e 07:30** |
| Grupos | ICM (Boa Vista) e Zoom, definidos nos Secrets |
| Credenciais | Secrets do repositório (`EVOLUTION_*`, `JID_GRUPO_*`, `NOME_GRUPO_*`) |

O runner **não tem acesso ao banco do painel**. Ele lê só os arquivos
versionados na pasta `data/`:

- `data/data.pdf` — lista oficial do ICM (aniversários e grupos);
- `data/aniversariantes_zoom.csv` — lista do Zoom;
- `data/generos.json` — quem é irmão/irmã (muda o texto da mensagem);
- `data/exclusoes.json` — quem **não** deve ser citado (Não enviar SMS).

Sem aniversariante no dia, o job termina com “Nenhum aniversariante em dd/mm.
Nada a enviar.” e não manda nada.

---

## 2. Atualizar no Git o que você mudou no painel

Sempre que mudar o **gênero** ou marcar/desmarcar **Não enviar SMS** na ficha
da vida, rode:

```bash
cd automatics/check-birthday
scripts/publicar_dados.sh
```

O script:

1. compara `data/generos.json` e `data/exclusoes.json` com o que está no
   GitHub;
2. publica só esses dois arquivos (commit direto no `main`, sem mexer no resto
   do repositório);
3. avisa `Nada para publicar` quando já está tudo igual.

Pré-requisito: `gh` instalado e autenticado (`gh auth login`).

> Se preferir, rode o mesmo comando pelo caminho completo:
> `automatics/check-birthday/scripts/publicar_dados.sh`.

### O que precisa de publicação e o que não precisa

| Ajuste no painel | Vai para o Git? |
|---|---|
| Gênero (irmão/irmã) | **Sim** — `data/generos.json` |
| Não enviar SMS | **Sim** — `data/exclusoes.json` |
| Telefone, grupo, igreja, presença, eventos, observações, orações | Não — fica só no banco e não entra na mensagem |
| Lista de aniversariantes nova | Troque `data/data.pdf` e dê `push` (veja a seção 4) |

---

## 3. Testar e disparar na mão

Pela aba **Actions** do repositório → *Disparo diário de aniversariantes* →
**Run workflow**:

- `fonte`: `ambos`, `icm` ou `zoom`;
- `dry_run`: **marcado** monta a mensagem no log e **não envia** no WhatsApp.

Ou pelo terminal:

```bash
# só mostra a mensagem (não envia)
gh workflow run disparo-diario.yml -R LucasCastro100/send-sms-whats \
  -f fonte=ambos -f dry_run=true

# envia de verdade para o grupo (cuidado: pode duplicar o envio do dia)
gh workflow run disparo-diario.yml -R LucasCastro100/send-sms-whats \
  -f fonte=ambos -f dry_run=false

# acompanhar
gh run list -R LucasCastro100/send-sms-whats --limit 3
```

Também dá para rodar o mesmo pipeline localmente, sem GitHub:

```bash
cd automatics/check-birthday
.venv/bin/python -m scripts.disparar_aniversariantes --dry-run
```

---

## 4. Trocar a lista oficial do ICM (`data.pdf`)

O `data/data.pdf` é a lista que o Git envia. Quando a igreja mandar uma lista
nova:

1. substitua `data/data.pdf` pelo arquivo novo;
2. importe no painel (**Importar planilhas**) para o banco também ficar igual —
   campos manuais (`genero`, `excluido`) não são sobrescritos;
3. publique o PDF no repositório (`git add data/data.pdf`, commit e push pelo
   fluxo normal do projeto).

---

## 5. Evitar mensagem duplicada

Existem dois lugares que sabem enviar: o GitHub Actions e a thread do backend
(`backend/app/services/disparo_automatico.py`, que lê o **banco** às 07:00).
Rodar os dois manda a mesma mensagem duas vezes no grupo.

Por isso o `.env` fica com:

```env
DISPARO_AUTOMATICO=false
```

Assim **só o Git envia**. Ligue `true` apenas se o painel for o único
responsável pelo envio (por exemplo, um servidor sem GitHub Actions).

---

## 6. Resumo de bolso

```bash
# mudou gênero ou "Não enviar SMS" no painel?
cd automatics/check-birthday && scripts/publicar_dados.sh

# quer ver a mensagem de hoje sem enviar?
gh workflow run disparo-diario.yml -R LucasCastro100/send-sms-whats \
  -f fonte=ambos -f dry_run=true
```
