# ADR-011 — A aplicação resolve o território antes do motor; provedores são injetados
**Status:** Aceita

## Contexto
Dois defeitos reais, achados ao examinar o código. **D1:** a regra de
distância abria `config/equipamentos_<ibge>.csv` por conta própria, com caminho
relativo ao diretório de trabalho, **dentro** de uma regra de domínio — a regra
sabia de arquivo, e testá-la exigia fixture em disco. **D2:** o provedor de
rede viajava em `ctx.config["roteador_rede"]`, injeção de dependência por chave
de string dentro de um dicionário de configuração YAML — o oposto do que o
resto do código faz.

## Decisão
A pergunta da regra é "quais são os equipamentos de educação deste município?",
e quem responde é a **aplicação**, antes de executar: `core/aplicacao/
resolver_territorio.py` traduz `Localizacao` → recorte de equipamentos e o
entrega em `Contexto.recorte_equipamentos`. O provedor de rede é um campo
tipado, `Contexto.roteador` (`dominio/contratos/roteador.py`, um `Protocol`),
construído **por quem chama** — `app/servicos/provedores.py`, a borda dos
segredos, ou a CLI da composição. O núcleo não procura chave em lugar nenhum.
A aplicação pergunta ao território pela porta `FontesTerritoriais`
(`dominio/contratos/fontes_territoriais.py`), implementada sobre os CSVs em
`infra/gis/fontes_csv.py` e injetada por `core/composicao.py`, como o `Roteador`.
O território é resolvido **só quando há terreno**: os únicos consumidores do
recorte são as regras com `exige_terreno`, e sem terreno o executor as gateia
antes do `checar`. Falha de leitura não sobe: o recorte fica `None`, a causa
vai para o log, e a regra sai `NAO_AVALIAVEL` por `erro_de_execucao`.

## Consequências
Fica fácil testar a regra de distância sem arquivo e trocar de provedor de rede
(ORS, euclidiana, um terceiro) sem tocar em regra. Fica fácil garantir
determinismo: um núcleo que lê o ambiente dá resultados diferentes em máquinas
diferentes e faz a suíte chamar a API de verdade. Fica difícil a
retrocompatibilidade: `config["roteador_rede"]` segue vivo como dívida
deliberada; a releitura do CSV dentro do `checar` saiu com a porta, e um
`Contexto` montado à mão precisa trazer o recorte pronto.
`None` de roteador **não é erro**: é a degradação declarada — as regras de
distância saem `NAO_AVALIAVEL` por `metrica_insuficiente`, nunca aprovadas com
o piso euclidiano (ADR-013).

## Evidência
- `core/aplicacao/resolver_territorio.py` (docstrings "Quando resolver" e
  "Falha ao ler não sobe daqui"); `core/composicao.py:montar_contexto`.
- `Contexto.recorte_equipamentos` e `Contexto.roteador` em
  `core/dominio/contratos/regra.py`; `core/dominio/contratos/roteador.py`;
  `core/dominio/contratos/fontes_territoriais.py` e `core/infra/gis/fontes_csv.py`.
- `core/regras/base/distancia_equipamento.py:_recorte` (só o recorte resolvido).
- `app/servicos/provedores.py:roteador_de_rede` (única leitura de `st.secrets`).
- `tests/core/aplicacao/test_resolver_territorio.py`,
  `tests/core/regras/gis/test_enq_distancia_rede.py`,
  `tests/core/infra/rede/test_ors.py`,
  `tests/core/infra/gis/test_recorte_municipal.py`.
