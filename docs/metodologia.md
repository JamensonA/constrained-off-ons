# Metodologia

Documento vivo: preenchido gate a gate (G1 carga, G2 qualificacao, G3 metricas/sensibilidade, G4 validacao externa).

## Fontes e janela

- Portal de dados abertos do ONS, pacotes CKAN `restricao_coff_eolica_usi` (EOL) e `restricao_coff_fotovoltaica` (UFV): dados **agregados por usina/conjunto**, semi-horarios (delta t = 30 min, inferido e verificado na carga).
- Janela: 2023-01 ate o ultimo mes publicado (EOL 2023_01→2026_08, 44 meses; UFV 2024_04→2026_08, 29 meses). Detalhes em `relatorio_carga.md`.

## Qualificacao (regras R1–R12)

Implementadas em `src/coff/qualificar.py` exatamente como escritas na spec v2, secao 4. Nenhuma linha e descartada: cada registro recebe `restrito`, `qualificado`, `motivo` (o primeiro que falhar, na ordem abaixo) e flags informativas. As contagens completas, por fonte e por ano, estao em `relatorio_qualificacao.md` (gerado por `scripts/rodar.py`).

| regra | criterio | efeito |
|---|---|---|
| R1 | `restrito` = codigo de razao nao nulo | nao restrito -> `motivo=sem_restricao`; a linha fica para a energia gerada |
| R2 | codigo (strip, upper) em {ENE, CNF, REL, PAR} | fora disso -> `motivo=codigo_desconhecido`, contado por valor |
| R3 | origem em {LOC, SIS} | outro/nulo -> flag `origem_desconhecida`, linha mantida |
| R4 | `din_instante` parseavel; unicidade por (`id_ons`, `din_instante`) | invalido -> `motivo=instante_invalido`; duplicata -> mantem a ultima, as demais `motivo=duplicata` |
| R5 | `val_geracao` e referencia efetiva nao nulas | nulo -> `motivo=valor_nulo` |
| R6 | referencia efetiva = coalesce(`val_geracaoreferenciafinal`, `val_geracaoreferencia`) (padrao) ou so `val_geracaoreferencia` (`--referencia referencia`) | nao existe opcao "final" (zeraria ENE/CNF) |
| R7 | `val_geracao` < 0 | usa 0 no calculo; flag `geracao_negativa` |
| R8 | qualificado = R1 e R2 e R4 e R5 | `eng_mw = max(ref_ef - ger, 0)`; `eng_mwh = eng_mw x delta t`; `ger >= ref_ef` -> flag `restrito_sem_eng` |
| R9 | `val_geracaolimitada` nao participa do calculo | flags `limite_zero` (limite = 0 com codigo) e `limite_nao_vinculante` (limite > ref_ef) |
| R10 | `val_disponibilidade` nao participa por padrao | flags `disponibilidade_zero`, `ref_maior_que_disp`, `ger_maior_que_disp`; `--excluir-disp-zero` transforma a primeira em `motivo` |
| R11 | lacunas nao sao reindexadas | intervalos presentes vs esperados por usina e mes, resumidos por fonte no relatorio |
| R12 | CSV lido em modo estrito | linhas com numero errado de campos sao contadas em `relatorio_carga.md` (0 na janela) |

Ordem de precedencia do `motivo`: instante_invalido > duplicata > sem_restricao > codigo_desconhecido > valor_nulo > disponibilidade_zero (opcional). Energia gerada (para a taxa de corte) = `max(val_geracao, 0) x delta t`, em todas as linhas, restritas ou nao.

## Metricas e sensibilidade

ENG (energia nao gerada) por registro = `max(ref_ef - max(val_geracao, 0), 0) x delta t` nos registros qualificados; energia gerada = `max(val_geracao, 0) x delta t` em todos os registros; taxa de corte = ENG / (ENG + energia gerada). Agregacoes em `src/coff/metricas.py`; figuras em `src/coff/figuras.py`; CSVs em `docs/`.

### Resumo anual

