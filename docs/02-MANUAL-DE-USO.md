# 🖱️ Manual de uso — cada tela e cada ação

Este documento percorre **todas as telas** do sistema e explica o que cada botão,
campo e aba faz. Para entender a arquitetura por trás, veja
[`01-VISAO-GERAL.md`](01-VISAO-GERAL.md); para os detalhes de implementação, veja
[`06-CODIGO-REFERENCIA.md`](06-CODIGO-REFERENCIA.md).

---

## 1. Antes de abrir o sistema

1. Ative o ambiente virtual:

   ```bash
   source .venv/bin/activate
   ```

2. Confira o `.env` (ou os *Secrets*, se estiver na nuvem):

   ```env
   EVOLUTION_BASE_URL=https://sua-evolution-api
   EVOLUTION_INSTANCE=igreja-bot
   EVOLUTION_APIKEY=sua-chave

   JID_GRUPO_IGREJA_FIXO=553498018995-1503451609@g.us
   NOME_GRUPO_IGREJA_FIXO=ICM - IGREJA BOA VISTA

   JID_GRUPO_ZOOM=120363023048839950@g.us
   NOME_GRUPO_ZOOM=ZOOM MG VALE PEDAGOGICO
   ```

3. Rode:

   ```bash
   streamlit run main.py
   ```

4. Abra `http://localhost:8501`. A barra lateral esquerda lista as páginas:
   **Painel**, **Aniversariantes ICM**, **Aniversariantes Zoom** e **Mensagens**.

> ⚠️ Deixe o processo do Streamlit rodando. É ele que mantém o agendador da
> meia-noite e os envios agendados vivos. Fechar o terminal derruba tudo.

---

## 2. Página inicial — 📌 Painel de Automação do WhatsApp

É a página `main.py`. Ela não envia nada; serve para conferir a saúde da
configuração.

| Elemento | O que significa |
|---|---|
| Banner verde | o agendador está ativo e os dois jobs diários foram registrados para **00:00** |
| Texto de aviso | lembrete de que o disparo só ocorre com o app em execução |
| `✅ Conectado à instância: ...` | `EVOLUTION_APIKEY` e `EVOLUTION_INSTANCE` estão preenchidos |
| `❌ Atenção: As credenciais...` | falta alguma das duas variáveis — o envio vai falhar |
| `ICM: ... — JID` | destino do disparo automático do ICM configurado |
| `ICM: JID não configurado` | preencha `JID_GRUPO_IGREJA_FIXO` |
| `ZOOM: ... — JID` | destino do disparo automático do Zoom configurado |
| `Zoom: JID não configurado` | apenas aviso: a consulta do Zoom continua funcionando, mas o disparo fica bloqueado |

Também há atalhos textuais para as três subpáginas. Nenhum botão desta tela
dispara mensagem.

**Ação prática:** abra esta página sempre que mudar o `.env` e reiniciar o app,
para confirmar que as credenciais e os dois JIDs foram lidos.

---

## 3. Aniversariantes ICM — 🎉

Lê `data/data.pdf` (lista oficial, com grupos de assistência).

### 3.1 Aviso de gêneros pendentes

Se algum nome do PDF não estiver em `data/generos.json`, aparece um expander:

> ⚠️ N nome(s) sem gênero cadastrado em generos.json

Abra, veja a lista e cadastre cada nome no JSON com `"M"` ou `"F"`. Enquanto não
cadastrar, a mensagem trata a pessoa como **irmão** (masculino).

### 3.2 Barra lateral — destino fixo

Mostra o **nome** e o **JID** do grupo que recebe o disparo automático
(`NOME_GRUPO_IGREJA_FIXO` / `JID_GRUPO_IGREJA_FIXO`). É só leitura.

### 3.3 Seleção de data

- Campo **Escolha a data desejada** (padrão: hoje);
- o sistema converte para `dd/mm` e filtra a lista do PDF.

Se houver aniversariantes:

- mensagem verde com a quantidade encontrada;
- o **texto exato** que seria enviado, em bloco de código (dá para conferir
  gênero, ícones e concordância antes de enviar);
- dois botões lado a lado.

### 3.4 Botões de envio

| Botão | O que faz |
|---|---|
| **🚀 Disparar para ICM - IGREJA BOA VISTA** | envia o texto pelo `POST /message/sendText` para o JID configurado. Mostra spinner, depois sucesso ou o erro retornado pela API |
| **Abrir no WhatsApp Web** | abre `web.whatsapp.com/send?text=...` com o texto já preenchido — você escolhe o grupo manualmente e envia pelo WhatsApp Web. **Não** usa a Evolution API |

> O botão de disparo **não** pergunta “tem certeza?”. Ao clicar, a mensagem vai
> para o grupo. Use o bloco de código para revisar antes.

### 3.5 Filtros e tabela

Na barra lateral, em **Filtros do PDF**:

