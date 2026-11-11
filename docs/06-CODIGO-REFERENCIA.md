# 📌 Painel de Automação do WhatsApp — Documentação

Sistema Streamlit para disparar mensagens no WhatsApp via **Evolution API**, com:

- **Aniversariantes do ICM** (lidos do `data/data.pdf`, com grupos de assistência)
- **Aniversariantes do Zoom** (lista manual em CSV, ordenada por mês/dia)
- **Mensagens avulsas** para grupos, contatos individuais ou número digitado
- **Agendamento de envio único** para uma data/hora escolhida
- **Disparos automáticos diários às 07:00** (ICM e Zoom)

---

## 1. Estrutura de arquivos

```
check-birthday/
├── main.py                        # Página inicial + agendador (jobs diários)
├── core/
│   ├── __init__.py
│   ├── comum.py                   # Regras compartilhadas (dados, gênero, envio, mensagens)
│   ├── evolution.py               # Instâncias, QR Code, grupos e contatos (Evolution API)
│   ├── auth.py                    # Login do painel + instância por usuário
│   └── agendamentos.py            # Envios agendados (data/hora) + scheduler único
├── pages/
│   ├── aniversariantes_icm.py     # Subpágina: aniversariantes do ICM
│   ├── aniversariantes_zoom.py    # Subpágina: aniversariantes do Zoom
│   ├── mensagens.py               # Subpágina: grupos, conversas e agendamento
│   └── conexao_whatsapp.py        # Subpágina: conectar o WhatsApp via QR Code
├── data/
│   ├── data.pdf                   # Lista oficial do ICM (não editar à mão)
│   ├── aniversariantes_zoom.csv   # Lista manual do Zoom
│   ├── generos.json               # Nome -> "M" / "F" (irmão / irmã)
│   └── exclusoes.json             # Quem NÃO deve ser citado (icm / zoom)
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
| `EVOLUTION_APIKEY` | Token da instância (funciona só para ela) |
| `EVOLUTION_GLOBAL_APIKEY` | Chave mestre do servidor (`AUTHENTICATION_API_KEY`); necessária para criar instâncias por usuário |
| `EVOLUTION_INSTANCE_PREFIX` | Prefixo das instâncias criadas por usuário (padrão `cb-`) |
| `APP_USERS` | Login do painel em JSON (`{"usuario": "senha"}` ou com `nome`/`instancia`) |
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

## 4. `main.py` — página inicial e agendador de envios avulsos

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

### 4.2 Agendador do app

```python
def inicializar_agendador_cron():
    return obter_agendador()
```

- `obter_agendador()` vem de `core/agendamentos.py` e é decorado com
  `@st.cache_resource` → existe **um único** `BackgroundScheduler` por processo,
  mesmo com os reruns do Streamlit.
- Esse scheduler cuida **apenas dos envios avulsos** (`DateTrigger`).
- O disparo diário dos aniversariantes **não** fica aqui: roda no GitHub Actions
  às **07:00** de Brasília (`.github/workflows/disparo-diario.yml`, cron
  `0 10 * * *` em UTC).

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
ARQUIVO_EXCLUSOES = PASTA_DADOS / "exclusoes.json"
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
POST {EVOLUTION_BASE_URL}/message/sendText/{instancia}
Headers: { "apikey": chave_api(instancia), "Content-Type": "application/json" }
Body: {
  "number": destino,
  "text": texto,
  "options": {"delay": 0, "presence": "composing", "linkPreview": false},
  "textMessage": {"text": texto}
}
```

- `instancia` é opcional; sem ela, usa `instancia_ativa()` (a do usuário logado)
  ou a padrão `EVOLUTION_INSTANCE`.
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
5. monta a mensagem, envia **pela instância fixa `EVOLUTION_INSTANCE`** e grava o
   resultado em `runtime/aniversariantes.log`.

> O automático não usa a instância do usuário logado: ele roda no GitHub Actions,
> sem sessão do painel, e precisa de uma instância fixa.

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

### 6.5 `core/evolution.py` — instâncias e QR Code

| Função | O que faz |
|---|---|
| `chave_api(instancia)` | usa a chave global, ou o token da instância padrão |
| `estado(instancia)` | `open` / `connecting` / `close` / `nao_existe` / `sem_chave` / `erro` |
| `criar_instancia(instancia)` | `POST /instance/create` (exige `EVOLUTION_GLOBAL_APIKEY`) |
| `conectar(instancia)` | `GET /instance/connect/{instancia}` → QR base64/código |
| `desconectar(instancia)` | `DELETE /instance/logout/{instancia}` |
| `deletar(instancia)` | `DELETE /instance/delete/{instancia}` (exige chave global) |
| `listar_instancias()` / `info_instancia()` | `GET /instance/fetchInstances` |
| `buscar_grupos()` / `buscar_contatos()` | grupos e contatos da instância |
| `extrair_qr()` / `qr_bytes()` | separa e decodifica o base64 do QR |

