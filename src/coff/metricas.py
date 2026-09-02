"""Metricas: ENG (energia nao gerada) e agregacoes — funcoes puras (spec v2, secao 5).

Todas recebem o DataFrame devolvido por ``qualificar.qualificar`` (colunas
``eng_mwh``, ``energia_gerada_mwh``, ``categoria``, ``origem``, ``qualificado``…)
e devolvem DataFrames pequenos prontos para figuras, CSVs e testes.
"""

from __future__ import annotations

import pandas as pd

from coff.categorias import ORDEM_CATEGORIAS

FONTES: tuple[str, ...] = ("EOL", "UFV")


def _mes(df: pd.DataFrame) -> pd.Series:
    return df["din_instante"].dt.to_period("M").astype(str)


def eng_por_mes(df: pd.DataFrame) -> pd.DataFrame:
    """1. ENG (MWh) por mes x fonte. Indice ``AAAA-MM``; colunas EOL/UFV (0 se ausente)."""
    tab = (
        df.groupby([_mes(df), df["fonte"].astype(str)], observed=True)["eng_mwh"]
        .sum()
        .unstack("fonte")
        .reindex(columns=list(FONTES), fill_value=0.0)
        .fillna(0.0)
        .sort_index()
    )
    tab.index.name = "mes"
    return tab


def eng_por_categoria(df: pd.DataFrame) -> pd.DataFrame:
    """2. ENG (MWh) por mes x categoria x origem, formato longo.

    Colunas: ``mes, categoria, origem, eng_mwh``. Apenas registros qualificados
    (os demais tem ENG 0). Origem desconhecida aparece como ``"desconhecida"``.
    """
    q = df[df["qualificado"]]
    origem = q["origem"].astype("string").fillna("desconhecida")
    tab = (
        q.groupby([_mes(q), q["categoria"].astype(str), origem], observed=True)["eng_mwh"]
        .sum()
        .reset_index()
    )
    tab.columns = ["mes", "categoria", "origem", "eng_mwh"]
    return tab.sort_values(["mes", "categoria", "origem"]).reset_index(drop=True)


def eng_por_subsistema(df: pd.DataFrame) -> pd.DataFrame:
    """3. ENG (MWh) por fonte x subsistema x estado, com energia gerada e taxa de corte."""
    g = df.groupby(
        [df["fonte"].astype(str), df["id_subsistema"].astype(str), df["id_estado"].astype(str)],
        observed=True,
    )
    tab = g.agg(eng_mwh=("eng_mwh", "sum"), energia_gerada_mwh=("energia_gerada_mwh", "sum"))
    tab = tab.reset_index()
    tab.columns = ["fonte", "subsistema", "estado", "eng_mwh", "energia_gerada_mwh"]
    tab["taxa_corte"] = taxa_corte(tab["eng_mwh"], tab["energia_gerada_mwh"])
    return tab.sort_values("eng_mwh", ascending=False).reset_index(drop=True)


def taxa_corte(eng: pd.Series, gerada: pd.Series) -> pd.Series:
    """Taxa de corte = ENG / (ENG + energia gerada); 0 quando o denominador e 0."""
    denominador = eng + gerada
    return (eng / denominador.where(denominador > 0)).fillna(0.0)


