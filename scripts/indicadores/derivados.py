"""Indicadores calculados a partir de outras séries já gravadas."""

from __future__ import annotations

import bisect
import datetime as dt

from .util import valores

TOLERANCIA_DIAS = 7  # a série "b" pode estar até 7 dias atrás da data de "a"


def _ultimo_ate(serie: list[tuple[dt.date, float]], data: dt.date) -> tuple[dt.date, float] | None:
    datas = [d for d, _ in serie]
    i = bisect.bisect_right(datas, data) - 1
    return serie[i] if i >= 0 else None


def diferenca(a: list[tuple[dt.date, float]], b: list[tuple[dt.date, float]]) -> list[tuple[str, float]]:
    """a − b nas datas de a, usando o último valor de b até aquela data."""
    obs = []
    for d, va in a:
        ref = _ultimo_ate(b, d)
        if ref and (d - ref[0]).days <= TOLERANCIA_DIAS:
            obs.append((d.isoformat(), round(va - ref[1], 6)))
    return obs


def inflacao_implicita(nominal: list[tuple[dt.date, float]], real: list[tuple[dt.date, float]]) -> list[tuple[str, float]]:
    """(1 + nominal) / (1 + real) − 1, em % a.a., nas datas em que as duas existem."""
    reais = dict(real)
    return [(d.isoformat(), round(((1 + n / 100) / (1 + reais[d] / 100) - 1) * 100, 4))
            for d, n in nominal if d in reais]


def calcular(fonte: dict) -> tuple[list[tuple[str, float]], str]:
    op = fonte["operacao"]
    if op == "diferenca":
        return diferenca(valores(fonte["a"]), valores(fonte["b"])), f"derivado: {fonte['a']} - {fonte['b']}"
    if op == "inflacao_implicita":
        return (inflacao_implicita(valores(fonte["nominal"]), valores(fonte["real"])),
                f"derivado: inflacao implicita de {fonte['nominal']} e {fonte['real']}")
    raise ValueError(f"operação desconhecida: {op}")
