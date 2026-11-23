"""Testes do Panorama Econômico (sem rede)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from indicadores import relatorio  # noqa: E402
import gerar_panorama  # noqa: E402

MD = """# Global Economic & Financial Intelligence — Edição em português

**Quinta-feira, 19 de novembro de 2026** · Execução iniciada às 07h31

## 1. Resumo executivo

- **Primeiro:** texto <script>alert(1)</script>.

## 2. Economia brasileira

### [Em andamento desde 12/11/2026] Senado conclui votação

O Senado concluiu a votação. O texto vai à Câmara. Terceira frase.

- **Título original:** "x"
- **Publicação:** Agência Senado · 18/11/2026 · 20h04
- **Tipo de fonte:** Comunicado oficial
- **Link:** https://www12.senado.leg.br/a

### Item sem link

Texto.

## 7. Agenda econômica do dia

| Horário (Brasília) | País | Evento | Consenso | Fonte |
| --- | --- | --- | --- | --- |
| 10h30 | EUA | Fala do Fed | n/d | InfoMoney |

---

### Itens não confirmados

- Data da votação: paywall.
"""


def test_le_secoes_itens_agenda_e_nao_confirmados():
    r = relatorio.ler(MD)
    assert r.resumo == ["**Primeiro:** texto <script>alert(1)</script>."]
    assert len(r.itens) == 1  # item sem link fica de fora
    it = r.itens[0]
    assert it.em_andamento and it.titulo == "Senado conclui votação"
    assert it.veiculo == "Agência Senado" and it.link == "https://www12.senado.leg.br/a"
    assert r.tabelas[7][1][2] == "Fala do Fed"
    assert r.nao_confirmados == ["Data da votação: paywall."]


def test_inline_html_escapa_antes_de_formatar():
    h = relatorio.inline_html("**Primeiro:** <script>x</script>")
    assert "<script>" not in h and h.startswith("<b>Primeiro:</b>")


def test_primeiras_frases_nao_corta_numeros():
    t = "O IPCA subiu 0,5. Depois caiu 1.000 vezes. Fim."
    assert relatorio.primeiras_frases(t, 2) == "O IPCA subiu 0,5. Depois caiu 1.000 vezes."


def test_intercala_secoes():
    itens = [relatorio.Item(secao=s, titulo=str(i)) for i, s in enumerate([2, 2, 3, 5])]
    assert gerar_panorama.intercalar(itens, [2, 3, 4, 5], 3) == [0, 2, 3]
    assert gerar_panorama.intercalar(itens, [2, 3, 4, 5], 2) == [0, 2]


def test_gatilho_curto_exige_palavra_inteira():
    assert gerar_panorama.casa_gatilho("a ata do Fed", "ata")
    assert not gerar_panorama.casa_gatilho("a data do Fed", "ata")
    assert not gerar_panorama.casa_gatilho("disse", "DI")
