"""Coletores das APIs oficiais. Cada um devolve (observações, url_pública).

Observações são pares (data ISO "AAAA-MM-DD", valor float). A URL pública é a
consulta sem credenciais, gravada em cada linha do CSV para rastreabilidade.
Conteúdo das APIs é dado: nada do que elas devolvem é interpretado como comando.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import urllib.parse

from .util import http_get, http_json

Obs = list[tuple[str, float]]


def _q(texto: str) -> str:
    return urllib.parse.quote(texto, safe="$=&'(),")


def _num(texto) -> float | None:
    if texto is None:
        return None
    t = str(texto).strip().replace(",", "")
    if t in ("", ".", "-", "N/E", "NaN", "nan"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _blocos(desde: dt.date, ate: dt.date, anos: int):
    """Divide o intervalo em blocos de até `anos` anos (o SGS limita séries diárias a 10)."""
    inicio = desde
    while inicio <= ate:
        fim = min(dt.date(inicio.year + anos, inicio.month, 1) - dt.timedelta(days=1), ate)
        yield inicio, fim
        inicio = fim + dt.timedelta(days=1)


# ---------------------------------------------------------------- Brasil

def bcb_sgs(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    cod = fonte["codigo"]
    obs: Obs = []
    url = ""
    for ini, fim in _blocos(desde, ate, 5):
        url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados?formato=json"
               f"&dataInicial={ini:%d/%m/%Y}&dataFinal={fim:%d/%m/%Y}")
        try:
            dados = http_json(url)
        except RuntimeError as e:
            if "http=404" in str(e):  # bloco sem dados
                continue
            raise
        for item in dados:
            v = _num(item.get("valor"))
            if v is not None:
                d = dt.datetime.strptime(item["data"], "%d/%m/%Y").date()
                obs.append((d.isoformat(), v))
    return obs, f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados?formato=json"


OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"


def _olinda(recurso: str, filtro: str) -> list[dict]:
    url = (f"{OLINDA}/{recurso}?$top=100000&$format=json&$select=Data,Mediana"
           f"&$filter={_q(filtro)}&$orderby=Data")
    return http_json(url, timeout=120)["value"]


def bcb_focus_12m(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    filtro = (f"Indicador eq '{fonte['indicador']}' and Suavizada eq 'S' and baseCalculo eq 0 "
              f"and Data ge '{desde}' and Data le '{ate}'")
    obs = {i["Data"]: float(i["Mediana"]) for i in _olinda("ExpectativasMercadoInflacao12Meses", filtro)}
    return sorted(obs.items()), f"{OLINDA}/ExpectativasMercadoInflacao12Meses"


def bcb_focus_anual(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    """Mediana do Focus para o ano corrente de cada data (o ano de referência muda em janeiro).

    Com `anos_a_frente: N`, o ano de referência é o ano da data + N (1 = ano seguinte).
    """
    obs: dict[str, float] = {}
    n = int(fonte.get("anos_a_frente", 0))
    for ano in range(desde.year, ate.year + 1):
        ini = max(desde, dt.date(ano, 1, 1))
        fim = min(ate, dt.date(ano, 12, 31))
        filtro = (f"Indicador eq '{fonte['indicador']}' and DataReferencia eq '{ano + n}' "
                  f"and baseCalculo eq 0 and Data ge '{ini}' and Data le '{fim}'")
        for i in _olinda("ExpectativasMercadoAnuais", filtro):
            if i.get("Mediana") is not None:
                obs[i["Data"]] = float(i["Mediana"])
    return sorted(obs.items()), f"{OLINDA}/ExpectativasMercadoAnuais"


# ---------------------------------------------------------------- EUA

_CACHE_TREASURY: dict[int, list[dict]] = {}


def _treasury_ano(ano: int) -> list[dict]:
    if ano not in _CACHE_TREASURY:
        url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
               f"daily-treasury-rates.csv/{ano}/all?type=daily_treasury_yield_curve"
               f"&field_tdr_date_value={ano}&page&_format=csv")
        texto = http_get(url).decode("utf-8-sig")
        _CACHE_TREASURY[ano] = list(csv.DictReader(io.StringIO(texto)))
    return _CACHE_TREASURY[ano]


def us_treasury(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    obs: Obs = []
    for ano in range(desde.year, ate.year + 1):
        for linha in _treasury_ano(ano):
            d = dt.datetime.strptime(linha["Date"], "%m/%d/%Y").date()
            v = _num(linha.get(fonte["coluna"]))
            if desde <= d <= ate and v is not None:
                obs.append((d.isoformat(), v))
    return obs, ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                 "TextView?type=daily_treasury_yield_curve")


def fred(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    chave = os.environ["FRED_API_KEY"]
    url = ("https://api.stlouisfed.org/fred/series/observations?file_type=json"
           f"&series_id={fonte['serie']}&observation_start={desde}&observation_end={ate}"
           f"&api_key={chave}")
    dados = http_json(url)
    obs = [(o["date"], _num(o["value"])) for o in dados["observations"]]
    return [(d, v) for d, v in obs if v is not None], f"https://fred.stlouisfed.org/series/{fonte['serie']}"


def bls(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    serie = fonte["serie"]
    corpo = {"seriesid": [serie], "startyear": str(desde.year), "endyear": str(ate.year),
             "registrationkey": os.environ["BLS_API_KEY"]}
    if fonte.get("calculo") == "variacao_12m":
        corpo["calculations"] = True
    obs: Obs = []
    # a API aceita até 20 anos por consulta com chave
    resp = json.loads(http_get("https://api.bls.gov/publicAPI/v2/timeseries/data/",
                               headers={"Content-Type": "application/json"},
                               data=json.dumps(corpo).encode()).decode())
    if resp.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS respondeu {resp.get('status')}")
    for item in resp["Results"]["series"][0]["data"]:
        if not item["period"].startswith("M") or item["period"] == "M13":
            continue
        if fonte.get("calculo") == "variacao_12m":
            v = _num(item.get("calculations", {}).get("pct_changes", {}).get("12"))
        else:
            v = _num(item["value"])
        if v is not None:
            obs.append((f"{item['year']}-{item['period'][1:]}-01", v))
    return sorted(obs), f"https://data.bls.gov/timeseries/{serie}"


# ---------------------------------------------------------------- Europa

def ecb(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    url = (f"https://data-api.ecb.europa.eu/service/data/{fonte['chave']}"
           f"?startPeriod={desde}&endPeriod={ate}&format=csvdata")
    texto = http_get(url, timeout=120).decode("utf-8")
    obs = [(l["TIME_PERIOD"], _num(l["OBS_VALUE"])) for l in csv.DictReader(io.StringIO(texto))]
    conjunto, serie = fonte["chave"].split("/", 1)
    return ([(d, v) for d, v in obs if v is not None],
            f"https://data.ecb.europa.eu/data/datasets/{conjunto}/{conjunto}.{serie}")


def eurostat(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    filtros = "&".join(f"{k}={v}" for k, v in fonte["filtros"].items())
    url = (f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{fonte['conjunto']}"
           f"?{filtros}&sinceTimePeriod={desde:%Y-%m}")
    dados = http_json(url, timeout=120)
    tempo = dados["dimension"]["time"]["category"]["index"]  # {"2016-01": 0, ...}
    pos_para_periodo = {i: p for p, i in tempo.items()}
    obs: Obs = []
    for pos, v in dados["value"].items():
        periodo = pos_para_periodo[int(pos)]
        data = dt.date.fromisoformat(f"{periodo}-01")
        if data <= ate and v is not None:
            obs.append((data.isoformat(), float(v)))
    return sorted(obs), url


# ---------------------------------------------------------------- América Latina

def bcra_cambio(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    obs: Obs = []
    base = f"https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/{fonte['moeda']}"
    for ini, fim in _blocos(desde, ate, 1):
        dados = http_json(f"{base}?fechadesde={ini}&fechahasta={fim}&limit=1000")
        for dia in dados.get("results", []):
            for det in dia.get("detalle", []):
                v = _num(det.get("tipoCotizacion"))
                if det.get("codigoMoneda") == fonte["moeda"] and v:
                    obs.append((dia["fecha"], v))
    return sorted(set(obs)), base


def bcra_monetaria(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    obs: Obs = []
    base = f"https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/{fonte['id_variavel']}"
    for ini, fim in _blocos(desde, ate, 2):
        dados = http_json(f"{base}?desde={ini}&hasta={fim}&limit=3000")
        for serie in dados.get("results", []):
            for item in serie.get("detalle", []):
                v = _num(item.get("valor"))
                if v is not None:
                    obs.append((item["fecha"], v))
    return sorted(set(obs)), base


def datos_gob_ar(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    url = (f"https://apis.datos.gob.ar/series/api/series/?ids={fonte['serie']}"
           f"&start_date={desde}&end_date={ate}&format=json&limit=5000")
    if fonte.get("modo"):
        url += f"&representation_mode={fonte['modo']}"
    dados = http_json(url)
    fator = 100.0 if fonte.get("modo") == "percent_change" else 1.0
    obs = [(d, v * fator) for d, v in dados["data"] if v is not None]
    return obs, url


def banxico(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    url = (f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{fonte['serie']}"
           f"/datos/{desde}/{ate}")
    dados = http_json(url, headers={"Bmx-Token": os.environ["BANXICO_TOKEN"]})
    obs: Obs = []
    for item in dados["bmx"]["series"][0].get("datos", []):
        v = _num(item.get("dato"))
        if v is not None:
            d = dt.datetime.strptime(item["fecha"], "%d/%m/%Y").date()
            obs.append((d.isoformat(), v))
    return obs, url


def bcentral_cl(fonte: dict, desde: dt.date, ate: dt.date) -> tuple[Obs, str]:
    publica = ("https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx?function=GetSeries"
               f"&timeseries={fonte['serie']}&firstdate={desde}&lastdate={ate}")
    credenciais = urllib.parse.urlencode({"user": os.environ["BCENTRAL_USER"],
                                          "pass": os.environ["BCENTRAL_PASS"]})
    dados = http_json(f"{publica}&{credenciais}")
    obs: Obs = []
    for item in (dados.get("Series") or {}).get("Obs") or []:
        v = _num(item.get("value"))
        if v is not None and item.get("statusCode", "OK") == "OK":
            d = dt.datetime.strptime(item["indexDateString"], "%d-%m-%Y").date()
            obs.append((d.isoformat(), v))
    return obs, publica


COLETORES = {
    "bcb_sgs": bcb_sgs,
    "bcb_focus_12m": bcb_focus_12m,
    "bcb_focus_anual": bcb_focus_anual,
    "us_treasury": us_treasury,
    "fred": fred,
    "bls": bls,
    "ecb": ecb,
    "eurostat": eurostat,
    "bcra_cambio": bcra_cambio,
    "bcra_monetaria": bcra_monetaria,
    "datos_gob_ar": datos_gob_ar,
    "banxico": banxico,
    "bcentral_cl": bcentral_cl,
}
