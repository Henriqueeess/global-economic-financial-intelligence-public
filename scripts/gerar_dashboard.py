#!/usr/bin/env python3
"""Gera o dashboard interativo da conjuntura (HTML) e os CSVs de apoio.

Uso:
  python scripts/gerar_dashboard.py                  # com os dados até hoje (America/Sao_Paulo)
  python scripts/gerar_dashboard.py --data 2026-11-19

Saída:
  painel/dashboard.html       página única, sem dependências externas, PT/EN, tema claro e escuro
  dados/conjuntura/*.csv      termômetros, condições financeiras e contas do IPCA (formato longo,
                              pronto para importar no Power BI ou em planilhas)

Nada aqui projeta câmbio, juros de mercado ou preço de ativo (ver config/conjuntura.yaml).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from indicadores import conjuntura  # noqa: E402
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


def gerar(ref: dt.date) -> Path:
    cat = carregar_catalogo()
    conj = conjuntura.calcular(ref, catalogo=cat)
    conjuntura.gravar_csv(conj)
    dados = montar_dados(ref, conj, cat)
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
