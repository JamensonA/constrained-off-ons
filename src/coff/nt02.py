"""Extracao das tabelas da NT-ONS DPL 0083/2026 (NT 02 da 1a Temporada de Acesso 2026).

Etapa 2 do cruzamento por ponto de conexao. O PDF publico e baixado para
``data/externo/`` (gitignored); o texto e extraido sem dependencias externas
(descompressao dos streams FlateDecode com ``zlib``) e as tabelas 4-2 (barramentos
candidatos do segmento geracao), 4-3 (LRCAP 2026) e as tabelas de "Capacidade
Remanescente e Fatores Limitantes" da secao 6 sao lidas por regex.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

URL_NT02 = (
    "https://www.ons.org.br/AcervoDigitalDocumentosEPublicacoes/NT-ONS%20DPL%200083-2026-PNAST.pdf"
)
ANOS: tuple[str, ...] = ("2027", "2028", "2029", "2030", "2031")
UF_POR_NOME = {
    "Rio Grande do Sul": "RS",
    "Paraná": "PR",
    "Mato Grosso do Sul": "MS",
    "São Paulo": "SP",
    "Rio de Janeiro": "RJ",
    "Minas Gerais": "MG",
    "Goiás": "GO",
    "Bahia e Sergipe": "BA/SE",
    "Alagoas": "AL",
    "Pernambuco": "PE",
    "Paraíba": "PB",
    "Rio Grande do Norte": "RN",
    "Piauí": "PI",
    "Pará": "PA",
}
FATOR_INTERCAMBIO = "limites de intercâmbio ou de fluxo"


def extrair_texto(caminho_pdf: Path) -> str:
    """Texto dos operadores Tj/TJ de todos os streams do PDF (sem dependencias externas)."""
    data = Path(caminho_pdf).read_bytes()
    partes: list[bytes] = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        bruto = m.group(1)
        try:
            dec = zlib.decompress(bruto)
        except Exception:
            try:
                dec = zlib.decompressobj().decompress(bruto)
            except Exception:
                continue
        if b"BT" not in dec:
            continue
        for t in re.finditer(rb"\[(.*?)\]\s*TJ|\((.*?)\)\s*Tj", dec, re.S):
            if t.group(1) is not None:
                partes.append(b"".join(re.findall(rb"\((.*?)(?<!\\)\)", t.group(1), re.S)))
            else:
                partes.append(t.group(2))
        partes.append(b"\n")
    texto = b"".join(partes).decode("latin-1", "replace")
    return texto.replace("\\(", "(").replace("\\)", ")")


def _chave_sigla(sigla: str) -> str:
    """Chave de casamento entre tabelas: sem espacos, hifens ou underscores, em maiusculas."""
    return re.sub(r"[\s\-–_]+", "", str(sigla)).upper()


def _numero(token: str) -> float | None:
    token = token.strip().replace(".", "").replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


_LINHA_4X = re.compile(
    r"\b([A-Z]{2})\s+(.+?)\s*\(([^()]+)\)\s+(\d{3})\s+"
    r"([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)"
)


def _parse_tabela_must(trecho: str, lrcap: bool) -> list[dict]:
    linhas = []
    trecho = re.sub(r"\s+", " ", trecho)
    trecho = trecho.split("2027 2028 2029 2030 2031", 1)[-1]
    for m in _LINHA_4X.finditer(trecho):
        uf, nome, sigla, tensao, *must = m.groups()
        # "Campo Formoso II  Barra II C1" aparece sem sigla em algumas tabelas; normaliza espacos
        nome = re.sub(r"\s+", " ", nome).strip(" -–")
        linhas.append(
            {
                "uf": uf,
                "barramento": nome,
                "sigla": sigla.strip(),
                "tensao_kv": int(tensao),
                **{f"must_{ano}": _numero(v) for ano, v in zip(ANOS, must, strict=True)},
                "lrcap": lrcap,
            }
        )
    return linhas


def tabelas_4_2_e_4_3(texto: str) -> pd.DataFrame:
    """Barramentos candidatos do segmento geracao (4-2) e LRCAP 2026 (4-3), com MUST por ano."""
    i = texto.find("Tabela 4-2 apresenta")
    j = texto.find("4.3", i)
    k = texto.find("pt-BR5 ", j)
    if min(i, j, k) < 0:
        raise ValueError("nao encontrei as tabelas 4-2/4-3 no texto da NT 02")
    linhas = _parse_tabela_must(texto[i:j], lrcap=False) + _parse_tabela_must(
        texto[j:k], lrcap=True
    )
    return pd.DataFrame(linhas)


_TITULO_6 = re.compile(
    r"Tabela (6-\d+): Segmento Geração( para Usinas do LRCAP 2026)?\s+Capacidade Remanescente e "
    r"Fatores Limitantes (?:d[aeo]s? )?(.*?)\s+Produto (\d{4}\+?)"
)
_CABECALHO_6 = "BARRAMENTO SUBÁREA ÁREA BARRAMENTO SUBÁREA ÁREA"
_NOME = r"[A-ZÁ-Ú][^().]{0,60}?"
_LINHA_6 = re.compile(
    rf"(?:SE\s+)?({_NOME})\s*\(([^()]+)\)\s+(\d{{3}})\s+(.*?)"
    rf"(?=(?:SE\s+)?{_NOME}\s*\([^()]+\)\s+\d{{3}}\s|ONS NT-ONS|Tabela 6-|$)",
    re.S,
)


def _capacidade_e_fator(resto: str) -> tuple[float | None, float | None, float | None, str]:
    """Separa os 3 valores de capacidade (barramento, subarea, area) do texto do fator."""
    tokens = resto.split()
    valores: list[float | None] = []
    idx = 0
    while idx < len(tokens) and len(valores) < 3:
        tok = tokens[idx]
        if re.fullmatch(r"[\d.,]+", tok):
            # "79, 024" quebrado em dois tokens
            if (
                tok.endswith(",")
                and idx + 1 < len(tokens)
                and re.fullmatch(r"\d+", tokens[idx + 1])
            ):
                tok = tok + tokens[idx + 1]
                idx += 1
            valores.append(_numero(tok))
            idx += 1
        elif re.fullmatch(r"[A-Z0-9_]+\+[A-Z0-9_]+|\+|[A-Z0-9_]+_\d{3}", tok):
            # limite compartilhado, ex.: "100 ALE2_230 + LIV3_230": conta como texto, nao numero
            idx += 1
        else:
            break
    fator = " ".join(tokens[idx:]).strip()
    fator = re.sub(r"\s+ONS NT-ONS DPL.*$", "", fator).strip()
    while len(valores) < 3:
        valores.append(None)
    return valores[0], valores[1], valores[2], fator


def tabelas_secao_6(texto: str) -> pd.DataFrame:
    """Uma linha por (tabela, barramento): capacidade remanescente e fator limitante."""
    ini = texto.find("pt-BR6  A seguir")
    sec6 = texto[ini:] if ini >= 0 else texto
    titulos = list(_TITULO_6.finditer(sec6))
    linhas = []
    for n, m in enumerate(titulos):
        fim = titulos[n + 1].start() if n + 1 < len(titulos) else len(sec6)
        corpo = sec6[m.end() : fim]
        c = corpo.find(_CABECALHO_6)
        if c < 0:
            continue
        corpo = re.sub(r"\s+", " ", corpo[c + len(_CABECALHO_6) :])
        corpo = re.split(r"\s+ONS NT-ONS DPL 0083/2026", corpo)[0]
        corpo = re.split(r"\s+pt-BR6\.", corpo)[0]
        for lm in _LINHA_6.finditer(corpo):
            nome, sigla, tensao, resto = lm.groups()
            cap_b, cap_s, cap_a, fator = _capacidade_e_fator(resto)
            linhas.append(
                {
                    "tabela": m.group(1),
                    "lrcap": bool(m.group(2)),
                    "regiao": m.group(3).strip(),
                    "produto": m.group(4),
                    "barramento": re.sub(r"\s+", " ", nome).strip(" -–"),
                    "sigla": sigla.strip(),
                    "tensao_kv": int(tensao),
                    "cap_rem_barramento": cap_b,
                    "cap_rem_subarea": cap_s,
                    "cap_rem_area": cap_a,
                    "fator_limitante": fator,
                }
            )
    return pd.DataFrame(linhas)


_ELEMENTO_FATOR = re.compile(
    r"\b(LTs?|SE|TR|bipolos?|elos?|rede)\s+(?:de\s+)?(\d{2,3}\s*kV\s+)?(?:da\s+malha\s+)?"
    r"([A-ZÁ-Ú][\wÁ-Úá-ú.]*(?:\s+(?:[A-ZÁ-Ú0-9][\wÁ-Úá-ú.]*|\b(?:de|do|da|dos|das)\b|[-–]|/))*)",
    re.I,
)


def elementos_do_fator(fator: str) -> str:
    """Elementos de rede citados no fator limitante (LT/SE/TR), separados por '; '."""
    if not fator:
        return ""
    if FATOR_INTERCAMBIO in fator.lower():
        return "limites de intercâmbio/fluxo (exportação do Nordeste)"
    achados = []
    for m in _ELEMENTO_FATOR.finditer(fator):
        el = f"{m.group(1)} {(m.group(2) or '').strip()} {m.group(3)}".strip()
        el = re.sub(r"\s+", " ", el)
        el = re.sub(r"\s+(?:na|em|no|para|seguidas|após)\b.*$", "", el).rstrip(" .")
        if el not in achados:
            achados.append(el)
    return "; ".join(achados)


def resultado_de(must_2031: float | None, cap_b: float | None, fator: str, lrcap: bool) -> str:
    """AD / ADVC / PC / INAB a partir de capacidade remanescente 2031 e do fator limitante."""
    f = (fator or "").lower()
    if cap_b is None:
        return "PC" if "+" in f or "compartilh" in f else "INAB"
    if cap_b <= 0:
        return "INAB"
    if "configuração" in f or "condicionad" in f:
        return "ADVC"
    if must_2031 is not None and cap_b + 1e-6 < must_2031:
        return "PC"
    return "AD"


@dataclass
class ResultadoNT02:
    barramentos: pd.DataFrame
    validacao: pd.DataFrame
    divergencias: list[str] = field(default_factory=list)


def consolidar(texto: str, infografico: pd.DataFrame | None = None) -> ResultadoNT02:
    """Tabela final por barramento (geracao + LRCAP) e validacao do INAB por UF."""
    base = tabelas_4_2_e_4_3(texto)
    sec6 = tabelas_secao_6(texto)
    # ultimo produto disponivel por sigla (2031, senao o mais recente)
    ordem = {a: i for i, a in enumerate(ANOS)}
    sec6["_ordem"] = sec6["produto"].str.replace("+", "").map(ordem).fillna(-1)
    sec6["_chave"] = sec6["sigla"].map(_chave_sigla)
    ultimo = sec6.sort_values("_ordem").drop_duplicates("_chave", keep="last").set_index("_chave")
    linhas = []
    for _, b in base.iterrows():
        chave = _chave_sigla(b["sigla"])
        u = ultimo.loc[chave] if chave in ultimo.index else None
        fator = str(u["fator_limitante"]) if u is not None else ""
        cap_b = (
            float(u["cap_rem_barramento"])
            if u is not None and pd.notna(u["cap_rem_barramento"])
            else None
        )
        cap_s = (
            float(u["cap_rem_subarea"])
            if u is not None and pd.notna(u["cap_rem_subarea"])
            else None
        )
        cap_a = float(u["cap_rem_area"]) if u is not None and pd.notna(u["cap_rem_area"]) else None
        linhas.append(
            {
                **{k: b[k] for k in b.index},
                "produto_ref": str(u["produto"]) if u is not None else "",
                "cap_rem_2031_barramento": cap_b,
                "cap_rem_2031_subarea": cap_s,
                "cap_rem_2031_area": cap_a,
                "resultado": resultado_de(b["must_2031"], cap_b, fator, bool(b["lrcap"])),
                "fator_limitante": fator,
                "elementos_citados": elementos_do_fator(fator),
            }
        )
    tab = pd.DataFrame(linhas)
    tab["inab_mw"] = tab["must_2031"].where(tab["resultado"] == "INAB", 0.0)
    val = tab.groupby("uf")["inab_mw"].sum().rename("inab_nt_mw").reset_index()
    divergencias: list[str] = []
    if infografico is not None:
        info = infografico.copy()
        info["uf"] = info["uf"].astype(str).str.upper()
        info["inab_mw"] = pd.to_numeric(info["inab_mw"], errors="coerce").fillna(0.0)
        val = val.merge(
            info[["uf", "inab_mw"]].rename(columns={"inab_mw": "inab_infografico_mw"}),
            on="uf",
            how="outer",
        )
        val = val.fillna({"inab_nt_mw": 0.0, "inab_infografico_mw": 0.0})
        val["dif_mw"] = val["inab_nt_mw"] - val["inab_infografico_mw"]
        for _, r in val.iterrows():
            if abs(r["dif_mw"]) > 0.5:
                divergencias.append(
                    f"{r['uf']}: NT {r['inab_nt_mw']:.1f} MW vs infográfico "
                    f"{r['inab_infografico_mw']:.1f} MW (dif {r['dif_mw']:+.1f})"
                )
    return ResultadoNT02(tab, val.sort_values("uf").reset_index(drop=True), divergencias)
