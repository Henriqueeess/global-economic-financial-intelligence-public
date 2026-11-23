#!/usr/bin/env python3
"""Gera o dashboard interativo da conjuntura (HTML) e os CSVs de apoio.

Uso:
  python scripts/gerar_dashboard.py                  # com os dados até hoje (America/Sao_Paulo)
  python scripts/gerar_dashboard.py --data 2026-11-19

Saída:
  painel/dashboard.html       página única, sem dependências externas, PT/EN, tema claro e escuro
  dados/conjuntura/*.csv      termômetros, condições financeiras e contas do IPCA (formato longo,
                              pronto para importar no Power BI ou em planilhas)
  dados/projecoes/*.csv       Focus, cenários pelo erro histórico do Focus e contas de mercado

O projeto não emite previsão própria: as projeções são o Focus do Banco Central, a faixa de erro
histórico do próprio Focus e contas com premissa declarada (ver config/projecoes.yaml).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from indicadores import conjuntura, projecoes  # noqa: E402
from indicadores.util import PASTA_PAINEL, RAIZ, agora, carregar_catalogo, hoje, ler_serie  # noqa: E402

MODELO = Path(__file__).resolve().parent / "indicadores" / "dashboard_modelo.html"
EPOCA = dt.date(1970, 1, 1)
DIARIO_ULTIMOS_DIAS = 730  # antes disso, um ponto por semana (o arquivo fica leve)

# Gráficos do dashboard: cada um com um eixo só e no máximo quatro linhas.
GRAFICOS = [
    {"id": "inflacao", "titulo_pt": "Inflação contra a meta", "titulo_en": "Inflation against the target",
     "nota_pt": "IPCA em 12 meses, Focus 12 meses à frente e a faixa da meta do CMN. As linhas tracejadas são "
                "contas mecânicas com premissa declarada, não previsões.",
     "nota_en": "12-month IPCA, Focus 12 months ahead and the CMN target band. Dashed lines are arithmetic "
                "under a stated assumption, not forecasts.",
     "unidade": "%", "decimais": 2, "meta": True,
     "series": [{"serie": "br_ipca_12m"}, {"serie": "br_focus_ipca_12m"},
                {"cenario": "media_3m"}, {"cenario": "meta"}]},
    {"id": "icf", "titulo_pt": "Condições financeiras (Brasil)", "titulo_en": "Financial conditions (Brazil)",
     "nota_pt": "Média simples dos percentis de juro real ex-ante, IPCA+ 5 anos e prefixado 5 anos. "
                "0 = mais frouxas, 100 = mais apertadas desde 2016.",
     "nota_en": "Simple average of the percentiles of the ex-ante real rate, 5-year IPCA+ and 5-year nominal. "
                "0 = loosest, 100 = tightest since 2016.",
     "unidade": "", "decimais": 0, "referencia": 50, "series": [{"icf": True}]},
    {"id": "monetaria", "titulo_pt": "Política monetária", "titulo_en": "Monetary policy",
     "nota_pt": "Juro real ex-ante = (1 + Selic) / (1 + IPCA esperado em 12 meses pelo Focus) − 1.",
     "nota_en": "Ex-ante real rate = (1 + Selic) / (1 + Focus 12-month IPCA expectation) − 1.",
     "unidade": "% a.a.", "decimais": 2,
     "series": [{"serie": "br_selic_meta"}, {"serie": "br_juro_real_ex_ante"}]},
    {"id": "curva", "titulo_pt": "Juros de mercado (Tesouro Direto)", "titulo_en": "Market rates (Tesouro Direto)",
     "nota_pt": "Vértices de prazo constante interpolados entre os títulos sem cupom.",
     "nota_en": "Constant-maturity points interpolated between zero-coupon bonds.",
     "unidade": "% a.a.", "decimais": 2,
     "series": [{"serie": "br_pre_1a"}, {"serie": "br_pre_5a"}, {"serie": "br_ipca_mais_5a"}]},
    {"id": "implicita", "titulo_pt": "Inflação implícita e expectativa", "titulo_en": "Breakeven and expectations",
     "nota_pt": "Inflação implícita de 5 anos na curva do Tesouro contra o Focus de 12 meses.",
     "nota_en": "5-year breakeven from the Treasury curve against the 12-month Focus expectation.",
     "unidade": "%", "decimais": 2,
     "series": [{"serie": "br_inflacao_implicita_5a"}, {"serie": "br_focus_ipca_12m"}]},
    {"id": "diferenciais", "titulo_pt": "Diferenciais de juros", "titulo_en": "Interest-rate differentials",
     "nota_pt": "Leitura do carry atual. Não indica para onde vai o câmbio.",
     "nota_en": "A reading of current carry. It says nothing about where FX is heading.",
     "unidade": "p.p.", "decimais": 2,
     "series": [{"serie": "br_diferencial_selic_t3m"}, {"serie": "br_diferencial_pre1a_t2a"}]},
    {"id": "focus_selic", "titulo_pt": "Selic: atual e Focus", "titulo_en": "Selic: actual and Focus",
     "nota_pt": "Meta Selic e a mediana do Focus para o fim do ano corrente e do seguinte. Cada linha do Focus "
                "muda de ano de referência em janeiro.",
     "nota_en": "Selic target and the Focus median for the end of the current and the next year. Each Focus line "
                "rolls to the next reference year in January.",
     "unidade": "% a.a.", "decimais": 2,
     "series": [{"serie": "br_selic_meta"}, {"serie": "br_focus_selic_ano"}, {"serie": "br_focus_selic_ano1"}]},
    {"id": "focus_cambio", "titulo_pt": "Dólar: PTAX e Focus", "titulo_en": "USD/BRL: PTAX and Focus",
     "nota_pt": "PTAX de venda e a mediana do Focus para o câmbio no fim do ano corrente e do seguinte.",
     "nota_en": "PTAX selling rate and the Focus median for the exchange rate at the end of the current and next year.",
     "unidade": "R$", "decimais": 2,
     "series": [{"serie": "br_dolar_ptax"}, {"serie": "br_focus_cambio_ano"}, {"serie": "br_focus_cambio_ano1"}]},
    {"id": "focus_pib", "titulo_pt": "PIB: Focus", "titulo_en": "GDP: Focus",
     "nota_pt": "Mediana do Focus para o crescimento do PIB no ano corrente e no seguinte.",
     "nota_en": "Focus median for GDP growth in the current and the next year.",
     "unidade": "%", "decimais": 2,
     "series": [{"serie": "br_focus_pib_ano"}, {"serie": "br_focus_pib_ano1"}]},
    {"id": "global_juros", "titulo_pt": "Juros globais", "titulo_en": "Global rates",
     "nota_pt": "Fed funds efetiva, Treasury 10 anos e taxa de depósito do BCE.",
     "nota_en": "Effective fed funds, 10-year Treasury and ECB deposit rate.",
     "unidade": "%", "decimais": 2,
     "series": [{"serie": "us_fed_funds"}, {"serie": "us_t10a"}, {"serie": "ez_taxa_deposito"}]},
    {"id": "global_inflacao", "titulo_pt": "Inflação: Brasil e zona do euro", "titulo_en": "Inflation: Brazil and euro area",
     "nota_pt": "IPCA e HICP em 12 meses.", "nota_en": "12-month IPCA and HICP.",
     "unidade": "%", "decimais": 1, "series": [{"serie": "br_ipca_12m"}, {"serie": "ez_hicp_12m"}]},
]


def dia(d: dt.date) -> int:
    return (d - EPOCA).days


def enxugar(serie: conjuntura.Serie, ref: dt.date, mensal: bool) -> list[list[float]]:
    """Diário nos últimos dois anos, semanal antes (séries mensais ficam inteiras)."""
    if mensal:
        pts = serie
    else:
        corte = ref - dt.timedelta(days=DIARIO_ULTIMOS_DIAS)
        pts = conjuntura.semanal([p for p in serie if p[0] < corte]) + [p for p in serie if p[0] >= corte]
    return [[dia(d), round(v, 4)] for d, v in pts]


def montar_dados(ref: dt.date, conj: conjuntura.Conjuntura, cat: dict) -> dict:
    por_id = {i["id"]: i for i in cat["indicadores"]}
    comps = {t.comp["id"]: t for t in conj.termometros}
    desde = dt.date.fromisoformat(conj.cfg["historico_desde"])

    def url_fonte(id_: str) -> str:
        s = ler_serie(id_)
        u = s[max(s)]["fonte_url"] if s else ""
        return u if u.startswith("http") else ""

    graficos = []
    for g in GRAFICOS:
        linhas = []
        for s in g["series"]:
            if "serie" in s:
                ind = por_id.get(s["serie"])
                if not ind or not ind.get("ativo", True):
                    continue
                pts = [p for p in conjuntura.serie_ou_derivada(s["serie"], cat) if desde <= p[0] <= ref]
                if ind["frequencia"] == "reuniao" and pts:
                    pts = conjuntura.diario(pts, ref)  # linha em degraus, até hoje
                linhas.append({"pt": ind["nome_pt"], "en": ind["nome_en"], "fonte": url_fonte(s["serie"]),
                               "pts": enxugar(pts, ref, ind["frequencia"] == "mensal")})
            elif "componente" in s and s["componente"] in comps:
                t = comps[s["componente"]]
                linhas.append({"pt": t.comp["nome_pt"], "en": t.comp["nome_en"], "fonte": url_fonte(t.comp["serie"]),
                               "pts": enxugar(t.serie, ref, t.mensal)})
            elif "cenario" in s and s["cenario"] in conj.cenarios:
                p = next(x for x in conj.cfg["cenarios_ipca"]["premissas"] if x["id"] == s["cenario"])
                linhas.append({"pt": f"Conta: {p['nome_pt'].lower()}", "en": f"Arithmetic: {p['nome_en'].lower()}",
                               "tracejado": True, "pts": [[dia(d), round(v, 4)] for d, v in conj.cenarios[s["cenario"]]]})
            elif s.get("icf") and conj.icf:
                linhas.append({"pt": "Índice de condições financeiras", "en": "Financial conditions index",
                               "pts": [[dia(d), round(v, 1)] for d, v in conj.icf]})
        if not linhas:
            continue
        item = {k: g[k] for k in g if k not in ("series", "meta")}
        item["linhas"] = linhas
        if g.get("meta"):
            faixa = []
            inicio = min(p[0] for l in linhas for p in l["pts"])
            fim = max(p[0] for l in linhas for p in l["pts"])
            for ano in range((EPOCA + dt.timedelta(days=inicio)).year, (EPOCA + dt.timedelta(days=fim)).year + 1):
                m = conjuntura.meta_do_ano(conj.cfg, ano)
                if m:
                    a, b = max(inicio, dia(dt.date(ano, 1, 1))), min(fim, dia(dt.date(ano, 12, 31)))
                    faixa.append([a, b, m["centro"], m["tolerancia"]])
            item["meta"] = faixa
            item["meta_fonte"] = conj.cfg["metas_inflacao"]["fonte_url"]
        graficos.append(item)

    blocos = {b["id"]: b for b in conj.cfg["blocos"]}
    termos = []
    for t in conj.termometros:
        if not t.ultimo:
            continue
        termos.append({"id": t.comp["id"], "bloco_pt": blocos[t.comp["bloco"]]["nome_pt"],
                       "bloco_en": blocos[t.comp["bloco"]]["nome_en"], "pt": t.comp["nome_pt"],
                       "en": t.comp["nome_en"], "unidade": t.comp["unidade"], "decimais": t.comp["decimais"],
                       "data": dia(t.ultimo[0]), "mensal": t.mensal, "valor": round(t.ultimo[1], 4),
                       "pct": round(t.pct, 1), "pct_1a": None if t.pct_1a is None else round(t.pct_1a, 1)})

    return {"ref": dia(ref), "gerado": agora().isoformat(timespec="minutes"), "desde": desde.year,
            "icf": None if not conj.icf else [dia(conj.icf[-1][0]), round(conj.icf[-1][1], 1)],
            "termometros": termos, "graficos": graficos}


def _r(x: float | None, dec: int = 4) -> float | None:
    return None if x is None else round(x, dec)


def montar_projecoes(proj: projecoes.Projecoes) -> dict:
    variaveis = []
    for v in proj.variaveis:
        c = v.cfg
        anos = [{"ano": h.ano, "data": dia(h.data) if h.data else None, "mediana": _r(h.mediana),
                 "revisao": _r(h.revisao), "otimista": _r(h.otimista), "pessimista": _r(h.pessimista),
                 "erro": _r(h.hist.medio_absoluto), "n": h.hist.n}
                for h in v.horizontes if h.mediana is not None]
        if anos:
            variaveis.append({"id": c["id"], "pt": c["nome_pt"], "en": c["nome_en"], "unidade": c["unidade"],
                              "decimais": c["decimais"], "tipo_erro": c["erro"], "anos": anos})
    contas = {}
    if proj.selic:
        sc = proj.selic
        contas["selic"] = {"data": dia(sc.data), "pre": _r(sc.prefixado), "efetiva": _r(sc.selic_efetiva),
                           "dif": _r(sc.diferenca), "fim": _r(sc.fim_12m), "mov": _r(sc.movimentos, 1),
                           "passo": sc.passo}
    if proj.cambio:
        ct = proj.cambio
        contas["cambio"] = {"data": dia(ct.data), "spot": _r(ct.spot), "br": _r(ct.juro_br), "us": _r(ct.juro_eua),
                            "termo": _r(ct.termo), "premio": _r(ct.premio_pct)}
    if proj.pib and proj.pib.focus is not None and proj.pib.ritmo_necessario is not None:
        pb = proj.pib
        contas["pib"] = {"ano": pb.ano, "mes": dia(pb.ultimo_mes), "meses": pb.meses, "parado": _r(pb.parado),
                         "focus": _r(pb.focus), "ritmo": _r(pb.ritmo_necessario), "carry": _r(pb.carry_seguinte)}
    focus1 = {v["id"]: (v["anos"][1]["mediana"] if len(v["anos"]) > 1 else None) for v in variaveis}
    return {"revisao_dias": proj.cfg["revisao_dias"], "erro_desde": proj.cfg["erro_desde"],
            "ano1": proj.ref.year + 1, "variaveis": variaveis, "contas": contas, "focus1": focus1}


def gerar(ref: dt.date) -> Path:
    cat = carregar_catalogo()
    conj = conjuntura.calcular(ref, catalogo=cat)
    conjuntura.gravar_csv(conj)
    dados = montar_dados(ref, conj, cat)
    try:
        proj = projecoes.calcular(ref, catalogo=cat)
        projecoes.gravar_csv(proj)
        dados["projecoes"] = montar_projecoes(proj)
    except Exception as e:  # as projeções nunca derrubam o dashboard
        print(f"projeções indisponíveis: {type(e).__name__}: {e}")
        dados["projecoes"] = None
    bruto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    # o JSON vai dentro de <script>: nada nele pode fechar a tag
    bruto = bruto.replace("</", "<\\/")
    html = MODELO.read_text(encoding="utf-8").replace("/*__DADOS__*/null", bruto)
    destino = PASTA_PAINEL / "dashboard.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="data de referência AAAA-MM-DD (padrão: hoje em America/Sao_Paulo)")
    args = ap.parse_args()
    ref = dt.date.fromisoformat(args.data) if args.data else hoje()
    destino = gerar(ref)
    print(f"dashboard gravado em {destino.relative_to(RAIZ)} ({destino.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
