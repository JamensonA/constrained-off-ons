"""Etapa 2 do cruzamento por PAC: barramentos e fatores limitantes da NT-ONS DPL 0083/2026.

Baixa o PDF publico (se ainda nao estiver em ``data/externo/``), extrai o texto, le as
tabelas e grava ``docs/nt02_barramentos_geracao.csv``; valida o INAB por UF contra a
transcricao do infografico (``docs/temporada_acesso_2026_nt02.csv``), que ganha as colunas
``fonte`` e ``inab_mw_nt`` (os valores originais nao sao alterados aqui).

Uso: ``python scripts/extrair_nt02.py``
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import pandas as pd  # noqa: E402

from coff import nt02  # noqa: E402
from coff.download import baixar_arquivo  # noqa: E402

log = logging.getLogger("coff.nt02")
COLUNAS = [
    "uf",
    "barramento",
    "sigla",
    "tensao_kv",
    "must_2027",
    "must_2028",
    "must_2029",
    "must_2030",
    "must_2031",
    "cap_rem_2031_barramento",
    "cap_rem_2031_subarea",
    "cap_rem_2031_area",
    "resultado",
    "fator_limitante",
    "elementos_citados",
    "lrcap",
    "produto_ref",
]


def _tabela_md(tab: pd.DataFrame) -> list[str]:
    cols = [str(c) for c in tab.columns]
    linhas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in tab.iterrows():
        linhas.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return linhas


def _substituir_bloco(caminho: Path, nome: str, conteudo: str) -> None:
    ini, fim = f"<!-- {nome}:inicio -->", f"<!-- {nome}:fim -->"
    texto = caminho.read_text(encoding="utf-8")
    a, b = texto.find(ini), texto.find(fim)
    if a < 0 or b < 0:
        raise ValueError(f"marcadores {nome} nao encontrados em {caminho}")
    caminho.write_text(texto[: a + len(ini)] + "\n" + conteudo + "\n" + texto[b:], encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    externo = RAIZ / "data" / "externo"
    pdf = externo / "NT-ONS-DPL-0083-2026-PNAST.pdf"
    if baixar_arquivo(nt02.URL_NT02, pdf):
        log.info("PDF baixado para %s", pdf)
    texto = nt02.extrair_texto(pdf)
    (externo / "nt02.txt").write_text(texto, encoding="utf-8")
    docs = RAIZ / "docs"
    info_path = docs / "temporada_acesso_2026_nt02.csv"
    info = pd.read_csv(info_path)
    res = nt02.consolidar(texto, info)
    tab = res.barramentos[COLUNAS]
    tab.to_csv(docs / "nt02_barramentos_geracao.csv", index=False)

    # infografico: onde o INAB diverge, a NT prevalece; o valor transcrito fica em
    # inab_mw_infografico e a coluna fonte registra a origem do valor de referencia
    val = res.validacao.set_index("uf")
    if "inab_mw_infografico" not in info.columns:
        info["inab_mw_infografico"] = info["inab_mw"]
    info["inab_mw_nt"] = info["uf"].map(val["inab_nt_mw"]).round(2)
    divergente = (info["inab_mw_infografico"].fillna(0) - info["inab_mw_nt"].fillna(0)).abs() > 0.5
    info["inab_mw"] = info["inab_mw_infografico"].where(~divergente, info["inab_mw_nt"])
    info["fonte"] = "infografico NT 02 (extrato 01/09/2026)"
    info.loc[divergente, "fonte"] = "NT-ONS DPL 0083/2026, tabelas 4-2 e 5-9 (NT prevalece)"
    info = info[
        ["uf", "ad_mw", "advc_mw", "pc_mw", "inab_mw", "inab_mw_infografico", "inab_mw_nt", "fonte"]
    ]
    info.to_csv(info_path, index=False)

    md = tab[
        [
            "uf",
            "barramento",
            "tensao_kv",
            "must_2031",
            "cap_rem_2031_barramento",
            "resultado",
            "lrcap",
            "fator_limitante",
        ]
    ].copy()
    md["fator_limitante"] = md["fator_limitante"].str.slice(0, 110)
    md["lrcap"] = md["lrcap"].map({True: "sim", False: ""})
    md.columns = [
        "UF",
        "barramento",
        "kV",
        "MUST 2031",
        "cap. rem. 2031",
        "resultado",
        "LRCAP",
        "fator limitante",
    ]
    valid = res.validacao.round(1)
    valid.columns = ["UF", "INAB NT (MW)", "INAB infografico (MW)", "dif (MW)"]
    texto_md = (
        f"{len(tab)} barramentos do segmento geracao ({int(tab['lrcap'].sum())} do LRCAP 2026). "
        f"Resultado: {tab['resultado'].value_counts().to_dict()}.\n\n"
        + "\n".join(_tabela_md(md))
        + "\n\n**Validacao do INAB por UF (NT x infografico)**\n\n"
        + "\n".join(_tabela_md(valid[valid.iloc[:, 1:3].sum(axis=1) > 0]))
        + "\n\nDivergencias: "
        + ("; ".join(res.divergencias) if res.divergencias else "nenhuma")
        + "."
    )
    _substituir_bloco(docs / "metodologia.md", "nt02", texto_md)
    log.info("%d barramentos; divergencias INAB: %s", len(tab), res.divergencias or "nenhuma")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