- **Filtrar por Mês** — `Todos` ou um mês específico;
- **Filtrar por Grupo** — `Todos` ou um grupo de assistência.

As métricas mostram **Pessoas Filtradas** e **Grupos Presentes**, e a tabela
lista `Número`, `Data Nasc.`, `Mês`, `Nome` e `Grupo de Assistência`. A tabela é
apenas consulta: não envia nada e não altera o PDF.

---

## 4. Aniversariantes Zoom — 🎉

Lê `data/aniversariantes_zoom.csv` e funciona igual à página do ICM, com quatro
diferenças:

1. a ordem da lista é **cronológica** (mês e dia), não a ordem do arquivo;
2. o texto usa `montar_mensagem_zoom()` — um “Parabéns, *Nome*!” por pessoa;
3. a tabela tem as colunas `Número`, `Data Nasc.`, `Mês`, `Dia`, `Nome`;
4. se `JID_GRUPO_ZOOM` estiver vazio, o botão de disparo fica **desabilitado** e
   a barra lateral mostra um aviso. A consulta e o botão do WhatsApp Web
   continuam funcionando.

O aviso de gêneros pendentes e os filtros de mês existem do mesmo jeito.

---

## 5. Mensagens — 💬

A página tem **duas etapas**: escrever o texto (passo 1) e escolher o destino
(passo 2). O texto do passo 1 é reaproveitado por **todas** as abas.

### 5.1 Passo 1 — Conteúdo da Mensagem

Campo de texto grande (220 px) com placeholder. Aceita qualquer conteúdo,
inclusive quebras de linha e emojis. O texto **não** é salvo em arquivo: se
recarregar a página, ele se perde.

### 5.2 Barra lateral — 🔄 Recarregar Grupos e Contatos

Grupos e contatos vêm da Evolution API e ficam em cache por **10 minutos**.
Clique nesse botão quando:

- um grupo foi criado/renomeado agora;
- um contato novo não aparece;
- a lista veio vazia por falha temporária de rede.

O botão limpa todo o cache de dados do Streamlit e força nova busca.

### 5.3 Aba 👥 Grupos

| Elemento | Ação |
|---|---|
| **🔍 Buscar grupo por nome** | filtra a lista em tempo real (não diferencia maiúsculas) |
| **✅ Marcar Todos Visíveis** | marca **somente** os grupos que passam pelo filtro atual |
| **❌ Desmarcar Todos** | desmarca **todos** os grupos, inclusive os que estão fora do filtro |
| Lista de checkboxes | uma caixa por grupo, dentro de um painel com rolagem (240 px) |
| **Grupos Selecionados (N)** | tabela `Grupo | Código (JID)` dos marcados |
| Bloco de código | um JID por linha — clique no ícone de copiar para usar no `.env` |
| **🚀 Disparar para os Grupos Selecionados** | envia o texto do passo 1 para cada grupo marcado |

O botão de disparo valida duas coisas: texto preenchido e pelo menos um grupo
marcado. Depois mostra:

- barra de progresso;
- `✅ Enviado para **Grupo**` ou `❌ Falha ...: motivo`, por destino;
- balões (se houve pelo menos um sucesso) e o resumo
  “N enviado(s) com sucesso, M falha(s)”.

A seleção fica em `st.session_state["selecao_grupos"]`, então marcar/desmarcar um
grupo não perde os outros ao interagir com a tela.

> Copiar o JID por aqui é o jeito mais fácil de preencher
> `JID_GRUPO_IGREJA_FIXO` e `JID_GRUPO_ZOOM`.

### 5.4 Aba 💬 Conversas

No topo: “**N contatos com número** encontrados na instância `...`”. Só entram
contatos com JID `@s.whatsapp.net`; identificadores `@lid`, canais e grupos são
ignorados.

Escolha o modo no radio **Como escolher o destinatário?**:

#### Modo “Escolher da lista”

- **🔍 Buscar e selecionar contatos** — multiselect com rótulos
  `Nome — +55 (34) 99999-8888`; a busca funciona por nome **ou** número;
- tabela **Contatos Selecionados** com nome e número formatado;
- **🚀 Enviar para os Contatos Selecionados** envia para todos os escolhidos.

#### Modo “Digitar número”

- **Número (com DDI e DDD)** — aceita máscara; o sistema remove tudo que não é
  dígito;
- **Nome (opcional, só para o resumo)** — não vai na mensagem, serve apenas para
  identificar o destino na confirmação;
- se o número tiver entre 10 e 15 dígitos, aparece
  `Destino: **Nome** — +55 (34) ...`; fora disso, aparece um aviso de número
  incompleto;
- **🚀 Enviar para este Número** valida texto e número e dispara.

> O número precisa ter **DDI**. Para Brasil: `55` + DDD + número, sem espaços
> (ex.: `5534999998888`). Com 13 dígitos a formatação fica
> `+55 (34) 99999-8888`; com 12, `+55 (34) 9999-8888`.

### 5.5 Aba ⏰ Agendar

