# 📌 Painel de Automação do WhatsApp — Documentação

Sistema Streamlit para disparar mensagens no WhatsApp via **Evolution API**, com:

- **Aniversariantes do ICM** (lidos do `data/data.pdf`, com grupos de assistência)
- **Aniversariantes do Zoom** (lista manual em CSV, ordenada por mês/dia)
- **Mensagens avulsas** para grupos, contatos individuais ou número digitado
- **Agendamento de envio único** para uma data/hora escolhida
- **Disparos automáticos diários à meia-noite** (ICM e Zoom)

---

## 1. Estrutura de arquivos

```
check-birthday/
├── main.py                        # Página inicial + agendador (jobs diários)
├── core/
│   ├── __init__.py
│   ├── comum.py                   # Regras compartilhadas (dados, gênero, envio, mensagens)
│   └── agendamentos.py            # Envios agendados (data/hora) + scheduler único
├── pages/
│   ├── aniversariantes_icm.py     # Subpágina: aniversariantes do ICM
│   ├── aniversariantes_zoom.py    # Subpágina: aniversariantes do Zoom
│   └── mensagens.py               # Subpágina: grupos, conversas e agendamento
├── data/
│   ├── data.pdf                   # Lista oficial do ICM (não editar à mão)
│   ├── aniversariantes_zoom.csv   # Lista manual do Zoom
│   └── generos.json               # Nome -> "M" / "F" (irmão / irmã)
├── runtime/                       # Gerado em execução (fora do git)
│   ├── aniversariantes.log
│   ├── envios_agendados.json
│   └── envios_agendados.log
├── docs/
│   └── DOCUMENTACAO.md            # Esta documentação
├── .env                           # Credenciais e JIDs (não versionar)
├── .gitignore
├── README.MD                      # Instalação e configuração rápida
└── requirements.txt
```

---

## 2. Configuração (`.env`)

| Variável | Para que serve |
|---|---|
| `EVOLUTION_BASE_URL` | URL da Evolution API (ex.: `https://evolution.ideiasdev.tech`) |
| `EVOLUTION_INSTANCE` | Nome da instância conectada ao WhatsApp (ex.: `igreja-bot`) |
| `EVOLUTION_APIKEY` | Chave de API da instância |
| `JID_GRUPO_IGREJA_FIXO` | JID do grupo que recebe os aniversariantes do ICM |
| `NOME_GRUPO_IGREJA_FIXO` | Nome amigável do grupo do ICM (só exibição) |
| `JID_GRUPO_ZOOM` | JID do grupo que recebe os aniversariantes do Zoom |
| `NOME_GRUPO_ZOOM` | Nome amigável do grupo do Zoom (só exibição) |

> O Streamlit Cloud não lê `.env`: nesse caso, cadastre as mesmas chaves em
> **App settings → Secrets**.

Como descobrir o JID de um grupo: abra **💬 Mensagens → aba 👥 Grupos**, busque o
grupo, marque o checkbox e copie o bloco de código que aparece.

---

## 3. Como rodar

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run main.py
```

O Streamlit abre em `http://localhost:8501`. As subpáginas aparecem na barra
lateral automaticamente (o Streamlit lê a pasta `pages/`).

---

## 4. `main.py` — página inicial e agendador diário

### 4.1 Carga do ambiente

```python
env_file = find_dotenv(usecwd=True)
if env_file:
    load_dotenv(dotenv_path=env_file, override=True)
else:
    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
```

Procura o `.env` a partir do diretório atual (funciona rodando da raiz do projeto
ou de outra pasta) e carrega as variáveis com `override=True`.

Esse trecho fica **antes** dos imports de `comum`/`agendamentos`, porque esses
módulos leem as variáveis no momento em que são importados.

### 4.2 Registro dos jobs diários

```python
def inicializar_agendador_cron():
    scheduler = obter_agendador()          # scheduler único do app (cache_resource)

    scheduler.add_job(
        disparar_aniversariantes_icm,
        trigger="cron", hour=0, minute=0,
        id="job_aniversariantes_icm",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )
    # ... job_aniversariantes_zoom igual, chamando disparar_aniversariantes_zoom
    return scheduler
```

- `obter_agendador()` vem de `core/agendamentos.py` e é decorado com
  `@st.cache_resource` → existe **um único** `BackgroundScheduler` por processo,
  mesmo com os reruns do Streamlit.
