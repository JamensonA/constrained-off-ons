"""Tabela de codigos de razao/origem da restricao -> categoria.

A fonte e o dicionario de dados do portal de dados abertos do ONS (recurso
``DicionarioDados_*.json`` de cada pacote CKAN). As definicoes operativas vem da
revisao da Fase A (spec v2, secao 2). Nada aqui e rotulo fixo de figura: as
figuras e metricas consultam esta tabela.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Categoria:
    """Uma categoria de razao de restricao."""

    codigo: str
    categoria: str
    descricao_ons: str
    definicao_operativa: str


CATEGORIAS: tuple[Categoria, ...] = (
    Categoria(
        "ENE",
        "energetica",
        "Razao energetica",
        "controle carga-frequencia do SIN; restricao sistemica",
    ),
    Categoria(
        "CNF",
        "confiabilidade",
        "Razao de atendimento a requisitos de confiabilidade",
        "limites de intercambio e inequacoes operativas",
    ),
    Categoria(
        "REL",
        "eletrica",
        "Razao de indisponibilidade externa (eletrica)",
        "indisponibilidade externa a usina (criterio N-1)",
    ),
    Categoria(
        "PAR",
        "parecer de acesso",
        "Restricao indicada no parecer de acesso",
        "restricao indicada no parecer de acesso; sem ocorrencias em jul/2026",
    ),
)

ORIGENS: dict[str, str] = {"LOC": "local", "SIS": "sistemica"}

CODIGOS_CONHECIDOS: frozenset[str] = frozenset(c.codigo for c in CATEGORIAS)
ORIGENS_CONHECIDAS: frozenset[str] = frozenset(ORIGENS)

# ordem canonica de exibicao (figuras, tabelas)
ORDEM_CATEGORIAS: tuple[str, ...] = tuple(c.categoria for c in CATEGORIAS)

_POR_CODIGO = {c.codigo: c for c in CATEGORIAS}


def normalizar_codigo(valor: object) -> str | None:
    """Remove espacos e poe em maiusculas; nulo/vazio vira ``None``."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip().upper()
    return texto or None


def categoria_de(codigo: object) -> str | None:
    """Categoria de um codigo de razao (``None`` se desconhecido ou nulo)."""
    chave = normalizar_codigo(codigo)
    if chave is None:
        return None
    cat = _POR_CODIGO.get(chave)
    return cat.categoria if cat else None


def origem_de(codigo: object) -> str | None:
    """Nome da origem (``local``/``sistemica``) ou ``None``."""
    chave = normalizar_codigo(codigo)
    return ORIGENS.get(chave) if chave else None


def tabela_categorias() -> pd.DataFrame:
    """Tabela codigo -> categoria, para docs e relatorios."""
    return pd.DataFrame(
        [
            {
                "codigo": c.codigo,
                "categoria": c.categoria,
                "descricao_ons": c.descricao_ons,
                "definicao_operativa": c.definicao_operativa,
            }
            for c in CATEGORIAS
        ]
    )
