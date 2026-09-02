"""Descoberta de recursos na API CKAN do ONS e download com cache local.

Regras (spec v2, secao 2): descoberta sempre pela API CKAN (nunca URL fixa),
preferencia por PARQUET com fallback para CSV, cache em
``data/raw/<dataset>/<AAAA_MM>.<ext>`` e sobrescrita apenas com ``forcar``.
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import requests

log = logging.getLogger(__name__)

CKAN_PACKAGE_SHOW = "https://dados.ons.org.br/api/3/action/package_show"

# fonte -> id do pacote CKAN (agregado por usina/conjunto, semi-horario)
DATASETS: dict[str, str] = {
    "EOL": "restricao_coff_eolica_usi",
    "UFV": "restricao_coff_fotovoltaica",
}

FORMATOS_PREFERIDOS: tuple[str, ...] = ("PARQUET", "CSV")
_PERIODO_RE = re.compile(r"_(20\d{2})_(\d{2})\.(parquet|csv)$", re.IGNORECASE)
_TIMEOUT = 120


@dataclass(frozen=True)
class Recurso:
    """Um arquivo mensal publicado no portal."""

    fonte: str
    dataset: str
    periodo: str  # AAAA_MM
    formato: str  # PARQUET | CSV
    url: str

    @property
    def nome_local(self) -> str:
        return f"{self.periodo}.{self.formato.lower()}"


def normalizar_periodo(texto: str | None) -> str | None:
    """Aceita ``AAAA-MM`` ou ``AAAA_MM`` e devolve ``AAAA_MM``; ``None`` passa."""
    if texto is None:
        return None
    m = re.fullmatch(r"(20\d{2})[-_](\d{2})", texto.strip())
    if not m:
        raise ValueError(f"periodo invalido: {texto!r} (use AAAA-MM)")
    return f"{m.group(1)}_{m.group(2)}"


def consultar_pacote(dataset: str, sessao: requests.Session | None = None) -> dict:
    """Chama ``package_show`` e devolve o campo ``result``."""
    s = sessao or requests.Session()
    resp = s.get(CKAN_PACKAGE_SHOW, params={"id": dataset}, timeout=_TIMEOUT)
    resp.raise_for_status()
    corpo = resp.json()
    if not corpo.get("success"):
        raise RuntimeError(f"CKAN devolveu success=false para {dataset}")
    return corpo["result"]


def selecionar_mensais(
    pacote: dict, fonte: str, desde: str | None = None, ate: str | None = None
) -> list[Recurso]:
    """Escolhe um recurso por mes dentro da janela, no melhor formato disponivel."""
    dataset = pacote["name"]
    por_periodo: dict[str, dict[str, str]] = {}
    for r in pacote.get("resources", []):
        formato = str(r.get("format", "")).upper()
        if formato not in FORMATOS_PREFERIDOS:
            continue
        m = _PERIODO_RE.search(r.get("url", ""))
        if not m:
            continue
        periodo = f"{m.group(1)}_{m.group(2)}"
        por_periodo.setdefault(periodo, {})[formato] = r["url"]

    escolhidos: list[Recurso] = []
    for periodo in sorted(por_periodo):
        if desde and periodo < desde:
            continue
        if ate and periodo > ate:
            continue
        formatos = por_periodo[periodo]
        formato = next(f for f in FORMATOS_PREFERIDOS if f in formatos)
        escolhidos.append(Recurso(fonte, dataset, periodo, formato, formatos[formato]))
    return escolhidos


def url_dicionario_json(pacote: dict) -> str | None:
    """URL do dicionario de dados em JSON, se publicado."""
    for r in pacote.get("resources", []):
        if str(r.get("format", "")).upper() == "JSON" and "icionario" in str(r.get("name", "")):
            return r["url"]
    return None


def baixar_arquivo(
    url: str, destino: Path, forcar: bool = False, sessao: requests.Session | None = None
) -> bool:
    """Baixa ``url`` para ``destino`` (atomico). Devolve True se baixou, False se usou cache."""
    if destino.exists() and not forcar:
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    s = sessao or requests.Session()
    temporario = destino.with_suffix(destino.suffix + ".parcial")
    with s.get(url, stream=True, timeout=_TIMEOUT) as resp:
        resp.raise_for_status()
        with temporario.open("wb") as f:
            for pedaco in resp.iter_content(chunk_size=1 << 20):
                f.write(pedaco)
    temporario.replace(destino)
    return True


def _baixar_um(rec: Recurso, pasta: Path, forcar: bool) -> tuple[Recurso, Path, bool]:
    destino = pasta / rec.nome_local
    baixou = baixar_arquivo(rec.url, destino, forcar, requests.Session())
    log.info("%s %s %s (%s)", rec.fonte, rec.periodo, "baixado" if baixou else "cache", rec.formato)
    return rec, destino, baixou


def baixar_janela(
    pasta_raw: Path,
    fontes: tuple[str, ...] = ("EOL", "UFV"),
    desde: str | None = "2023-01",
    ate: str | None = None,
    forcar: bool = False,
    paralelismo: int = 4,
) -> dict[str, list[tuple[Recurso, Path, bool]]]:
    """Descobre e baixa todos os meses da janela para cada fonte.

    Devolve, por fonte, a lista ``(recurso, caminho_local, baixado_agora)``.
    Tambem grava o dicionario JSON de cada pacote em ``<dataset>/dicionario.json``.
    """
    desde_n = normalizar_periodo(desde)
    ate_n = normalizar_periodo(ate)
    sessao = requests.Session()
    resultado: dict[str, list[tuple[Recurso, Path, bool]]] = {}
    for fonte in fontes:
        dataset = DATASETS[fonte]
        pacote = consultar_pacote(dataset, sessao)
        pasta = pasta_raw / dataset
        url_dic = url_dicionario_json(pacote)
        if url_dic:
            baixar_arquivo(url_dic, pasta / "dicionario.json", forcar, sessao)
        recursos = selecionar_mensais(pacote, fonte, desde_n, ate_n)

        with ThreadPoolExecutor(max_workers=paralelismo) as executor:
            itens = list(executor.map(partial(_baixar_um, pasta=pasta, forcar=forcar), recursos))
        resultado[fonte] = itens
    return resultado


def gerar_dicionario_md(pasta_raw: Path, destino: Path) -> str:
    """Gera ``docs/dicionario.md`` a partir dos JSON do portal e da tabela de categorias."""
    from coff.categorias import ORIGENS, tabela_categorias

    partes = [
        "# Dicionario de dados\n",
        "Gerado automaticamente a partir dos recursos `DicionarioDados_*.json` do portal de",
        "dados abertos do ONS (campo `dicionario_simplificado`). Nao editar a mao.\n",
    ]
    for fonte, dataset in DATASETS.items():
        caminho = pasta_raw / dataset / "dicionario.json"
        partes.append(f"## `{dataset}` ({fonte})\n")
        if not caminho.exists():
            partes.append("_dicionario nao encontrado no cache_\n")
            continue
        dic = json.loads(caminho.read_text(encoding="utf-8"))
        partes.append(f"Titulo: `{dic.get('titulo', '')}`\n")
        partes.append("| coluna | descricao |\n|---|---|")
        for item in dic.get("dicionario_simplificado", []):
            desc = str(item.get("descricao", "")).replace("|", "/").replace("\n", " ")
            partes.append(f"| `{item.get('codigo', '')}` | {desc} |")
        partes.append("")
    partes.append("## Codigos de razao -> categoria (tabela usada pelo pacote)\n")
    partes.append("| codigo | categoria | descricao no dicionario ONS | definicao operativa |")
    partes.append("|---|---|---|---|")
    for _, linha in tabela_categorias().iterrows():
        partes.append(
            f"| {linha.codigo} | {linha.categoria} | {linha.descricao_ons} | "
            f"{linha.definicao_operativa} |"
        )
    partes.append("\n## Codigos de origem\n")
    partes.append("| codigo | origem |\n|---|---|")
    partes.extend(f"| {k} | {v} |" for k, v in ORIGENS.items())
    texto = "\n".join(partes) + "\n"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return texto
