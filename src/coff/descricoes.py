"""Normalizacao e parsing de ``dsc_restricao`` (Etapa 1 do cruzamento por ponto de conexao).

O campo e texto livre do ONS, preenchido desde 2025-09. Aqui ele e normalizado por
regras (nunca agrupado a mao) e decomposto em ``tipo``, ``elemento`` e ``tensao_kv``.
Descricoes de rede sao classificadas em ``exportacao`` (limites de intercambio do
Nordeste) ou ``local`` (LT/SE/TR nomeados).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

TIPOS: tuple[str, ...] = (
    "Controle de frequência",
    "Controle do fluxo",
    "Controle de inequação",
    "Limitação da transmissão",
    "Esquema",
    "outro",
)

# sufixos numericos/referencias que variam sem mudar a restricao
_SUFIXOS = [
    re.compile(r"\s*[-–,]?\s*conforme\s+(?:a\s+)?(?:SGI|IO|MOP)\b.*$", re.I),
    re.compile(r"\s*[-–,.]?\s*SGI\s*(?:N[°º]?\s*)?[\d.\-/]+.*$", re.I),
    re.compile(r"\s*[-–]\s*SGI\s*$", re.I),
    re.compile(r"^\s*SGI\s*[\d.\-/]+\s*:\s*", re.I),
    re.compile(r"\s+e\s+MOP\s+[\w\-/.]+\s*$", re.I),
    re.compile(r"\s+revis[aã]o\s+\d+\s*$", re.I),
    re.compile(r"\s*\(\d+(?:\.\d+)?\)\s*", re.I),
]
_ESPACOS = re.compile(r"\s+")

_FLUXOS_EXPORTACAO = (
    "FNESE",
    "FNS",
    "FNEN",
    "EXPNE",
    "EXPNNE",
    "FSENE",
    "NORDESTE/SUDESTE",
    "NORDESTE/NORTE",
    "NORTE/NORDESTE",
)
_TENSAO = re.compile(r"(\d{2,3})\s*/?\s*(?:\d{2,3}\s*)?KV", re.I)
_ELEMENTO = re.compile(
    r"\b(LTS?|TRS?|TRANSFORMADOR(?:ES)?|TRANSFORMA[CÇ][AÃ]O|SE|SUB|BIPOLOS?|FLUXO)\b"
    r"(.*?)(?=\s+[-–]\s+C\d|\s+C\d\s*\(|\s*,|\s+PARA\s|\s+PREVENINDO|\s+E\s+LT|\s+OU\s+C\d|\s+[-–]\s+IO|"
    r"\s+[-–]\s+CONFORME|\s+COM\s+GVA|\s+PARA\s+CONTING|\s+EM\s+FUN|\s*$)",
    re.I,
)


@dataclass(frozen=True)
class Descricao:
    original: str
    normalizada: str
    tipo: str
    elemento: str | None
    tensao_kv: float | None
    classe: str  # frequencia | exportacao | local | outro


def normalizar(texto: object) -> str:
    """Colapsa espacos e remove referencias numericas (SGI, MOP, revisao) e sufixos."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    t = _ESPACOS.sub(" ", str(texto).replace("\n", " ")).strip()
    anterior = None
    while anterior != t:
        anterior = t
        for padrao in _SUFIXOS:
            t = padrao.sub("", t).strip()
    t = t.rstrip(" .,;:-–").strip()
    return _ESPACOS.sub(" ", t)


def tipo_de(normalizada: str) -> str:
    n = normalizada.lower()
    if n.startswith("controle de frequ"):
        return "Controle de frequência"
    if n.startswith(("controle do fluxo", "controle dos fluxos", "controle do fnese")):
        return "Controle do fluxo"
    if "esquema" in n or "erac" in n or " ece " in f" {n} ":
        return "Esquema"
    if (
        "limitação da transmissão" in n
        or "limitação do fluxo" in n
        or "limitacao da transmissao" in n
    ):
        return "Limitação da transmissão"
    if n.startswith(
        ("controle de inequa", "controle da inequa", "controle de carregamento", "limite de")
    ):
        return "Controle de inequação"
    return "outro"


def _capitalizar(texto: str) -> str:
    from coff.figuras import _capitalizar_nome

    return _capitalizar_nome(texto)


