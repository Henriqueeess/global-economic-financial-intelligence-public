"""Gráficos em SVG puro (sem dependências), legíveis no tema claro e no escuro.

O GitHub exibe SVG como imagem; a media query prefers-color-scheme dentro do
próprio arquivo troca as cores no tema escuro. Paleta categórica fixa:
azul (hoje / série principal), laranja (7 dias atrás), verde-água (30 dias atrás).
"""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

ESTILO = """<style>
  .s1{stroke:#2a78d6}.s2{stroke:#eb6834}.s3{stroke:#1baf7a}
  .f1{fill:#2a78d6}.f2{fill:#eb6834}.f3{fill:#1baf7a}
  .ponto{stroke:#fcfcfb;stroke-width:2}
  .grade{stroke:#e1e0d9;stroke-width:1}.eixo{stroke:#c3c2b7;stroke-width:1}
  text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#6f6d66;font-size:11px}
  .rotulo{fill:#2b2a27;font-size:11px;font-weight:600}
  @media (prefers-color-scheme: dark){
    .s1{stroke:#3987e5}.s2{stroke:#d95926}.s3{stroke:#199e70}
    .f1{fill:#3987e5}.f2{fill:#d95926}.f3{fill:#199e70}
    .ponto{stroke:#1a1a19}
    .grade{stroke:#2c2c2a}.eixo{stroke:#383835}
    text{fill:#a3a19a}.rotulo{fill:#e8e6df}
  }
</style>"""


def _esc(t: str) -> str:
    return escape(str(t))


def passos_bonitos(minimo: float, maximo: float, alvo: int = 4) -> list[float]:
    """Marcas de eixo "redondas" (1, 2, 2,5 ou 5 × 10^n) cobrindo o intervalo."""
    if maximo == minimo:
        delta = abs(maximo) * 0.05 or 1.0
        minimo, maximo = minimo - delta, maximo + delta
    bruto = (maximo - minimo) / alvo
    mag = 10 ** math.floor(math.log10(bruto))
    passo = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= bruto)
    inicio = math.floor(minimo / passo) * passo
    marcas = []
    v = inicio
    while v <= maximo + passo * 1e-9:
        marcas.append(round(v, 10))
        v += passo
    if marcas[-1] < maximo:
        marcas.append(round(marcas[-1] + passo, 10))
    return marcas


def casas_decimais(passo: float) -> int:
    """Casas decimais suficientes para mostrar as marcas de um eixo com este passo."""
    for casas in range(0, 4):
        if abs(round(passo, casas) - passo) < 1e-9:
            return casas
    return 4


def minigrafico(pontos: list[tuple[float, float]], largura: int = 120, altura: int = 28) -> str:
    """Sparkline: uma linha de 1,5 px e um ponto no último valor."""
    if len(pontos) < 2:
        return ""
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if y1 == y0:
        y0, y1 = y0 - 1, y1 + 1
    m = 4

    def px(x):
        return m + (x - x0) / ((x1 - x0) or 1) * (largura - 2 * m)

    def py(y):
        return altura - m - (y - y0) / (y1 - y0) * (altura - 2 * m)

    caminho = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in pontos)
    ux, uy = px(xs[-1]), py(ys[-1])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
            f'viewBox="0 0 {largura} {altura}" role="img">{ESTILO}'
            f'<polyline points="{caminho}" fill="none" class="s1" stroke-width="1.5" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{ux:.1f}" cy="{uy:.1f}" r="3" class="f1 ponto"/></svg>')


def grafico_linhas(series: list[tuple[str, list[tuple[float, float]]]], titulo_acessivel: str,
                   fmt_x, fmt_y, marcas_x: list[float] | None = None,
                   largura: int = 640, altura: int = 260, marcadores: bool = False,
                   fmt_marca_y=None) -> str:
    """Gráfico de linhas com eixo único, grade discreta, legenda e rótulo no fim de cada linha.

    `series` = [(rótulo, [(x, y), ...]), ...] na ordem da paleta (máximo 3).
    """
    series = [(r, sorted(p)) for r, p in series if p][:3]
    if not series:
        return ""
    todos = [p for _, ps in series for p in ps]
    xs = [p[0] for p in todos]
    ys = [p[1] for p in todos]
    marcas_y = passos_bonitos(min(ys), max(ys))
    y0, y1 = marcas_y[0], marcas_y[-1]
    passo_y = marcas_y[1] - marcas_y[0] if len(marcas_y) > 1 else 1
    casas = casas_decimais(passo_y)
    x0, x1 = min(xs), max(xs)
    if marcas_x is None:
        marcas_x = passos_bonitos(x0, x1, 7)
        marcas_x = [m for m in marcas_x if x0 <= m <= x1] or [x0, x1]
    esq, dir_, topo, base = 52, 92, 34, 28
    lp, ap = largura - esq - dir_, altura - topo - base

    def px(x):
        return esq + (x - x0) / ((x1 - x0) or 1) * lp

    def py(y):
        return topo + ap - (y - y0) / ((y1 - y0) or 1) * ap

    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
              f'viewBox="0 0 {largura} {altura}" role="img" aria-label="{_esc(titulo_acessivel)}">',
              ESTILO, f"<title>{_esc(titulo_acessivel)}</title>"]
    for m in marcas_y:
        y = py(m)
        partes.append(f'<line x1="{esq}" x2="{esq + lp}" y1="{y:.1f}" y2="{y:.1f}" class="grade"/>')
        rotulo = fmt_marca_y(m, casas) if fmt_marca_y else fmt_y(m)
        partes.append(f'<text x="{esq - 8}" y="{y + 4:.1f}" text-anchor="end">{_esc(rotulo)}</text>')
    partes.append(f'<line x1="{esq}" x2="{esq + lp}" y1="{topo + ap}" y2="{topo + ap}" class="eixo"/>')
    for m in marcas_x:
        x = px(m)
        partes.append(f'<text x="{x:.1f}" y="{topo + ap + 18}" text-anchor="middle">{_esc(fmt_x(m))}</text>')
    # legenda em uma linha, acima do gráfico
    lx = esq
    for i, (rotulo, _) in enumerate(series, start=1):
        partes.append(f'<line x1="{lx}" x2="{lx + 16}" y1="14" y2="14" class="s{i}" stroke-width="2"/>')
        partes.append(f'<text x="{lx + 22}" y="18">{_esc(rotulo)}</text>')
        lx += 30 + 7 * len(rotulo)
    # linhas: a principal (s1) por último, para ficar por cima
    rotulos_fim = []
    for i, (rotulo, pts) in reversed(list(enumerate(series, start=1))):
        caminho = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in pts)
        partes.append(f'<polyline points="{caminho}" fill="none" class="s{i}" stroke-width="2" '
                      f'stroke-linejoin="round" stroke-linecap="round"/>')
        if marcadores:
            for x, y in pts:
                partes.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3.5" class="f{i} ponto"/>')
        ux, uy = pts[-1]
        rotulos_fim.append([py(uy), f"{fmt_y(uy)}", i, px(ux)])
    # rótulos no fim das linhas, afastados para não colidir
    rotulos_fim.sort()
    for j in range(1, len(rotulos_fim)):
        if rotulos_fim[j][0] - rotulos_fim[j - 1][0] < 13:
            rotulos_fim[j][0] = rotulos_fim[j - 1][0] + 13
    for y, texto, i, x in rotulos_fim:
        partes.append(f'<text x="{x + 8:.1f}" y="{y + 4:.1f}" class="rotulo">{_esc(texto)}</text>')
    partes.append("</svg>")
    return "".join(partes)
