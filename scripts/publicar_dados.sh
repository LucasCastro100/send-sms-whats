#!/usr/bin/env bash
# Publica no GitHub os dados que o disparo diário lê (data/generos.json e
# data/exclusoes.json). Rode depois de ajustar gênero ou "Não enviar SMS" no
# painel: o workflow do Actions não enxerga o banco, só esses arquivos.
#
# Usa o `gh` já autenticado (gh auth login) e não toca no resto do repositório.
#
#   scripts/publicar_dados.sh
#
set -euo pipefail

REPO="${REPO:-LucasCastro100/send-sms-whats}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
MENSAGEM="${MENSAGEM:-dados: espelha generos e exclusoes do painel}"
ARQUIVOS=(data/generos.json data/exclusoes.json)

if ! command -v gh >/dev/null 2>&1; then
  echo "gh não encontrado: instale o GitHub CLI e rode 'gh auth login'." >&2
  exit 1
fi

alterados=0
for arquivo in "${ARQUIVOS[@]}"; do
  local="$RAIZ/$arquivo"
  if [[ ! -f "$local" ]]; then
    echo "faltando: $arquivo" >&2
    exit 1
  fi

  resposta="$(gh api "repos/$REPO/contents/$arquivo" 2>/dev/null || true)"
  sha="$(printf '%s' "$resposta" | python3 -c 'import json,sys; d=sys.stdin.read(); print(json.loads(d)["sha"] if d.strip() else "")')"
  remoto="$(printf '%s' "$resposta" | python3 -c '
import base64, json, sys
d = sys.stdin.read().strip()
print(base64.b64decode(json.loads(d)["content"]).decode("utf-8") if d else "", end="")
')"

  if [[ "$remoto" == "$(cat "$local")" ]]; then
    echo "sem mudanças: $arquivo"
    continue
  fi

  conteudo="$(base64 < "$local" | tr -d '\n')"
  if [[ -n "$sha" ]]; then
    gh api -X PUT "repos/$REPO/contents/$arquivo" \
      -f message="$MENSAGEM" -f content="$conteudo" -f sha="$sha" >/dev/null
  else
    gh api -X PUT "repos/$REPO/contents/$arquivo" \
      -f message="$MENSAGEM" -f content="$conteudo" >/dev/null
  fi
  echo "publicado: $arquivo"
  alterados=$((alterados + 1))
done

if [[ $alterados -eq 0 ]]; then
  echo "Nada para publicar: o GitHub já está igual ao painel."
else
  echo "$alterados arquivo(s) publicado(s) em $REPO. O próximo disparo já usa."
fi
