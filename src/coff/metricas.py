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
    """6. ``dsc_restricao`` por ENG (MWh), com categoria, origem e nº de registros."""
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
