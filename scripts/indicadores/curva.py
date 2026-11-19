"""Curva de juros brasileira a partir das taxas oficiais do Tesouro Direto.

Fonte: arquivo "Preço e taxa dos títulos ofertados pelo Tesouro Direto"
(Tesouro Transparente, dados abertos). Usa só os títulos sem cupom:
Tesouro Prefixado (curva nominal) e Tesouro IPCA+ (curva real).

Os vértices de prazo constante (1, 3, 5, 10 anos) são interpolados
linearmente no prazo em anos corridos (dias/365,25) entre os dois títulos
vizinhos. Fora do intervalo coberto pelos títulos do dia, o vértice não é
calculado: nunca há extrapolação. É uma aproximação: a convenção oficial usa
dias úteis/252, e as taxas são as do varejo (taxa de compra da manhã).
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from collections import defaultdict

from .util import PASTA_CURVA, http_get

ARQUIVO_CURVA = PASTA_CURVA / "tesouro_direto.csv"
CAMPOS = ["data_base", "curva", "vencimento", "taxa_compra", "taxa_venda"]


def baixar_curva(cfg: dict, desde: dt.date) -> int:
    """Baixa o arquivo oficial e regrava dados/curva/tesouro_direto.csv. Retorna o nº de linhas."""
    bruto = http_get(cfg["arquivo_fonte"], timeout=300).decode("latin-1")
    nomes = {v: k for k, v in cfg["titulos"].items()}  # "Tesouro Prefixado" -> "prefixado"
    linhas = []
    for l in csv.DictReader(io.StringIO(bruto), delimiter=";"):
        curva = nomes.get(l["Tipo Titulo"].strip())
        if not curva:
            continue
        base = dt.datetime.strptime(l["Data Base"], "%d/%m/%Y").date()
        if base < desde:
            continue
        venc = dt.datetime.strptime(l["Data Vencimento"], "%d/%m/%Y").date()
        linhas.append({
            "data_base": base.isoformat(),
            "curva": curva,
            "vencimento": venc.isoformat(),
            "taxa_compra": l["Taxa Compra Manha"].replace(",", ".").strip(),
            "taxa_venda": l["Taxa Venda Manha"].replace(",", ".").strip(),
        })
    if not linhas:
        raise RuntimeError("arquivo do Tesouro Direto sem títulos reconhecidos")
    linhas.sort(key=lambda r: (r["data_base"], r["curva"], r["vencimento"]))
    PASTA_CURVA.mkdir(parents=True, exist_ok=True)
    with ARQUIVO_CURVA.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    return len(linhas)


def ler_curvas(campo: str = "taxa_compra") -> dict[tuple[dt.date, str], list[tuple[dt.date, float]]]:
    """{(data_base, curva): [(vencimento, taxa), ...] ordenado por vencimento}."""
    curvas: dict = defaultdict(list)
    if not ARQUIVO_CURVA.exists():
        return {}
    with ARQUIVO_CURVA.open(encoding="utf-8", newline="") as f:
        for l in csv.DictReader(f):
            if l[campo]:
                curvas[(dt.date.fromisoformat(l["data_base"]), l["curva"])].append(
                    (dt.date.fromisoformat(l["vencimento"]), float(l[campo])))
    return {k: sorted(v) for k, v in curvas.items()}


def prazo_anos(base: dt.date, vencimento: dt.date) -> float:
    return (vencimento - base).days / 365.25


def interpolar(pontos: list[tuple[float, float]], alvo: float) -> float | None:
    """Interpolação linear em (prazo, taxa); None fora do intervalo coberto."""
    pontos = sorted(p for p in pontos if p[0] > 0)
    if not pontos or alvo < pontos[0][0] or alvo > pontos[-1][0]:
        return None
    for (x0, y0), (x1, y1) in zip(pontos, pontos[1:]):
        if x0 <= alvo <= x1:
            if x1 == x0:
                return y0
            return y0 + (y1 - y0) * (alvo - x0) / (x1 - x0)
    return pontos[-1][1] if alvo == pontos[-1][0] else None


def serie_vertice(curvas: dict, curva: str, anos: float) -> list[tuple[str, float]]:
    obs = []
    for (base, nome), titulos in sorted(curvas.items()):
        if nome != curva:
            continue
        v = interpolar([(prazo_anos(base, venc), taxa) for venc, taxa in titulos], anos)
        if v is not None:
            obs.append((base.isoformat(), round(v, 4)))
    return obs
