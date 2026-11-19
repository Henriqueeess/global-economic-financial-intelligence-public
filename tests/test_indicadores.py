"""Testes dos cálculos do painel e da coleta (sem rede)."""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from indicadores import curva, derivados, painel, svg, util  # noqa: E402

D = dt.date


def test_variacao_pp_e_pct():
    assert painel.variacao(13.75, 14.25, "pp") == -0.5
    assert round(painel.variacao(5.5, 5.0, "pct"), 6) == 10.0
    assert painel.variacao(1.0, None, "pct") is None
    assert painel.variacao(1.0, 0.0, "pct") is None


def test_ultimo_ate_usa_ultimo_valor_disponivel():
    serie = [(D(2026, 11, 13), 1.0), (D(2026, 11, 16), 2.0)]
    assert painel.ultimo_ate(serie, D(2026, 11, 15)) == (D(2026, 11, 13), 1.0)
    assert painel.ultimo_ate(serie, D(2026, 11, 12)) is None


def test_linha_diaria_compara_com_7_e_30_dias():
    ind = {"id": "x", "variacao": "pct", "frequencia": "diaria"}
    serie = [(D(2026, 10, 19), 100.0), (D(2026, 11, 11), 110.0), (D(2026, 11, 18), 121.0)]
    l = painel.calcular_linha(ind, serie, D(2026, 11, 18))
    assert round(l.var_7d, 6) == 10.0
    assert round(l.var_30d, 6) == 21.0
    assert (l.minimo_30d, l.maximo_30d) == (100.0, 121.0)
    assert l.status == "ok"


def test_linha_ignora_datas_futuras_e_marca_atraso():
    ind = {"id": "x", "variacao": "pp", "frequencia": "diaria"}
    serie = [(D(2026, 11, 1), 1.0), (D(2026, 12, 9), 9.0)]
    l = painel.calcular_linha(ind, serie, D(2026, 11, 18))
    assert l.valor == 1.0
    assert l.status == "desatualizado"


def test_linha_mensal_compara_com_leitura_anterior():
    ind = {"id": "x", "variacao": "pp", "frequencia": "mensal"}
    serie = [(D(2026, 9, 1), 0.82), (D(2026, 10, 1), 0.14)]
    l = painel.calcular_linha(ind, serie, D(2026, 11, 18))
    assert round(l.var_anterior, 6) == -0.68
    assert l.anterior_data == D(2026, 9, 1)


def test_interpolacao_da_curva_sem_extrapolar():
    pontos = [(1.0, 14.0), (3.0, 15.0)]
    assert curva.interpolar(pontos, 2.0) == 14.5
    assert curva.interpolar(pontos, 0.5) is None
    assert curva.interpolar(pontos, 3.5) is None


def test_inflacao_implicita():
    obs = derivados.inflacao_implicita([(D(2026, 1, 2), 15.0)], [(D(2026, 1, 2), 7.0)])
    assert obs == [("2026-01-02", round((1.15 / 1.07 - 1) * 100, 4))]


def test_diferenca_respeita_tolerancia():
    a = [(D(2026, 1, 20), 13.75)]
    assert derivados.diferenca(a, [(D(2026, 1, 16), 4.0)]) == [("2026-01-20", 9.75)]
    assert derivados.diferenca(a, [(D(2026, 1, 1), 4.0)]) == []


def test_url_publica_remove_credenciais():
    url = "https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key=SEGREDO"
    assert "SEGREDO" not in util.url_publica(url)
    assert "series_id=DFF" in util.url_publica(url)
    url_cl = "https://si3.bcentral.cl/x?function=GetSeries&user=u&pass=p"
    assert "pass=" not in util.url_publica(url_cl) and "user=" not in util.url_publica(url_cl)


def test_formatar_valor_estavel():
    assert util.formatar_valor(5.81020000) == "5.8102"
    assert util.formatar_valor(-0.0000001) == "0"
    assert util.formatar_valor(13.0) == "13"


def test_marcas_de_eixo():
    assert svg.passos_bonitos(12.7, 15.35) == [12.0, 13.0, 14.0, 15.0, 16.0]
    assert svg.casas_decimais(0.5) == 1 and svg.casas_decimais(2.0) == 0


def test_gravar_serie_descarta_futuro_e_registra_revisao(tmp_path, monkeypatch):
    monkeypatch.setattr(util, "PASTA_SERIES", tmp_path)
    limite = D(2026, 11, 18)
    assert util.gravar_serie("t", [("2026-11-17", 1.0), ("2026-12-09", 2.0)], "https://x?api_key=k", limite) == (1, 0)
    assert util.gravar_serie("t", [("2026-11-17", 1.5)], "https://x", limite) == (0, 1)
    texto = (tmp_path / "t.csv").read_text()
    assert "2026-12-09" not in texto and "api_key" not in texto
