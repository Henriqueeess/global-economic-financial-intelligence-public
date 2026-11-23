"""Testes das projeções (sem rede): Focus, erro histórico e contas de mercado."""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from indicadores import fontes, projecoes  # noqa: E402

D = dt.date


def series_falsas(monkeypatch, dados: dict):
    monkeypatch.setattr(projecoes, "serie_ou_derivada", lambda id_, cat: dados.get(id_, []))


def test_focus_anual_pede_o_ano_seguinte(monkeypatch):
    pedidos = []

    def falso(recurso, filtro):
        pedidos.append(filtro)
        return [{"Data": "2026-11-19", "Mediana": 5.5}]

    monkeypatch.setattr(fontes, "_olinda", falso)
    obs, _ = fontes.bcb_focus_anual({"indicador": "Câmbio", "anos_a_frente": 1}, D(2026, 11, 1), D(2026, 11, 20))
    assert "DataReferencia eq '2027'" in pedidos[0]
    assert obs == [("2026-11-19", 5.5)]
    fontes.bcb_focus_anual({"indicador": "Câmbio"}, D(2026, 11, 1), D(2026, 11, 20))
    assert "DataReferencia eq '2026'" in pedidos[1]


def test_realizado_exige_ano_encerrado():
    ipca = [(D(2025, 12, 1), 4.5), (D(2026, 10, 1), 5.0)]
    assert projecoes.realizado_no_ano(ipca, 2025, "br_ipca_12m") == 4.5
    assert projecoes.realizado_no_ano(ipca, 2026, "br_ipca_12m") is None
    selic = [(D(2024, 12, 11), 12.25), (D(2025, 1, 29), 13.25)]
    assert projecoes.realizado_no_ano(selic, 2024, "br_selic_meta") == 12.25
    assert projecoes.realizado_no_ano([(D(2026, 3, 1), 1.0)], 2026, "br_selic_meta") is None
    assert projecoes.realizado_no_ano([(D(2025, 1, 1), 2.29)], 2025, "br_pib_anual") == 2.29


def test_erro_historico_compara_mesmo_dia_do_ano():
    focus = [(D(2023, 11, 20), 10.0), (D(2024, 11, 20), 11.0), (D(2025, 11, 20), 12.0)]
    realizado = [(D(2023, 12, 13), 11.75), (D(2024, 12, 11), 12.25), (D(2025, 12, 10), 15.0), (D(2026, 1, 28), 15.0)]
    h0 = projecoes.erro_historico(focus, realizado, "br_selic_meta", 0, D(2026, 11, 23), 2016, "pp", 10)
    assert [a[0] for a in h0.amostras] == [2023, 2024, 2025]
    assert round(h0.medio_absoluto, 4) == round((1.75 + 1.25 + 3.0) / 3, 4)
    # horizonte de 1 ano: o Focus de 2023 é comparado com o realizado de 2024; 2025 + 1 ainda não fechou
    h1 = projecoes.erro_historico(focus, realizado, "br_selic_meta", 1, D(2026, 11, 23), 2016, "pp", 10)
    assert [(a[0], a[1], a[2]) for a in h1.amostras] == [(2024, 10.0, 12.25), (2025, 11.0, 15.0)]


def test_cenarios_seguem_a_direcao_pessimista(monkeypatch):
    cfg = {"revisao_dias": 28, "erro_desde": 2016, "erro_min_amostras": 2, "tolerancia_dias": 10}
    anos = range(2020, 2026)
    dados = {
        "f0": [(D(a, 11, 20), 2.0) for a in anos] + [(D(2026, 10, 20), 1.5), (D(2026, 11, 20), 1.8)],
        "real": [(D(a, 1, 1), 3.0) for a in anos],  # erro de +1 p.p. todo ano
    }
    series_falsas(monkeypatch, dados)
    v = {"id": "pib", "focus": ["f0"], "realizado": "br_pib_anual", "erro": "pp", "pessimista": "baixa"}
    monkeypatch.setitem(dados, "br_pib_anual", dados["real"])
    out = projecoes.calcular_variavel(v, D(2026, 11, 23), cfg, {})
    h = out.horizontes[0]
    assert h.mediana == 1.8 and round(h.revisao, 4) == 0.3
    assert h.hist.n == 6 and h.hist.medio_absoluto == 1.0
    assert round(h.otimista, 4) == 2.8 and round(h.pessimista, 4) == 0.8


def test_cambio_usa_erro_percentual(monkeypatch):
    cfg = {"revisao_dias": 28, "erro_desde": 2016, "erro_min_amostras": 1, "tolerancia_dias": 10}
    dados = {"f": [(D(2025, 11, 20), 5.0), (D(2026, 11, 20), 6.0)],
             "br_dolar_ptax": [(D(2025, 12, 30), 5.5), (D(2026, 1, 2), 5.5)]}
    series_falsas(monkeypatch, dados)
    v = {"id": "cambio", "focus": ["f"], "realizado": "br_dolar_ptax", "erro": "pct", "pessimista": "alta"}
    h = projecoes.calcular_variavel(v, D(2026, 11, 23), cfg, {}).horizontes[0]
    assert round(h.hist.medio_absoluto, 4) == 10.0
    assert round(h.pessimista, 4) == 6.6 and round(h.otimista, 4) == 5.4


def test_selic_na_curva_e_dolar_a_termo(monkeypatch):
    dados = {"pre": [(D(2026, 11, 19), 13.15)], "selic": [(D(2026, 9, 17), 14.25)],
             "ptax": [(D(2026, 11, 19), 5.0)], "us": [(D(2026, 11, 19), 4.0)]}
    series_falsas(monkeypatch, dados)
    sc = projecoes.selic_na_curva({"prefixado": "pre", "selic": "selic", "spread_over": 0.1, "passo": 0.25},
                                  D(2026, 11, 23), {})
    assert round(sc.diferenca, 4) == -1.0 and round(sc.fim_12m, 4) == 12.25 and round(sc.movimentos, 4) == -8
    ct = projecoes.dolar_a_termo({"spot": "ptax", "juro_br": "pre", "juro_eua": "us"}, D(2026, 11, 23), {})
    assert round(ct.termo, 6) == round(5.0 * 1.1315 / 1.04, 6)


def test_carregamento_do_ibc(monkeypatch):
    ibc = [(D(2025, m, 1), 100.0) for m in range(1, 13)] + [(D(2026, m, 1), 102.0) for m in range(1, 10)]
    series_falsas(monkeypatch, {"ibc": ibc, "focus": [(D(2026, 11, 20), 2.5)]})
    c = projecoes.carregamento_ibc({"indice": "ibc", "focus": "focus"}, D(2026, 11, 23), {})
    assert c.meses == 9 and round(c.parado, 6) == 2.0 and round(c.carry_seguinte, 6) == 0.0
    # com o ritmo achado, o ano bate o Focus
    cresc = projecoes._crescimento_com_ritmo([102.0] * 9, 3, 102.0, 100.0, c.ritmo_necessario)
    assert abs(cresc - 2.5) < 1e-6 and c.ritmo_necessario > 0


def test_config_das_projecoes_e_coerente():
    from indicadores.util import carregar_catalogo

    cfg = projecoes.carregar_config()
    ids = {i["id"] for i in carregar_catalogo()["indicadores"]}
    for v in cfg["variaveis"]:
        assert set(v["focus"]) <= ids and v["realizado"] in ids
        assert v["erro"] in {"pp", "pct"} and v["pessimista"] in {"alta", "baixa"}
    for conta in cfg["mercado"].values():
        for k, x in conta.items():
            if isinstance(x, str):
                assert x in ids, (k, x)
