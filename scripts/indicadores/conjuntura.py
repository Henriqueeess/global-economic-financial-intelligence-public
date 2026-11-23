"""Conjuntura macro: termômetros (percentis históricos), condições financeiras e cenários do IPCA.

Tudo é calculado a partir de dados/series/, sem chamar APIs. As contas são descritivas:
nada aqui projeta câmbio, juros de mercado ou preço de ativo. Os cenários do IPCA são
aritmética com premissa declarada (o que acontece com a taxa em 12 meses se cada mês
seguir uma regra fixa), não previsões.
"""

from __future__ import annotations

import bisect
import csv
import datetime as dt
import math
from dataclasses import dataclass, field
from pathlib import Path

from . import derivados
from .util import RAIZ, agora, carregar_catalogo, valores

CONFIG = RAIZ / "config" / "conjuntura.yaml"
PASTA_CONJUNTURA = RAIZ / "dados" / "conjuntura"

Serie = list[tuple[dt.date, float]]


def carregar_config() -> dict:
    import yaml

    with CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- leitura

def serie_ou_derivada(id_: str, catalogo: dict | None) -> Serie:
    """Lê dados/series/<id>.csv; se ainda não existir e o catálogo a define como derivada, calcula."""
    s = valores(id_)
    if s or not catalogo:
        return s
    ind = next((i for i in catalogo.get("indicadores", []) if i["id"] == id_), None)
    if ind and ind["fonte"]["tipo"] == "derivado":
        obs, _ = derivados.calcular(ind["fonte"])
        return [(dt.date.fromisoformat(d), v) for d, v in obs]
    return []


# ---------------------------------------------------------------- contas

def ultimo_ate(serie: Serie, data: dt.date) -> tuple[dt.date, float] | None:
    datas = [d for d, _ in serie]
    i = bisect.bisect_right(datas, data) - 1
    return serie[i] if i >= 0 else None


def diferenca(a: Serie, b: Serie, tolerancia: int = 7) -> Serie:
    datas_b = [d for d, _ in b]
    out = []
    for d, v in a:
        i = bisect.bisect_right(datas_b, d) - 1
        if i >= 0 and (d - b[i][0]).days <= tolerancia:
            out.append((d, v - b[i][1]))
    return out


def ritmo_indice(serie: Serie, janela: int = 3) -> Serie:
    """Média dos últimos `janela` meses contra a dos `janela` anteriores, anualizada (%)."""
    out = []
    for i in range(2 * janela - 1, len(serie)):
        atual = sum(v for _, v in serie[i - janela + 1:i + 1]) / janela
        antes = sum(v for _, v in serie[i - 2 * janela + 1:i - janela + 1]) / janela
        if antes > 0:
            out.append((serie[i][0], ((atual / antes) ** (12 / janela) - 1) * 100))
    return out


def acumulado_anualizado(mensal: Serie, janela: int = 3) -> Serie:
    """Taxas mensais em % acumuladas em `janela` meses e anualizadas (%)."""
    out = []
    for i in range(janela - 1, len(mensal)):
        fator = math.prod(1 + v / 100 for _, v in mensal[i - janela + 1:i + 1])
        out.append((mensal[i][0], (fator ** (12 / janela) - 1) * 100))
    return out


def variacao_dias(serie: Serie, dias: int, tolerancia: int = 7) -> Serie:
    """Variação % contra o último valor disponível `dias` dias corridos antes."""
    datas = [d for d, _ in serie]
    out = []
    for d, v in serie:
        alvo = d - dt.timedelta(days=dias)
        i = bisect.bisect_right(datas, alvo) - 1
        if i >= 0 and (alvo - serie[i][0]).days <= tolerancia and serie[i][1]:
            out.append((d, (v / serie[i][1] - 1) * 100))
    return out


def acumulado_12m(mensal: list[float]) -> float:
    return (math.prod(1 + v / 100 for v in mensal[-12:]) - 1) * 100


def percentil(ordenados: list[float], x: float) -> float:
    """Posição de x na amostra (0 a 100), com empates contados pela metade."""
    if not ordenados:
        return float("nan")
    abaixo = bisect.bisect_left(ordenados, x)
    iguais = bisect.bisect_right(ordenados, x) - abaixo
    return (abaixo + iguais / 2) / len(ordenados) * 100