<!-- resumo_anual:inicio -->
| ano | fonte | eng_gwh | energia_gerada_gwh | taxa_corte_pct |
|---|---|---|---|---|
| 2023 | EOL | 3149.64 | 91472.75 | 3.33 |
| 2024 | EOL | 9152.15 | 102673.77 | 8.18 |
| 2024 | UFV | 3184.05 | 21054.22 | 13.14 |
| 2025 | EOL | 25411.36 | 111086.36 | 18.62 |
| 2025 | UFV | 10756.73 | 31719.41 | 25.32 |
| 2026 | EOL | 15911.51 | 67103.11 | 19.17 |
| 2026 | UFV | 7948.1 | 24352.79 | 24.61 |
<!-- resumo_anual:fim -->

### Sensibilidade a referencia efetiva

<!-- sensibilidade:inicio -->
Tabela de sensibilidade (R6): ENG por fonte e categoria com referencia efetiva `coalesce(final, referencia)` versus apenas `referencia`, sobre os registros qualificados de toda a janela.

| fonte | categoria | ENG coalesce (GWh) | ENG referencia (GWh) | dif (GWh) | dif (%) |
|---|---|---|---|---|---|
| EOL | energetica | 26711.9 | 26711.9 | 0.0 | 0.0 |
| EOL | confiabilidade | 21308.5 | 21308.5 | 0.0 | 0.0 |
| EOL | eletrica | 5604.3 | 7116.4 | -1512.2 | -21.25 |
| UFV | energetica | 14993.6 | 14993.6 | 0.0 | 0.0 |
| UFV | confiabilidade | 4807.0 | 4807.0 | 0.0 | 0.0 |
| UFV | eletrica | 2088.3 | 2420.5 | -332.2 | -13.72 |

Ocorrencias de PAR: Nenhuma ocorrencia do codigo PAR na janela.
<!-- sensibilidade:fim -->

### Validacao externa

<!-- validacao:inicio -->
Duas referencias publicadas pelo ONS foram encontradas e comparadas com o resultado do pipeline (referencia `coalesce`, todos os registros qualificados):

1. **RT DGL-ONS 0189/2025 (GT Cortes de Geracao, secao 4.2)**: restricoes por razao energetica em 2024 = **4.330 GWh**. Este repositorio: **4,330 GWh** (diferenca +0 GWh, +0.0 %).
2. **Serie mensal "Geracao Nao Realizada (Apurada), eolica + fotovoltaica, % do potencial de geracao"** (apresentacao do ONS no XXXI Simposio Juridico da ABCE, out/2025; a parte de 2023 coincide com a Fig. 4-3 do RT acima), transcrita em `validacao_ons_serie.csv`. Comparacao em 33 meses (2023-01 a 2025-09): correlacao 0.996, erro absoluto medio 0.37 p.p., vies -0.36 p.p. Tabela completa em `validacao_externa.csv`.

