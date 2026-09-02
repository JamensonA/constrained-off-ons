# Dicionario de dados

Gerado automaticamente a partir dos recursos `DicionarioDados_*.json` do portal de
dados abertos do ONS (campo `dicionario_simplificado`). Nao editar a mao.

## `restricao_coff_eolica_usi` (EOL)

_dicionario nao encontrado no cache_

## `restricao_coff_fotovoltaica` (UFV)

_dicionario nao encontrado no cache_

## Codigos de razao -> categoria (tabela usada pelo pacote)

| codigo | categoria | descricao no dicionario ONS | definicao operativa |
|---|---|---|---|
| ENE | energetica | Razao energetica | controle carga-frequencia do SIN; restricao sistemica |
| CNF | confiabilidade | Razao de atendimento a requisitos de confiabilidade | limites de intercambio e inequacoes operativas |
| REL | eletrica | Razao de indisponibilidade externa (eletrica) | indisponibilidade externa a usina (criterio N-1) |
| PAR | parecer de acesso | Restricao indicada no parecer de acesso | restricao indicada no parecer de acesso; sem ocorrencias em jul/2026 |

## Codigos de origem

| codigo | origem |
|---|---|
| LOC | local |
| SIS | sistemica |