def top_usinas(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """4. Ranking por ``id_ons``: ENG acumulada e taxa de corte."""
    g = df.groupby(df["id_ons"].astype(str), observed=True)
    tab = g.agg(
        nom_usina=("nom_usina", "first"),
        fonte=("fonte", "first"),
        subsistema=("id_subsistema", "first"),
        estado=("id_estado", "first"),
        eng_mwh=("eng_mwh", "sum"),
        energia_gerada_mwh=("energia_gerada_mwh", "sum"),
    ).reset_index()
    for c in ("nom_usina", "fonte", "subsistema", "estado"):
        tab[c] = tab[c].astype(str)
    tab["taxa_corte"] = taxa_corte(tab["eng_mwh"], tab["energia_gerada_mwh"])
    return tab.sort_values("eng_mwh", ascending=False).head(n).reset_index(drop=True)


def perfil_hora_mes(df: pd.DataFrame) -> pd.DataFrame:
    """5. Hora do dia x mes: ENG media por dia (MWh), isto e, soma no mes / dias do mes."""
    q = df[df["qualificado"]]
    mes = _mes(q).rename("mes")
    hora = q["din_instante"].dt.hour.rename("hora")
    soma = q.groupby([hora, mes], observed=True)["eng_mwh"].sum().unstack("mes")
    soma = soma.reindex(index=range(24), fill_value=0.0).fillna(0.0)
    dias = pd.PeriodIndex(soma.columns, freq="M").days_in_month
    perfil = soma / dias
    perfil.index.name = "hora"
    perfil.columns.name = "mes"
    return perfil


def top_descricoes(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """6. ``dsc_restricao`` por ENG (MWh), com categoria, origem e nº de registros.

    Descricao vazia (coluna presente mas nao preenchida, 2025_01–2025_08) vira
    ``"(sem descricao)"``; descricao nula (coluna ausente ate 2024_12) fica de fora.
    """
    q = df[df["qualificado"] & df["dsc_restricao"].notna()]
    dsc = q["dsc_restricao"].astype(str).str.strip().replace("", "(sem descricao)")
    g = q.groupby(
        [
            dsc,
            q["categoria"].astype(str),
            q["origem"].astype("string").fillna("desconhecida"),
        ],
        observed=True,
    )
    tab = g.agg(eng_mwh=("eng_mwh", "sum"), registros=("eng_mwh", "size")).reset_index()
    tab.columns = ["dsc_restricao", "categoria", "origem", "eng_mwh", "registros"]
    return tab.sort_values("eng_mwh", ascending=False).head(n).reset_index(drop=True)


def sensibilidade_referencia(df: pd.DataFrame, delta_t_h: float = 0.5) -> pd.DataFrame:
    """7. ENG por fonte x categoria com referencia ``coalesce`` vs ``referencia`` (R6).

    Recalcula as duas variantes a partir das colunas brutas dos registros
    qualificados, independentemente da referencia usada em ``qualificar``.
    """
    q = df[df["qualificado"]]
    ger = q["ger_calc"].astype("float64")
    ref = q["val_geracaoreferencia"].astype("float64")
    coalesce = q["val_geracaoreferenciafinal"].astype("float64").fillna(ref)
    base = pd.DataFrame(
        {
            "fonte": q["fonte"].astype(str),
            "categoria": q["categoria"].astype(str),
            "eng_coalesce_mwh": (coalesce - ger).clip(lower=0) * delta_t_h,
            "eng_referencia_mwh": (ref - ger).clip(lower=0) * delta_t_h,
        }
    )
    tab = base.groupby(["fonte", "categoria"], observed=True).sum().reset_index()
    tab["dif_abs_mwh"] = tab["eng_coalesce_mwh"] - tab["eng_referencia_mwh"]
    tab["dif_rel"] = (
        tab["dif_abs_mwh"] / tab["eng_referencia_mwh"].where(tab["eng_referencia_mwh"] > 0)
    ).fillna(0.0)
    ordem = {c: i for i, c in enumerate(ORDEM_CATEGORIAS)}
    tab["_o"] = tab["categoria"].map(ordem).fillna(99)
    return tab.sort_values(["fonte", "_o"]).drop(columns="_o").reset_index(drop=True)


def ocorrencias_par(df: pd.DataFrame) -> pd.DataFrame:
    """8. Meses em que o codigo PAR aparece, com descricoes (pode ser vazio)."""
    p = df[df["codigo"] == "PAR"]
    if p.empty:
        return pd.DataFrame(columns=["fonte", "mes", "dsc_restricao", "registros", "eng_mwh"])
    g = p.groupby(
        [
            p["fonte"].astype(str),
            _mes(p),
            p["dsc_restricao"].astype("string").fillna("(sem descricao)"),
        ],
        observed=True,
    )
    tab = g.agg(registros=("eng_mwh", "size"), eng_mwh=("eng_mwh", "sum")).reset_index()
    tab.columns = ["fonte", "mes", "dsc_restricao", "registros", "eng_mwh"]
    return tab


def taxa_mensal(df: pd.DataFrame) -> pd.DataFrame:
    """ENG, energia gerada e taxa de corte por mes (EOL + UFV somadas e por fonte).

    Colunas: ``mes, eng_mwh, energia_gerada_mwh, taxa_corte, taxa_corte_EOL, taxa_corte_UFV``.
    A taxa e comparavel ao "% do potencial de geracao" publicado pelo ONS.
    """
    mes = _mes(df)
    total = df.groupby(mes, observed=True).agg(
        eng_mwh=("eng_mwh", "sum"), energia_gerada_mwh=("energia_gerada_mwh", "sum")
    )
    total["taxa_corte"] = taxa_corte(total["eng_mwh"], total["energia_gerada_mwh"])
    por_fonte = df.groupby([mes, df["fonte"].astype(str)], observed=True).agg(
        eng=("eng_mwh", "sum"), ger=("energia_gerada_mwh", "sum")
    )
    for fonte in FONTES:
        if fonte in por_fonte.index.get_level_values(1):
            sub = por_fonte.xs(fonte, level=1)
            total[f"taxa_corte_{fonte}"] = taxa_corte(sub["eng"], sub["ger"]).reindex(total.index)
        else:
            total[f"taxa_corte_{fonte}"] = float("nan")
    total.index.name = "mes"
    return total.reset_index()


def resumo_anual(df: pd.DataFrame) -> pd.DataFrame:
    """Tabela ano x fonte: ENG (GWh), energia gerada (GWh), taxa de corte (%)."""
    g = df.dropna(subset=["ano"]).groupby(
        [df["ano"].astype("Int64"), df["fonte"].astype(str)], observed=True
    )
    tab = g.agg(eng_mwh=("eng_mwh", "sum"), gerada_mwh=("energia_gerada_mwh", "sum")).reset_index()
    tab.columns = ["ano", "fonte", "eng_mwh", "gerada_mwh"]
    saida = pd.DataFrame(
        {
            "ano": tab["ano"].astype(int),
            "fonte": tab["fonte"],
            "eng_gwh": tab["eng_mwh"] / 1000,
            "energia_gerada_gwh": tab["gerada_mwh"] / 1000,
            "taxa_corte_pct": 100 * taxa_corte(tab["eng_mwh"], tab["gerada_mwh"]),
        }
    )
    return saida.sort_values(["ano", "fonte"]).reset_index(drop=True)


def eng_por_uf(df: pd.DataFrame, desde: str = "2025-01") -> pd.DataFrame:
    """ENG por UF e categoria (GWh), energia gerada (GWh) e taxa de corte, desde ``desde``.

    ``desde`` e ``AAAA-MM`` (inclusive). Janela padrao 2025-01 -> ultimo mes, comparavel ao
    cadastro da 1a Temporada de Acesso 2026. Colunas: ``uf, eng_energetica_gwh,
    eng_confiabilidade_gwh, eng_eletrica_gwh, eng_parecer_de_acesso_gwh, eng_gwh,
    energia_gerada_gwh, taxa_corte``.
    """
    mes = _mes(df)
    q = df[mes >= desde]
    uf = q["id_estado"].astype(str)
    por_cat = (
        q[q["qualificado"]]
        .groupby(
            [uf[q["qualificado"]], q.loc[q["qualificado"], "categoria"].astype(str)], observed=True
        )["eng_mwh"]
        .sum()
        .unstack("categoria")
        .reindex(columns=list(ORDEM_CATEGORIAS), fill_value=0.0)
        .fillna(0.0)
    )
    por_cat.columns = [f"eng_{c.replace(' ', '_')}_gwh" for c in por_cat.columns]
    tot = q.groupby(uf, observed=True).agg(
        eng_mwh=("eng_mwh", "sum"), gerada_mwh=("energia_gerada_mwh", "sum")
    )
    tab = tot.join(por_cat, how="left").fillna(0.0)
    for c in [c for c in tab.columns if c.startswith("eng_") and c.endswith("_gwh")]:
        tab[c] = tab[c] / 1000
    tab["eng_gwh"] = tab["eng_mwh"] / 1000
    tab["energia_gerada_gwh"] = tab["gerada_mwh"] / 1000
    tab["taxa_corte"] = taxa_corte(tab["eng_mwh"], tab["gerada_mwh"])
    tab = (
        tab.drop(columns=["eng_mwh", "gerada_mwh"])
        .reset_index()
        .rename(columns={"id_estado": "uf"})
    )
    return tab.sort_values("eng_gwh", ascending=False).reset_index(drop=True)


def cruzar_temporada(eng_uf: pd.DataFrame, temporada: pd.DataFrame) -> pd.DataFrame:
    """Junta ENG por UF com o cadastro da Temporada de Acesso (outer join por UF).

    ``temporada`` tem colunas ``uf, ad_mw, advc_mw, pc_mw, inab_mw`` (vazio = nao informado).
    Acrescenta ``cadastrado_mw`` (soma das quatro parcelas) e ``frac_inab`` = inab / cadastrado
    quando cadastrado > 0. UF sem ENG fica com zeros; UF sem Temporada fica vazia.
    """
    t = temporada.copy()
    t["uf"] = t["uf"].astype(str).str.strip().str.upper()
    parcelas = ["ad_mw", "advc_mw", "pc_mw", "inab_mw"]
    for c in parcelas:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t["cadastrado_mw"] = t[parcelas].fillna(0.0).sum(axis=1)
    t["frac_inab"] = (
        t["inab_mw"].fillna(0.0) / t["cadastrado_mw"].where(t["cadastrado_mw"] > 0)
    ).where(t["cadastrado_mw"] > 0)
    e = eng_uf.copy()
    e["uf"] = e["uf"].astype(str).str.strip().str.upper()
    cruz = e.merge(t, on="uf", how="outer")
    for c in [c for c in e.columns if c != "uf"]:
        cruz[c] = cruz[c].fillna(0.0)
    return cruz.sort_values("eng_gwh", ascending=False).reset_index(drop=True)


def spearman_taxa_inabilitacao(cruz: pd.DataFrame) -> tuple[float, int]:
    """Spearman entre taxa de corte e fracao inabilitada; so UFs com os dois dados."""
    sub = cruz.dropna(subset=["frac_inab"])
    sub = sub[sub["energia_gerada_gwh"] + sub["eng_gwh"] > 0]
    n = len(sub)
    if n < 3:
        return float("nan"), n
    # Spearman = Pearson dos postos (empates recebem posto medio); sem dependencia de scipy
    postos_x = sub["taxa_corte"].rank(method="average")
    postos_y = sub["frac_inab"].rank(method="average")
    return float(postos_x.corr(postos_y)), n
