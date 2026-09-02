"""Qualificacao dos registros — regras R1 a R12 da spec v2, secao 4.

Nenhuma linha e descartada: o DataFrame devolvido e o de entrada acrescido de
``restrito``, ``qualificado``, ``motivo``, flags booleanas, referencia efetiva
e ENG (energia nao gerada) por registro. Cada motivo e cada flag e contado em
``relatorio_qualificacao``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from coff.categorias import (
    CODIGOS_CONHECIDOS,
    ORIGENS_CONHECIDAS,
    categoria_de,
    origem_de,
)

REFERENCIAS: tuple[str, ...] = ("coalesce", "referencia")

# motivos de nao qualificacao, na ordem de precedencia em que sao atribuidos
MOTIVOS: tuple[str, ...] = (
    "instante_invalido",  # R4
    "duplicata",  # R4
    "sem_restricao",  # R1
    "codigo_desconhecido",  # R2
    "valor_nulo",  # R5
    "disponibilidade_zero",  # R10 (apenas com excluir_disp_zero)
)

FLAGS: tuple[str, ...] = (
    "origem_desconhecida",  # R3
    "geracao_negativa",  # R7
    "restrito_sem_eng",  # R8
    "limite_zero",  # R9
    "limite_nao_vinculante",  # R9
    "disponibilidade_zero",  # R10
    "ref_maior_que_disp",  # R10
    "ger_maior_que_disp",  # R10
)


def _normalizar(serie: pd.Series) -> pd.Series:
    """strip + upper; vazio vira nulo."""
    s = serie.astype("string").str.strip().str.upper()
    return s.replace("", pd.NA)


def referencia_efetiva(df: pd.DataFrame, referencia: str = "coalesce") -> pd.Series:
    """R6: ``coalesce(final, referencia)`` (padrao) ou apenas ``referencia``."""
    if referencia not in REFERENCIAS:
        raise ValueError(f"referencia deve ser uma de {REFERENCIAS}, nao {referencia!r}")
    ref = df["val_geracaoreferencia"].astype("float64")
    if referencia == "referencia":
        return ref
    return df["val_geracaoreferenciafinal"].astype("float64").fillna(ref)


def qualificar(
    df: pd.DataFrame,
    referencia: str = "coalesce",
    delta_t_h: float = 0.5,
    excluir_disp_zero: bool = False,
) -> pd.DataFrame:
    """Aplica R1–R10 e calcula ENG por registro. Devolve copia com colunas novas.

    Colunas acrescentadas: ``codigo``, ``categoria``, ``origem``, ``restrito``,
    ``qualificado``, ``motivo``, as flags de ``FLAGS``, ``ref_ef``, ``ger_calc``,
    ``eng_mw``, ``eng_mwh``, ``energia_gerada_mwh``, ``ano``.
    """
    df = df.copy()
    n = len(df)

    codigo = _normalizar(df["cod_razaorestricao"])
    origem = _normalizar(df["cod_origemrestricao"])
    df["codigo"] = codigo
    df["categoria"] = codigo.map(categoria_de).astype("string")
    df["origem"] = origem.map(origem_de).astype("string")

    ger = df["val_geracao"].astype("float64")
    lim = df["val_geracaolimitada"].astype("float64")
    disp = df["val_disponibilidade"].astype("float64")
    ref_ef = referencia_efetiva(df, referencia)
    df["ref_ef"] = ref_ef

    # R1 — restrito
    restrito = codigo.notna().to_numpy()
    df["restrito"] = restrito

    # R4 — instante invalido e duplicatas (manter a ultima ocorrencia)
    instante_invalido = df["din_instante"].isna().to_numpy()
    duplicata = (
        df.duplicated(subset=["id_ons", "din_instante"], keep="last").to_numpy()
        & ~instante_invalido
    )

    # R2 — codigo conhecido
    codigo_desconhecido = restrito & ~codigo.isin(CODIGOS_CONHECIDOS).fillna(False).to_numpy()

    # R5 — valores nulos
    valor_nulo = (ger.isna() | ref_ef.isna()).to_numpy()

    # R3 — origem
    df["origem_desconhecida"] = restrito & ~origem.isin(ORIGENS_CONHECIDAS).fillna(False).to_numpy()

    # R7 — geracao negativa
    df["geracao_negativa"] = (ger < 0).fillna(False).to_numpy()
    ger_calc = ger.clip(lower=0)
    df["ger_calc"] = ger_calc

    # R10 — disponibilidade (flags informativas)
    disp_zero = (disp == 0).fillna(False).to_numpy()
    df["disponibilidade_zero"] = disp_zero
    df["ref_maior_que_disp"] = (ref_ef > disp).fillna(False).to_numpy()
    df["ger_maior_que_disp"] = (ger > disp).fillna(False).to_numpy()

    # R9 — limite (flags informativas, nunca excluem)
    df["limite_zero"] = restrito & (lim == 0).fillna(False).to_numpy()
    df["limite_nao_vinculante"] = restrito & (lim > ref_ef).fillna(False).to_numpy()

    # motivo por precedencia
    motivo = np.full(n, "", dtype=object)
    qualificado = np.ones(n, dtype=bool)
    condicoes = [
        ("instante_invalido", instante_invalido),
        ("duplicata", duplicata),
        ("sem_restricao", ~restrito),
        ("codigo_desconhecido", codigo_desconhecido),
        ("valor_nulo", valor_nulo),
    ]
    if excluir_disp_zero:
        condicoes.append(("disponibilidade_zero", disp_zero))
    for nome, cond in condicoes:
        marcar = cond & qualificado
        motivo[marcar] = nome
        qualificado &= ~cond
    df["qualificado"] = qualificado
    df["motivo"] = pd.Series(motivo, index=df.index, dtype="string").replace("", pd.NA)

    # R8 — ENG do registro (so qualificados; demais = 0)
    eng_mw = (ref_ef - ger_calc).clip(lower=0).fillna(0.0).where(qualificado, 0.0)
    df["eng_mw"] = eng_mw
    df["eng_mwh"] = eng_mw * delta_t_h
    df["restrito_sem_eng"] = qualificado & (ger_calc >= ref_ef).fillna(False).to_numpy()

    # energia gerada de todos os registros (para a taxa de corte), com ger negativa zerada
    df["energia_gerada_mwh"] = ger_calc.fillna(0.0) * delta_t_h
    df["ano"] = df["din_instante"].dt.year.astype("Int64")
    return df


def lacunas_por_usina_mes(df: pd.DataFrame, delta_t_h: float = 0.5) -> pd.DataFrame:
    """R11: intervalos presentes vs esperados por (fonte, id_ons, periodo). Nao reindexa."""
    validos = df.dropna(subset=["din_instante"])
    g = validos.groupby(["fonte", "id_ons", "periodo"], observed=True)["din_instante"]
    tab = g.agg(presentes="size", inicio="min", fim="max").reset_index()
    periodo = tab["periodo"].astype(str)
    ano = periodo.str[:4].astype(int)
    mes = periodo.str[5:7].astype(int)
    dias = pd.to_datetime(dict(year=ano, month=mes, day=1)).dt.days_in_month
    tab["esperados"] = (dias * 24 / delta_t_h).astype(int)
    tab["faltantes"] = tab["esperados"] - tab["presentes"]
    tab["cobertura"] = tab["presentes"] / tab["esperados"]
    return tab


@dataclass
class RelatorioQualificacao:
    referencia: str
    delta_t_h: float
    total: int
    motivos: pd.DataFrame = field(default_factory=pd.DataFrame)  # fonte x ano x motivo
    flags: pd.DataFrame = field(default_factory=pd.DataFrame)  # fonte x ano x flag
    codigos_desconhecidos: pd.Series = field(default_factory=pd.Series)
    eng_total_mwh: pd.Series = field(default_factory=pd.Series)  # por fonte
    lacunas: pd.DataFrame = field(default_factory=pd.DataFrame)


def relatorio_qualificacao(
    df: pd.DataFrame, referencia: str, delta_t_h: float
) -> RelatorioQualificacao:
    """Contagens por motivo e por flag, por fonte e por ano (spec v2, secao 4)."""
    chave = [df["fonte"].astype(str), df["ano"].astype("Int64")]
    motivo = df["motivo"].fillna("(qualificado)")
    motivos = pd.crosstab(chave, motivo, margins=True, margins_name="total")
    colunas = ["(qualificado)", *MOTIVOS, "total"]
    motivos = motivos.reindex(columns=colunas, fill_value=0)
    flags = pd.DataFrame(
        {f: df.groupby(chave, observed=True)[f].sum() for f in FLAGS if f in df.columns}
    )
    flags.loc[("total", ""), :] = flags.sum(numeric_only=True)
    desconhecidos = (
        df.loc[df["motivo"] == "codigo_desconhecido", "codigo"].astype(str).value_counts()
    )
    eng_total = df.groupby(df["fonte"].astype(str), observed=True)["eng_mwh"].sum()
    lac = lacunas_por_usina_mes(df, delta_t_h)
    resumo_lac = (
        lac.groupby("fonte", observed=True)
        .agg(
            usinas_mes=("presentes", "size"),
            com_lacuna=("faltantes", lambda s: int((s > 0).sum())),
            intervalos_faltantes=("faltantes", "sum"),
            cobertura_media=("cobertura", "mean"),
        )
        .reset_index()
    )
    return RelatorioQualificacao(
        referencia,
        delta_t_h,
        len(df),
        motivos,
        flags.astype("Int64"),
        desconhecidos,
        eng_total,
        resumo_lac,
    )


def _tabela_md(tab: pd.DataFrame) -> list[str]:
    t = tab.reset_index()
    cols = [str(c) for c in t.columns]
    linhas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in t.iterrows():
        linhas.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return linhas


def relatorio_markdown(rel: RelatorioQualificacao) -> str:
    linhas = [
        "# Relatorio de qualificacao (Gate 2)\n",
        f"Registros: {rel.total:,} | referencia efetiva: `{rel.referencia}` | "
        f"delta t: {rel.delta_t_h} h\n",
        "## Contagem por motivo (fonte x ano)\n",
        *_tabela_md(rel.motivos),
        "",
        "## Contagem por flag (fonte x ano)\n",
        *_tabela_md(rel.flags),
        "",
        "## Codigos desconhecidos\n",
    ]
    if rel.codigos_desconhecidos.empty:
        linhas.append("Nenhum codigo fora de {ENE, CNF, REL, PAR}.")
    else:
        linhas.extend(_tabela_md(rel.codigos_desconhecidos.rename("linhas").to_frame()))
    linhas += ["", "## ENG total por fonte (MWh, registros qualificados)\n"]
    linhas.extend(_tabela_md(rel.eng_total_mwh.round(1).to_frame()))
    linhas += ["", "## Lacunas (R11): intervalos presentes vs esperados por usina e mes\n"]
    linhas.extend(_tabela_md(rel.lacunas.set_index("fonte").round(4)))
    return "\n".join(linhas) + "\n"