### 6.6 `core/auth.py` — login e instância por usuário

- Lê `APP_USERS` (JSON) e normaliza
  `{usuario: {senha, nome, instancia, admin}}`.
- `instancia_do_usuario()` usa `instancia` do cadastro ou
  `EVOLUTION_INSTANCE_PREFIX + slug(usuario)`.
- `eh_admin()` libera a página `pages/usuarios.py`; para os demais, o item do
  menu é escondido e a página mostra "acesso restrito".
- `exigir_login()` renderiza o formulário, guarda `st.session_state["usuario"]` e
  `st.session_state["instancia_whatsapp"]` e chama `st.stop()` quando não há
  login. Sem `APP_USERS`, mantém o modo antigo (sem login, instância padrão).
- `instancia_atual()` é usada por todas as páginas para saber qual WhatsApp usar.

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
buscar_grupos_whatsapp(instancia)   # GET /group/fetchAllGroups/{instancia}?getParticipants=false
buscar_contatos_whatsapp(instancia) # POST /chat/findContacts/{instancia}  body: {"where": {}}
```

As funções ficam em `core/evolution.py` e são embrulhadas com
`@st.cache_data(ttl=600)` (10 minutos) na página. A instância vem do usuário
logado (`instancia_atual()`), então o cache é separado por instância. O botão
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

### 9.5 `pages/conexao_whatsapp.py`

1. `exigir_login()` → usuário logado e instância atual;
2. consulta `evolution.estado(instancia)` e mostra o status:
   - `open` → perfil/número conectados + botão **Desconectar** (com confirmação);
   - `nao_existe` → botão **Criar instância e gerar QR Code** (exige chave global);
   - `close`/`connecting` → botão **Gerar QR Code**;
   - `sem_chave`/`erro` → aviso de configuração;
3. o QR vem de `GET /instance/connect/{instancia}` e é exibido com `st.image`;
4. um `st.fragment(run_every=3)` acompanha o estado e, quando fica `open`, limpa o
   QR e recarrega a página.

### 9.6 `core/presenca.py` — faltas, números e mensagens

- `data/presencas.json` → `{"datas": {"AAAA-MM-DD": [nomes]}, "visitas": {nome: {data, faltas}}}`.
- `salvar_faltas(dia, nomes)` grava o dia **mesmo vazio** — é o que quebra a
  sequência de faltas de quem compareceu.
- `faltas_consecutivas(nome, dia)` percorre os dias registrados de trás para
  frente e conta até a primeira presença.
- `precisa_visita(nome, dia)` → `(bool, sequencia)`: `True` ao atingir
  `LIMITE_VISITA` (7) e ainda não avisado nesta sequência; `registrar_visita`
  guarda o aviso para não repetir.
- `data/contatos_membros.json` → nome normalizado → JID/número.
- `data/mensagens_presenca.json` → `{"falta": "...", "visita": "..."}` com
  `{nome}`, `{data}` e `{faltas}`.

### 9.7 `pages/presenca.py` — página 📋 Presença

1. lê `data.pdf` com `read_and_parse_pdf` (137 pessoas, com Grupo de Assistência);
2. **📋 Marcar faltas**: `date_input` + filtros + checkboxes; salva com
   `salvar_faltas`; mostra faltantes, envia "sentimos sua falta" e a mensagem de
   visita para quem passou de 7 faltas seguidas;
3. **📱 Números**: contatos da instância (`buscar_contatos`, cache de 10 min),
   vínculo automático pelo nome e formulário manual;
4. **✉️ Mensagens**: edita os dois textos e mostra prévia.

### 9.8 `core/importacao.py` — planilhas, PDF e junção

- `ler_planilha(nome, bytes, cabecalho=None)` → `{aba: DataFrame}` para
  csv/tsv/txt/xlsx/xls/ods. `cabecalho=None` detecta: primeira linha só com
  texto = cabeçalho; com número/telefone = dado.
- CSV é lido com separadores explícitos `,` `;` `\t` (sem detector automático,
  que quebra telefone no espaço).
- `ler_pdf(nome, bytes, cabecalho=None)` → uma tabela por página/tabela do
  `pdfplumber`. Célula com caminho de imagem vem como texto.
- `extrair_imagens_pdf(nome, bytes)` → salva em `data/fotos/` e devolve
  `{arquivo, pagina, x, y}`.
- `juntar(itens, modo)`:
  - `modo="coluna"` → chave normalizada, junção externa (`merge how="outer"`),
    chave repetida fica a primeira;
  - `modo="posicao"` → `concat(axis=1)`, linha 1 com linha 1;
  - colunas com nome repetido ganham sufixo `(arquivo)`.
- `normalizar_telefone` → só dígitos + DDI 55 quando tem 10/11 dígitos.
- `ajustar_caminho_imagem` → troca caminho absoluto por `data/fotos/<arquivo>`
  quando a foto existe lá.
- `salvar_json(df, colunas, nome, chave_raiz)` → `data/<slug>.json` no formato
  `{"<chave_raiz>": [ {...} ]}`.

### 9.9 `pages/importar.py` — página 📤 Importar planilhas

1. `file_uploader` múltiplo (csv/tsv/txt/xlsx/xls/ods/pdf);
2. por arquivo: cabeçalho (auto/cabeçalho/dado), aba, renomear colunas,
   prévia e, no modo por coluna, a coluna-chave;
3. detecta colunas de telefone e de caminho de imagem;
4. **🔗 Juntar tabelas** chama `importacao.juntar` e guarda o resultado em
   `st.session_state`;
5. escolhe as colunas do JSON, normaliza telefones, ajusta fotos e salva com
   `importacao.salvar_json` (+ download).

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

Separado por fonte (`icm` e `zoom`), para o mesmo nome não vazar de uma lista
para a outra:

```json
{
  "icm": {
    "FULANO DE TAL": "M",
    "SICRANA DE TAL": "F"
  },
  "zoom": {
    "TANIA": "F"
  }
}
```

Chaves podem ser nome completo **ou** primeiro nome. Se a pessoa não estiver
cadastrada, a mensagem usa "irmão" e a página mostra o aviso de pendências.

No código:

```python
carregar_generos("icm")   # só ICM
carregar_generos("zoom")  # só Zoom
carregar_generos()        # junta as duas fontes
```

O formato antigo (um único dicionário plano) continua sendo aceito.

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

GitHub Actions (07:00 de Brasília)
   └── scripts/disparar_aniversariantes.py
        ├── ICM  → parse_pdf  → filtra hoje → monta msg → sendText → log
        └── Zoom → parse_csv  → filtra hoje → monta msg → sendText → log

Usuário na página Mensagens
   └── envia agora (grupos/contatos/número)
   └── agenda → JSON + DateTrigger
        └── no horário: _executar → sendText → status no JSON
```