- `trigger="cron", hour=0, minute=0` → todo dia à **00:00**.
- `replace_existing=True` → reexecutar `main.py` não cria jobs duplicados.
- `coalesce=True` → se o app ficou travado e acumulou horários, roda só uma vez.
- `misfire_grace_time=3600` → tolera até 1h de atraso (ex.: thread ocupada ou
  máquina que hibernou e voltou antes de 01:00).

O scheduler é criado com `timezone="America/Sao_Paulo"`, então "meia-noite" é
sempre o horário de Brasília, independente do fuso do servidor.

### 4.3 Interface

Mostra o status do agendador, atalhos para as subpáginas, valida se
`EVOLUTION_APIKEY`/`EVOLUTION_INSTANCE` existem e informa se os JIDs do ICM e do
Zoom estão configurados (com aviso quando o do Zoom está vazio).

---

## 5. `core/comum.py` — o "cérebro" compartilhado

Todos os dados, mensagens e envios passam por aqui. É importado pelas três
subpáginas e pelo `core/agendamentos.py`.

### 5.1 Constantes

```python
RAIZ              = Path(__file__).resolve().parent.parent
PASTA_DADOS       = RAIZ / "data"
PASTA_RUNTIME     = RAIZ / "runtime"   # criada automaticamente

ARQUIVO_PDF       = PASTA_DADOS / "data.pdf"
ARQUIVO_ZOOM      = PASTA_DADOS / "aniversariantes_zoom.csv"
ARQUIVO_GENEROS   = PASTA_DADOS / "generos.json"
ARQUIVO_LOG       = PASTA_RUNTIME / "aniversariantes.log"

ICONE_ANIVERSARIANTE = "🥳"
ICONE_IRMA           = "👧🎉"
ICONE_IRMAO          = "👦🎉"
MESES_MAP            = {1: "Janeiro", ...}
```

Para trocar os emojis da mensagem, basta editar essas três constantes.

### 5.2 Leitura do PDF (ICM) — `parse_pdf()`

Abre `data/data.pdf` com `pypdf` e, para cada linha de cada página, aplica a regex:

```python
r"^(\d+)\s+(\d{2}/\d{2})\s+(.+?)\s+(\d+\s*-.*)$"
#     nº           data          nome        grupo de assistência
```

Resultado: `DataFrame` com `Número`, `Data Nasc.` (`dd/mm`), `Mês_Num`, `Nome`
e `Grupo de Assistência`. Retorna `DataFrame` vazio se o arquivo não existir ou
não tiver linhas válidas.

`read_and_parse_pdf()` é só um wrapper com `@st.cache_data` — usado pela tela
para não reler o PDF a cada interação. O agendador usa `parse_pdf()` direto,
porque cache do Streamlit fora de uma sessão não faz sentido.

### 5.3 Leitura do CSV (Zoom) — `parse_csv()`

Lê `data/aniversariantes_zoom.csv` (`Nome`, `Data Nasc.` em `dd/mm`), descarta linhas
inválidas, cria `Dia`, `Mês_Num`, `Mês` e `Número` e **ordena por mês e depois
por dia**:

```python
df.sort_values(["Mês_Num", "Dia", "Nome"])
```

Assim a tabela e a mensagem saem em ordem cronológica, não na ordem em que você
digitou no arquivo.

`read_and_parse_csv()` é a versão com cache.

### 5.4 Gênero (irmão / irmã) — `genero_de()`

1. Normaliza o nome (maiúsculas, espaços colapsados);
2. Procura no `data/generos.json` pelo **nome completo**;
3. Se não achar, procura pelo **primeiro nome**;
4. Se ainda não achar, devolve `None` → a mensagem trata como **irmão**.

`nomes_sem_genero(df)` lista quem está sem cadastro; as páginas mostram isso num
expander de aviso. Quando o nome não é encontrado, basta abrir `data/generos.json` e
adicionar `"NOME": "M"` ou `"NOME": "F"`.

### 5.5 Envio — `enviar_via_evolution_api()`

```python
POST {EVOLUTION_BASE_URL}/message/sendText/{EVOLUTION_INSTANCE}
Headers: { "apikey": EVOLUTION_APIKEY, "Content-Type": "application/json" }
Body: {
  "number": destino,
  "text": texto,
  "options": {"delay": 0, "presence": "composing", "linkPreview": false},
  "textMessage": {"text": texto}
}
```

