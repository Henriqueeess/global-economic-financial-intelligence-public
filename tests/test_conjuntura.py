"""Testes das contas da conjuntura (sem rede)."""

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from indicadores import conjuntura, derivados  # noqa: E402

D = dt.date


def test_juro_real_ex_ante_usa_ultima_expectativa():
    selic = [(D(2026, 11, 18), 13.75), (D(2026, 11, 19), 13.75)]
    focus = [(D(2026, 11, 13), 5.0)]
    obs = derivados.juro_real(selic, focus)
    assert obs[0][0] == "2026-11-18"
    assert round(obs[0][1], 4) == round((1.1375 / 1.05 - 1) * 100, 4)
    # expectativa velha demais (mais de 7 dias) não entra
    assert derivados.juro_real([(D(2026, 12, 1), 13.75)], focus) == []


def test_percentil_conta_empates_pela_metade():
    amostra = sorted([1.0, 2.0, 2.0, 3.0])
    assert conjuntura.percentil(amostra, 2.0) == 50.0
    assert conjuntura.percentil(amostra, 3.0) == 87.5
    assert conjuntura.percentil(amostra, 0.5) == 0.0


def test_acumulado_3m_anualizado():
    mensal = [(D(2026, m, 1), 0.5) for m in range(1, 4)]
    out = conjuntura.acumulado_anualizado(mensal, 3)
    assert len(out) == 1
    assert round(out[0][1], 4) == round((1.005 ** 12 - 1) * 100, 4)


def test_ritmo_indice_compara_trimestres():
    serie = [(D(2026, m, 1), v) for m, v in zip(range(1, 7), [100, 100, 100, 101, 101, 101])]
    out = conjuntura.ritmo_indice(serie, 3)
    assert len(out) == 1
    assert round(out[0][1], 4) == round((1.01 ** 4 - 1) * 100, 4)


def test_variacao_em_dias_exige_base_proxima():
    serie = [(D(2026, 1, 1), 5.0), (D(2026, 4, 2), 5.5)]
    out = conjuntura.variacao_dias(serie, 91)
    assert len(out) == 1 and round(out[0][1], 6) == 10.0
    assert conjuntura.variacao_dias([(D(2025, 1, 1), 5.0), (D(2026, 4, 2), 5.5)], 91) == []


def test_diario_repete_taxa_de_reuniao_ate_o_fim():
    s = conjuntura.diario([(D(2026, 1, 1), 2.0), (D(2026, 1, 4), 2.25)], D(2026, 1, 5))
    assert [v for _, v in s] == [2.0, 2.0, 2.0, 2.25, 2.25]


def test_cenarios_ipca_sao_aritmetica():
    cfg = conjuntura.carregar_config()
    mensal = [(D(2025, m, 1), 0.3) for m in range(1, 13)]
    cen = conjuntura.cenarios_ipca(mensal, cfg)
    # repetir a média dos últimos 3 meses (0,3%) mantém o 12 meses igual
    assert round(cen["media_3m"][-1][1], 6) == round(cen["media_3m"][0][1], 6)
    # rodar no ritmo do centro da meta por 12 meses leva o 12 meses exatamente ao centro
    assert round(cen["meta"][-1][1], 6) == conjuntura.meta_do_ano(cfg, 2026)["centro"]
    assert cen["meta"][-1][0] == D(2026, 12, 1)


def test_media_de_percentis_pede_todos_os_componentes():
    a = [(D(2026, 1, 2) + dt.timedelta(days=7 * i), float(i)) for i in range(10)]
    b = [(d, -v) for d, v in a]
    out = conjuntura.media_percentis([a, b], 14)
    assert out and all(round(v, 6) == 50.0 for _, v in out)
    assert conjuntura.media_percentis([a, []], 14) == []


def test_config_da_conjuntura_e_coerente():
    cfg = conjuntura.carregar_config()
    blocos = {b["id"] for b in cfg["blocos"]}
    ids = [c["id"] for c in cfg["componentes"]]
    assert len(ids) == len(set(ids))
    for c in cfg["componentes"]:
        assert c["bloco"] in blocos
        assert c["calculo"] in {"nivel", "ritmo_indice_3m", "acumulado_3m_anualizado", "variacao_dias", "diferenca"}
        assert c["nome_pt"] and c["nome_en"]
    assert set(cfg["condicoes_financeiras"]["componentes"]) <= set(ids)


def test_dashboard_nao_deixa_fechar_a_tag_script(tmp_path, monkeypatch):
    import gerar_dashboard

    modelo = tmp_path / "m.html"
    modelo.write_text("<script>const D = /*__DADOS__*/null;</script>", encoding="utf-8")
    monkeypatch.setattr(gerar_dashboard, "MODELO", modelo)
    monkeypatch.setattr(gerar_dashboard, "PASTA_PAINEL", tmp_path)
    monkeypatch.setattr(gerar_dashboard.conjuntura, "gravar_csv", lambda c: [])
    monkeypatch.setattr(gerar_dashboard, "montar_dados", lambda ref, conj, cat: {"x": "</script><b>"})
    destino = gerar_dashboard.gerar(D(2026, 11, 19))
    html = destino.read_text(encoding="utf-8")
    assert html.count("</script>") == 1
    corpo = html.split("const D = ")[1].split(";</script>")[0]
    assert json.loads(corpo) == {"x": "</script><b>"}