def elemento_de(normalizada: str, tipo: str) -> str | None:
    """Elemento de rede citado (fluxo, LT, SE, TR, bipolo); ``None`` se nao identificado."""
    if tipo == "Controle de frequência":
        return "SIN"
    corpo = normalizada.split(":", 1)[1].strip() if ":" in normalizada else normalizada
    if tipo == "Controle do fluxo":
        codigo = corpo.split("#", 1)[0].strip()
        maiusculo = codigo.upper()
        for fluxo in ("FNS_FNESE", "FNESE", "FNEN", "FNS", "FSENE", "EXPNNE", "EXPNE"):
            if fluxo in maiusculo:
                return "FNS+FNESE" if fluxo == "FNS_FNESE" else fluxo
        if "#" in corpo:
            return _capitalizar(corpo.split("#", 1)[1].strip())
        return _capitalizar(codigo) if codigo else None
    m = _ELEMENTO.search(corpo)
    if not m:
        return None
    elemento = f"{m.group(1)} {m.group(2)}".strip()
    elemento = re.sub(r"\s+", " ", elemento)
    return _capitalizar(elemento)


def tensao_de(normalizada: str) -> float | None:
    m = _TENSAO.search(normalizada)
    return float(m.group(1)) if m else None


def classe_de(tipo: str, elemento: str | None, normalizada: str) -> str:
    if tipo == "Controle de frequência":
        return "frequencia"
    texto = (normalizada + " " + (elemento or "")).upper()
    if any(f in texto for f in _FLUXOS_EXPORTACAO):
        return "exportacao"
    if tipo in (
        "Controle do fluxo",
        "Controle de inequação",
        "Limitação da transmissão",
        "Esquema",
    ):
        return "local" if elemento else "outro"
    return "outro"


def analisar(texto: object) -> Descricao:
    """Normaliza e decompoe uma descricao."""
    normalizada = normalizar(texto)
    tipo = tipo_de(normalizada) if normalizada else "outro"
    elemento = elemento_de(normalizada, tipo) if normalizada else None
    return Descricao(
        original=str(texto) if texto is not None else "",
        normalizada=normalizada,
        tipo=tipo,
        elemento=elemento,
        tensao_kv=tensao_de(normalizada) if normalizada else None,
        classe=classe_de(tipo, elemento, normalizada) if normalizada else "outro",
    )


def tabela_descricoes(df: pd.DataFrame, desde: str = "2025-09") -> pd.DataFrame:
    """ENG por descricao normalizada (registros qualificados desde ``desde``).

    Colunas: ``descricao, tipo, elemento, tensao_kv, classe, categorias, origens,
    subsistemas, categoria_principal, origem_principal, eng_gwh, usinas, meses, registros``.
    """
    mes = df["din_instante"].dt.to_period("M").astype(str)
    q = df[df["qualificado"] & (mes >= desde)].copy()
    q["mes"] = mes[q.index]
    brutas = q["dsc_restricao"].astype("string").fillna("")
    cache: dict[str, Descricao] = {}
    normal = []
    for b in brutas:
        if b not in cache:
            cache[b] = analisar(b)
        normal.append(cache[b].normalizada)
    q["descricao"] = normal
    q.loc[q["descricao"] == "", "descricao"] = "(sem descricao)"
    info = {d.normalizada or "(sem descricao)": d for d in cache.values()}

    def _lista(s: pd.Series) -> str:
        return "/".join(sorted({str(v) for v in s.dropna()}))

    def _principal(s: pd.Series, pesos: pd.Series) -> str:
        agg = pesos.groupby(s.astype(str)).sum()
        return str(agg.idxmax()) if len(agg) else ""

    linhas = []
    for desc, g in q.groupby("descricao", sort=False):
        d = info.get(desc)
        linhas.append(
            {
                "descricao": desc,
                "tipo": d.tipo if d else "outro",
                "elemento": d.elemento if d else None,
                "tensao_kv": d.tensao_kv if d else None,
                "classe": d.classe if d else "outro",
                "categorias": _lista(g["categoria"]),
                "origens": _lista(g["origem"]),
                "subsistemas": _lista(g["id_subsistema"]),
                "categoria_principal": _principal(g["categoria"], g["eng_mwh"]),
                "origem_principal": _principal(
                    g["origem"].astype("string").fillna("desconhecida"), g["eng_mwh"]
                ),
                "eng_gwh": float(g["eng_mwh"].sum()) / 1000,
                "usinas": int(g["id_ons"].nunique()),
                "meses": int(g["mes"].nunique()),
                "registros": int(len(g)),
            }
        )
    tab = pd.DataFrame(linhas).sort_values("eng_gwh", ascending=False).reset_index(drop=True)
    return tab