Permite programar **um envio único** para uma data/hora, usando o texto do
passo 1.

**Destino**

- **Número** — campos de número e nome opcional (mesmas regras da aba
  Conversas);
- **Grupo** — `selectbox` com todos os grupos encontrados. Se nenhum grupo foi
  carregado, aparece um aviso e não é possível agendar.

**Quando**

- **Data do envio** — padrão: hoje;
- **Hora do envio (Brasília)** — padrão: próxima hora cheia;
- abaixo, a confirmação `⏰ Será enviado em dd/mm/aaaa às hh:mm`.

**Botão ⏰ Agendar envio**

Valida, nesta ordem:

1. o texto do passo 1 está preenchido;
2. o destino é um número válido (10–15 dígitos) ou um grupo selecionado;
3. o horário está no futuro.

Se tudo estiver certo:

- grava o registro em `runtime/envios_agendados.json`;
- registra um job `DateTrigger` no agendador;
- mostra a faixa verde “Envio agendado para **Destino** em **data às hora**”;
- recarrega a tela para atualizar a lista.

**Envios pendentes**

- tabela com `Destino`, `Quando` e os primeiros 60 caracteres da mensagem;
- **Selecione para cancelar** + **🗑️ Cancelar agendamento** — remove o job e
  marca o registro como `cancelado`. Cancelar depois do horário não desfaz uma
  mensagem já enviada.

**Histórico de envios agendados** (expander)

Tabela com `Destino`, `Quando`, `Status` e `Resultado`. Status possíveis:

| Status | Significado |
|---|---|
| `pendente` | aguardando o horário; job ativo |
| `enviado` | a API respondeu 200/201 |
| `erro` | a API recusou ou houve falha de conexão (motivo em `Resultado`) |
| `cancelado` | removido pelo botão de cancelar |
| `perdido` | o horário passou com o app desligado; **não** é reenviado |

---

## 6. Fluxo recomendado no dia a dia

### Enviar um comunicado agora

1. **💬 Mensagens** → escreva o texto no passo 1;
2. escolha **👥 Grupos** ou **💬 Conversas**;
3. marque/selecione os destinos;
4. clique em **🚀 Disparar/Enviar**;
5. confira o resumo de sucessos e falhas.

### Programar um aviso para amanhã

1. escreva o texto no passo 1;
2. vá em **⏰ Agendar**;
3. escolha número ou grupo;
4. defina data e hora (no futuro);
5. clique em **⏰ Agendar envio**;
6. confirme na tabela de pendentes.

### Conferir o que vai sair à meia-noite

1. abra **🎉 Aniversariantes ICM** e **🎉 Aniversariantes Zoom**;
2. selecione **hoje** (ou a data desejada) no campo de data;
3. revise o bloco de código com o texto montado.

### Corrigir “irmão”/“irmã” errado

1. abra `data/generos.json`;
2. adicione ou ajuste a chave com o nome em maiúsculas:

   ```json
   "MARIA DA SILVA": "F",
   "JOSE PEREIRA": "M"
   ```

3. salve. A página relê o JSON a cada execução (não há cache para gêneros), mas
   o Streamlit pode precisar de um clique em **Rerun** (canto superior direito)
   para atualizar a tela.

### Descobrir o JID de um grupo

1. **💬 Mensagens** → **🔄 Recarregar Grupos e Contatos**;
2. aba **👥 Grupos**;
3. busque e marque o grupo;
4. copie o JID que aparece na tabela ou no bloco de código;
5. cole no `.env` (`JID_GRUPO_...`) e reinicie o app.

---

## 7. Onde olhar quando algo dá errado

| Sintoma | O que verificar |
|---|---|
| Nada foi enviado à meia-noite | o app estava rodando? veja `runtime/aniversariantes.log` |
| “JID não configurado” no painel | preencha `JID_GRUPO_IGREJA_FIXO` e/ou `JID_GRUPO_ZOOM` |
| “Credenciais não identificadas” | `EVOLUTION_APIKEY` e `EVOLUTION_INSTANCE` no `.env`/Secrets |
| Erro 401/403 ao enviar | apikey errada ou instância desconectada no WhatsApp |
| Lista de grupos/contatos vazia | clique em 🔄; confira `EVOLUTION_BASE_URL` e a instância |
| Pessoa não aparece na data | confira a data no PDF/CSV; o formato é `dd/mm` |
| Gênero errado na mensagem | cadastre/ajuste o nome em `data/generos.json` |
| Agendamento não disparou | veja o histórico da aba ⏰; app estava ligado? status `perdido`? |
| Mensagem duplicada | há mais de uma instância do app rodando (dois schedulers) |

Os detalhes técnicos de cada erro estão em
[`04-WHATSAPP.md`](04-WHATSAPP.md) e [`03-CRON-E-AGENDAMENTOS.md`](03-CRON-E-AGENDAMENTOS.md).

---

📚 Índice completo: [`README.md`](README.md)
