# ⏰ Cron e agendamentos — como o sistema dispara sozinho

Este documento explica os **dois tipos de agendamento** do sistema:

1. **Disparo diário (GitHub Actions)** — todo dia às **07:00** (Brasília) envia
   os aniversariantes do ICM e do Zoom;
2. **Envio avulso agendado** — uma mensagem única para uma data/hora escolhida
   na tela **💬 Mensagens → ⏰ Agendar**.

O envio avulso usa o `BackgroundScheduler` do
[APScheduler](https://apscheduler.readthedocs.io/) dentro do Streamlit. O
disparo diário roda fora do app, no GitHub Actions
(`.github/workflows/disparo-diario.yml`).

---

## 1. O que é o APScheduler

O APScheduler é uma biblioteca Python que mantém uma fila de jobs e executa cada
um no horário definido, em uma thread de fundo. Ele **não** é um serviço do
sistema operacional: vive dentro do processo Python. Se o processo morre, os
jobs morrem com ele.

| Conceito | No projeto |
|---|---|
| `BackgroundScheduler` | roda os jobs em uma thread separada, sem bloquear o Streamlit |
| `trigger` | regra de quando executar (`cron` ou `date`) |
| `job` | a função a executar + seus parâmetros |
| `job id` | nome único; permite substituir/cancelar sem duplicar |
| timezone | `America/Sao_Paulo` (horário de Brasília) |

### 1.1 Por que `@st.cache_resource`

```python
@st.cache_resource
def obter_agendador() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=FUSO)
    _reagendar_pendentes(scheduler)
    scheduler.start()
    return scheduler
```

O Streamlit **reexecuta o script inteiro** a cada interação. Sem o cache, cada
clique criaria um novo scheduler — e cada scheduler dispararia a mesma mensagem,
gerando duplicatas. Com `@st.cache_resource`, o objeto é criado **uma vez por
processo** e reaproveitado por todas as sessões e reruns.

`main.py` e `pages/mensagens.py` chamam a mesma função `obter_agendador()`, então
todos os envios avulsos convivem em um único agendador:

```
obter_agendador()  (singleton)
└── envio_<id>                  date (cada agendamento)
```

---

## 2. Job diário dos aniversariantes (GitHub Actions)

O disparo diário **não** fica no agendador do Streamlit. Quem executa é o
workflow `.github/workflows/disparo-diario.yml`, no horário do `cron`:

```yaml
on:
  schedule:
    - cron: "0 10 * * *"   # 10:00 UTC = 07:00 em America/Sao_Paulo
```

O runner do GitHub Actions não tem o `.env`: as credenciais e os JIDs vêm dos
**Secrets** do repositório. O workflow chama
`python -m scripts.disparar_aniversariantes --fonte ambos`, que delega para
`_disparar_do_dia()` (`core/comum.py`):

1. o JID do grupo está configurado?
2. a lista (PDF/CSV) tem dados?
3. filtra `Data Nasc. == hoje (dd/mm)`;
4. sem aniversariantes → grava no log e encerra sem enviar;
5. com aniversariantes → monta o texto, chama `sendText` pela instância fixa
   `EVOLUTION_INSTANCE` e grava o resultado em `runtime/aniversariantes.log`.

### 2.1 Horário e fuso

O `cron` do GitHub Actions é sempre em **UTC** e não considera horário de verão
(o Brasil não usa mais DST, então `10:00 UTC` = `07:00 BRT` o ano inteiro). O
GitHub pode atrasar alguns minutos em horários de pico.

### 2.2 Testar sem esperar as 07:00

Não há botão “executar agora”. Duas opções:

```bash
# roda os dois disparos na hora, fora do Streamlit
.venv/bin/python -c "from core.comum import disparar_aniversariantes_icm, disparar_aniversariantes_zoom; print(disparar_aniversariantes_icm()); print(disparar_aniversariantes_zoom())"
```

ou use os botões **🚀 Disparar** das páginas **Aniversariantes ICM/Zoom** (enviam
o texto da data selecionada, não necessariamente hoje).

---

## 3. Envio avulso agendado

Implementado em `core/agendamentos.py`.

### 3.1 Criação

```python
agendar_envio(texto, destino_jid, nome_destino, quando)
```

1. Se `quando` não tem fuso, assume `America/Sao_Paulo`;
2. recusa horário no passado (`ValueError`);
3. cria um registro com `id` de 8 caracteres, status `pendente`;
4. grava em `runtime/envios_agendados.json`;
5. registra um job `DateTrigger` com `id=f"envio_{id}"`.

### 3.2 `DateTrigger`

Diferente do `cron`, executa **uma única vez**, na data/hora exata:

```python
DateTrigger(run_date=quando, timezone=FUSO)
```

Se o horário já passou quando o job é registrado, o APScheduler o descarta (por
isso a validação no passo 2).

### 3.3 Execução

No horário, a thread do scheduler chama `_executar(id)`:

1. relê o JSON e localiza o registro;
2. se o status não for `pendente` (cancelado, já enviado), não faz nada;
3. chama `enviar_via_evolution_api(texto, jid)`;
4. atualiza o registro para `enviado` ou `erro`, com `resultado` e
   `executado_em`;
5. grava uma linha em `runtime/envios_agendados.log`.

### 3.4 Persistência e recuperação

`runtime/envios_agendados.json` é a fonte da verdade. Ao subir o app,
`_reagendar_pendentes()` percorre a lista:

| Situação | Resultado |
|---|---|
| `pendente` com horário **no futuro** | job `DateTrigger` recriado |
| `pendente` com horário **no passado** | vira `perdido` (não reenvia) |
| `quando` inválido | vira `erro` com “data inválida” |
| outros status | ignorados |

Exemplo de registro:

```json
{
  "id": "7be5dcf1",
  "texto": "Mensagem agendada",
  "jid": "5534999998888",
  "nome": "Lucas",
  "quando": "2026-10-30T09:30:00-03:00",
  "status": "pendente",
  "criado_em": "2026-10-29T21:50:27-03:00",
  "resultado": ""
}
```

### 3.5 Cancelamento

`cancelar_agendamento(id)`:

1. tenta remover o job `envio_<id>` (ignora erro se ele não existe mais);
2. marca o registro como `cancelado`;
3. grava no log.

Cancelar **depois** do envio não desfaz a mensagem no WhatsApp.

### 3.6 Limites

- O app precisa estar rodando no horário;
- se o processo estava desligado no horário, o agendamento vira `perdido` e
  **não** é reenviado;
- se o processo estava rodando mas a thread atrasou até 1h, ainda executa
  (`misfire_grace_time=3600`);
- dois processos do app = dois schedulers = envio duplicado.

---

## 4. Streamlit vs. cron do sistema

O agendador interno é prático (não exige configuração externa), mas depende do
processo do Streamlit. Comparação:

| | APScheduler no Streamlit | `cron` / `launchd` / systemd |
|---|---|---|
| Precisa do app aberto | sim | não |
| Configuração | zero (já no código) | arquivo de serviço/agendamento |
| Interface para o usuário | sim | não |
| Logs | arquivos em `runtime/` | arquivo definido por você |
| Streamlit Cloud | hiberna e perde o horário | não se aplica |
| Duplicação acidental | fácil (2 instâncias) | controlada pelo sistema |

Para **garantia real** de envio diário, o ideal é rodar o job fora do Streamlit.
Abaixo, três alternativas.

### 4.1 Script standalone (recomendado como base)

Crie `enviar_hoje.py` na raiz:

```python
"""Executa os disparos do dia sem depender do Streamlit."""
from core.comum import disparar_aniversariantes_icm, disparar_aniversariantes_zoom

if __name__ == "__main__":
    print(disparar_aniversariantes_icm())
    print(disparar_aniversariantes_zoom())
```

Teste:

```bash
.venv/bin/python enviar_hoje.py
```

### 4.2 `cron` no Linux/macOS

```bash
crontab -e
```

```cron
# todo dia às 07:00 (horário local do servidor; ajuste TZ se necessário)
0 7 * * * cd /caminho/check-birthday && TZ=America/Sao_Paulo .venv/bin/python enviar_hoje.py >> runtime/cron.log 2>&1
```

No macOS o `cron` funciona, mas `launchd` é o mecanismo nativo e lida melhor com
hibernação.

### 4.3 `launchd` no macOS

Crie `~/Library/LaunchAgents/tech.ideiasdev.checkbirthday.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>tech.ideiasdev.checkbirthday</string>

  <key>ProgramArguments</key>
  <array>
    <string>/caminho/check-birthday/.venv/bin/python</string>
    <string>/caminho/check-birthday/enviar_hoje.py</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/caminho/check-birthday</string>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>7</integer>
    <key>Minute</key><integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/caminho/check-birthday/runtime/launchd.log</string>
  <key>StandardErrorPath</key>
  <string>/caminho/check-birthday/runtime/launchd.err.log</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>TZ</key><string>America/Sao_Paulo</string>
  </dict>
</dict>
</plist>
```

Carregar e testar:

```bash
launchctl load ~/Library/LaunchAgents/tech.ideiasdev.checkbirthday.plist
launchctl start tech.ideiasdev.checkbirthday
```

> Se a máquina estiver **dormindo** às 07:00, o `launchd` executa ao
> acordar. Ainda assim, confira o log.

### 4.4 GitHub Actions (nuvem)

Útil se você não quer manter um computador ligado. O repositório é privado, então
use **Secrets** do repositório (nunca commite o `.env`):

```yaml
# .github/workflows/aniversariantes.yml
name: Aniversariantes
on:
  schedule:
    - cron: "0 10 * * *"   # 10:00 UTC = 07:00 em America/Sao_Paulo
  workflow_dispatch:

jobs:
  enviar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python enviar_hoje.py
        env:
          EVOLUTION_BASE_URL: ${{ secrets.EVOLUTION_BASE_URL }}
          EVOLUTION_INSTANCE: ${{ secrets.EVOLUTION_INSTANCE }}
          EVOLUTION_APIKEY: ${{ secrets.EVOLUTION_APIKEY }}
          JID_GRUPO_IGREJA_FIXO: ${{ secrets.JID_GRUPO_IGREJA_FIXO }}
          NOME_GRUPO_IGREJA_FIXO: ${{ secrets.NOME_GRUPO_IGREJA_FIXO }}
          JID_GRUPO_ZOOM: ${{ secrets.JID_GRUPO_ZOOM }}
          NOME_GRUPO_ZOOM: ${{ secrets.NOME_GRUPO_ZOOM }}
```

Atenção: o `schedule` do GitHub Actions pode atrasar alguns minutos em horários
de pico e **não** considera horário de verão (o Brasil não usa mais DST, então
`10:00 UTC` = `07:00 BRT` o ano inteiro).

### 4.5 VPS

A opção mais previsível: uma VPS Linux sempre ligada com `cron` ou um serviço
`systemd`:

```ini
# /etc/systemd/system/check-birthday.service
[Unit]
Description=Disparo diario de aniversariantes

[Service]
Type=oneshot
WorkingDirectory=/opt/check-birthday
Environment=TZ=America/Sao_Paulo
ExecStart=/opt/check-birthday/.venv/bin/python enviar_hoje.py
```

```ini
# /etc/systemd/system/check-birthday.timer
[Unit]
Description=Todo dia às 07:00

[Timer]
OnCalendar=*-*-* 07:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl enable --now check-birthday.timer
```

`Persistent=true` executa o job atrasado se a máquina estava desligada no
horário.

---

## 5. Fuso horário

- `core/agendamentos.py` usa `FUSO = "America/Sao_Paulo"` no scheduler, nos
  `DateTrigger` e em `agora()`;
- o disparo diário é agendado no GitHub Actions em UTC (`0 10 * * *` = 07:00 de
  Brasília);
- o **filtro da data** em `_disparar_do_dia()` usa `datetime.now()` do sistema.
  Se o servidor estiver em outro fuso, o “hoje” pode divergir do horário do job.
  Em VPS, configure `TZ=America/Sao_Paulo` (veja os exemplos acima).

---

## 6. Resumo operacional

| Pergunta | Resposta |
|---|---|
| Que horas envia os aniversariantes? | todo dia às 07:00 de Brasília (GitHub Actions) |
| Preciso abrir o navegador? | não; precisa do **processo** `streamlit run` vivo |
| Se eu reiniciar o app, perco os agendamentos? | não; os pendentes são recarregados do JSON |
| Se o app estava desligado no horário? | o agendamento vira `perdido` |
| Onde vejo o que aconteceu? | `runtime/aniversariantes.log` e `runtime/envios_agendados.log` |
| Posso ter dois apps abertos? | não; causa envio duplicado |
| Como garantir o envio sem o app? | `launchd`, `cron`, VPS ou GitHub Actions com `enviar_hoje.py` |

---

📚 Índice completo: [`README.md`](README.md)
