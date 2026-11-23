#!/usr/bin/env bash
# Monta a cópia pública do projeto (código, instruções e documentação) numa pasta,
# a partir de uma lista fixa de caminhos, e confere que nada privado entrou.
#
# Uso: scripts/espelho/montar.sh <pasta-de-saída>
# Rode a partir da raiz do repositório privado. A pasta de saída é recriada.
#
# Só entra o que está em INCLUIR. Relatórios, estado, dados, painel e prévias HTML
# resumem matérias de terceiros ou são dados do responsável: ficam só no privado.
set -euo pipefail

SAIDA="${1:?informe a pasta de saída}"

INCLUIR=(
  CLAUDE.md
  .gitignore
  requirements.txt
  config
  etapas
  modelos
  glossario
  scripts
  tests
  docs
  integracoes
)

# Caminhos que nunca podem aparecer na cópia pública.
PROIBIDO='^(relatorios|estado|dados|painel)/|\.html?$|(^|/)\.env|\.(pem|key|p12|pfx)$|(^|/)(credenciais|secrets)'

# Exceção: os modelos HTML do dashboard e do Panorama são código (sem dados; o
# gerador troca o marcador /*__DADOS__*/null pelo JSON do dia). Só entram se o
# marcador estiver vazio, conferido abaixo.
MODELOS_HTML='^scripts/indicadores/[a-z_]+_modelo\.html$'

# Formatos de credencial reais (mais estrito que a etapa 7, porque o código
# tem linhas legítimas como "const token = ...").
SEGREDOS='(ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|xox[abp]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)'

rm -rf "$SAIDA"
mkdir -p "$SAIDA"

for caminho in "${INCLUIR[@]}"; do
  [ -e "$caminho" ] || { echo "Aviso: $caminho não existe; pulado."; continue; }
  # git ls-files: só arquivos versionados (nada de caches ou arquivos locais).
  git ls-files -z -- "$caminho" | while IFS= read -r -d '' arq; do
    mkdir -p "$SAIDA/$(dirname "$arq")"
    cp -p "$arq" "$SAIDA/$arq"
  done
done

# README e licença próprios da versão pública.
cp publico/README.md "$SAIDA/README.md"
[ -f publico/LICENSE ] && cp publico/LICENSE "$SAIDA/LICENSE"

# Workflows só como referência: fora de .github/workflows, o GitHub não os executa.
if ls .github/workflows/*.yml >/dev/null 2>&1; then
  mkdir -p "$SAIDA/referencia/workflows"
  cp -p .github/workflows/*.yml "$SAIDA/referencia/workflows/"
fi

# Checagens: qualquer falha impede a publicação.
cd "$SAIDA"
if find . -type f | sed 's|^\./||' | grep -Ev "$MODELOS_HTML" | grep -E "$PROIBIDO"; then
  echo "BLOQUEADO: caminho privado na cópia pública."; exit 1
fi
for modelo in $(find . -type f | sed 's|^\./||' | grep -E "$MODELOS_HTML" || true); do
  if ! grep -qF '/*__DADOS__*/null' "$modelo"; then
    echo "BLOQUEADO: $modelo não está com o marcador de dados vazio."; exit 1
  fi
done
if grep -rIlE "$SEGREDOS" .; then
  echo "BLOQUEADO: padrão de credencial na cópia pública."; exit 1
fi
# O valor de cada chave configurada (passada por variável de ambiente) não pode aparecer.
for var in ESPELHO_TOKEN FRED_API_KEY BLS_API_KEY BANXICO_TOKEN BCENTRAL_USER BCENTRAL_PASS; do
  valor="${!var:-}"
  if [ -n "$valor" ] && grep -rIqF -- "$valor" .; then
    echo "BLOQUEADO: valor de $var na cópia pública."; exit 1
  fi
done

echo "Cópia pública montada: $(find . -type f | wc -l) arquivos. SEM_SEGREDOS"
