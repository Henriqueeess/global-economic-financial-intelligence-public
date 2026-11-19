"""Cálculos do painel: último valor, variações em 7 e 30 dias, extremos e destaques."""

from __future__ import annotations

import bisect
import datetime as dt
import statistics
from dataclasses import dataclass, field

Serie = list[tuple[dt.date, float]]

LIMITE_ATRASO_DIAS = {"diaria": 5, "semanal": 12, "mensal": 100, "reuniao": None}


def ultimo_ate(serie: Serie, data: dt.date) -> tuple[dt.date, float] | None:
    """Último ponto com data <= `data` (a série tem de estar ordenada)."""
    i = bisect.bisect_right([d for d, _ in serie], data) - 1
    return serie[i] if i >= 0 else None


def variacao(atual: float, anterior: float | None, tipo: str) -> float | None:
    """pp: diferença simples. pct: variação percentual."""
    if anterior is None:
        return None
    if tipo == "pp":
        return atual - anterior
    if anterior == 0:
        return None
    return (atual / anterior - 1) * 100


@dataclass
class Linha:
    ind: dict
    status: str = "ok"           # ok | sem_dados | desatualizado
    data: dt.date | None = None
    valor: float | None = None
    anterior_data: dt.date | None = None   # séries mensais: leitura anterior
    anterior: float | None = None
    var_7d: float | None = None
    var_30d: float | None = None
    var_anterior: float | None = None
    minimo_30d: float | None = None
    maximo_30d: float | None = None
    z_7d: float | None = None
    pontos: list[tuple[float, float]] = field(default_factory=list)


def calcular_linha(ind: dict, serie: Serie, ref: dt.date) -> Linha:
    serie = [p for p in serie if p[0] <= ref]
    linha = Linha(ind=ind)
    if not serie:
        linha.status = "sem_dados"
        return linha
    linha.data, linha.valor = serie[-1]
    tipo = ind["variacao"]
    freq = ind["frequencia"]
    limite = LIMITE_ATRASO_DIAS.get(freq)
    if limite is not None and (ref - linha.data).days > limite:
        linha.status = "desatualizado"

    if freq == "mensal":
        if len(serie) >= 2:
            linha.anterior_data, linha.anterior = serie[-2]
            linha.var_anterior = variacao(linha.valor, linha.anterior, tipo)
        ult = serie[-13:]
        linha.pontos = [(i, v) for i, (_, v) in enumerate(ult)]
        return linha

    p7 = ultimo_ate(serie, ref - dt.timedelta(days=7))
    p30 = ultimo_ate(serie, ref - dt.timedelta(days=30))
    linha.var_7d = variacao(linha.valor, p7[1] if p7 else None, tipo)
    linha.var_30d = variacao(linha.valor, p30[1] if p30 else None, tipo)
    janela = ([p30] if p30 else []) + [p for p in serie if p[0] > ref - dt.timedelta(days=30)]
    linha.minimo_30d = min(v for _, v in janela)
    linha.maximo_30d = max(v for _, v in janela)
    # o ponto inicial (as-of de 30 dias atrás) entra na data do início da janela
    pts = [((max(d, ref - dt.timedelta(days=30)) - ref).days, v) for d, v in janela]
    if pts and pts[-1][0] < 0 and freq == "reuniao":
        pts.append((0, linha.valor))  # taxa sem mudança: linha reta até hoje
    linha.pontos = pts
    if freq == "diaria" and linha.var_7d is not None:
        linha.z_7d = z_movimento_7d(serie, ref, tipo)
    return linha


def z_movimento_7d(serie: Serie, ref: dt.date, tipo: str) -> float | None:
    """Movimento dos últimos 7 dias em desvios-padrão dos movimentos de 7 dias do último ano."""
    atual = serie[-1][1]
    p7 = ultimo_ate(serie, ref - dt.timedelta(days=7))
    if not p7:
        return None
    hoje = variacao(atual, p7[1], tipo)
    historico = []
    for d, v in serie:
        if ref - dt.timedelta(days=365) <= d <= ref - dt.timedelta(days=7):
            ant = ultimo_ate(serie, d - dt.timedelta(days=7))
            if ant:
                m = variacao(v, ant[1], tipo)
                if m is not None:
                    historico.append(m)
    if len(historico) < 30 or hoje is None:
        return None
    dp = statistics.pstdev(historico)
    return hoje / dp if dp else None


def destaques(linhas: list[Linha], n: int = 5) -> list[Linha]:
    candidatas = [l for l in linhas if l.z_7d is not None and l.status == "ok"]
    return sorted(candidatas, key=lambda l: abs(l.z_7d), reverse=True)[:n]
