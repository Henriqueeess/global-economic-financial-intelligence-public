"""Funções comuns: HTTP, datas, leitura e gravação das séries em CSV."""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SERIES = RAIZ / "dados" / "series"
PASTA_CURVA = RAIZ / "dados" / "curva"
PASTA_PAINEL = RAIZ / "painel"
CATALOGO = RAIZ / "config" / "indicadores.yaml"

FUSO = ZoneInfo("America/Sao_Paulo")
USER_AGENT = "global-economic-financial-intelligence/1.0 (coleta de dados oficiais abertos)"
CAMPOS_SERIE = ["data", "valor", "fonte_url", "coletado_em"]


def agora() -> dt.datetime:
    return dt.datetime.now(FUSO)


def hoje() -> dt.date:
    return agora().date()


def http_get(url: str, headers: dict | None = None, timeout: int = 60, tentativas: int = 3,
             data: bytes | None = None) -> bytes:
    """GET (ou POST, se `data`) com novas tentativas e espera crescente.

    Nunca registra cabeçalhos: eles podem carregar chaves de API.
    """
    cab = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    cab.update(headers or {})
    ultimo_erro: Exception | None = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=cab, data=data)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            ultimo_erro = e
            if 400 <= e.code < 500 and e.code != 429:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            ultimo_erro = e
        time.sleep(2 ** (i + 1))
    raise RuntimeError(f"falha HTTP em {url_publica(url)}: {descrever_erro(ultimo_erro)}")


def http_json(url: str, tentativas: int = 4, **kw):
    """Como http_get, mas também tenta de novo quando a resposta não é JSON.

    O BCB às vezes devolve uma página de erro em HTML no lugar do JSON
    (bloqueio momentâneo); uma nova tentativa costuma resolver.
    """
    for i in range(tentativas):
        corpo = http_get(url, **kw)
        try:
            return json.loads(corpo.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            if i == tentativas - 1:
                raise RuntimeError(f"resposta não é JSON em {url_publica(url)}")
            time.sleep(5 * (i + 1))


def descrever_erro(e: Exception | None) -> str:
    if isinstance(e, urllib.error.HTTPError):
        return f"http={e.code}"
    return type(e).__name__ if e else "desconhecido"


PARAMETROS_SECRETOS = {"api_key", "registrationkey", "token", "user", "pass", "password", "key"}


def url_publica(url: str) -> str:
    """Remove da URL qualquer parâmetro que possa conter credencial."""
    partes = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(partes.query, keep_blank_values=True)
             if k.lower() not in PARAMETROS_SECRETOS]
    return urllib.parse.urlunsplit(partes._replace(query=urllib.parse.urlencode(query, safe="$,'()[]|:/")))


# ---------------------------------------------------------------- séries

def caminho_serie(id_: str) -> Path:
    return PASTA_SERIES / f"{id_}.csv"


def ler_serie(id_: str) -> dict[str, dict]:
    """Lê dados/series/<id>.csv como {data_iso: linha}."""
    p = caminho_serie(id_)
    if not p.exists():
        return {}
    with p.open(encoding="utf-8", newline="") as f:
        return {linha["data"]: linha for linha in csv.DictReader(f)}


def valores(id_: str) -> list[tuple[dt.date, float]]:
    """Série ordenada por data, como (data, valor)."""
    return sorted((dt.date.fromisoformat(d), float(l["valor"])) for d, l in ler_serie(id_).items())


def gravar_serie(id_: str, novos: list[tuple[str, float]], fonte_url: str,
                 limite: dt.date) -> tuple[int, int]:
    """Funde observações novas ao CSV existente.

    Datas posteriores a `limite` (o dia da coleta) são descartadas: algumas séries
    do BCB trazem datas futuras (ex.: a meta Selic até a próxima reunião do Copom).
    Retorna (linhas novas, linhas revisadas).
    """
    existentes = ler_serie(id_)
    carimbo = agora().isoformat(timespec="seconds")
    url = url_publica(fonte_url)
    novas = revisadas = 0
    for data, valor in novos:
        if dt.date.fromisoformat(data) > limite:
            continue
        texto = formatar_valor(valor)
        antigo = existentes.get(data)
        if antigo is None:
            novas += 1
        elif antigo["valor"] == texto:
            continue
        else:
            revisadas += 1
        existentes[data] = {"data": data, "valor": texto, "fonte_url": url, "coletado_em": carimbo}
    if novas or revisadas or not caminho_serie(id_).exists():
        PASTA_SERIES.mkdir(parents=True, exist_ok=True)
        with caminho_serie(id_).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS_SERIE, lineterminator="\n")
            w.writeheader()
            for d in sorted(existentes):
                w.writerow(existentes[d])
    return novas, revisadas


def formatar_valor(v: float) -> str:
    """Texto estável para o CSV: até 6 casas, sem zeros à direita."""
    t = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if t in ("-0", "") else t


def carregar_catalogo() -> dict:
    import yaml  # dependência declarada em requirements.txt

    with CATALOGO.open(encoding="utf-8") as f:
        return yaml.safe_load(f)
