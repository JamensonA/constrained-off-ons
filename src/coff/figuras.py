"""Figuras (matplotlib, estilo unico): 1600x900 px, fundo branco, textos em portugues,
rodape com fonte dos dados e data de download. Uma funcao por figura; cada uma recebe
a tabela pronta de ``metricas`` e o caminho de saida.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from coff.categorias import ORDEM_CATEGORIAS  # noqa: E402

TAMANHO = (16, 9)
DPI = 100
CORES_FONTE = {"EOL": "#1f77b4", "UFV": "#ff9f1c"}
CORES_CATEGORIA = {
    "energetica": "#ff9f1c",
    "confiabilidade": "#1f77b4",
    "eletrica": "#2ca02c",
    "parecer de acesso": "#9467bd",
}
NOMES_CATEGORIA = {
    "energetica": "energética (ENE)",
    "confiabilidade": "confiabilidade (CNF)",
    "eletrica": "elétrica (REL)",
    "parecer de acesso": "parecer de acesso (PAR)",
}


def _rodape(fig: plt.Figure, rodape: str) -> None:
    fig.text(0.01, 0.01, rodape, fontsize=9, color="#555555", ha="left", va="bottom")


def _figura():
    fig, ax = plt.subplots(figsize=TAMANHO, dpi=DPI, facecolor="white")
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig, ax


def _salvar(fig: plt.Figure, caminho: Path) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(caminho, dpi=DPI, facecolor="white")
    plt.close(fig)
    return caminho


def _gwh(mwh: pd.Series | pd.DataFrame):
    return mwh / 1000


def fig1_eng_mensal(tab: pd.DataFrame, caminho: Path, rodape: str) -> Path:
    """Barras empilhadas por fonte, ENG mensal em GWh."""
    fig, ax = _figura()
    base = pd.Series(0.0, index=tab.index)
    x = range(len(tab.index))
    for fonte in tab.columns:
        valores = _gwh(tab[fonte])
        ax.bar(
            x, valores, bottom=base, color=CORES_FONTE.get(fonte, "#777"), label=fonte, width=0.8
        )
        base = base + valores
    ax.set_xticks(list(x))
    ax.set_xticklabels(tab.index, rotation=90, fontsize=8)
    ax.set_ylabel("Energia não gerada (GWh)")
    ax.set_xlabel("Mês")
    ax.set_title("Energia não gerada por constrained-off, por mês e fonte")
    ax.legend(title="Fonte", frameon=False)
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    _rodape(fig, rodape)
    return _salvar(fig, caminho)


def fig2_eng_por_categoria(tab_longa: pd.DataFrame, caminho: Path, rodape: str) -> Path:
    """Barras empilhadas por categoria de restricao (soma das fontes), ENG mensal em GWh."""
    pivot = (
        tab_longa.groupby(["mes", "categoria"], observed=True)["eng_mwh"]
        .sum()
        .unstack("categoria")
        .fillna(0.0)
    )
    colunas = [c for c in ORDEM_CATEGORIAS if c in pivot.columns] + [
        c for c in pivot.columns if c not in ORDEM_CATEGORIAS
    ]
    pivot = pivot[colunas]
    fig, ax = _figura()
    base = pd.Series(0.0, index=pivot.index)
    x = range(len(pivot.index))
    for cat in pivot.columns:
        valores = _gwh(pivot[cat])
        ax.bar(
            x,
            valores,
            bottom=base,
            color=CORES_CATEGORIA.get(cat, "#777"),
            label=NOMES_CATEGORIA.get(cat, cat),
            width=0.8,
        )
        base = base + valores
    ax.set_xticks(list(x))
    ax.set_xticklabels(pivot.index, rotation=90, fontsize=8)
    ax.set_ylabel("Energia não gerada (GWh)")
    ax.set_xlabel("Mês")
    ax.set_title("Energia não gerada por categoria da restrição (eólica + fotovoltaica)")
    ax.legend(title="Categoria", frameon=False)
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    _rodape(fig, rodape)
    return _salvar(fig, caminho)


def fig3_top_usinas(tab: pd.DataFrame, caminho: Path, rodape: str) -> Path:
    """Barras horizontais: top N usinas/conjuntos por ENG (GWh) com taxa de corte anotada."""
    tab = tab.iloc[::-1]
    fig, ax = _figura()
    cores = [CORES_FONTE.get(f, "#777") for f in tab["fonte"]]
    rotulos = [f"{n} ({f})" for n, f in zip(tab["nom_usina"], tab["fonte"], strict=True)]
    valores = _gwh(tab["eng_mwh"])
    posicoes = list(range(len(tab)))
    ax.barh(posicoes, valores, color=cores)
    ax.set_yticks(posicoes)
    ax.set_yticklabels(rotulos)
    maximo = float(valores.max()) if len(valores) else 1.0
    for i, (v, taxa) in enumerate(zip(valores, tab["taxa_corte"], strict=True)):
        ax.text(
            v + maximo * 0.01,
            i,
            f"{v:,.0f} GWh · taxa de corte {taxa:.1%}",
            va="center",
            fontsize=9,
        )
    ax.set_xlim(0, maximo * 1.3)
    ax.set_xlabel("Energia não gerada acumulada (GWh)")
    ax.set_title(f"{len(tab)} usinas/conjuntos com maior energia não gerada")
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="x", linestyle=":", alpha=0.6)
    _rodape(fig, rodape + "  ·  taxa de corte = ENG ÷ (ENG + energia gerada)")
    return _salvar(fig, caminho)


def fig4_perfil_hora_mes(perfil: pd.DataFrame, caminho: Path, rodape: str) -> Path:
    """Mapa de calor hora do dia x mes, ENG media por dia (MWh)."""
    fig, ax = _figura()
    im = ax.imshow(perfil.values, aspect="auto", origin="lower", cmap="YlOrRd")
    ax.set_yticks(range(0, 24, 2))
    ax.set_yticklabels([f"{h:02d}h" for h in range(0, 24, 2)])
    ax.set_xticks(range(len(perfil.columns)))
    ax.set_xticklabels(perfil.columns, rotation=90, fontsize=8)
    ax.set_xlabel("Mês")
    ax.set_ylabel("Hora do dia")
    ax.set_title("Perfil da energia não gerada: hora do dia × mês (MWh médios por dia)")
    barra = fig.colorbar(im, ax=ax, pad=0.01)
    barra.set_label("MWh por dia, no intervalo horário")
    _rodape(fig, rodape)
    return _salvar(fig, caminho)


def fig5_top_descricoes(tab: pd.DataFrame, caminho: Path, rodape: str, n: int = 15) -> Path:
    """Barras horizontais das N maiores descricoes de restricao por ENG (GWh)."""
    tab = tab.head(n).iloc[::-1]
    fig, ax = _figura()
    cores = [CORES_CATEGORIA.get(c, "#777") for c in tab["categoria"]]
    rotulos = [
        (d if len(d) <= 70 else d[:67] + "…") + f"  [{o}]"
        for d, o in zip(tab["dsc_restricao"], tab["origem"], strict=True)
    ]
    valores = _gwh(tab["eng_mwh"])
    posicoes = list(range(len(tab)))
    ax.barh(posicoes, valores, color=cores)
    ax.set_yticks(posicoes)
    ax.set_yticklabels(rotulos)
    ax.set_xlabel("Energia não gerada (GWh)")
    ax.set_title(f"{len(tab)} descrições de restrição com maior energia não gerada (desde 2025-01)")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="x", linestyle=":", alpha=0.6)
    legendas = [plt.Rectangle((0, 0), 1, 1, color=CORES_CATEGORIA[c]) for c in ORDEM_CATEGORIAS]
    ax.legend(
        legendas,
        [NOMES_CATEGORIA[c] for c in ORDEM_CATEGORIAS],
        title="Categoria",
        frameon=False,
        loc="lower right",
    )
    _rodape(fig, rodape + "  ·  [LOC] origem local, [SIS] sistêmica")
    return _salvar(fig, caminho)
