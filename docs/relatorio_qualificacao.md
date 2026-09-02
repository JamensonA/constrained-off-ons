# Relatorio de qualificacao (Gate 2)

Registros: 12,861,264 | referencia efetiva: `coalesce` | delta t: 0.5 h

## Contagem por motivo (fonte x ano)

| fonte | ano | (qualificado) | instante_invalido | duplicata | sem_restricao | codigo_desconhecido | valor_nulo | disponibilidade_zero | total |
|---|---|---|---|---|---|---|---|---|---|
| EOL | 2023 | 235358 | 0 | 0 | 2497186 | 0 | 0 | 0 | 2732544 |
| EOL | 2024 | 668026 | 0 | 0 | 2106710 | 0 | 0 | 0 | 2774736 |
| EOL | 2025 | 1121670 | 0 | 0 | 1591242 | 0 | 0 | 0 | 2712912 |
| EOL | 2026 | 684652 | 0 | 0 | 1101620 | 0 | 0 | 0 | 1786272 |
| UFV | 2024 | 132518 | 0 | 0 | 660634 | 0 | 0 | 0 | 793152 |
| UFV | 2025 | 310523 | 0 | 0 | 850597 | 0 | 0 | 0 | 1161120 |
| UFV | 2026 | 257247 | 0 | 0 | 643281 | 0 | 0 | 0 | 900528 |
| total |  | 3409994 | 0 | 0 | 9451270 | 0 | 0 | 0 | 12861264 |

## Contagem por flag (fonte x ano)

| fonte | ano | origem_desconhecida | geracao_negativa | restrito_sem_eng | limite_zero | limite_nao_vinculante | disponibilidade_zero | ref_maior_que_disp | ger_maior_que_disp |
|---|---|---|---|---|---|---|---|---|---|
| EOL | 2023 | 0 | 0 | 91444 | 28763 | 109710 | 281705 | 319080 | 410109 |
| EOL | 2024 | 0 | 0 | 220517 | 62650 | 299648 | 197004 | 285465 | 300077 |
| EOL | 2025 | 0 | 0 | 180722 | 106090 | 322428 | 53820 | 212230 | 88657 |
| EOL | 2026 | 0 | 21 | 65670 | 68674 | 176301 | 30817 | 103346 | 27469 |
| UFV | 2024 | 0 | 0 | 48078 | 15800 | 50629 | 140393 | 27983 | 44767 |
| UFV | 2025 | 0 | 0 | 67484 | 23198 | 89329 | 109496 | 24138 | 22221 |
| UFV | 2026 | 0 | 8 | 48298 | 12251 | 74596 | 117524 | 10413 | 7404 |
| total |  | 0 | 29 | 722213 | 317426 | 1122641 | 930759 | 982655 | 900704 |

## Codigos desconhecidos

Nenhum codigo fora de {ENE, CNF, REL, PAR}.

## ENG total por fonte (MWh, registros qualificados)

| fonte | eng_mwh |
|---|---|
| EOL | 53624659.4 |
| UFV | 21888883.1 |

## Lacunas (R11): intervalos presentes vs esperados por usina e mes

| fonte | usinas_mes | com_lacuna | intervalos_faltantes | cobertura_media |
|---|---|---|---|---|
| EOL | 6890 | 85 | 57408 | 0.9943 |
| UFV | 1971 | 37 | 26160 | 0.991 |
