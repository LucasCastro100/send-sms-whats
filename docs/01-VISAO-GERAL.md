# 🧭 Visão geral — como o sistema funciona

Este documento explica **o que o sistema faz**, **quais são as partes** e **como
os dados circulam** entre elas. Para detalhes de uso, veja
[`02-MANUAL-DE-USO.md`](02-MANUAL-DE-USO.md); para detalhes de código, veja
[`06-CODIGO-REFERENCIA.md`](06-CODIGO-REFERENCIA.md).

---

## 1. Objetivo

Automatizar o envio de mensagens de WhatsApp do ICM e do grupo Zoom:

1. **Aniversariantes do ICM** — lista oficial extraída do `data/data.pdf`;
2. **Aniversariantes do Zoom** — lista manual em `data/aniversariantes_zoom.csv`;
3. **Mensagens avulsas** — para grupos, contatos ou número digitado;
4. **Envios agendados** — mensagem única para uma data/hora escolhida;
5. **Disparo diário automático à meia-noite** para os dois grupos de aniversariantes.

Tudo em uma interface web local (Streamlit), falando com o WhatsApp pela
**Evolution API**.

---

## 2. Peças do sistema

| Peça | Tipo | Responsabilidade |
|---|---|---|
| `main.py` | código | página inicial + registra os jobs diários no agendador |
| `core/comum.py` | código | ler PDF/CSV, gênero, montar mensagens, enviar pela API |
| `core/agendamentos.py` | código | scheduler único + fila de envios com data/hora |
| `pages/aniversariantes_icm.py` | interface | consulta/disparo manual do ICM |
| `pages/aniversariantes_zoom.py` | interface | consulta/disparo manual do Zoom |
| `pages/mensagens.py` | interface | grupos, conversas, número digitado e agendamento |
| `data/data.pdf` | dado | lista oficial do ICM |
| `data/aniversariantes_zoom.csv` | dado | lista manual do Zoom |
| `data/generos.json` | dado | quem é irmão (`M`) e quem é irmã (`F`) |
| `runtime/*` | gerado | logs e fila de agendamentos |
| `.env` | configuração | URL/instância/apikey e JIDs dos grupos |
| Evolution API | externo | entrega as mensagens no WhatsApp |
| Streamlit | externo | serve a interface e mantém o processo vivo |

---

## 3. Arquitetura em uma imagem

```
                    ┌──────────────────────────────┐
                    │  Navegador (Streamlit :8501) │
                    └──────────────┬───────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
┌───────▼────────┐        ┌────────▼────────┐        ┌────────▼────────┐
│ Aniversariantes │        │ Aniversariantes │        │    Mensagens    │
│      ICM        │        │      Zoom       │        │ grupos/contatos │
└───────┬────────┘        └────────┬────────┘        └────────┬────────┘
        │                          │                          │
        └──────────────┬───────────┴──────────────┬───────────┘
                       │                          │
              ┌────────▼────────┐        ┌────────▼─────────┐
              │  core/comum.py   │        │core/agendamentos │
              │ dados + mensagens│        │ scheduler + JSON │
              └────────┬─────────┘        └────────┬─────────┘
                       │                          │
              ┌────────▼─────────┐        ┌────────▼─────────┐
              │  Evolution API   │◄───────┤  jobs 00:00 e    │
              │  sendText        │        │  envios avulsos  │
              └────────┬─────────┘        └──────────────────┘
                       │
                 WhatsApp (grupos / contatos)
```

---

## 4. Fluxo dos dados

### 4.1 Aniversariantes do ICM

```
data/data.pdf
   └── parse_pdf()  (regex: nº, dd/mm, nome, grupo de assistência)
        └── hoje = Data Nasc. == dd/mm atual
             └── montar_mensagem_aniversariantes()  (gênero + ícones)
                  └── sendText → JID_GRUPO_IGREJA_FIXO
```

### 4.2 Aniversariantes do Zoom

```
data/aniversariantes_zoom.csv  (Nome, Data Nasc.)
   └── parse_csv()  (ordena por mês/dia)
        └── hoje = Data Nasc. == dd/mm atual
             └── montar_mensagem_zoom()  (um "Parabéns, Nome!" por pessoa)
                  └── sendText → JID_GRUPO_ZOOM
```

### 4.3 Mensagens avulsas

```
texto digitado + destino escolhido (grupo / contato / número)
   └── enviar_via_evolution_api()
        └── sendText → destino
```

### 4.4 Envio agendado

```
texto + destino + data/hora
   └── agendar_envio()
        ├── grava runtime/envios_agendados.json
        └── registra job DateTrigger no scheduler
             └── no horário: _executar() → sendText → status no JSON
```

### 4.5 Disparo diário automático

```
Streamlit inicia → obter_agendador() (singleton)
   ├── re-registra agendamentos pendentes salvos no JSON
   ├── job cron 00:00 → disparar_aniversariantes_icm()
   └── job cron 00:00 → disparar_aniversariantes_zoom()
```

---

## 5. Regras de texto (resumo)

As mensagens do ICM variam com a quantidade e o gênero dos aniversariantes:

| Situação | Abertura | Fechamento |
|---|---|---|
| 1 mulher | vida da nossa irmã | a sua vida |
| 1 homem | vida do nosso irmão | a sua vida |
| várias mulheres | vida das nossas irmãs | a vida de cada uma |
| vários homens | vida dos nossos irmãos | a vida de cada um |
| misto | vida dos nossos irmãos | a vida de cada um |

O Zoom usa outro formato, nominal: `👧🎉 Parabéns, *Sara*! Que o Senhor abençoe
grandemente a sua vida! 🎂🎈`.

O gênero vem de `data/generos.json`. Sem cadastro, a pessoa é tratada como irmão
e aparece um aviso na página.

---

## 6. O que é persistido e onde

| Arquivo | Conteúdo | Vai para o git? |
|---|---|---|
| `data/data.pdf` | lista do ICM | sim |
| `data/aniversariantes_zoom.csv` | lista do Zoom | sim (regra explícita no `.gitignore`) |
| `data/generos.json` | gênero por nome | sim |
| `.env` | segredos e JIDs | **não** |
| `runtime/aniversariantes.log` | histórico dos disparos automáticos | não |
| `runtime/envios_agendados.json` | fila de envios agendados | não |
| `runtime/envios_agendados.log` | histórico dos agendados | não |

---

## 7. Dependências externas

- **Evolution API** — precisa estar no ar e com a instância conectada ao WhatsApp
  (QR Code lido). Se a instância desconectar, os envios falham.
- **Streamlit** — precisa estar rodando para a interface e para os jobs
  automáticos.
- **Internet** — para falar com a Evolution API.

---

## 8. Limites conhecidos

1. Os disparos automáticos dependem do processo do Streamlit vivo.
2. Streamlit Cloud hiberna por inatividade → pode perder a meia-noite.
3. Duas instâncias do app geram envios duplicados.
4. Agendamentos perdidos (app parado no horário) ficam marcados como `perdido`
   e **não** são reenviados automaticamente.
5. A API do WhatsApp pode impor limites/banimento em casos de envio massivo.

---

## 9. Próximos passos sugeridos

- Rodar o disparo diário fora do Streamlit (`launchd`/`cron`/VPS) para
  independência total da interface.
- Editar gêneros e datas pela própria interface.
- Suporte a mídia (imagem/áudio) nas mensagens.

---

📚 Índice completo: [`README.md`](README.md)
