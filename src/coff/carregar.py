"""Leitura tipada dos arquivos mensais, validacao de schema e inferencia de delta t.

Fatos assumidos e testados (spec v2, secao 2): 16 colunas fixas; chave
(``id_ons``, ``din_instante``); delta t = 30 min inferido pela moda das
diferencas por ``id_ons`` (aborta se for outro); leitura de CSV em modo
estrito com contagem de linhas malformadas (R12).
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from coff.download import DATASETS

COLUNAS_ESPERADAS: tuple[str, ...] = (
    "id_subsistema",
    "nom_subsistema",
    "id_estado",
    "nom_estado",
    "nom_usina",
    "id_ons",
    "ceg",
    "din_instante",
    "val_geracao",
    "val_geracaolimitada",
    "val_disponibilidade",
    "val_geracaoreferencia",
    "val_geracaoreferenciafinal",
    "cod_razaorestricao",
    "cod_origemrestricao",
    "dsc_restricao",
)
COLUNAS_NUMERICAS: tuple[str, ...] = (
    "val_geracao",
    "val_geracaolimitada",
    "val_disponibilidade",
    "val_geracaoreferencia",
    "val_geracaoreferenciafinal",
)
COLUNAS_CATEGORICAS: tuple[str, ...] = (
    "id_subsistema",
    "nom_subsistema",
    "id_estado",
    "nom_estado",
    "nom_usina",
    "id_ons",
    "ceg",
    "cod_razaorestricao",
    "cod_origemrestricao",
    "dsc_restricao",
)
DELTA_T_ESPERADO = pd.Timedelta(minutes=30)
_PERIODO_RE = re.compile(r"(20\d{2})_(\d{2})\.(parquet|csv)$", re.IGNORECASE)


class SchemaInvalidoError(ValueError):
    """As colunas do arquivo divergem das 16 esperadas."""


class DeltaTInesperadoError(ValueError):
    """A moda das diferencas de instante nao e 30 min."""


@dataclass
class ArquivoCarregado:
    fonte: str
    periodo: str
    formato: str
    caminho: Path
    bytes: int
    linhas: int
    usinas: int
    linhas_malformadas: int


@dataclass
class RelatorioCarga:
    arquivos: list[ArquivoCarregado] = field(default_factory=list)
    delta_t: dict[str, pd.Timedelta] = field(default_factory=dict)
    distribuicao_delta_t: dict[str, pd.Series] = field(default_factory=dict)
    schema_divergente: list[str] = field(default_factory=list)
    codigos_por_mes: pd.DataFrame | None = None

    def bytes_total(self) -> int:
        return sum(a.bytes for a in self.arquivos)


COLUNAS_TOLERADAS_AUSENTES: frozenset[str] = frozenset({"dsc_restricao"})


def validar_schema(colunas: list[str] | pd.Index, origem: str) -> str | None:
    """Falha com mensagem clara se faltar ou sobrar coluna (A5.8).

    Excecao documentada: meses antigos (ate 2025) nao tem ``dsc_restricao``; essa
    ausencia e tolerada (a coluna e criada nula) e devolvida como texto de
    divergencia para o relatorio. Qualquer outra diferenca aborta.
    """
    atuais = list(colunas)
    faltam = [c for c in COLUNAS_ESPERADAS if c not in atuais]
    sobram = [c for c in atuais if c not in COLUNAS_ESPERADAS]
    if faltam and not sobram and set(faltam) <= COLUNAS_TOLERADAS_AUSENTES:
        return f"{origem}: sem coluna(s) {faltam} (tolerado; criada(s) nula(s))"
    if faltam or sobram:
        raise SchemaInvalidoError(
            f"schema divergente em {origem}: faltam={faltam} sobram={sobram}. "
            f"Esperadas {len(COLUNAS_ESPERADAS)} colunas: {list(COLUNAS_ESPERADAS)}"
        )
    return None


def _periodo_do_nome(caminho: Path) -> str:
    m = _PERIODO_RE.search(caminho.name)
    if not m:
        raise ValueError(f"nao consigo extrair AAAA_MM de {caminho.name}")
    return f"{m.group(1)}_{m.group(2)}"


def _ler_csv_estrito(caminho: Path) -> tuple[pd.DataFrame, int]:
    """Le CSV (``;``, UTF-8) com o modulo csv; linhas com numero errado de campos
    sao contadas e removidas (nunca em silencio). Campos vazios viram nulo."""
    with caminho.open(encoding="utf-8", newline="") as f:
        leitor = csv.reader(f, delimiter=";")
        cabecalho = next(leitor)
        boas: list[list[str]] = []
        malformadas = 0
        for linha in leitor:
            if len(linha) == len(cabecalho):
                boas.append(linha)
            elif linha:  # ignora linhas totalmente vazias
                malformadas += 1
    df = pd.DataFrame(boas, columns=cabecalho, dtype="string")
    return df.replace("", pd.NA), malformadas


def ler_arquivo(caminho: Path, fonte: str) -> tuple[pd.DataFrame, int, str | None]:
    """Le um mes (parquet ou csv): ``(df bruto, linhas_malformadas, divergencia_schema)``.

    O CSV e lido em modo estrito: cada linha com numero errado de campos e
    contada e devolvida no segundo item (nunca descartada em silencio).
    """
    caminho = Path(caminho)
    malformadas = 0
    if caminho.suffix.lower() == ".parquet":
        df = pd.read_parquet(caminho)
    else:
        df, malformadas = _ler_csv_estrito(caminho)
    divergencia = validar_schema(df.columns, f"{fonte} {caminho.name}")
    for c in COLUNAS_ESPERADAS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df.loc[:, list(COLUNAS_ESPERADAS)].copy()
    df["fonte"] = fonte
    df["periodo"] = _periodo_do_nome(caminho)
    return df, malformadas, divergencia


def tipar(df: pd.DataFrame) -> pd.DataFrame:
    """Converte tipos sem descartar linhas; instantes invalidos viram NaT (R4).

    Guarda o texto original do instante em ``din_instante_bruto`` quando a
    conversao falha, para o relatorio de qualificacao.
    """
    df = df.copy()
    bruto = df["din_instante"].astype("string")
    df["din_instante"] = pd.to_datetime(df["din_instante"], errors="coerce", format="ISO8601")
    df["din_instante_bruto"] = bruto.where(df["din_instante"].isna(), other=pd.NA)
    for c in COLUNAS_NUMERICAS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    for c in COLUNAS_CATEGORICAS:
        serie = df[c]
        if isinstance(serie.dtype, pd.CategoricalDtype):
            serie = serie.astype("string")
        serie = serie.astype("string").str.strip()
        df[c] = serie.astype("category")
    df["fonte"] = df["fonte"].astype("category")
    df["periodo"] = df["periodo"].astype("category")
    return df


def inferir_delta_t(df: pd.DataFrame) -> tuple[pd.Timedelta, pd.Series]:
    """Moda das diferencas de ``din_instante`` dentro de cada ``id_ons``."""
    ordenado = df.dropna(subset=["din_instante"]).sort_values(["id_ons", "din_instante"])
    difs = ordenado.groupby("id_ons", observed=True)["din_instante"].diff().dropna()
    if difs.empty:
        raise DeltaTInesperadoError("sem diferencas de instante para inferir delta t")
    distribuicao = difs.value_counts()
    return distribuicao.index[0], distribuicao


def verificar_delta_t(delta_t: pd.Timedelta, fonte: str) -> None:
    if delta_t != DELTA_T_ESPERADO:
        raise DeltaTInesperadoError(
            f"delta t inferido para {fonte} = {delta_t}, esperado 30 min (D9)"
        )


def listar_arquivos(pasta_raw: Path, fonte: str, desde: str | None, ate: str | None) -> list[Path]:
    pasta = Path(pasta_raw) / DATASETS[fonte]
    if not pasta.exists():
        return []
    por_periodo: dict[str, Path] = {}
    for p in sorted(pasta.iterdir()):
        if not _PERIODO_RE.search(p.name):
            continue
        periodo = _periodo_do_nome(p)
        if desde and periodo < desde:
            continue
        if ate and periodo > ate:
            continue
        # prefere parquet se houver os dois
        if periodo not in por_periodo or p.suffix.lower() == ".parquet":
            por_periodo[periodo] = p
    return [por_periodo[k] for k in sorted(por_periodo)]


def contar_codigos_por_mes(df: pd.DataFrame) -> pd.DataFrame:
    """Contagem de ``cod_razaorestricao`` (normalizado) por periodo e fonte, inclusive nulo."""
    cod = df["cod_razaorestricao"].astype("string").str.strip().str.upper()
    cod = cod.replace("", pd.NA).fillna("(nulo)")
    tabela = (
        pd.crosstab([df["fonte"].astype(str), df["periodo"].astype(str)], cod)
        .rename_axis(index=["fonte", "periodo"], columns=None)
        .reset_index()
    )
    return tabela


def carregar(
    pasta_raw: Path,
    fontes: tuple[str, ...] = ("EOL", "UFV"),
    desde: str | None = "2023_01",
    ate: str | None = None,
) -> tuple[pd.DataFrame, RelatorioCarga]:
    """Le todos os meses em cache, valida, tipa e infere delta t por fonte."""
    rel = RelatorioCarga()
    partes: list[pd.DataFrame] = []
    for fonte in fontes:
        for caminho in listar_arquivos(pasta_raw, fonte, desde, ate):
            bruto, malformadas, divergencia = ler_arquivo(caminho, fonte)
            if divergencia:
                rel.schema_divergente.append(divergencia)
            df = tipar(bruto)
            rel.arquivos.append(
                ArquivoCarregado(
                    fonte=fonte,
                    periodo=str(df["periodo"].iloc[0]),
                    formato=caminho.suffix.lstrip(".").upper(),
                    caminho=caminho,
                    bytes=caminho.stat().st_size,
                    linhas=len(df),
                    usinas=int(df["id_ons"].nunique()),
                    linhas_malformadas=malformadas,
                )
            )
            partes.append(df)
    if not partes:
        raise FileNotFoundError(f"nenhum arquivo mensal em {pasta_raw} para {fontes}")
    df = pd.concat(partes, ignore_index=True)
    for c in COLUNAS_CATEGORICAS + ("fonte", "periodo"):
        df[c] = df[c].astype("string").astype("category")
    for fonte in fontes:
        sub = df[df["fonte"] == fonte]
        if sub.empty:
            continue
        dt, dist = inferir_delta_t(sub)
        verificar_delta_t(dt, fonte)
        rel.delta_t[fonte] = dt
        rel.distribuicao_delta_t[fonte] = dist
    rel.codigos_por_mes = contar_codigos_por_mes(df)
    return df, rel


def relatorio_markdown(rel: RelatorioCarga, titulo: str = "Relatorio de carga") -> str:
    """Relatorio do Gate 1 em Markdown."""
    linhas = [f"# {titulo}\n"]
    linhas.append(
        f"Arquivos: {len(rel.arquivos)} | cache total: {rel.bytes_total() / 1e6:,.1f} MB\n"
    )
    for fonte in sorted({a.fonte for a in rel.arquivos}):
        arqs = [a for a in rel.arquivos if a.fonte == fonte]
        periodos = [a.periodo for a in arqs]
        linhas.append(f"## {fonte}\n")
        linhas.append(
            f"- meses: {len(arqs)} ({periodos[0]} a {periodos[-1]}); "
            f"formatos: {dict(Counter(a.formato for a in arqs))}; "
            f"cache: {sum(a.bytes for a in arqs) / 1e6:,.1f} MB"
        )
        linhas.append(
            f"- linhas: {sum(a.linhas for a in arqs):,}; usinas/conjuntos distintos por mes: "
            f"min {min(a.usinas for a in arqs)} / max {max(a.usinas for a in arqs)}; "
            f"linhas malformadas (CSV): {sum(a.linhas_malformadas for a in arqs)}"
        )
        dt = rel.delta_t.get(fonte)
        dist = rel.distribuicao_delta_t.get(fonte)
        if dt is not None and dist is not None:
            total = int(dist.sum())
            top = ", ".join(f"{k} ({v / total:.2%})" for k, v in dist.head(3).items())
            linhas.append(f"- delta t inferido: **{dt}** — distribuicao: {top}")
        linhas.append("")
        linhas.append("| periodo | formato | MB | linhas | usinas | malformadas |")
        linhas.append("|---|---|---:|---:|---:|---:|")
        for a in arqs:
            linhas.append(
                f"| {a.periodo} | {a.formato} | {a.bytes / 1e6:.1f} | {a.linhas:,} | "
                f"{a.usinas} | {a.linhas_malformadas} |"
            )
        linhas.append("")
    linhas.append("## Schema\n")
    if rel.schema_divergente:
        linhas.append(
            f"- {len(rel.schema_divergente)} arquivo(s) sem as 16 colunas (divergencia tolerada, "
            "coluna criada nula):"
        )
        linhas.extend(f"  - {s}" for s in rel.schema_divergente)
    else:
        linhas.append("- todos os arquivos com as 16 colunas esperadas; nenhuma divergencia.")
    linhas.append("")
    if rel.codigos_por_mes is not None:
        tab = rel.codigos_por_mes
        linhas.append("## Codigos de razao por mes\n")
        linhas.append("| " + " | ".join(tab.columns) + " |")
        linhas.append("|" + "---|" * len(tab.columns))
        for _, r in tab.iterrows():
            linhas.append("| " + " | ".join(str(v) for v in r.values) + " |")
        linhas.append("")
        par = tab["PAR"] if "PAR" in tab.columns else pd.Series(0, index=tab.index)
        linhas.append("## Ocorrencias de PAR por mes\n")
        if int(par.sum()) == 0:
            linhas.append(
                f"Nenhuma ocorrencia de PAR em {len(tab)} meses x fonte "
                "(tabela acima, coluna ausente ou zerada)."
            )
        else:
            linhas.append("| fonte | periodo | PAR |\n|---|---|---:|")
            for _, r in tab[par > 0].iterrows():
                linhas.append(f"| {r['fonte']} | {r['periodo']} | {int(r['PAR'])} |")
        linhas.append("")
    return "\n".join(linhas)
