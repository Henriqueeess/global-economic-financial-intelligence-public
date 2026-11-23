#!/usr/bin/env python3
"""Gera o Panorama Econômico do dia: uma página HTML com as edições em português e inglês.

Uso:
  python scripts/gerar_panorama.py                        # briefing mais recente até hoje (America/Sao_Paulo)
  python scripts/gerar_panorama.py --data 2026-11-19      # briefing mais recente até essa data
  python scripts/gerar_panorama.py --pasta relatorios/2026/11/2026-11-19_0731

Entradas (só leitura):
  relatorios/<execução>/relatorio-pt.md e relatorio-en.md   textos, agenda, itens não confirmados
  dados/series/, dados/curva/                                números oficiais e curvas do Tesouro
  config/panorama.yaml, config/conjuntura.yaml               o que entra e os termômetros

Saída:
  panorama/ultimo.html                    a página mais recente (é a que o Apps Script mostra)
  panorama/AAAA/MM/AAAA-MM-DD.html        arquivo do dia (regravado se houver nova execução no mesmo dia)

Sem IA e sem rede. Nada aqui projeta câmbio, juros de mercado ou preço de ativo.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from indicadores import conjuntura, curva, painel, relatorio  # noqa: E402
from indicadores.util import RAIZ, agora, carregar_catalogo, hoje, ler_serie, valores  # noqa: E402

CONFIG = RAIZ / "config" / "panorama.yaml"
MODELO = Path(__file__).resolve().parent / "indicadores" / "panorama_modelo.html"
PASTA_RELATORIOS = RAIZ / "relatorios"
PASTA_PANORAMA = RAIZ / "panorama"
PADRAO_EXECUCAO = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}(-manual)?$")


def carregar_config() -> dict:
    import yaml

    with CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- briefing

def escolher_execucao(ref: dt.date) -> Path | None:
    """A execução mais recente com data <= ref que tenha as duas edições."""
    candidatas = []
    for p in PASTA_RELATORIOS.glob("*/*/*"):
        if p.is_dir() and PADRAO_EXECUCAO.match(p.name) and p.name[:10] <= ref.isoformat():
            if (p / "relatorio-pt.md").exists() and (p / "relatorio-en.md").exists():
                candidatas.append(p)
    return max(candidatas, key=lambda p: p.name) if candidatas else None


def intercalar(itens: list[relatorio.Item], secoes: list[int], maximo: int) -> list[int]:
    """Índices dos itens, alternando entre as seções na ordem configurada (o briefing já ordena por relevância)."""
    filas = {s: [i for i, it in enumerate(itens) if it.secao == s] for s in secoes}
    escolhidos: list[int] = []
    while len(escolhidos) < maximo and any(filas.values()):
        for s in secoes:
            if filas[s] and len(escolhidos) < maximo:
                escolhidos.append(filas[s].pop(0))
    return sorted(escolhidos)


def casa_gatilho(texto: str, g: str) -> bool:
    flags = 0 if any(c.isupper() for c in g) else re.I
    fim = r"(?!\w)" if len(g) <= 4 else ""
    return re.search(r"(?<!\w)" + re.escape(g) + fim, texto, flags) is not None


def glossario(cfg: dict, texto: str) -> list[dict]:
    g = cfg["glossario"]
    sempre = set(g.get("sempre", []))
    fixos = [t for t in g["termos"] if t["id"] in sempre]
    outros = [t for t in g["termos"] if t["id"] not in sempre and any(casa_gatilho(texto, x) for x in t["gatilhos"])]
    return (fixos + outros)[: g["maximo"]]


def montar_edicoes(cfg: dict, pasta: Path) -> tuple[dict, list[str]]:
    avisos: list[str] = []
    rel = {lg: relatorio.ler((pasta / f"relatorio-{lg}.md").read_text(encoding="utf-8")) for lg in ("pt", "en")}
    lc = cfg["leitura"]

    # Leitura do dia: mesmos índices nas duas edições, para manter a paridade.
    idx = intercalar(rel["pt"].itens, lc["secoes"], lc["maximo_itens"])
    if len(rel["pt"].itens) != len(rel["en"].itens):
        avisos.append(f"edições com número diferente de notícias (PT {len(rel['pt'].itens)}, EN {len(rel['en'].itens)})")
    # Agenda: destaque se a linha casar numa das duas edições.
    agendas = {lg: (rel[lg].tabelas.get(7) or [])[1:] for lg in rel}
    destaque = set()
    for lg, linhas in agendas.items():
        for i, cel in enumerate(linhas):
            if any(casa_gatilho(" ".join(cel), w) for w in cfg["agenda_destaque"]):
                destaque.add(i)
    termos = glossario(cfg, rel["pt"].texto_corrido + "\n" + rel["en"].texto_corrido)

    edicoes = {}
    for lg, r in rel.items():
        itens = []
        for i in idx:
            if i >= len(r.itens):
                continue
            it = r.itens[i]
            itens.append({
                "titulo": relatorio.sem_marcacao(it.titulo),
                "texto_html": relatorio.inline_html(relatorio.primeiras_frases(it.texto, lc["frases_por_item"])),
                "tipo": it.tipo, "link": it.link, "veiculo": it.veiculo, "data": it.data,
                "andamento": it.em_andamento, "secao": r.secoes.get(it.secao, ""),
            })
        mercados = r.tabelas.get(5) or []
        edicoes[lg] = {
            "titulo": r.titulo,
            "subtitulo": relatorio.sem_marcacao(r.subtitulo),
            "resumo_html": [relatorio.inline_html(t) for t in r.resumo],
            "itens": itens,
            "mercados": {"cab": mercados[0] if mercados else [], "linhas": [
                [relatorio.sem_marcacao(c) for c in l] for l in mercados[1:]]},
            "agenda": [{"hora": c[0] if c else "", "pais": c[1] if len(c) > 1 else "",
                        "evento": relatorio.sem_marcacao(c[2]) if len(c) > 2 else "",
                        "consenso": c[3] if len(c) > 3 else "", "fonte": c[4] if len(c) > 4 else "",
                        "destaque": i in destaque} for i, c in enumerate(agendas[lg])],
            "nao_confirmados_html": [relatorio.inline_html(t) for t in r.nao_confirmados],
            "glossario": [{"termo": t[lg]["termo"], "texto": t[lg]["texto"]} for t in termos],
        }
    incompleto = rel["pt"].incompleto or rel["en"].incompleto
    return {"edicoes": edicoes, "incompleto": incompleto}, avisos


# ---------------------------------------------------------------- números

def linha_serie(ind: dict, ref: dt.date, cat: dict, pct: float | None = None) -> dict | None:
    s = conjuntura.serie_ou_derivada(ind["id"], cat)
    l = painel.calcular_linha(ind, s, ref)
    if l.status == "sem_dados":
        return None
    linhas_csv = ler_serie(ind["id"])
    url = linhas_csv[l.data.isoformat()]["fonte_url"] if l.data and l.data.isoformat() in linhas_csv else ""
    mensal = ind["frequencia"] == "mensal"
    return {
        "id": ind["id"], "pt": ind["nome_pt"], "en": ind["nome_en"], "unidade": ind["unidade"],
        "decimais": ind["decimais"], "tipo_var": ind["variacao"], "data": l.data.isoformat(), "mensal": mensal,
        "valor": l.valor, "var": l.var_anterior if mensal else l.var_7d,
        "anterior_data": l.anterior_data.isoformat() if mensal and l.anterior_data else None,
        "desatualizado": l.status == "desatualizado", "pct": None if pct is None else round(pct, 1),
        "url": url if url.startswith("http") else "",
    }


def montar_numeros(cfg: dict, ref: dt.date, cat: dict) -> dict:
    por_id = {i["id"]: i for i in cat["indicadores"] if i.get("ativo", True)}
    conj = conjuntura.calcular(ref, catalogo=cat)
    termos = {t.comp["id"]: t for t in conj.termometros}
    pct_da_serie = {t.comp["serie"]: t.pct for t in conj.termometros
                    if t.comp["calculo"] == "nivel" and t.pct is not None}

    cartoes = []
    for c in cfg["cartoes"]:
        ind = por_id.get(c["serie"])
        if not ind:
            continue
        t = termos.get(c.get("termometro"))
        l = linha_serie(ind, ref, cat, t.pct if t else None)
        if l:
            curto = cfg.get("nomes_curtos", {}).get(c["serie"])
            if curto:
                l["pt"], l["en"] = curto["pt"], curto["en"]
            cartoes.append(l)

    bancos = []
    for b in cfg["bancos_centrais"]:
        ind = por_id.get(b["principal"])
        principal = linha_serie(ind, ref, cat, pct_da_serie.get(b["principal"])) if ind else None
        if not principal:
            continue
        linhas = [linha_serie(por_id[x], ref, cat, pct_da_serie.get(x)) for x in b["linhas"] if x in por_id]
        bancos.append({"pt": b["nome_pt"], "en": b["nome_en"], "principal": principal,
                       "linhas": [l for l in linhas if l]})

    blocos = {x["id"]: x for x in conj.cfg["blocos"]}
    termometros = [{
        "bloco_pt": blocos[t.comp["bloco"]]["nome_pt"], "bloco_en": blocos[t.comp["bloco"]]["nome_en"],
        "pt": t.comp["nome_pt"], "en": t.comp["nome_en"], "unidade": t.comp["unidade"],
        "decimais": t.comp["decimais"], "valor": round(t.ultimo[1], 4), "data": t.ultimo[0].isoformat(),
        "pct": round(t.pct, 1), "pct_1a": None if t.pct_1a is None else round(t.pct_1a, 1),
    } for t in conj.termometros if t.ultimo and t.pct is not None]

    return {"cartoes": cartoes, "bancos": bancos, "termometros": termometros,
            "curvas": montar_curvas(cfg, ref), "desde": conj.cfg["historico_desde"][:4]}


def montar_curvas(cfg: dict, ref: dt.date) -> dict | None:
    curvas = curva.ler_curvas()
    datas = sorted({d for d, c in curvas if d <= ref and (d, "prefixado") in curvas and (d, "ipca") in curvas})
    if not datas:
        return None
    a = datas[-1]
    antes = [d for d in datas if d <= a - dt.timedelta(days=cfg["curvas"]["comparar_dias"])]
    b = antes[-1] if antes else None
    saida = {"data_a": a.isoformat(), "data_b": b.isoformat() if b else None}
    for nome in ("prefixado", "ipca"):
        anteriores = dict(curvas.get((b, nome), [])) if b else {}
        saida[nome] = [{"venc": v.isoformat(), "prazo": round(curva.prazo_anos(a, v), 3), "a": taxa,
                        "b": anteriores.get(v)} for v, taxa in curvas[(a, nome)] if v > a]
    return saida


# ---------------------------------------------------------------- página

def montar_dados(ref: dt.date, pasta: Path | None = None) -> tuple[dict, list[str]]:
    cfg = carregar_config()
    cat = carregar_catalogo()
    pasta = pasta or escolher_execucao(ref)
    if pasta is None:
        raise SystemExit("nenhum relatório com as duas edições até " + ref.isoformat())
    textos, avisos = montar_edicoes(cfg, pasta)
    dia = dt.date.fromisoformat(pasta.name[:10])
    dados = {
        "dia": dia.isoformat(), "execucao": pasta.name, "pasta": pasta.relative_to(RAIZ).as_posix(),
        "gerado": agora().isoformat(timespec="minutes"), **textos, **montar_numeros(cfg, dia, cat),
    }
    return dados, avisos


def renderizar(dados: dict) -> str:
    bruto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    bruto = bruto.replace("</", "<\\/")  # o JSON vai dentro de <script>: nada nele pode fechar a tag
    return MODELO.read_text(encoding="utf-8").replace("/*__DADOS__*/null", bruto)


def gerar(ref: dt.date, pasta: Path | None = None) -> tuple[list[Path], list[str]]:
    dados, avisos = montar_dados(ref, pasta)
    html = renderizar(dados)
    dia = dt.date.fromisoformat(dados["dia"])
    destinos = [PASTA_PANORAMA / f"{dia:%Y}" / f"{dia:%m}" / f"{dia.isoformat()}.html"]
    # ultimo.html só avança: regerar um dia antigo não troca a página mais recente
    ultimo = PASTA_PANORAMA / "ultimo.html"
    atual = re.search(r'"execucao":"([^"]+)"', ultimo.read_text(encoding="utf-8")) if ultimo.exists() else None
    if not atual or atual.group(1) <= dados["execucao"]:
        destinos.append(ultimo)
    for d in destinos:
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(html, encoding="utf-8")
    return destinos, avisos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="data de referência AAAA-MM-DD (padrão: hoje em America/Sao_Paulo)")
    ap.add_argument("--pasta", help="pasta de uma execução em relatorios/ (padrão: a mais recente até --data)")
    args = ap.parse_args()
    ref = dt.date.fromisoformat(args.data) if args.data else hoje()
    pasta = None
    if args.pasta:
        pasta = (RAIZ / args.pasta).resolve()
        if PASTA_RELATORIOS.resolve() not in pasta.parents or not PADRAO_EXECUCAO.match(pasta.name):
            raise SystemExit("--pasta precisa ser uma execução dentro de relatorios/")
    destinos, avisos = gerar(ref, pasta)
    for a in avisos:
        print("aviso:", a)
    for d in destinos:
        print(f"panorama gravado em {d.relative_to(RAIZ)} ({d.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