def percentis(serie: Serie) -> Serie:
    """Cada ponto comparado com toda a amostra da série."""
    ordenados = sorted(v for _, v in serie)
    return [(d, percentil(ordenados, v)) for d, v in serie]


def semanal(serie: Serie) -> Serie:
    """Último valor de cada semana (ISO)."""
    por_semana: dict[tuple[int, int], tuple[dt.date, float]] = {}
    for d, v in serie:
        por_semana[d.isocalendar()[:2]] = (d, v)
    return sorted(por_semana.values())


def media_percentis(series: list[Serie], tolerancia: int) -> Serie:
    """Média simples dos percentis, nas sextas-feiras em que todos os componentes têm dado recente."""
    if not series or any(not s for s in series):
        return []
    pcts = [percentis(s) for s in series]
    inicio = max(s[0][0] for s in pcts)
    fim = max(s[-1][0] for s in pcts)
    d = inicio + dt.timedelta(days=(4 - inicio.weekday()) % 7)
    datas = []
    while d <= fim:
        datas.append(d)
        d += dt.timedelta(days=7)
    if not datas or datas[-1] != fim:
        datas.append(fim)
    out = []
    for d in datas:
        vals = []
        for s in pcts:
            ref = ultimo_ate(s, d)
            if not ref or (d - ref[0]).days > tolerancia:
                break
            vals.append(ref[1])
        else:
            out.append((d, sum(vals) / len(vals)))
    return out


def meta_do_ano(cfg: dict, ano: int) -> dict | None:
    metas = cfg["metas_inflacao"]
    if ano in metas["por_ano"]:
        return metas["por_ano"][ano]
    if ano >= metas["continua"]["desde"]:
        return metas["continua"]
    return None


