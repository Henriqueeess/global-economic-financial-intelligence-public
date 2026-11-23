#!/usr/bin/env python3
"""Gera o painel diário de indicadores a partir de dados/series/*.csv.

Uso:
  python scripts/gerar_painel.py                  # painel de hoje (America/Sao_Paulo)
  python scripts/gerar_painel.py --data 2026-11-18

Saída (nunca apaga painéis de outros dias):
  painel/AAAA/MM/AAAA-MM-DD/painel-pt.md e painel-en.md, com graficos/*.svg
  painel/ultimo-pt.md e painel/ultimo-en.md, cópia do painel mais recente
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from indicadores import conjuntura, curva  # noqa: E402
from indicadores.painel import Linha, calcular_linha, destaques, ultimo_ate  # noqa: E402
from indicadores.svg import grafico_linhas, minigrafico  # noqa: E402
from indicadores.util import PASTA_PAINEL, RAIZ, carregar_catalogo, hoje, ler_serie, valores  # noqa: E402

MESES = {
    "pt": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}

T = {
    "pt": {
        "titulo": "Painel diário de indicadores",
        "outra": "[English version]({arq})",
        "intro": ("Dados oficiais coletados em {coleta} (horário de Brasília). As variações comparam o último "
                  "valor com o último disponível 7 e 30 dias corridos antes de {ref}. Cada indicador leva à "
                  "fonte; o histórico completo está em [`dados/series/`]({dados})."),
        "destaques": "Maiores movimentos em 7 dias",
        "destaques_nota": ("Medidos em desvios-padrão dos movimentos de 7 dias do último ano: "
                           "acima de 2 é um movimento incomum."),
        "dp": "desvios-padrão",
        "diarias": "Juros, câmbio e expectativas",
        "mensais": "Indicadores mensais",
        "cab_d": "| Indicador | Último | Data | Δ 7 dias | Δ 30 dias | Mín.–máx. 30 dias | 30 dias |",
        "cab_m": "| Indicador | Última leitura | Referência | Anterior | Variação | 13 meses |",
        "curva": "Curva de juros (Tesouro Direto)",
        "curva_nota": ("Taxas de compra dos títulos sem cupom do Tesouro Direto, por prazo até o vencimento. "
                       "Os vértices de 1, 3, 5 e 10 anos das tabelas acima são interpolados entre esses títulos."),
        "pre": "Prefixado (nominal)",
        "ipca": "IPCA+ (real)",
        "cab_c": "| Título | Vencimento | Taxa ({d0}) | Δ 7 dias | Δ 30 dias |",
        "hoje": "Hoje",
        "d7": "7 dias antes",
        "d30": "30 dias antes",
        "anos": "{v} a",
        "fora": "Fora do painel hoje",
        "sem_chave": "aguarda a chave gratuita `{var}`",
        "falha": "falha na coleta: {motivo}",
        "sem_dados": "sem dados",
        "desatualizado": "desatualizado",
        "falha_hoje": "coleta de hoje falhou; último dado gravado",
        "termo": "Termômetros da conjuntura",
        "termo_nota": ("Cada indicador em percentil do próprio histórico desde {desde}: 0 é o menor valor do período, "
                       "100 o maior e 50 a mediana. É uma leitura descritiva de onde estamos, não uma previsão. "
                       "Painel interativo com o histórico completo: [`painel/dashboard.html`]({dash})."),
        "cab_t": "| Bloco | Indicador | Último | Data | Percentil | Há 1 ano |",
        "icf": ("**Índice de condições financeiras (Brasil)**: {v} de 100 em {d} ({q}). Média simples, com pesos "
                "iguais, dos percentis de {comps}. Acima de 50, condições mais apertadas que a mediana desde {desde}."),
        "icf_q": ["muito frouxas", "frouxas", "neutras", "apertadas", "muito apertadas"],
        "cen": ("**Conta mecânica do IPCA (não é previsão)**: o IPCA em 12 meses está em {atual} ({mes}). "
                "Se cada mês seguinte repetir a média dos últimos 3 meses ({m3}% ao mês), ele chega a {v_m3} em {fim}; "
                "se cada mês rodar no ritmo do centro da meta ({meta}%), chega a {v_meta}. Meta: {centro}%, "
                "com tolerância de {tol} p.p."),
        "metodo": "Método",
        "metodo_txt": [
            "Fonte única: APIs oficiais e gratuitas listadas em `config/indicadores.yaml`. Nenhum número é digitado à mão.",
            "Δ em p.p. para taxas (diferença simples) e em % para preços e índices.",
            "Fins de semana e feriados não têm cotação nova: cada linha mostra a data do último dado real.",
            "Indicadores derivados (diferencial de juros, inclinação, inflação implícita, juro real ex-ante) são calculados a partir das séries oficiais.",
            "Termômetros, condições financeiras e contas do IPCA seguem `config/conjuntura.yaml` e não projetam câmbio, juros nem preço de ativos.",
        ],
        "pp": "p.p.",
        "bps": "{v} p.b.",
    },
    "en": {
        "titulo": "Daily indicators dashboard",
        "outra": "[Versão em português]({arq})",
        "intro": ("Official data collected at {coleta} (Brasília time). Changes compare the latest value with "
                  "the latest available 7 and 30 calendar days before {ref}. Each indicator links to its source; "
                  "the full history is in [`dados/series/`]({dados})."),
        "destaques": "Largest 7-day moves",
        "destaques_nota": ("Measured in standard deviations of 7-day moves over the past year: "
                           "above 2 is an unusual move."),
        "dp": "standard deviations",
        "diarias": "Rates, FX and expectations",
        "mensais": "Monthly indicators",
        "cab_d": "| Indicator | Latest | Date | 7-day Δ | 30-day Δ | 30-day low–high | 30 days |",
        "cab_m": "| Indicator | Latest reading | Period | Previous | Change | 13 months |",
        "curva": "Yield curve (Tesouro Direto)",
        "curva_nota": ("Purchase rates of Tesouro Direto zero-coupon bonds, by time to maturity. "
                       "The 1-, 3-, 5- and 10-year points in the tables above are interpolated between these bonds."),
        "pre": "Fixed-rate (nominal)",
        "ipca": "IPCA+ (real)",
        "cab_c": "| Bond | Maturity | Yield ({d0}) | 7-day Δ | 30-day Δ |",
        "hoje": "Today",
        "d7": "7 days earlier",
        "d30": "30 days earlier",
        "anos": "{v}y",
        "fora": "Not on the dashboard today",
        "sem_chave": "waiting for the free `{var}` key",
        "falha": "collection failed: {motivo}",
        "sem_dados": "no data",
        "desatualizado": "stale",
        "falha_hoje": "today's collection failed; last stored value",
        "termo": "Macro thermometers",
        "termo_nota": ("Each indicator as a percentile of its own history since {desde}: 0 is the lowest value in the "
                       "period, 100 the highest and 50 the median. It describes where we are; it is not a forecast. "
                       "Interactive dashboard with the full history: [`painel/dashboard.html`]({dash})."),
        "cab_t": "| Block | Indicator | Latest | Date | Percentile | 1 year ago |",
        "icf": ("**Financial conditions index (Brazil)**: {v} out of 100 on {d} ({q}). Simple equal-weight average "
                "of the percentiles of {comps}. Above 50 means tighter than the median since {desde}."),
        "icf_q": ["very loose", "loose", "neutral", "tight", "very tight"],
        "cen": ("**IPCA arithmetic (not a forecast)**: 12-month IPCA inflation stands at {atual} ({mes}). "
                "If each coming month repeats the average of the last 3 months ({m3}% a month), it reaches {v_m3} "
                "by {fim}; if each month runs at the pace of the target midpoint ({meta}%), it reaches {v_meta}. "
                "Target: {centro}%, with a {tol} pp tolerance band."),
        "metodo": "Method",
        "metodo_txt": [
            "Single source: free official APIs listed in `config/indicadores.yaml`. No number is typed by hand.",
            "Δ in pp for rates (simple difference) and in % for prices and indices.",
            "Weekends and holidays have no new quotes: each row shows the date of the latest actual data point.",
            "Derived indicators (rate differential, curve slope, breakeven inflation, ex-ante real rate) are computed from the official series.",
            "Thermometers, financial conditions and the IPCA arithmetic follow `config/conjuntura.yaml` and do not project FX, rates or asset prices.",
        ],
        "pp": "pp",
        "bps": "{v} bp",
    },
}


# ---------------------------------------------------------------- formatação

def num(v: float, dec: int, lang: str, sinal: bool = False) -> str:
    t = f"{v:+,.{dec}f}" if sinal else f"{v:,.{dec}f}"
    if lang == "pt":
        t = t.replace(",", "_").replace(".", ",").replace("_", ".")
    return t.replace("-", "−")


def data_curta(d: dt.date, lang: str) -> str:
    return f"{d:%d/%m/%Y}" if lang == "pt" else d.isoformat()


def mes(d: dt.date, lang: str) -> str:
    return f"{MESES[lang][d.month - 1]}/{d.year}" if lang == "pt" else f"{MESES[lang][d.month - 1]} {d.year}"


def valor_fmt(l: Linha, v: float, lang: str) -> str:
    u = l.ind["unidade"]
    n = num(v, l.ind["decimais"], lang)
    return f"{u} {n}" if u in ("R$", "US$") else f"{n} {u}" if u not in ("%", "índice") else (f"{n}%" if u == "%" else n)


def delta_fmt(l: Linha, v: float | None, lang: str) -> str:
    if v is None:
        return "—"
    if l.ind["variacao"] == "pp":
        return f"{num(v, max(1, min(l.ind['decimais'], 4)), lang, sinal=True)} {T[lang]['pp']}"
    return f"{num(v, 2, lang, sinal=True)}%"


def nome(l: Linha, lang: str, prefixo: str) -> str:
    rotulo = l.ind[f"nome_{lang}"]
    serie = ler_serie(l.ind["id"])
    url = serie[max(serie)]["fonte_url"] if serie else ""
    alvo = url if url.startswith("http") else f"{prefixo}dados/series/{l.ind['id']}.csv"
    return f"[{rotulo}]({alvo})"


# ---------------------------------------------------------------- seções

def tabela_diaria(linhas: list[Linha], lang: str, prefixo: str, graf: str, coleta: dict) -> list[str]:
    t = T[lang]
    out = [t["cab_d"], "| --- | ---: | --- | ---: | ---: | --- | --- |"]
    for l in linhas:
        data = data_curta(l.data, lang)
        if l.status == "desatualizado":
            data += f" ({t['desatualizado']})"
        if coleta.get(l.ind["id"], {}).get("status") == "falha":
            data += f" ({t['falha_hoje']})"
        faixa = f"{num(l.minimo_30d, l.ind['decimais'], lang)} – {num(l.maximo_30d, l.ind['decimais'], lang)}"
        spark = f"![]({graf}spark-{l.ind['id']}.svg)" if len(l.pontos) >= 2 else ""
        out.append(f"| {nome(l, lang, prefixo)} | {valor_fmt(l, l.valor, lang)} | {data} | "
                   f"{delta_fmt(l, l.var_7d, lang)} | {delta_fmt(l, l.var_30d, lang)} | {faixa} | {spark} |")
    return out


def tabela_mensal(linhas: list[Linha], lang: str, prefixo: str, graf: str, coleta: dict) -> list[str]:
    t = T[lang]
    out = [t["cab_m"], "| --- | ---: | --- | ---: | ---: | --- |"]
    for l in linhas:
        ref = mes(l.data, lang)
        if l.status == "desatualizado":
            ref += f" ({t['desatualizado']})"
        if coleta.get(l.ind["id"], {}).get("status") == "falha":
            ref += f" ({t['falha_hoje']})"
        ant = f"{valor_fmt(l, l.anterior, lang)} ({mes(l.anterior_data, lang)})" if l.anterior is not None else "—"
        spark = f"![]({graf}spark-{l.ind['id']}.svg)" if len(l.pontos) >= 2 else ""
        out.append(f"| {nome(l, lang, prefixo)} | {valor_fmt(l, l.valor, lang)} | {ref} | {ant} | "
                   f"{delta_fmt(l, l.var_anterior, lang)} | {spark} |")
    return out


def dados_curva(ref: dt.date, cfg: dict):
    curvas = curva.ler_curvas(cfg.get("taxa_usada", "taxa_compra"))
    if not curvas:
        return None
    bases = sorted({b for b, _ in curvas if b <= ref})
    if not bases:
        return None

    def base_ate(d):
        anteriores = [b for b in bases if b <= d]
        return anteriores[-1] if anteriores else None

    b0 = bases[-1]
    datas = {"hoje": b0, "d7": base_ate(ref - dt.timedelta(days=7)), "d30": base_ate(ref - dt.timedelta(days=30))}
    return curvas, datas


def secao_curva(ref: dt.date, cfg: dict, lang: str, graf: str, pasta_graf: Path | None) -> list[str]:
    t = T[lang]
    dc = dados_curva(ref, cfg)
    if not dc:
        return []
    curvas, datas = dc
    out = [f"### {t['curva']}", "", t["curva_nota"], ""]
    for nome_curva in ("prefixado", "ipca"):
        series = []
        for chave in ("hoje", "d7", "d30"):
            b = datas[chave]
            if b and (b, nome_curva) in curvas:
                pts = [(curva.prazo_anos(b, v), tx) for v, tx in curvas[(b, nome_curva)]
                       if curva.prazo_anos(b, v) > 0]
                series.append((f"{t[chave]} ({data_curta(b, lang)})", pts))
        if pasta_graf is not None:
            svg = grafico_linhas(series, f"{t[nome_curva if nome_curva == 'ipca' else 'pre']}",
                                 fmt_x=lambda x: t["anos"].format(v=num(x, 0, lang)),
                                 fmt_y=lambda y: f"{num(y, 2, lang)}%", marcadores=True,
                                 fmt_marca_y=lambda y, c: f"{num(y, c, lang)}%")
            (pasta_graf / f"curva-{nome_curva}-{lang}.svg").write_text(svg, encoding="utf-8")
        titulo = t["pre"] if nome_curva == "prefixado" else t["ipca"]
        out += [f"**{titulo}**", "", f"![{titulo}]({graf}curva-{nome_curva}-{lang}.svg)", ""]

    b0 = datas["hoje"]
    out += [t["cab_c"].format(d0=data_curta(b0, lang)), "| --- | --- | ---: | ---: | ---: |"]
    for nome_curva in ("prefixado", "ipca"):
        hoje_pts = dict(curvas.get((b0, nome_curva), []))
        ant = {k: dict(curvas.get((datas[k], nome_curva), [])) if datas[k] else {} for k in ("d7", "d30")}
        for venc, taxa in sorted(hoje_pts.items()):
            deltas = []
            for k in ("d7", "d30"):
                if venc in ant[k]:
                    deltas.append(t["bps"].format(v=num((taxa - ant[k][venc]) * 100, 0, lang, sinal=True)))
                else:
                    deltas.append("—")
            rot = cfg["titulos"][nome_curva]
            out.append(f"| {rot} | {data_curta(venc, lang)} | {num(taxa, 2, lang)}% | {deltas[0]} | {deltas[1]} |")
    out.append("")
    out.append(f"[{'Fonte' if lang == 'pt' else 'Source'}: Tesouro Transparente]({cfg['pagina_dataset']})")
    return out


def barra(pct: float) -> str:
    cheios = int(round(pct / 10))
    return "█" * cheios + "░" * (10 - cheios)


def secao_termometros(conj: "conjuntura.Conjuntura | None", lang: str, prefixo: str) -> list[str]:
    if conj is None or not any(t.ultimo for t in conj.termometros):
        return []
    t = T[lang]
    desde = dt.date.fromisoformat(conj.cfg["historico_desde"])
    out = [f"## {t['termo']}", "",
           t["termo_nota"].format(desde=desde.year, dash=f"{prefixo}painel/dashboard.html"), "",
           t["cab_t"], "| --- | --- | ---: | --- | ---: | ---: |"]
    blocos = {b["id"]: b[f"nome_{lang}"] for b in conj.cfg["blocos"]}
    for tm in conj.termometros:
        if not tm.ultimo:
            continue
        c = tm.comp
        d, v = tm.ultimo
        u = c["unidade"]
        val = f"{num(v, c['decimais'], lang)}{'%' if u == '%' else ' ' + (t['pp'] if u == 'p.p.' else u)}"
        quando = mes(d, lang) if tm.mensal else data_curta(d, lang)
        ano = num(tm.pct_1a, 0, lang) if tm.pct_1a is not None else "—"
        out.append(f"| {blocos[c['bloco']]} | {c[f'nome_{lang}']} | {val} | {quando} | "
                   f"`{barra(tm.pct)}` {num(tm.pct, 0, lang)} | {ano} |")
    out.append("")
    if conj.icf:
        d, v = conj.icf[-1]
        q = t["icf_q"][min(4, int(v // 20))]
        nomes = {x.comp["id"]: x.comp[f"nome_{lang}"] for x in conj.termometros}
        comps = [nomes[c] for c in conj.cfg["condicoes_financeiras"]["componentes"] if c in nomes]
        junta = (", ".join(comps[:-1]) + (" e " if lang == "pt" else " and ") + comps[-1]) if len(comps) > 1 else comps[0]
        out += [t["icf"].format(v=num(v, 0, lang), d=data_curta(d, lang), q=q, comps=junta, desde=desde.year), ""]
    cen = conj.cenarios
    if "media_3m" in cen and "meta" in cen and conj.ipca_mensal:
        ini, atual = cen["media_3m"][0]
        fim, v_m3 = cen["media_3m"][-1]
        meta = conjuntura.meta_do_ano(conj.cfg, fim.year) or {}
        m3 = sum(v for _, v in conj.ipca_mensal[-3:]) / 3
        meta_m = ((1 + meta.get("centro", 0) / 100) ** (1 / 12) - 1) * 100
        out += [t["cen"].format(atual=f"{num(atual, 2, lang)}%", mes=mes(ini, lang), m3=num(m3, 2, lang),
                                v_m3=f"{num(v_m3, 2, lang)}%", fim=mes(fim, lang), meta=num(meta_m, 2, lang),
                                v_meta=f"{num(cen['meta'][-1][1], 2, lang)}%",
                                centro=num(meta.get("centro", 0), 1, lang),
                                tol=num(meta.get("tolerancia", 0), 1, lang)), ""]
    return out


def montar(lang: str, ref: dt.date, cat: dict, linhas: dict[str, Linha], coleta: dict, prefixo: str,
           graf: str, outra: str, pasta_graf: Path | None, conj: "conjuntura.Conjuntura | None" = None) -> str:
    t = T[lang]
    quando = coleta.get("_coleta")
    coleta_txt = (dt.datetime.fromisoformat(quando).strftime("%d/%m/%Y %Hh%M" if lang == "pt" else "%Y-%m-%d %H:%M")
                  if quando else "—")
    out = [f"# {t['titulo']} — {data_curta(ref, lang)}", "", t["outra"].format(arq=outra), "",
           t["intro"].format(coleta=coleta_txt, ref=data_curta(ref, lang), dados=f"{prefixo}dados/series/"), ""]

    validas = [l for l in linhas.values() if l.status != "sem_dados"]
    top = destaques(validas)
    if top:
        out += [f"## {t['destaques']}", "", t["destaques_nota"], ""]
        for l in top:
            out.append(f"- **{l.ind[f'nome_{lang}']}**: {valor_fmt(l, l.valor, lang)}, "
                       f"{delta_fmt(l, l.var_7d, lang)} ({num(l.z_7d, 1, lang, sinal=True)} {t['dp']})")
        out.append("")

    out += secao_termometros(conj, lang, prefixo)

    for reg in cat["regioes"]:
        da_regiao = [linhas[i["id"]] for i in cat["indicadores"]
                     if i["regiao"] == reg["id"] and i["id"] in linhas and linhas[i["id"]].status != "sem_dados"]
        if not da_regiao:
            continue
        out += [f"## {reg[f'nome_{lang}']}", ""]
        diarias = [l for l in da_regiao if l.ind["frequencia"] != "mensal"]
        mensais = [l for l in da_regiao if l.ind["frequencia"] == "mensal"]
        if diarias:
            out += [f"### {t['diarias']}", ""] + tabela_diaria(diarias, lang, prefixo, graf, coleta) + [""]
        if mensais:
            out += [f"### {t['mensais']}", ""] + tabela_mensal(mensais, lang, prefixo, graf, coleta) + [""]
        if reg["id"] == "brasil":
            out += secao_curva(ref, cat["curva_tesouro"], lang, graf, pasta_graf) + [""]

    fora = [l for l in linhas.values() if l.status == "sem_dados"]
    if fora:
        out += [f"## {t['fora']}", ""]
        for l in fora:
            info = coleta.get(l.ind["id"], {})
            if info.get("status") == "sem_chave":
                motivo = t["sem_chave"].format(var=l.ind.get("requer_chave", ""))
            elif info.get("status") == "falha":
                motivo = t["falha"].format(motivo=info.get("motivo", "")[:80])
            else:
                motivo = t["sem_dados"]
            out.append(f"- {l.ind[f'nome_{lang}']}: {motivo}")
        out.append("")

    out += [f"## {t['metodo']}", ""] + [f"- {x}" for x in t["metodo_txt"]] + [""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="data de referência AAAA-MM-DD (padrão: hoje em America/Sao_Paulo)")
    args = ap.parse_args()
    ref = dt.date.fromisoformat(args.data) if args.data else hoje()

    cat = carregar_catalogo()
    resumo_arq = RAIZ / "dados" / "ultima-coleta.json"
    coleta: dict = {}
    if resumo_arq.exists():
        bruto = json.loads(resumo_arq.read_text(encoding="utf-8"))
        coleta = dict(bruto.get("indicadores", {}))
        coleta["_coleta"] = bruto.get("coleta")

    linhas = {i["id"]: calcular_linha(i, valores(i["id"]), ref)
              for i in cat["indicadores"] if i.get("ativo", True)}

    try:
        conj = conjuntura.calcular(ref, catalogo=cat)
    except Exception as e:  # a conjuntura nunca derruba o painel
        print(f"conjuntura indisponível: {type(e).__name__}: {e}")
        conj = None

    pasta = PASTA_PAINEL / f"{ref:%Y}" / f"{ref:%m}" / ref.isoformat()
    graficos = pasta / "graficos"
    graficos.mkdir(parents=True, exist_ok=True)
    for l in linhas.values():
        if len(l.pontos) >= 2:
            (graficos / f"spark-{l.ind['id']}.svg").write_text(minigrafico(l.pontos), encoding="utf-8")

    relativo = f"{ref:%Y}/{ref:%m}/{ref.isoformat()}/"
    for lang in ("pt", "en"):
        outro = "en" if lang == "pt" else "pt"
        texto = montar(lang, ref, cat, linhas, coleta, prefixo="../../../../", graf="graficos/",
                       outra=f"painel-{outro}.md", pasta_graf=graficos, conj=conj)
        (pasta / f"painel-{lang}.md").write_text(texto, encoding="utf-8")
        ultimo = montar(lang, ref, cat, linhas, coleta, prefixo="../", graf=f"{relativo}graficos/",
                        outra=f"ultimo-{outro}.md", pasta_graf=None, conj=conj)
        (PASTA_PAINEL / f"ultimo-{lang}.md").write_text(ultimo, encoding="utf-8")
    print(f"painel gravado em {pasta.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
