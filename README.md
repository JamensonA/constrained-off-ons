# constrained-off-ons

*A small, reproducible descriptive analysis of curtailment ("constrained-off") of wind and solar plants in Brazil, built only on ONS open data: explicit qualification rules, every discarded record counted, and a sensitivity check on the choice of reference generation.*

Análise descritiva reproduzível do constrained-off (energia não gerada — ENG) de usinas eólicas e fotovoltaicas do SIN, usando exclusivamente os dados abertos do ONS.

> O dado de constrained-off do ONS só vira informação quando a regra de qualificação é explícita — este repositório fixa a regra, conta tudo o que descarta e mostra quanto o resultado muda com a escolha da referência.

## O problema

_(a preencher no Gate 4 — 4 linhas: o que é constrained-off, por que importa, o que o ONS publica, o que este repositório faz.)_

## Resultados

_(5 figuras, cada uma com uma frase de leitura escrita pelo autor no Gate 4.)_

| | |
|---|---|
| `docs/figuras/fig1_eng_mensal.png` | ENG mensal por fonte |
| `docs/figuras/fig2_eng_por_categoria.png` | ENG mensal por categoria de restrição |
| `docs/figuras/fig3_top_usinas.png` | 15 usinas/conjuntos com maior ENG e taxa de corte |
| `docs/figuras/fig4_perfil_hora_mes.png` | perfil hora do dia × mês |
| `docs/figuras/fig5_top_descricoes.png` | 15 descrições de restrição com maior ENG |

## Método

_(5 a 8 linhas no Gate 4: fontes, janela, qualificação — ver `docs/metodologia.md` —, definição de ENG, sensibilidade.)_

Nota de terminologia: **ENG ≡ GNR** (geração não realizada) dos documentos anteriores.

## Reproduzir

Requisitos: Python ≥ 3.11 e `git`. Dois caminhos equivalentes para o ambiente — escolha um:

```bash
# (a) venv padrão da biblioteca do Python
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

```bash
# (b) uv (instala o Python 3.12 se necessário)
uv venv --python 3.12 .venv && source .venv/bin/activate && uv pip install -e ".[dev]"
```

Depois, em qualquer dos dois casos:

```bash
python scripts/rodar.py --desde 2023-01      # baixa, qualifica, calcula e gera figuras/CSVs
jupyter notebook notebooks/01_exploracao.ipynb
```

## Limitações

_(texto do autor no Gate 4.)_

## Próximos passos

_(lista curta; ver issues do repositório.)_

## Autor

Jamenson Alves Júnior — UFPE. Licença MIT.
