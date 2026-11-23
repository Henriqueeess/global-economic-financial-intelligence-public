"""Projeções de Selic, câmbio, PIB e IPCA: Focus, cenários pelo erro histórico e contas de mercado.

Tudo é calculado a partir de dados/series/, sem chamar APIs (ver config/projecoes.yaml).
O projeto não emite previsão própria:
- "Focus" é a mediana publicada pelo Banco Central;
- os cenários são a mediana mais e menos o erro absoluto médio do próprio Focus no mesmo
  horizonte, medido nos anos já encerrados;
- as contas de mercado (Selic na curva, dólar a termo, carregamento do IBC-Br) são
  aritmética com premissa declarada.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from .conjuntura import Serie, serie_ou_derivada, ultimo_ate
from .util import RAIZ, agora, carregar_catalogo

CONFIG = RAIZ / "config" / "projecoes.yaml"
PASTA_PROJECOES = RAIZ / "dados" / "projecoes"


def carregar_config() -> dict:
    import yaml

    with CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- realizado e erro histórico

def realizado_no_ano(serie: Serie, ano: int, id_serie: str) -> float | None:
    """Valor observado no fim do ano. Só vale para anos encerrados e com a leitura de dezembro."""
    do_ano = [(d, v) for d, v in serie if d.year == ano]
    if not do_ano:
        return None
    d, v = do_ano[-1]
    if id_serie == "br_pib_anual":
        return v
    # séries mensais: precisa da leitura de dezembro; diárias e por reunião: do fim de dezembro,
    # ou de um ano seguinte já com dados (a taxa por reunião pode ficar meses sem mudar)
    if d.month == 12 and (d.day == 1 or d.day >= 15):
        return v
    if any(x.year > ano for x, _ in serie):
        return v
    return None


def no_mesmo_dia(serie: Serie, ano: int, ref: dt.date, tolerancia: int) -> float | None:
    """Leitura da série no mesmo dia e mês de `ref`, no ano `ano` (ou a última antes, até `tolerancia`)."""
    try:
        alvo = ref.replace(year=ano)
    except ValueError:  # 29 de fevereiro
        alvo = ref.replace(year=ano, day=28)
    p = ultimo_ate(serie, alvo)
    if not p or (alvo - p[0]).days > tolerancia:
        return None
    return p[1]


def erro(previsto: float, observado: float, tipo: str) -> float:
    return (observado / previsto - 1) * 100 if tipo == "pct" else observado - previsto


@dataclass
class ErroHistorico:
    amostras: list[tuple[int, float, float, float]] = field(default_factory=list)  # (ano alvo, Focus, realizado, erro)

    @property
    def n(self) -> int:
        return len(self.amostras)

    @property
    def medio_absoluto(self) -> float | None:
        return sum(abs(e) for *_, e in self.amostras) / self.n if self.n else None

    @property
    def vies(self) -> float | None:
        return sum(e for *_, e in self.amostras) / self.n if self.n else None


def erro_historico(focus: Serie, realizado: Serie, id_realizado: str, horizonte: int, ref: dt.date,
                   desde: int, tipo: str, tolerancia: int) -> ErroHistorico:
    """Erro do Focus lido no mesmo dia do ano de `ref`, `horizonte` anos antes do ano-alvo."""
    out = ErroHistorico()
    for ano in range(desde, ref.year):
        alvo = ano + horizonte
        if alvo >= ref.year:
            break
        prev = no_mesmo_dia(focus, ano, ref, tolerancia)
        obs = realizado_no_ano(realizado, alvo, id_realizado)
        if prev is None or obs is None or (tipo == "pct" and not prev):
            continue
        out.amostras.append((alvo, prev, obs, erro(prev, obs, tipo)))
    return out


# ---------------------------------------------------------------- Focus e cenários

@dataclass
class Horizonte:
    ano: int
    data: dt.date | None = None
    mediana: float | None = None
    anterior: float | None = None          # mediana `revisao_dias` antes
    revisao: float | None = None           # na unidade de `erro` (pp ou %)
    hist: ErroHistorico = field(default_factory=ErroHistorico)
    otimista: float | None = None
    pessimista: float | None = None


@dataclass
class Variavel:
    cfg: dict
    horizontes: list[Horizonte]
    fontes: list[str] = field(default_factory=list)


def calcular_variavel(v: dict, ref: dt.date, cfg: dict, catalogo: dict) -> Variavel:
    real = serie_ou_derivada(v["realizado"], catalogo)
    real = [(d, x) for d, x in real if d <= ref]
    out = Variavel(cfg=v, horizontes=[])
    for k, id_focus in enumerate(v["focus"]):
        s = [(d, x) for d, x in serie_ou_derivada(id_focus, catalogo) if d <= ref]
        h = Horizonte(ano=ref.year + k)
        out.fontes.append(id_focus)
        p = s[-1] if s else None
        # no começo do ano a série ainda pode estar no ano de referência anterior
        if p and p[0].year == ref.year:
            h.data, h.mediana = p
            ant = ultimo_ate(s, p[0] - dt.timedelta(days=cfg["revisao_dias"]))
            if ant and ant[0].year == p[0].year:
                h.anterior = ant[1]
                h.revisao = erro(ant[1], h.mediana, v["erro"]) if ant[1] else None
        h.hist = erro_historico(s, real, v["realizado"], k, ref, cfg["erro_desde"], v["erro"],
                                cfg["tolerancia_dias"])
        mae = h.hist.medio_absoluto
        if h.mediana is not None and mae is not None and h.hist.n >= cfg["erro_min_amostras"]:
            if v["erro"] == "pct":
                alto, baixo = h.mediana * (1 + mae / 100), h.mediana * (1 - mae / 100)
            else:
                alto, baixo = h.mediana + mae, h.mediana - mae
            h.pessimista, h.otimista = (alto, baixo) if v["pessimista"] == "alta" else (baixo, alto)
        out.horizontes.append(h)
    out.fontes.append(v["realizado"])
    return out


# ---------------------------------------------------------------- contas de mercado

@dataclass
class SelicCurva:
    data: dt.date
    selic: float
    selic_efetiva: float
    prefixado: float
    diferenca: float          # prefixado − Selic efetiva (média dos próximos 12 meses contra hoje)
    fim_12m: float            # ponto final em trajetória linear
    movimentos: float         # (fim − meta) / passo; negativo = cortes
    passo: float


def selic_na_curva(c: dict, ref: dt.date, catalogo: dict) -> SelicCurva | None:
    pre = [(d, x) for d, x in serie_ou_derivada(c["prefixado"], catalogo) if d <= ref]
    sel = [(d, x) for d, x in serie_ou_derivada(c["selic"], catalogo) if d <= ref]
    if not pre or not sel:
        return None
    d, p = pre[-1]
    s = ultimo_ate(sel, d)
    if not s:
        return None
    efetiva = s[1] - c["spread_over"]
    dif = p - efetiva
    fim = s[1] + 2 * dif
    return SelicCurva(data=d, selic=s[1], selic_efetiva=efetiva, prefixado=p, diferenca=dif,
                      fim_12m=fim, movimentos=(fim - s[1]) / c["passo"], passo=c["passo"])


@dataclass
class CambioTermo:
    data: dt.date
    spot: float
    juro_br: float
    juro_eua: float
    termo: float
    premio_pct: float         # termo contra o spot, em %


def dolar_a_termo(c: dict, ref: dt.date, catalogo: dict, tolerancia: int = 7) -> CambioTermo | None:
    spot = [(d, x) for d, x in serie_ou_derivada(c["spot"], catalogo) if d <= ref]
    br = [(d, x) for d, x in serie_ou_derivada(c["juro_br"], catalogo) if d <= ref]
    us = [(d, x) for d, x in serie_ou_derivada(c["juro_eua"], catalogo) if d <= ref]
    if not spot or not br or not us:
        return None
    d, s = spot[-1]
    b, u = ultimo_ate(br, d), ultimo_ate(us, d)
    if not b or not u or (d - b[0]).days > tolerancia or (d - u[0]).days > tolerancia:
        return None
    termo = s * (1 + b[1] / 100) / (1 + u[1] / 100)
    return CambioTermo(data=d, spot=s, juro_br=b[1], juro_eua=u[1], termo=termo, premio_pct=(termo / s - 1) * 100)


@dataclass
class Carregamento:
    ano: int
    ultimo_mes: dt.date
    meses: int                     # meses do ano já publicados
    parado: float                  # crescimento do ano se o índice ficar no último nível
    focus: float | None
    ritmo_necessario: float | None  # variação mensal constante (%) que leva o ano ao Focus
    carry_seguinte: float          # quanto o ano seguinte herda se o índice ficar parado


def _media(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _crescimento_com_ritmo(ano_atual: list[float], faltam: int, ultimo: float, base: float, g: float) -> float:
    futuros = [ultimo * (1 + g / 100) ** (i + 1) for i in range(faltam)]
    return (_media(ano_atual + futuros) / base - 1) * 100


def carregamento_ibc(c: dict, ref: dt.date, catalogo: dict) -> Carregamento | None:
    s = [(d, x) for d, x in serie_ou_derivada(c["indice"], catalogo) if d <= ref]
    if not s:
        return None
    ult_d, ult = s[-1]
    ano = ult_d.year
    atual = [x for d, x in s if d.year == ano]
    anterior = [x for d, x in s if d.year == ano - 1]
    if len(anterior) < 12 or not atual:
        return None
    base = _media(anterior)
    faltam = 12 - len(atual)
    parado = _crescimento_com_ritmo(atual, faltam, ult, base, 0.0)
    completo = atual + [ult] * faltam
    carry = (ult / _media(completo) - 1) * 100

    focus = None
    fs = [(d, x) for d, x in serie_ou_derivada(c["focus"], catalogo) if d <= ref and d.year == ano]
    if fs:
        focus = fs[-1][1]
    ritmo = None
    if focus is not None and faltam:
        lo, hi = -10.0, 10.0
        f = lambda g: _crescimento_com_ritmo(atual, faltam, ult, base, g) - focus  # noqa: E731
        if f(lo) <= 0 <= f(hi):
            for _ in range(60):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
            ritmo = (lo + hi) / 2
    return Carregamento(ano=ano, ultimo_mes=ult_d, meses=len(atual), parado=parado, focus=focus,
                        ritmo_necessario=ritmo, carry_seguinte=carry)


# ---------------------------------------------------------------- resultado

@dataclass
class Projecoes:
    cfg: dict
    ref: dt.date
    variaveis: list[Variavel]
    selic: SelicCurva | None
    cambio: CambioTermo | None
    pib: Carregamento | None

    def variavel(self, id_: str) -> Variavel | None:
        return next((v for v in self.variaveis if v.cfg["id"] == id_), None)


def calcular(ref: dt.date | None = None, cfg: dict | None = None, catalogo: dict | None = None) -> Projecoes:
    cfg = cfg or carregar_config()
    if catalogo is None:
        catalogo = carregar_catalogo()
    ref = ref or agora().date()
    variaveis = [calcular_variavel(v, ref, cfg, catalogo) for v in cfg["variaveis"]]
    m = cfg["mercado"]
    return Projecoes(cfg=cfg, ref=ref, variaveis=variaveis, selic=selic_na_curva(m["selic"], ref, catalogo),
                     cambio=dolar_a_termo(m["cambio"], ref, catalogo), pib=carregamento_ibc(m["pib"], ref, catalogo))


def _f(x: float | None, dec: int = 4) -> str:
    return "" if x is None else f"{x:.{dec}f}"


def gravar_csv(p: Projecoes, pasta: Path = PASTA_PROJECOES) -> list[Path]:
    """Retrato do dia em CSV de formato longo (fácil de importar no Power BI)."""
    pasta.mkdir(parents=True, exist_ok=True)
    escritos = []

    arq = pasta / "focus_cenarios.csv"
    with arq.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["variavel", "ano", "data_focus", "mediana", "mediana_anterior", "revisao", "unidade_erro",
                    "erro_medio_absoluto", "vies", "anos_no_erro", "otimista", "pessimista", "serie_focus"])
        for v in p.variaveis:
            for h, id_focus in zip(v.horizontes, v.cfg["focus"]):
                w.writerow([v.cfg["id"], h.ano, h.data.isoformat() if h.data else "", _f(h.mediana),
                            _f(h.anterior), _f(h.revisao), v.cfg["erro"], _f(h.hist.medio_absoluto),
                            _f(h.hist.vies), h.hist.n, _f(h.otimista), _f(h.pessimista), id_focus])
    escritos.append(arq)

    arq = pasta / "erro_historico_focus.csv"
    with arq.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["variavel", "horizonte_anos", "ano_alvo", "focus_no_mesmo_dia", "realizado", "erro",
                    "unidade_erro"])
        for v in p.variaveis:
            for k, h in enumerate(v.horizontes):
                for alvo, prev, obs, e in h.hist.amostras:
                    w.writerow([v.cfg["id"], k, alvo, _f(prev), _f(obs), _f(e), v.cfg["erro"]])
    escritos.append(arq)

    arq = pasta / "contas_mercado.csv"
    with arq.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["conta", "data", "campo", "valor"])
        for nome, obj in (("selic_na_curva", p.selic), ("dolar_a_termo", p.cambio), ("carregamento_ibc", p.pib)):
            if obj is None:
                continue
            data = getattr(obj, "data", None) or getattr(obj, "ultimo_mes")
            for campo, valor in vars(obj).items():
                if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                    w.writerow([nome, data.isoformat(), campo, _f(float(valor))])
    escritos.append(arq)
    return escritos
