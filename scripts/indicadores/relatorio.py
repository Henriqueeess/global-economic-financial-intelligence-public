"""Leitura do relatório diário em Markdown (as duas edições têm a mesma estrutura numerada).

Usado pelo Panorama Econômico. Só lê: nunca altera relatórios. Todo texto daqui é tratado
como dado e escapado antes de virar HTML (ver `inline_html`).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

ROTULOS = {
    "tipo": ("tipo de fonte", "source type"),
    "link": ("link",),
    "publicacao": ("publicação", "publication"),
    "titulo": ("título original", "original headline"),
}
NAO_CONFIRMADOS = re.compile(r"^itens não confirmados$|^unconfirmed items$", re.I)
EM_ANDAMENTO = re.compile(r"^\[(?:em andamento desde|ongoing since)[^\]]*\]\s*", re.I)
URL_OK = re.compile(r"^https?://[^\s<>\"']+$")


@dataclass
class Item:
    secao: int
    titulo: str
    texto: str = ""
    tipo: str = ""
    link: str = ""
    veiculo: str = ""
    data: str = ""
    em_andamento: bool = False


@dataclass
class Relatorio:
    titulo: str = ""
    subtitulo: str = ""
    incompleto: bool = False
    secoes: dict[int, str] = field(default_factory=dict)      # número -> título
    resumo: list[str] = field(default_factory=list)
    itens: list[Item] = field(default_factory=list)
    tabelas: dict[int, list[list[str]]] = field(default_factory=dict)  # primeira tabela de cada seção
    nao_confirmados: list[str] = field(default_factory=list)
    texto_corrido: str = ""   # todo o texto, para o glossário


def _celulas(linha: str) -> list[str]:
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def _meta(linha: str) -> tuple[str, str] | None:
    m = re.match(r"^\s*-\s+\*\*(.+?):\*\*\s*(.*)$", linha)
    if not m:
        return None
    rotulo = m.group(1).strip().lower()
    for chave, nomes in ROTULOS.items():
        if rotulo in nomes:
            return chave, m.group(2).strip()
    return None


def ler(md: str) -> Relatorio:
    r = Relatorio()
    linhas = md.replace("\r\n", "\n").split("\n")
    r.incompleto = any("INCOMPLETO" in l or "INCOMPLETE" in l for l in linhas[:6])
    secao = 0
    item: Item | None = None
    em_nao_confirmados = False
    tabela_atual: list[list[str]] | None = None
    corpo: list[str] = []

    def fechar_item():
        nonlocal item
        if item is not None and item.link:
            r.itens.append(item)
        item = None

    for linha in linhas:
        s = linha.strip()
        if s.startswith("|"):
            cel = _celulas(s)
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cel):
                continue
            if tabela_atual is None and secao and secao not in r.tabelas and not em_nao_confirmados:
                tabela_atual = []
                r.tabelas[secao] = tabela_atual
            if tabela_atual is not None:
                tabela_atual.append(cel)
            corpo.append(" ".join(cel))
            continue
        tabela_atual = None

        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            nivel, texto = len(m.group(1)), m.group(2).strip()
            if nivel == 1:
                if not texto.upper().startswith("INCOMPLET"):
                    r.titulo = texto
                continue
            if nivel == 2:
                fechar_item()
                em_nao_confirmados = False
                mn = re.match(r"^(\d+)\.\s*(.*)$", texto)
                secao = int(mn.group(1)) if mn else 0
                if mn:
                    r.secoes[secao] = re.sub(r"\s*\*\(.*\)\*\s*$", "", mn.group(2)).strip()
                continue
            fechar_item()
            if NAO_CONFIRMADOS.match(texto):
                em_nao_confirmados = True
                continue
            em_nao_confirmados = False
            if 2 <= secao <= 6:
                andamento = bool(EM_ANDAMENTO.match(texto))
                item = Item(secao=secao, titulo=EM_ANDAMENTO.sub("", texto), em_andamento=andamento)
            continue

        if not s:
            continue
        corpo.append(s)
        if secao == 0:
            if s.startswith("**") and not r.subtitulo:
                r.subtitulo = s
            continue
        if em_nao_confirmados:
            if s.startswith("- "):
                r.nao_confirmados.append(s[2:].strip())
            continue
        if secao == 1 and s.startswith("- "):
            r.resumo.append(s[2:].strip())
            continue
        if item is not None:
            meta = _meta(s)
            if meta:
                chave, valor = meta
                if chave == "tipo":
                    item.tipo = valor
                elif chave == "link":
                    u = valor.split()[0] if valor else ""
                    item.link = u if URL_OK.match(u) else ""
                elif chave == "publicacao":
                    partes = [p.strip() for p in valor.split("·")]
                    item.veiculo = partes[0]
                    item.data = " · ".join(partes[1:])
            elif not s.startswith("-") and not item.texto:
                item.texto = s
    fechar_item()
    r.texto_corrido = "\n".join(corpo)
    return r


# ---------------------------------------------------------------- texto

FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ\"“(])")


def primeiras_frases(texto: str, n: int) -> str:
    """As n primeiras frases. Não corta em números (5,5. / 1.000) porque exige maiúscula depois."""
    partes = FRASE.split(texto.strip())
    return " ".join(partes[:n]).strip()


def sem_marcacao(texto: str) -> str:
    """Tira negrito, itálico e links do Markdown, deixando o texto."""
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1", texto)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", t)
    return t.replace("`", "")


def inline_html(texto: str) -> str:
    """Markdown mínimo e seguro: escapa tudo e só depois aplica **negrito** e *itálico*."""
    t = html.escape(sem_links(texto), quote=True)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", t)
    return t.replace("`", "")


def sem_links(texto: str) -> str:
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1", texto)
