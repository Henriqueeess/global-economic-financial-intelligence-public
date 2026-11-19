#!/usr/bin/env python3
"""Coleta as séries do catálogo (config/indicadores.yaml) e grava dados/series/*.csv.

Uso:
  python scripts/coletar_series.py              # coleta diária (últimos N dias, N = janela_incremental_dias)
  python scripts/coletar_series.py --backfill   # histórico completo desde backfill_desde
  python scripts/coletar_series.py --ids br_dolar_ptax us_t10a

Chaves de API são lidas de variáveis de ambiente e nunca impressas.
O resultado de cada indicador vai para dados/ultima-coleta.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from indicadores import curva, derivados  # noqa: E402
from indicadores.fontes import COLETORES  # noqa: E402
from indicadores.util import RAIZ, agora, caminho_serie, carregar_catalogo, gravar_serie, hoje  # noqa: E402

RESUMO = RAIZ / "dados" / "ultima-coleta.json"


def log(evento: str, **campos) -> None:
    detalhes = " ".join(f"{k}={v}" for k, v in campos.items())
    print(f"{agora().isoformat(timespec='seconds')} | coleta | {evento} | {detalhes}", flush=True)


def ordem(ind: dict) -> int:
    tipo = ind["fonte"]["tipo"]
    return {"tesouro_direto_vertice": 1, "derivado": 2}.get(tipo, 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", action="store_true", help="busca o histórico desde backfill_desde")
    ap.add_argument("--ids", nargs="*", help="coleta só estes indicadores")
    args = ap.parse_args()

    cat = carregar_catalogo()
    limite = hoje()
    inicio_backfill = dt.date.fromisoformat(cat["backfill_desde"])
    inicio_incremental = limite - dt.timedelta(days=cat["janela_incremental_dias"])
    indicadores = [i for i in cat["indicadores"] if i.get("ativo", True)]
    if args.ids:
        indicadores = [i for i in indicadores if i["id"] in args.ids]
    indicadores.sort(key=ordem)

    resumo: dict[str, dict] = {}
    if RESUMO.exists() and args.ids:
        resumo = json.loads(RESUMO.read_text(encoding="utf-8")).get("indicadores", {})

    curvas = None
    if any(i["fonte"]["tipo"] == "tesouro_direto_vertice" for i in indicadores):
        try:
            n = curva.baixar_curva(cat["curva_tesouro"], inicio_backfill)
            log("ok", fonte="tesouro_direto_curva", linhas=n)
        except Exception as e:  # mantém o arquivo anterior
            log("falha", fonte="tesouro_direto_curva", motivo=str(e)[:200])
        curvas = curva.ler_curvas(cat["curva_tesouro"].get("taxa_usada", "taxa_compra"))

    for ind in indicadores:
        id_, fonte = ind["id"], ind["fonte"]
        chave = ind.get("requer_chave")
        if chave and not os.environ.get(chave):
            log("falha", indicador=id_, motivo="sem_chave", variavel=chave)
            resumo[id_] = {"status": "sem_chave", "em": agora().isoformat(timespec="seconds")}
            continue
        desde = inicio_backfill if (args.backfill or not caminho_serie(id_).exists()) else inicio_incremental
        try:
            if fonte["tipo"] == "derivado":
                obs, url = derivados.calcular(fonte)
            elif fonte["tipo"] == "tesouro_direto_vertice":
                obs = curva.serie_vertice(curvas or {}, fonte["curva"], fonte["anos"])
                url = cat["curva_tesouro"]["pagina_dataset"]
            else:
                obs, url = COLETORES[fonte["tipo"]](fonte, desde, limite)
            novas, revisadas = gravar_serie(id_, obs, url, limite)
            ultima = max((d for d, _ in obs if d <= limite.isoformat()), default=None)
            log("ok", indicador=id_, desde=desde, obs=len(obs), novas=novas, revisadas=revisadas, ultima=ultima)
            resumo[id_] = {"status": "ok", "ultima_data": ultima, "novas": novas, "revisadas": revisadas,
                           "em": agora().isoformat(timespec="seconds")}
        except Exception as e:
            motivo = str(e)[:200]
            log("falha", indicador=id_, motivo=motivo)
            resumo[id_] = {"status": "falha", "motivo": motivo, "em": agora().isoformat(timespec="seconds")}

    RESUMO.parent.mkdir(parents=True, exist_ok=True)
    RESUMO.write_text(json.dumps({"coleta": agora().isoformat(timespec="seconds"), "indicadores": resumo},
                                 ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ok = sum(1 for r in resumo.values() if r["status"] == "ok")
    log("fim", ok=ok, total=len(resumo))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