| mes | ENG (MWh) | energia gerada (MWh) | taxa repo (%) | taxa ONS (%) | dif (p.p.) |
|---|---|---|---|---|---|
| 2023-01 | 15254.56 | 6167370.78 | 0.25 | 0.3 | -0.05 |
| 2023-02 | 8502.56 | 6447477.9 | 0.13 | 0.2 | -0.07 |
| 2023-03 | 35958.7 | 6027380.14 | 0.59 | 1.0 | -0.41 |
| 2023-04 | 24912.78 | 4811016.82 | 0.52 | 0.6 | -0.08 |
| 2023-05 | 34870.02 | 6836403.66 | 0.51 | 0.5 | 0.01 |
| 2023-06 | 212007.37 | 8500603.36 | 2.43 | 2.6 | -0.17 |
| 2023-07 | 166114.25 | 9815791.02 | 1.66 | 1.8 | -0.14 |
| 2023-08 | 350460.97 | 8897081.94 | 3.79 | 4.2 | -0.41 |
| 2023-09 | 1275166.9 | 8953052.03 | 12.47 | 12.6 | -0.13 |
| 2023-10 | 474469.14 | 9396638.8 | 4.81 | 5.6 | -0.79 |
| 2023-11 | 312388.11 | 7727282.74 | 3.89 | 4.2 | -0.31 |
| 2023-12 | 239533.75 | 7892648.96 | 2.95 | 3.4 | -0.45 |
| 2024-01 | 34024.73 | 5241470.61 | 0.64 | 0.6 | 0.04 |
| 2024-02 | 167904.13 | 6021299.26 | 2.71 | 3.1 | -0.39 |
| 2024-03 | 108052.99 | 5113080.22 | 2.07 | 2.1 | -0.03 |
| 2024-04 | 154672.17 | 7936527.82 | 1.91 | 1.9 | 0.01 |
| 2024-05 | 559807.47 | 10765940.58 | 4.94 | 5.0 | -0.06 |
| 2024-06 | 1029753.71 | 11343742.41 | 8.32 | 8.6 | -0.28 |
| 2024-07 | 1589477.51 | 12670092.5 | 11.15 | 11.8 | -0.65 |
| 2024-08 | 2206203.61 | 13801597.7 | 13.78 | 14.3 | -0.52 |
| 2024-09 | 2636360.54 | 13716677.07 | 16.12 | 16.5 | -0.38 |
| 2024-10 | 1400573.98 | 13057033.37 | 9.69 | 9.9 | -0.21 |
| 2024-11 | 1166822.77 | 12264719.16 | 8.69 | 8.8 | -0.11 |
| 2024-12 | 1282544.27 | 11795799.87 | 9.81 | 9.8 | 0.01 |
| 2025-01 | 776403.31 | 8331990.33 | 8.52 | 10.1 | -1.58 |
| 2025-02 | 2699273.44 | 9635573.26 | 21.88 | 25.8 | -3.92 |
| 2025-03 | 1564510.57 | 11090650.07 | 12.36 | 12.6 | -0.24 |
| 2025-04 | 1129135.98 | 9923556.78 | 10.22 | 10.3 | -0.08 |
| 2025-05 | 2570209.12 | 12647227.15 | 16.89 | 17.2 | -0.31 |
| 2025-06 | 2494842.22 | 12618277.81 | 16.51 | 16.8 | -0.29 |
| 2025-07 | 3385894.69 | 13220252.3 | 20.39 | 20.4 | -0.01 |
| 2025-08 | 4518090.07 | 13671458.78 | 24.84 | 24.7 | 0.14 |
| 2025-09 | 5070819.81 | 14405660.83 | 26.04 | 26.0 | 0.04 |

Leitura: o ONS publica percentuais apurados (com regras da REN ANEEL 1.030/2022 e reconsistencias) e nao a serie bruta; diferencas de alguns pontos percentuais sao esperadas. Nao foi encontrado um total mensal em GWh publicado pelo ONS por fonte.
<!-- validacao:fim -->

## Limitacoes

- Os dados publicados pelo ONS fazem parte de um processo de consistencia recorrente e podem ser atualizados apos a publicacao; o cache local so e refeito com `--forcar`.
- A coluna `dsc_restricao` (descricao textual da restricao) **so existe a partir de 2025_01** (EOL 2023_01→2024_12 e UFV 2024_04→2024_12 nao a possuem; 33 arquivos, criada nula) e **so e preenchida pelo ONS a partir de 2025_09**: de 2025_01 a 2025_08 a coluna existe mas esta vazia em todas as linhas. Por isso a metrica "top descricoes" (figura 5, `top_descricoes.csv`) cobre efetivamente 2025_09 em diante; a ENG dos registros restritos de 2025_01–2025_08 aparece como "(sem descricao)".
- O codigo de razao **PAR** ("restricao indicada no parecer de acesso") consta do dicionario de dados, mas **nao ocorre em nenhum dos 73 meses x fonte** da janela (contagem mes a mes em `relatorio_carga.md`). E tratado como codigo conhecido e contado; a categoria "parecer de acesso" aparece vazia.
- Os conjuntos de usinas nao sao desagregados por usina individual (datasets `*_detail` fora do escopo).
- Na eolica, usinas/conjuntos entram e saem do dataset ao longo da janela (153 a 164 por mes); a serie por usina nao e um painel balanceado.
- A apuracao regulatoria (REN ANEEL 1.030/2022) nao e reproduzida: nao ha franquias nem regras de elegibilidade por usina; a ENG aqui e uma medida descritiva.