def cenarios_ipca(mensal: Serie, cfg: dict) -> dict[str, Serie]:
    """Trajetória do IPCA em 12 meses se cada mês seguinte seguir uma regra fixa."""
    if len(mensal) < 12:
        return {}
    meses = cfg["cenarios_ipca"]["meses"]
    ult = mensal[-1][0]
    out = {}
    for p in cfg["cenarios_ipca"]["premissas"]:
        if p["id"] == "media_3m":
            taxa = sum(v for _, v in mensal[-3:]) / 3
        elif p["id"] == "meta":
            meta = meta_do_ano(cfg, ult.year + 1) or meta_do_ano(cfg, ult.year)
            taxa = ((1 + meta["centro"] / 100) ** (1 / 12) - 1) * 100
        else:
            continue
        hist = [v for _, v in mensal]
        traj = [(ult, acumulado_12m(hist))]
        d = ult
        for _ in range(meses):
            d = (d.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
            hist.append(taxa)
            traj.append((d, acumulado_12m(hist)))
        out[p["id"]] = traj
    return out


def diario(serie: Serie, ate: dt.date) -> Serie:
    """Repete cada valor até a mudança seguinte (taxas definidas em reunião), um ponto por dia."""
    out = []
    for i, (d, v) in enumerate(serie):
        fim = serie[i + 1][0] if i + 1 < len(serie) else ate + dt.timedelta(days=1)
        while d < fim:
            out.append((d, v))
            d += dt.timedelta(days=1)
    return out


def calcular_componente(comp: dict, catalogo: dict | None, ate: dt.date | None = None) -> Serie:
    base = serie_ou_derivada(comp["serie"], catalogo)
    calc = comp["calculo"]
    if calc == "nivel":
        ind = next((i for i in (catalogo or {}).get("indicadores", []) if i["id"] == comp["serie"]), {})
        if ind.get("frequencia") == "reuniao" and base:
            # sem isso, o percentil contaria reuniões, não tempo: o mesmo nível por 2 anos pesaria 1 ponto
            return diario(base, ate or base[-1][0])
        return base
    if calc == "ritmo_indice_3m":
        return ritmo_indice(base, 3)
    if calc == "acumulado_3m_anualizado":
        return acumulado_anualizado(base, 3)
    if calc == "variacao_dias":
        return variacao_dias(base, comp["dias"])
    if calc == "diferenca":
        return diferenca(base, serie_ou_derivada(comp["menos"], catalogo))
    raise ValueError(f"cálculo desconhecido: {calc}")


# ---------------------------------------------------------------- resultado

@dataclass
class Termometro:
    comp: dict
    serie: Serie
    ultimo: tuple[dt.date, float] | None = None
    pct: float | None = None
    pct_1a: float | None = None  # percentil do valor de um ano antes
    pcts: Serie = field(default_factory=list)
    mensal: bool = False


@dataclass
class Conjuntura:
    cfg: dict
    termometros: list[Termometro]
    icf: Serie
    cenarios: dict[str, Serie]
    ipca_12m: Serie
    ipca_mensal: Serie


def calcular(ref: dt.date | None = None, cfg: dict | None = None, catalogo: dict | None = None) -> Conjuntura:
    cfg = cfg or carregar_config()
    if catalogo is None:
        catalogo = carregar_catalogo()
    ref = ref or agora().date()
    desde = dt.date.fromisoformat(cfg["historico_desde"])

    def recorte(s: Serie) -> Serie:
        return [(d, v) for d, v in s if desde <= d <= ref]

    termos = []
    for comp in cfg["componentes"]:
        s = recorte(calcular_componente(comp, catalogo, ref))
        ind = next((i for i in catalogo.get("indicadores", []) if i["id"] == comp["serie"]), {})
        t = Termometro(comp=comp, serie=s, mensal=ind.get("frequencia") == "mensal")
        if s:
            t.pcts = percentis(s)
            t.ultimo = s[-1]
            t.pct = t.pcts[-1][1]
            um_ano = ultimo_ate(t.pcts, s[-1][0] - dt.timedelta(days=365))
            t.pct_1a = um_ano[1] if um_ano else None
        termos.append(t)

    por_id = {t.comp["id"]: t for t in termos}
    icf_cfg = cfg["condicoes_financeiras"]
    icf = media_percentis([por_id[c].serie for c in icf_cfg["componentes"] if c in por_id],
                          icf_cfg["tolerancia_dias"])

    mensal = recorte(serie_ou_derivada("br_ipca_mensal", catalogo))
    return Conjuntura(cfg=cfg, termometros=termos, icf=icf, cenarios=cenarios_ipca(mensal, cfg),
                      ipca_12m=recorte(serie_ou_derivada("br_ipca_12m", catalogo)), ipca_mensal=mensal)


# ---------------------------------------------------------------- gravação (para Power BI e afins)

def gravar_csv(c: Conjuntura, pasta: Path = PASTA_CONJUNTURA) -> list[Path]:
    """Grava as contas da conjuntura em CSV de formato longo, fácil de importar no Power BI."""
    pasta.mkdir(parents=True, exist_ok=True)
    escritos = []

    # Retrato do dia: um componente por linha (o arquivo inteiro muda todo dia, por isso é curto).
    p = pasta / "termometros.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["componente", "bloco", "nome_pt", "nome_en", "serie_origem", "calculo", "unidade",
                    "data", "valor", "percentil", "percentil_1_ano_antes"])
        for t in c.termometros:
            if not t.ultimo:
                continue
            w.writerow([t.comp["id"], t.comp["bloco"], t.comp["nome_pt"], t.comp["nome_en"], t.comp["serie"],
                        t.comp["calculo"], t.comp["unidade"], t.ultimo[0].isoformat(), f"{t.ultimo[1]:.4f}",
                        f"{t.pct:.1f}", "" if t.pct_1a is None else f"{t.pct_1a:.1f}"])
    escritos.append(p)

    # Histórico das contas que não existem em dados/series/ (ritmos, variações, inclinações).
    p = pasta / "contas.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["componente", "data", "valor"])
        for t in c.termometros:
            if t.comp["calculo"] == "nivel":
                continue
            for d, v in t.serie:
                w.writerow([t.comp["id"], d.isoformat(), f"{v:.4f}"])
    escritos.append(p)

    p = pasta / "condicoes_financeiras.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["data", "indice"])
        for d, v in c.icf:
            w.writerow([d.isoformat(), f"{v:.1f}"])
    escritos.append(p)

    p = pasta / "cenarios_ipca.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["premissa", "mes", "ipca_12m"])
        for pid, traj in c.cenarios.items():
            for d, v in traj:
                w.writerow([pid, d.isoformat(), f"{v:.2f}"])
    escritos.append(p)
    return escritos
