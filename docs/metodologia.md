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

## Limitacoes

- Os dados publicados pelo ONS fazem parte de um processo de consistencia recorrente e podem ser atualizados apos a publicacao; o cache local so e refeito com `--forcar`.
- A coluna `dsc_restricao` (descricao textual da restricao) **so existe a partir de 2025_01** (EOL 2023_01→2024_12 e UFV 2024_04→2024_12 nao a possuem; 33 arquivos). Nesses meses ela e criada nula e as metricas por descricao cobrem apenas 2025_01 em diante.
- O codigo de razao **PAR** ("restricao indicada no parecer de acesso") consta do dicionario de dados, mas **nao ocorre em nenhum dos 73 meses x fonte** da janela (contagem mes a mes em `relatorio_carga.md`). E tratado como codigo conhecido e contado; a categoria "parecer de acesso" aparece vazia.
- Os conjuntos de usinas nao sao desagregados por usina individual (datasets `*_detail` fora do escopo).
- As regras de apuracao da REN ANEEL 1.030/2022 nao sao reproduzidas; ENG aqui e uma medida descritiva, nao um montante contratual.
