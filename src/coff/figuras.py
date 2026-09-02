"""Figuras (matplotlib, estilo unico): 1600x900 px, fundo branco, textos em portugues,
rodape com fonte dos dados e data de download. Uma funcao por figura; cada uma recebe
a tabela pronta de ``metricas`` e o caminho de saida.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from coff.categorias import (  # noqa: E402
    ORDEM_CATEGORIAS,
    ROTULOS_CATEGORIA,
    ROTULOS_ORIGEM,
)

TAMANHO = (16, 9)
DPI = 100
CORES_FONTE = {"EOL": "#1f77b4", "UFV": "#ff9f1c"}
CORES_CATEGORIA = {
    "energetica": "#ff9f1c",
    "confiabilidade": "#1f77b4",
    "eletrica": "#2ca02c",
    "parecer de acesso": "#9467bd",
}
_CODIGO_DA_CATEGORIA = {
    "energetica": "ENE",
    "confiabilidade": "CNF",
    "eletrica": "REL",
    "parecer de acesso": "PAR",
}
NOMES_CATEGORIA = {
    cat: f"{ROTULOS_CATEGORIA[cat]} ({cod})" for cat, cod in _CODIGO_DA_CATEGORIA.items()
}

_SIGLAS = {
    "SIN",
    "ONS",
    "LT",
    "LTS",
    "SE",
    "TR",
    "SGI",
    "FNS",
    "FNESE",
    "FJUSC",
    "UFV",
    "EOL",
    "UHE",
    "UTE",
    "BESS",
    "II",
    "III",
    "IV",
    "VI",
    "VII",
    "VIII",
    "IX",
    "XI",
    "XII",
    "PCH",
    "CGH",
    "SECO",
    "NE",
    "N",
    "S",
    "CE",
    "BA",
    "RN",
    "PI",
    "PE",
    "PB",
    "MG",
    "SP",
    "GO",
    "MS",
    "PR",
    "RS",
    "SC",
    "MA",
    "PA",
    "RJ",
    "AL",
    "TO",
    "MT",
    "DF",
    "ES",
    "AM",
    "AP",
    "RO",
    "RR",
}
_MINUSCULAS = {
    "de",
    "da",
    "do",
    "das",
    "dos",
    "e",
    "em",
    "na",
    "no",
    "nas",
    "nos",
    "com",
    "por",
    "a",
    "o",
}


def _capitalizar_nome(texto: str) -> str:
    """Nome de exibicao: tokens em caixa alta viram 'Inicial Maiuscula'; o resto fica.

    Apenas apresentacao. Siglas (lista, ou caixa alta sem vogal), numeros e tokens ja em
    caixa mista nao mudam. Ex.: 'CONJ. RIO DO VENTO' -> 'Conj. Rio do Vento'; 'KV' -> 'kV'.
    """
    saida = []
    for i, token in enumerate(str(texto).split(" ")):
        nucleo = token.strip(".,;:()[]/-–")
        if not nucleo or not nucleo.isupper():
            saida.append(token)  # vazio, numero ou ja em caixa mista/minuscula
            continue
        letras = "".join(ch for ch in nucleo if ch.isalpha())
        partes = [q for q in re.split(r"[^A-Za-zÀ-ÿ]+", nucleo) if q]
        if partes and all(q in _SIGLAS for q in partes):
            saida.append(token)
            continue
        if nucleo.upper() == "KV" or (nucleo.endswith("KV") and nucleo[:-2].isdigit()):
            saida.append(token.replace("KV", "kV"))
        elif (
            letras in _SIGLAS
            or not any(v in letras for v in "AEIOUÁÉÍÓÚÂÊÔÃÕ")
            or any(ch.isdigit() for ch in nucleo)
            or "." in nucleo[:-1]
        ):
            saida.append(token)
        elif letras.lower() in _MINUSCULAS and i > 0:
            saida.append(token.lower())
        else:
            saida.append(token[:1].upper() + token[1:].lower())
    return " ".join(saida)


def _capitalizar_descricao(texto: str) -> str:
    """Descricao de restricao: mantem o prefixo ('Controle de inequação: ') e trata o resto."""
    if ": " in texto:
        prefixo, resto = texto.split(": ", 1)
        return f"{prefixo[:1].upper()}{prefixo[1:]}: {_capitalizar_nome(resto)}"
    return _capitalizar_nome(texto)


def _rodape(fig: plt.Figure, rodape: str) -> None:
    fig.text(0.01, 0.01, rodape, fontsize=9, color="#555555", ha="left", va="bottom")


def _figura():
    fig, ax = plt.subplots(figsize=TAMANHO, dpi=DPI, facecolor="white")
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig, ax


def _salvar(fig: plt.Figure, caminho: Path, margem_inferior: float = 0.03) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, margem_inferior, 1, 1))
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
    rotulos = [
        f"{_capitalizar_nome(n)} ({f})" for n, f in zip(tab["nom_usina"], tab["fonte"], strict=True)
    ]
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
            f"{v:,.0f} GWh · Taxa de corte {taxa:.1%}",
            va="center",
            fontsize=9,
        )
    ax.set_xlim(0, maximo * 1.3)
    ax.set_xlabel("Energia não gerada acumulada (GWh)")
    ax.set_title(f"As {len(tab)} usinas/conjuntos com maior energia não gerada")
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="x", linestyle=":", alpha=0.6)
    _rodape(fig, rodape + "  ·  Taxa de corte = ENG ÷ (ENG + energia gerada)")
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
    """Barras horizontais das N maiores descricoes de restricao por ENG (GWh).

    A linha "(sem descricao)" (campo vazio de 2025_01 a 2025_08) fica fora da figura e
    permanece apenas na tabela ``top_descricoes.csv``.
    """
    tab = tab[tab["dsc_restricao"] != "(sem descricao)"].head(n).iloc[::-1]
    fig, ax = _figura()
    cores = [CORES_CATEGORIA.get(c, "#777") for c in tab["categoria"]]
    rotulos = []
    for d, o in zip(tab["dsc_restricao"], tab["origem"], strict=True):
        d = _capitalizar_descricao(str(d))
        rotulos.append((d if len(d) <= 70 else d[:67] + "…") + f"  [{ROTULOS_ORIGEM.get(o, o)}]")
    valores = _gwh(tab["eng_mwh"])
    posicoes = list(range(len(tab)))
    ax.barh(posicoes, valores, color=cores)
    ax.set_yticks(posicoes)
    ax.set_yticklabels(rotulos)
    ax.set_xlabel("Energia não gerada (GWh)")
    ax.set_title(
        f"As {len(tab)} descrições de restrição com maior energia não gerada "
        "(campo preenchido pelo ONS desde 2025-09)"
    )
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
    _rodape(fig, rodape + "  ·  [Local] origem local, [Sistêmica] origem sistêmica")
    return _salvar(fig, caminho)


# --- figuras 6 e 7: estilo "storytelling com dados" (titulo = mensagem, cor com intencao)
CINZA_TITULO = "#222222"
CINZA_SUBTITULO = "#6f6f6f"
CINZA_EIXO = "#7a7a7a"
CINZA_RODAPE = "#9a9a9a"
CINZA_GRADE = "#e6e6e6"
COR_DESTAQUE = "#c8641e"  # laranja-escuro
TONS_CATEGORIA = {"energetica": "#4a4a4a", "confiabilidade": "#8a8a8a", "eletrica": "#bdbdbd"}
NOMES_CURTOS = {c: ROTULOS_CATEGORIA[c] for c in ("energetica", "confiabilidade", "eletrica")}
TONS_TEMPORADA = {
    "inab_mw": (COR_DESTAQUE, "Inabilitado"),
    "ad_mw": ("#9e9e9e", "Atendimento direto"),
    "pc_mw": ("#7a7a7a", "Processo competitivo"),
    "advc_mw": ("#cfcfcf", "Condicionado"),
}


def _limpar(ax, grade: bool = True) -> None:
    """Desordem zero: sem spines superior/direita, sem tick marks, grade horizontal leve."""
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(CINZA_EIXO)
    ax.tick_params(length=0, colors=CINZA_EIXO, labelsize=10)
    ax.yaxis.label.set_color(CINZA_EIXO)
    ax.xaxis.label.set_color(CINZA_EIXO)
    if grade:
        ax.grid(axis="y", color=CINZA_GRADE, linewidth=0.8)
        ax.set_axisbelow(True)
    ax.grid(axis="x", visible=False)


def _titulo(fig, titulo: str, subtitulo: str) -> None:
    fig.text(0.04, 0.965, titulo, fontsize=16, fontweight="bold", color=CINZA_TITULO, ha="left")
    fig.text(0.04, 0.935, subtitulo, fontsize=11.5, color=CINZA_SUBTITULO, ha="left")


def _rodape_fontes(fig, fontes: list[str]) -> None:
    fig.text(0.04, 0.012, "\n".join(fontes), fontsize=9, color=CINZA_RODAPE, ha="left", va="bottom")


def _rotular_empilhamento(ax, x, tab, colunas, cores, nomes, minimo_rel=0.12) -> None:
    """Rotula cada serie no maior segmento: dentro (rotacionado) se couber, senao fora."""
    maximo = float(tab[colunas].fillna(0.0).sum(axis=1).max()) or 1.0
    bases = pd.DataFrame(0.0, index=tab.index, columns=colunas)
    acumulado = pd.Series(0.0, index=tab.index)
    for col in colunas:
        bases[col] = acumulado
        acumulado = acumulado + tab[col].fillna(0.0)
    ax.set_ylim(0, maximo * 1.08)
    px_por_unidade = (ax.transData.transform((0, 1)) - ax.transData.transform((0, 0)))[1]
    externos_por_barra: dict[int, int] = {}
    for col in colunas:
        serie = tab[col].fillna(0.0)
        if serie.sum() == 0:
            continue
        i = int(serie.idxmax())
        altura = float(serie.iloc[i])
        centro = float(bases[col].iloc[i]) + altura / 2
        cor = cores[col]
        largura_texto_px = len(nomes[col]) * 9.5 * 0.62 * DPI / 72 + 10
        cabe = altura >= minimo_rel * maximo and altura * px_por_unidade >= largura_texto_px
        if cabe:
            texto_cor = (
                "white" if cor in (COR_DESTAQUE, "#4a4a4a", "#7a7a7a", "#8a8a8a") else "#333333"
            )
            ax.text(
                x[i],
                centro,
                nomes[col],
                ha="center",
                va="center",
                fontsize=9.5,
                color=texto_cor,
                rotation=90,
            )
        else:
            n_ext = externos_por_barra.get(i, 0)
            externos_por_barra[i] = n_ext + 1
            topo = float(acumulado.iloc[i])
            ax.annotate(
                nomes[col],
                (x[i], centro),
                xytext=(x[i] + 0.55, topo + (0.06 + 0.10 * n_ext) * maximo),
                fontsize=9.5,
                color=cor if cor != "#cfcfcf" else "#8a8a8a",
                arrowprops={"arrowstyle": "-", "color": CINZA_EIXO, "lw": 0.8},
            )


def fig6_temporada_x_eng(cruz: pd.DataFrame, caminho: Path, rodape: str) -> Path:
    """Dois painéis por UF: ENG por categoria (GWh, cinzas) e Temporada (MW, INAB em destaque).

    ``rodape``: fontes separadas por ``  |  `` (uma linha por fonte).
    """
    tab = cruz.sort_values("eng_gwh", ascending=False).reset_index(drop=True)
    ufs = list(tab["uf"])
    x = list(range(len(ufs)))
    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=TAMANHO,
        dpi=DPI,
        facecolor="white",
        sharex=True,
        gridspec_kw={"hspace": 0.10},
    )
    for ax in (ax1, ax2):
        ax.set_facecolor("white")
        _limpar(ax)
    cols_cat = [f"eng_{c}_gwh" for c in TONS_CATEGORIA if f"eng_{c}_gwh" in tab.columns]
    cores_cat = {f"eng_{c}_gwh": TONS_CATEGORIA[c] for c in TONS_CATEGORIA}
    nomes_cat = {f"eng_{c}_gwh": NOMES_CURTOS[c] for c in TONS_CATEGORIA}
    base = pd.Series(0.0, index=tab.index)
    for col in cols_cat:
        ax1.bar(x, tab[col].fillna(0.0), bottom=base, color=cores_cat[col], width=0.78)
        base = base + tab[col].fillna(0.0)
    _rotular_empilhamento(ax1, x, tab, cols_cat, cores_cat, nomes_cat)
    ax1.set_ylabel("Energia não gerada (GWh)")

    cols_temp = list(TONS_TEMPORADA)
    cores_temp = {c: TONS_TEMPORADA[c][0] for c in cols_temp}
    nomes_temp = {c: TONS_TEMPORADA[c][1] for c in cols_temp}
    base = pd.Series(0.0, index=tab.index)
    for col in cols_temp:
        ax2.bar(x, tab[col].fillna(0.0), bottom=base, color=cores_temp[col], width=0.78)
        base = base + tab[col].fillna(0.0)
    _rotular_empilhamento(ax2, x, tab, cols_temp, cores_temp, nomes_temp)
    sem_cadastro = tab[(tab["cadastrado_mw"].fillna(0) == 0) & (tab["eng_gwh"] >= 500)]
    maximo_mw = float(tab[cols_temp].fillna(0.0).sum(axis=1).max()) or 1.0
    for i_uf, _r in sem_cadastro.iterrows():
        ax2.annotate(
            "Nenhum MW cadastrado",
            (i_uf, 0),
            xytext=(i_uf + 0.1, 0.27 * maximo_mw),
            textcoords="data",
            ha="left",
            fontsize=9.5,
            color=CINZA_SUBTITULO,
            arrowprops={"arrowstyle": "-", "color": CINZA_EIXO, "lw": 0.8, "shrinkB": 2},
        )
    ax2.set_ylabel("Temporada de Acesso 2026 (MW)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(ufs)
    # negrito: UFs no topo dos dois paineis (muita ENG e maioria da potencia inabilitada)
    destaque = set(tab.loc[(tab["frac_inab"].fillna(0) >= 0.5) & (tab["eng_gwh"] >= 500), "uf"])
    for rotulo in ax2.get_xticklabels():
        if rotulo.get_text() in destaque:
            rotulo.set_fontweight("bold")
            rotulo.set_color(CINZA_TITULO)
    _titulo(
        fig,
        "Falta de margem e corte coincidem no mapa, mas não na taxa",
        "Energia não gerada por UF e categoria, 2025-01 → 2026-08 (GWh) · potência cadastrada na "
        "1ª Temporada de Acesso 2026 por resultado (MW); UFs em ordem de energia não gerada",
    )
    _rodape_fontes(fig, rodape.split("  |  "))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.90, bottom=0.11)
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho, dpi=DPI, facecolor="white")
    plt.close(fig)
    return caminho


def _taxa_pct(sub: pd.DataFrame, uf: str) -> float:
    linhas = sub.loc[sub["uf"] == uf, "taxa_corte"]
    return 100 * float(linhas.iloc[0]) if len(linhas) else float("nan")


def fig7_taxa_corte_x_inabilitacao(
    cruz: pd.DataFrame, caminho: Path, rodape: str, spearman: float, n: int
) -> Path:
    """Dispersão taxa de corte (%) × fração inabilitada (%), tamanho = MW cadastrados.

    Pontos em cinza; MG e SP em destaque e anotados; CE (sem cadastro na Temporada) anotado
    na linha de base, fora da amostra do Spearman. Quadrante "Alta margem, alto corte" sombreado.
    """
    sub = cruz.dropna(subset=["frac_inab"]).copy()
    sub = sub[sub["energia_gerada_gwh"] + sub["eng_gwh"] > 0]
    fig, ax = plt.subplots(figsize=TAMANHO, dpi=DPI, facecolor="white")
    ax.set_facecolor("white")
    _limpar(ax, grade=False)
    ax.grid(axis="y", color=CINZA_GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    xs = 100 * sub["taxa_corte"]
    ys = 100 * sub["frac_inab"]
    xmax = max(float(xs.max()) * 1.18, 30.0)
    # quadrante "Alta margem, alto corte": taxa >= 15 % e inabilitacao <= 50 %
    ax.add_patch(plt.Rectangle((15, 0), xmax - 15, 50, color="#f2f2f2", zorder=0))
    ax.text(
        xmax - 0.4,
        47,
        "Alta margem, alto corte",
        ha="right",
        va="top",
        fontsize=10.5,
        color=CINZA_SUBTITULO,
    )
    tamanhos = 60 + 1100 * sub["cadastrado_mw"] / max(float(sub["cadastrado_mw"].max()), 1.0)
    destaques = {"MG", "SP"}
    cores = [COR_DESTAQUE if uf in destaques else "#b5b5b5" for uf in sub["uf"]]
    bordas = [COR_DESTAQUE if uf in destaques else "#8a8a8a" for uf in sub["uf"]]
    ax.scatter(
        xs, ys, s=tamanhos, color=cores, alpha=0.85, edgecolor=bordas, linewidth=0.8, zorder=3
    )
    deslocamento_rotulo = {"PE": (-24, 14), "BA": (12, -10)}
    for _, r in sub.iterrows():
        cor = CINZA_TITULO if r["uf"] in destaques else CINZA_EIXO
        peso = "bold" if r["uf"] in destaques else "normal"
        ax.annotate(
            r["uf"],
            (100 * r["taxa_corte"], 100 * r["frac_inab"]),
            textcoords="offset points",
            xytext=deslocamento_rotulo.get(r["uf"], (9, 7)),
            fontsize=10.5,
            color=cor,
            fontweight=peso,
        )
    notas = {
        "MG": (
            f"{_taxa_pct(sub, 'MG'):.0f}% de corte, 2/3 de margem",
            (-150, 45),
        ),
        "SP": (
            f"{_taxa_pct(sub, 'SP'):.0f}% de corte, margem para tudo",
            (-250, 22),
        ),
    }
    for uf, (texto, desloc) in notas.items():
        if uf not in set(sub["uf"]):
            continue
        r = sub[sub["uf"] == uf].iloc[0]
        ax.annotate(
            texto,
            (100 * r["taxa_corte"], 100 * r["frac_inab"]),
            textcoords="offset points",
            xytext=desloc,
            fontsize=10.5,
            color=COR_DESTAQUE,
            arrowprops={"arrowstyle": "-", "color": COR_DESTAQUE, "lw": 0.9, "shrinkB": 8},
        )
    ce = cruz[(cruz["uf"] == "CE") & cruz["frac_inab"].isna()]
    if not ce.empty:
        r = ce.iloc[0]
        xc = 100 * float(r["taxa_corte"])
        ax.scatter(
            [xc], [0], s=110, marker="x", color="#8a8a8a", linewidth=1.6, zorder=4, clip_on=False
        )
        ax.annotate(
            f"CE: {r['eng_gwh'] / 1000:.1f} TWh cortados, nenhum MW cadastrado".replace(".", ","),
            (xc, 0),
            textcoords="offset points",
            xytext=(-14, 78),
            ha="right",
            arrowprops={"arrowstyle": "-", "color": COR_DESTAQUE, "lw": 0.9, "shrinkB": 6},
            fontsize=10.5,
            color=COR_DESTAQUE,
        )
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, 105)
    ax.set_xlabel("Taxa de corte por UF, 2025-01 → 2026-08 (%)")
    ax.set_ylabel("Potência cadastrada inabilitada por falta de margem (%)")
    _titulo(
        fig,
        f"Ter margem no barramento não reduz o corte (Spearman {spearman:.2f})".replace(".", ","),
        f"Taxa de corte = ENG ÷ (ENG + energia gerada), 2025-01 → 2026-08 · fração inabilitada na "
        f"1ª Temporada de Acesso 2026 · tamanho = MW cadastrados · n = {n} UFs com os dois dados",
    )
    _rodape_fontes(fig, rodape.split("  |  "))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.90, bottom=0.12)
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho, dpi=DPI, facecolor="white")
    plt.close(fig)
    return caminho
