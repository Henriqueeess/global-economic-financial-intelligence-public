# Etapa 7 — Entrega e arquivo

**Objetivo:** gravar a execução no repositório, atualizar o estado e publicar com commit e push, sem sobrescrever nada e sem expor segredos.

## Passos

1. **Confira a pasta da execução:** devem existir os seis arquivos de `saida.arquivos` (`relatorio-en.md`, `relatorio-pt.md`, `fontes.json`, `verificacao.md`, `paridade.md`, `execucao.log`).
2. **Atualize o estado:**
   - `estado/urls-publicadas.csv`: acrescente uma linha por fonte principal publicada (nunca apague linhas).
   - `estado/temas-em-andamento.md`: atualize os temas que seguem relevantes e remova os encerrados, registrando a data.
3. **Confirme o escopo de escrita:** `git status --porcelain` só pode listar arquivos em `relatorios/`, `estado/` e `glossario/termos-financeiros.yaml`. Se houver qualquer outro arquivo alterado, desfaça essa alteração (`git checkout -- <arquivo>`) e registre no log.
4. **Confirme que nada foi sobrescrito:** `git diff --name-status` não pode mostrar `M` ou `D` em arquivos de pastas de execuções anteriores.
5. **Checagem de segredos** (obrigatória antes do commit):

   ```bash
   git add relatorios/ estado/ glossario/termos-financeiros.yaml
   git diff --cached | grep -nEi \
     '(ghp_|gho_|github_pat_|sk-[a-z0-9]{20,}|xox[abp]-|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|api[_-]?key[\"'\'' ]*[:=]|token[\"'\'' ]*[:=]|password[\"'\'' ]*[:=]|senha[\"'\'' ]*[:=])' \
     && echo "SEGREDO_SUSPEITO" || echo "SEM_SEGREDOS"
   ```

   Se a saída for `SEGREDO_SUSPEITO`, **não faça commit**: remova o conteúdo, registre `checagem_segredos falha` no log (sem copiar o valor) e repita.
6. **Finalize o log:** registre `checagem_segredos ok`, os totais da execução e `fim`. Adicione o log ao commit.
7. **Commit** com a mensagem de `git.mensagem_commit`, por exemplo:
   `Relatório 2026-11-19 07h30` (agendada) ou `Relatório 2026-11-18 15h40-manual` (manual).
8. **Push** para `main`: `git push origin main`. Em caso de erro de rede, tente até 4 vezes com espera de 2 s, 4 s, 8 s e 16 s. Se o push for rejeitado porque a `main` remota avançou, faça `git pull --rebase origin main` (apenas para os seus commits ainda não publicados) e tente de novo. Nunca use `--force`.

## Saída

Commit publicado na `main` com a pasta da execução e o estado atualizado. Na resposta final da sessão, informe a pasta, o resultado da paridade, os totais de verificação e o link do commit.