- Se o JID termina em `@g.us` (grupo), envia o JID inteiro;
- Caso contrário, remove tudo que não é dígito e envia só o número;
- `200`/`201` → sucesso; qualquer outro status ou exceção → falha com mensagem.

### 5.6 Texto da mensagem do ICM — `montar_mensagem_aniversariantes()`

Monta linhas com ícone por pessoa e escolhe a concordância:

| Cenário | Abertura | Fechamento |
|---|---|---|
| 1 mulher | "vida da nossa **irmã**" | "abençoe grandemente a **sua vida**" |
| 1 homem | "vida do nosso **irmão**" | "abençoe grandemente a **sua vida**" |
| Várias, todas mulheres | "vida das nossas **irmãs**" | "abençoe ... a vida de **cada uma**" |
| Vários homens | "vida dos nossos **irmãos**" | "abençoe ... a vida de **cada um**" |
| Misto | "vida dos nossos **irmãos**" | "abençoe ... a vida de **cada um**" |

Exemplo (duas mulheres):

```
🎉 *ANIVERSARIANTES DO DIA (30/10)* 🎉

Hoje é dia de comemorar a vida das nossas irmãs: 🥳

• 👧🎉 *KATHELIN ALVES LOBATO*
• 👧🎉 *JOVELINA LOPES LOUBACH*

Desejamos que o Senhor abençoe grandemente a vida de cada uma! Parabéns! 🎂🎈
```

No ICM a linha leva o grupo de assistência entre parênteses; se o `DataFrame`
não tiver essa coluna (Zoom), o parêntese não aparece.

### 5.7 Texto da mensagem do Zoom — `montar_mensagem_zoom()`

Um parabéns nominal por aniversariante:

```
🎉 *ANIVERSARIANTES DO DIA (25/10)* 🎉

👧🎉 Parabéns, *Sara*! Que o Senhor abençoe grandemente a sua vida! 🎂🎈
```

Com duas pessoas, saem duas linhas — cada uma com o seu "Parabéns, *Nome*!".

### 5.8 Disparo automático

`_disparar_do_dia(df, origem, destino_jid, nome_grupo, montar_mensagem)` é o
núcleo:

1. verifica se o JID do destino está configurado;
2. verifica se a lista tem dados;
3. filtra `Data Nasc. == hoje (dd/mm)`;
4. se não houver ninguém, grava no log e encerra sem enviar;
5. monta a mensagem, envia e grava o resultado em `runtime/aniversariantes.log`.

As funções chamadas pelo agendador são apenas atalhos:

```python
disparar_aniversariantes_icm()   # parse_pdf + envio para o grupo do ICM
disparar_aniversariantes_zoom()  # parse_csv + envio para o grupo do Zoom
```

Ambas capturam exceções e registram o erro no log — um problema no ICM nunca
impede o disparo do Zoom (são jobs independentes).

---

## 6. `core/agendamentos.py` — envios com data/hora escolhida

### 6.1 Armazenamento

Cada agendamento é um registro em `runtime/envios_agendados.json`:

```json
{
  "id": "7be5dcf1",
  "texto": "Mensagem...",
  "jid": "5534999998888",
  "nome": "Lucas teste",
  "quando": "2026-10-30T09:30:00-03:00",
  "status": "pendente",
  "criado_em": "2026-10-29T21:50:27-03:00",
  "resultado": ""
}
```

Status possíveis: `pendente`, `enviado`, `erro`, `cancelado`, `perdido`.

### 6.2 Funções

| Função | O que faz |
|---|---|
| `agora()` | data/hora atual no fuso `America/Sao_Paulo` |
| `ler_agendamentos()` | lê o JSON (lista, ou `[]` se não existir) |
| `_gravar_agendamentos()` / `_atualizar()` | persiste e altera um registro |
| `_executar(id)` | roda no horário: confere status, envia pela Evolution API, grava `enviado`/`erro` |
| `_reagendar_pendentes()` | ao subir o app, re-registra no scheduler tudo que ainda está `pendente` e no futuro; o que venceu enquanto o app estava parado vira `perdido` |
| `obter_agendador()` | `BackgroundScheduler` único (`@st.cache_resource`), usado pelos jobs diários e pelos agendamentos |
| `agendar_envio()` | valida o horário, grava no JSON e cria um job `DateTrigger` |
| `cancelar_agendamento()` | remove o job e marca `cancelado` |

