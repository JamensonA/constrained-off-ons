# constrained-off-ons

*A small, reproducible descriptive analysis of curtailment ("constrained-off") of wind and solar plants in Brazil, built only on ONS open data: explicit qualification rules, every discarded record counted, and a sensitivity check on the choice of reference generation.*

Análise descritiva reproduzível do constrained-off (energia não gerada — ENG) de usinas eólicas e fotovoltaicas do SIN, usando exclusivamente os dados abertos do ONS.

## O problema

Constrained-off é o corte de geração eólica e solar determinado pelo ONS por restrições do sistema: energética, de confiabilidade ou elétrica. O ONS publica os registros semi-horários por usina nos dados abertos, mas o dado bruto só vira informação quando a regra de qualificação é explícita: o que conta como restrição, qual referência define a energia não gerada e o que é descartado. Este repositório fixa essa regra, conta tudo o que exclui e mostra quanto o resultado muda com a escolha da referência.

## Resultados

Janela 2023-01 → 2026-08 (eólica) e 2024-04 → 2026-08 (fotovoltaica), referência efetiva `coalesce(referência final, referência)`.

![ENG mensal por fonte](docs/figuras/fig1_eng_mensal.png)

**Fig. 1** — A energia não gerada saltou de 3,2 TWh em 2023 para 25,4 TWh em 2025 na eólica; a taxa de corte foi de 3,3% para 18,6% no mesmo período, e a FV já corta um quarto do que poderia gerar.

![ENG mensal por categoria](docs/figuras/fig2_eng_por_categoria.png)

**Fig. 2** — A razão energética (controle carga-frequência, sistêmica) domina o volume; confiabilidade e elétrica são menores em energia, mas são as que dependem da rede local — e as únicas que a expansão da transmissão resolve.

![Top 15 usinas](docs/figuras/fig3_top_usinas.png)

**Fig. 3** — O corte é concentrado: um único conjunto FV acumula 1,9 TWh, com 25,7% de taxa de corte. A taxa de corte separa usinas mal posicionadas de usinas grandes.

![Perfil hora do dia × mês](docs/figuras/fig4_perfil_hora_mes.png)

**Fig. 4** — Desde maio de 2025 o corte se concentra entre 8h e 14h: é a assinatura do excesso de geração no meio do dia, quando solar e eólica coincidem com carga baixa.

![Top 15 descrições de restrição](docs/figuras/fig5_top_descricoes.png)

**Fig. 5** — Desde que o ONS passou a descrever as restrições (set/2025), "Controle de frequência do SIN" responde sozinho pela maior parte da energia cortada; as demais descrições nomeiam linhas e fluxos específicos, e são o mapa dos gargalos.

Tabelas: [`docs/resumo_anual.csv`](docs/resumo_anual.csv) (ano × fonte: ENG, energia gerada, taxa de corte), [`docs/top_usinas.csv`](docs/top_usinas.csv), [`docs/top_descricoes.csv`](docs/top_descricoes.csv), [`docs/eng_por_subsistema.csv`](docs/eng_por_subsistema.csv), [`docs/sensibilidade_referencia.csv`](docs/sensibilidade_referencia.csv), [`docs/validacao_externa.csv`](docs/validacao_externa.csv).

## Método

1. **Fontes**: pacotes CKAN `restricao_coff_eolica_usi` e `restricao_coff_fotovoltaica` do Portal de Dados Abertos do ONS (agregados por usina/conjunto, semi-horários), descobertos pela API e baixados em Parquet com cache local; dicionário de dados gerado do JSON do portal ([`docs/dicionario.md`](docs/dicionario.md)).
2. **Carga**: validação das 16 colunas, Δt inferido dos dados (30 min), leitura estrita com contagem de linhas malformadas ([`docs/relatorio_carga.md`](docs/relatorio_carga.md)).
3. **Qualificação**: regras R1–R12 explícitas — restrito = código de razão presente; código ∈ {ENE, CNF, REL, PAR}; chave (`id_ons`, instante); nada é descartado em silêncio, cada motivo e flag é contado ([`docs/metodologia.md`](docs/metodologia.md), [`docs/relatorio_qualificacao.md`](docs/relatorio_qualificacao.md)).
4. **ENG** por registro = max(referência efetiva − geração, 0) × 0,5 h; energia gerada = geração × 0,5 h; taxa de corte = ENG ÷ (ENG + energia gerada). Nota de terminologia: **ENG ≡ GNR** (geração não realizada) dos documentos anteriores.
5. **Sensibilidade**: a referência final só existe para REL; usá-la (coalesce) em vez da referência reduz a ENG elétrica em 21% (eólica) e 14% (FV) e não altera ENE nem CNF.
6. **Validação**: a energia não gerada por razão energética em 2024 (4.330 GWh) coincide com o valor publicado pelo ONS no RT DGL-ONS 0189/2025. A série mensal de GNR% (eólica + FV) reproduz a curva apresentada pelo ONS em out/2025 com correlação 0,996 e erro absoluto médio de 0,37 p.p. em 33 meses. A coincidência em ENE é esperada, a referência final não afeta essa categoria, portanto valida a ingestão e a qualificação, não a escolha da referência para REL, onde a sensibilidade é de −21% (eólica) e −14% (FV).

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
python scripts/rodar.py --desde 2023-01      # baixa (~360 MB), qualifica, calcula e gera figuras/CSVs
jupyter notebook notebooks/01_exploracao.ipynb
```

Opções: `--referencia referencia` (sem a referência final), `--excluir-disp-zero`, `--ate AAAA-MM`, `--fontes EOL`, `--forcar` (rebaixa o cache), `--sem-download`. Testes: `pytest`; lint: `ruff check .`.

## Limitações

Os dados são sujeitos a reconsistência pelo ONS após a publicação. A apuração regulatória (REN ANEEL 1.030/2022) não é reproduzida: não há franquias, nem regras de elegibilidade por usina. Conjuntos (Tipo II-C) não são desagregados por usina. `dsc_restricao` só é preenchida desde set/2025. O código PAR consta do dicionário e não ocorre em nenhum dos 73 meses. Na eólica, usinas entram e saem do dataset ao longo da janela.

## Próximos passos

1. Desagregar conjuntos por usina com os datasets `*_detail` (proporção da geração estimada) e usar a flag de dado inválido.
2. Auditar a coerência da classificação do ONS contra as diretrizes de operação, com reclassificação.
3. Comparar usinas da mesma região / ponto de conexão.
4. Cruzar com carga, intercâmbios e reanálise meteorológica (ERA5).
5. Valorar a ENG (PLD) e dimensionar armazenamento (BESS).
6. Modelo preditivo de probabilidade de constrained-off por usina e hora.

## Autor

Jamenson Alves Júnior — UFPE. Licença MIT.