def eng_rede_ne_por_elemento(
    df: pd.DataFrame, desde: str = "2025-09"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """CNF + REL no Nordeste, por elemento e classe (exportacao vs local).

    Devolve ``(por_elemento, resumo_classe)``. ``por_elemento`` traz tambem a origem
    (LOC/SIS) predominante por ENG de cada elemento; o resumo traz ENG e fracao por classe.
    """
    mes = df["din_instante"].dt.to_period("M").astype(str)
    q = df[
        df["qualificado"]
        & (mes >= desde)
        & (df["id_subsistema"].astype(str) == "NE")
        & df["categoria"].isin(["confiabilidade", "eletrica"])
    ].copy()
    brutas = q["dsc_restricao"].astype("string").fillna("")
    cache: dict[str, Descricao] = {}
    els, cls = [], []
    for b in brutas:
        if b not in cache:
            cache[b] = analisar(b)
        els.append(cache[b].elemento or "(sem elemento)")
        cls.append(cache[b].classe)
    q["elemento"] = els
    q["classe"] = cls
    q["origem_txt"] = q["origem"].astype("string").fillna("desconhecida")
    por_el = (
        q.groupby(["classe", "elemento"], observed=True)
        .agg(
            eng_mwh=("eng_mwh", "sum"), usinas=("id_ons", "nunique"), registros=("eng_mwh", "size")
        )
        .reset_index()
    )
    por_origem = (
        q.groupby(["classe", "elemento", "origem_txt"], observed=True)["eng_mwh"]
        .sum()
        .reset_index()
    )
    principal = (
        por_origem.sort_values("eng_mwh", ascending=False)
        .drop_duplicates(["classe", "elemento"])
        .rename(columns={"origem_txt": "origem_principal"})
    )
    por_el = por_el.merge(
        principal[["classe", "elemento", "origem_principal"]], on=["classe", "elemento"], how="left"
    )
    por_el["eng_gwh"] = por_el["eng_mwh"] / 1000
    por_el["classe_efetiva"] = [
        classe_efetiva(c, o)
        for c, o in zip(por_el["classe"], por_el["origem_principal"], strict=True)
    ]
    por_el = (
        por_el.drop(columns="eng_mwh")
        .sort_values("eng_gwh", ascending=False)
        .reset_index(drop=True)
    )
    resumo = (
        por_el.groupby("classe_efetiva")["eng_gwh"].sum().reindex(CLASSES_EFETIVAS, fill_value=0.0)
    )
    resumo = resumo.reset_index()
    resumo["fracao"] = resumo["eng_gwh"] / resumo["eng_gwh"].sum()
    return por_el, resumo


CLASSES_EFETIVAS: tuple[str, ...] = (
    "intercâmbio nomeado",
    "corredor de exportação",
    "local NE",
    "outro",
)


def classe_efetiva(classe: str, origem_principal: str) -> str:
    """Classificacao efetiva para a ENG de rede do Nordeste (nao altera ``classe``).

    - ``intercâmbio nomeado``: limites de intercambio (FNESE, FNS+FNESE, FNEN e equivalentes);
    - ``corredor de exportação``: elemento nomeado (LT/SE/TR/bipolo) com origem predominante
      sistemica; na janela, sao elementos fora do Nordeste ou na sua fronteira (Rio Novo do
      Sul, Itabira, Campos, Pocoes III/Padre Paraiso, Colinas/Ribeiro Goncalves);
    - ``local NE``: elemento nomeado com origem predominante local;
    - ``outro``: o restante (sem elemento, desligamentos, frequencia).
    """
    if classe == "exportacao":
        return "intercâmbio nomeado"
    if classe == "local" and origem_principal == "sistemica":
        return "corredor de exportação"
    if classe == "local" and origem_principal == "local":
        return "local NE"
    return "outro"