### 6.3 Garantias e limites

- Os agendamentos **sobrevivem a reinícios** do app (ficam no JSON).
- Mas só disparam com o **processo do Streamlit em execução** no horário marcado.
- Se o app estava parado no momento e voltou depois: se o atraso for ≤ 1h e o job
  estava registrado, executa; se o processo estava morto, o registro é marcado
  como `perdido` na próxima subida.
- Cancelar depois que o envio já ocorreu não desfaz a mensagem no WhatsApp.

---

## 7. `pages/aniversariantes_icm.py`

1. `st.set_page_config(...)` e título da página;
2. `read_and_parse_pdf(ARQUIVO_PDF)`;
3. se o PDF não existir/estiver vazio → `st.error` e `return`;
4. mapeia `Mês_Num` para nome do mês;
5. mostra o expander com nomes sem gênero cadastrado;
6. barra lateral exibe o grupo fixo do ICM (nome + JID);
7. `st.date_input` (padrão: hoje) → filtra `Data Nasc. == dd/mm`;
8. se houver aniversariantes: mostra o texto, botão de disparo real e botão
   "Abrir no WhatsApp Web" (`https://web.whatsapp.com/send?text=...`);
9. abaixo, tabela completa com filtros de mês e grupo de assistência e métricas.

O bloco final `if __name__ == "__main__": render_pagina()` permite importar o
módulo (é o que o `main.py` faz) sem renderizar a interface fora da página.

---

## 8. `pages/aniversariantes_zoom.py`

Mesma estrutura da página do ICM, com diferenças:

- lê `data/aniversariantes_zoom.csv` (`read_and_parse_csv`);
- a lista já vem **ordenada por mês/dia**;
- a barra lateral mostra o grupo do Zoom; se `JID_GRUPO_ZOOM` estiver vazio, o
  botão de disparo fica desabilitado e aparece um aviso;
- a tabela mostra `Número`, `Data Nasc.`, `Mês`, `Dia` e `Nome`;
- usa `montar_mensagem_zoom()` (parabéns nominal), não o texto do ICM.

---

## 9. `pages/mensagens.py`

Tem uma mensagem compartilhada no topo (passo 1) e **três abas** (passo 2).

### 9.1 Fonte dos dados

```python
buscar_grupos_whatsapp()   # GET /group/fetchAllGroups/{instance}?getParticipants=false
buscar_contatos_whatsapp() # POST /chat/findContacts/{instance}  body: {"where": {}}
```

Ambas usam `@st.cache_data(ttl=600)` (10 minutos). O botão
**🔄 Recarregar Grupos e Contatos** na barra lateral limpa o cache.

Dos contatos retornados, só entram os que terminam em `@s.whatsapp.net` (números
reais). Identificadores `@lid` e canais (`@newsletter`) são ignorados. O nome
exibido é o `pushName`; se não houver, o número formatado.

`formatar_numero()` transforma `5534999998888` em `+55 (34) 99999-8888`.

### 9.2 Aba 👥 Grupos

- Campo de busca por nome;
- "Marcar Todos Visíveis" / "Desmarcar Todos";
- lista de checkboxes em um container com rolagem, estado guardado em
  `st.session_state["selecao_grupos"]`;
- **tabela** `Grupo | Código (JID)` dos marcados + bloco de código clicável para
  copiar o JID;
- botão de disparo → `disparar_para_destinos()`, que mostra progresso,
  sucesso/erro por destino e resumo final.

### 9.3 Aba 💬 Conversas

Dois modos:

1. **Escolher da lista**: `st.multiselect` com rótulos `Nome — +55 (34) ...`
   (a busca filtra por nome ou número) e tabela dos selecionados;
2. **Digitar número**: campos de número e nome opcional; valida 10–15 dígitos;
   mostra o destino formatado e envia com o botão.

O envio individual usa o mesmo `enviar_via_evolution_api()`; para números, o
payload leva apenas os dígitos.

### 9.4 Aba ⏰ Agendar