---

## 12. Limitações e cuidados

1. **O app precisa estar rodando** para os envios avulsos agendados. Aba do
   navegador pode ficar fechada; o processo (`streamlit run`) não pode.
2. No **Streamlit Cloud**, o app hiberna por inatividade e um envio avulso pode
   ser perdido. O disparo diário não depende disso: roda no GitHub Actions.
3. Reiniciar o app **não perde** agendamentos futuros (são recarregados do JSON),
   mas o horário precisa continuar no futuro.
4. Duas instâncias do app rodando ao mesmo tempo = mensagens automáticas
   **duplicadas** (cada processo tem seu scheduler).
5. O filtro de data usa `datetime.now()` do servidor; o agendador usa o fuso de
   Brasília. Em servidores com fuso muito atrasado, o dia pode divergir.
6. Credenciais ficam no `.env` — não versione esse arquivo.
7. **Criar instância por usuário exige a chave global** (`EVOLUTION_GLOBAL_APIKEY`).
   Com só o token da instância, o painel apenas reconecta `EVOLUTION_INSTANCE`.
8. O **disparo automático das 07:00** continua usando a instância fixa
   `EVOLUTION_INSTANCE`; a conexão por usuário vale para os envios manuais.
9. Para enviar a um grupo, a conta conectada precisa **participar** do grupo. O
   JID é o mesmo, mas a conta sem acesso recebe erro da Evolution API.

---

## 13. Solução de problemas

| Sintoma | Onde olhar |
|---|---|
| Nada foi enviado às 07:00 | veja o log da execução em **Actions** e `runtime/aniversariantes.log` |
| "JID não configurado" | preencha `JID_GRUPO_IGREJA_FIXO` / `JID_GRUPO_ZOOM` |
| Erro 401/403 na Evolution API | `EVOLUTION_APIKEY` e `EVOLUTION_INSTANCE` |
| Erro 401 ao criar instância | falta `EVOLUTION_GLOBAL_APIKEY` (chave mestre) |
| QR Code não aparece | clique em **Gerar QR Code** de novo; confira a instância |
| Grupos/contatos de outra conta | a instância ativa é a do usuário logado |
| Mensagem no gênero errado | ajuste o nome em `data/generos.json` |
| Pessoa não aparece | confira a data no PDF/CSV (`dd/mm`) |
| Agendamento não disparou | status no histórico da aba ⏰; app estava rodando? |
| Lista de grupos/contatos vazia | botão 🔄 ou verifique a conexão da instância |

---

## 14. Ideias de evolução

- Botão "Executar agora" para testar cada job sem esperar as 07:00;
- Editar datas/gêneros direto na interface (em vez de CSV/JSON);
- Enviar imagem/áudio além de texto;
- Reagendar um agendamento existente;
- Substituir o scheduler interno por `launchd`/`cron` + script standalone.