- Destino: **Número** (com nome opcional) ou **Grupo** (selectbox);
- Data (`st.date_input`) e hora (`st.time_input`, padrão = próxima hora cheia);
- usa a mensagem digitada no passo 1;
- valida texto, destino e se o horário está no futuro;
- chama `agendar_envio()` → grava no JSON, cria o job e mostra confirmação;
- lista os agendamentos **pendentes** em tabela, com selectbox + botão
  **🗑️ Cancelar agendamento**;
- expander com o **histórico** (destino, quando, status, resultado).

---

## 10. Arquivos de dados

### 10.1 `data/aniversariantes_zoom.csv`

```csv
Nome,Data Nasc.
Rosa,04/01
Marilene,10/02
...
```

- Cabeçalho obrigatório com `Nome` e `Data Nasc.`;
- Data sempre no formato `dd/mm` (sem ano);
- Pode adicionar linhas em qualquer ordem — o código ordena por mês/dia;
- Nomes são a chave do `data/generos.json` (ou o primeiro nome).

### 10.2 `data/generos.json`

```json
{
  "FULANO DE TAL": "M",
  "SICRANA DE TAL": "F",
  "TANIA": "F"
}
```

Chaves podem ser nome completo **ou** primeiro nome. Se a pessoa não estiver
cadastrada, a mensagem usa "irmão" e a página mostra o aviso de pendências.

### 10.3 Logs

- `runtime/aniversariantes.log`: disparos automáticos (ICM/Zoom), com data/hora, nomes e
  resultado;
- `runtime/envios_agendados.log`: criação, execução e cancelamento de agendamentos.

Formato: `[2026-10-29 21:50:27] [ICM] Aniversariantes de 29/10: ... | Envio ...: OK`.

---

## 11. Fluxo de execução resumido

```
Streamlit inicia main.py
   └── carrega .env
   └── obter_agendador()  (scheduler único, cache_resource)
        └── re-registra agendamentos pendentes do JSON
   └── add_job(ICM,  cron 00:00)
   └── add_job(Zoom, cron 00:00)

00:00 (Brasília)
   ├── ICM  → parse_pdf  → filtra hoje → monta msg → sendText → log
   └── Zoom → parse_csv  → filtra hoje → monta msg → sendText → log

Usuário na página Mensagens
   └── envia agora (grupos/contatos/número)
   └── agenda → JSON + DateTrigger
        └── no horário: _executar → sendText → status no JSON
```

---

## 12. Limitações e cuidados

1. **O app precisa estar rodando** para qualquer disparo automático. Aba do
   navegador pode ficar fechada; o processo (`streamlit run`) não pode.
2. No **Streamlit Cloud**, o app hiberna por inatividade e a meia-noite pode ser
   perdida. Para garantia real: VPS, `launchd`/`cron` no Mac ou GitHub Actions.
3. Reiniciar o app **não perde** agendamentos futuros (são recarregados do JSON),
   mas o horário precisa continuar no futuro.
4. Duas instâncias do app rodando ao mesmo tempo = mensagens automáticas
   **duplicadas** (cada processo tem seu scheduler).
5. O filtro de data usa `datetime.now()` do servidor; o agendador usa o fuso de
   Brasília. Em servidores com fuso muito atrasado, o dia pode divergir.
6. Credenciais ficam no `.env` — não versione esse arquivo.

---

## 13. Solução de problemas

| Sintoma | Onde olhar |
|---|---|
| Nada foi enviado à meia-noite | app estava rodando? veja `runtime/aniversariantes.log` |
| "JID não configurado" | preencha `JID_GRUPO_IGREJA_FIXO` / `JID_GRUPO_ZOOM` |
| Erro 401/403 na Evolution API | `EVOLUTION_APIKEY` e `EVOLUTION_INSTANCE` |
| Mensagem no gênero errado | ajuste o nome em `data/generos.json` |
| Pessoa não aparece | confira a data no PDF/CSV (`dd/mm`) |
| Agendamento não disparou | status no histórico da aba ⏰; app estava rodando? |
| Lista de grupos/contatos vazia | botão 🔄 ou verifique a conexão da instância |

---

## 14. Ideias de evolução

- Botão "Executar agora" para testar cada job sem esperar a meia-noite;
- Editar datas/gêneros direto na interface (em vez de CSV/JSON);
- Enviar imagem/áudio além de texto;
- Reagendar um agendamento existente;
- Substituir o scheduler interno por `launchd`/`cron` + script standalone.
