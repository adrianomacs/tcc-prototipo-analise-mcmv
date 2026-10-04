# `tests/`

Espelha `core/` e `app/`: um teste de `core/dominio/equipamentos.py` mora em
`tests/core/dominio/test_equipamentos.py`. Um teste cujo assunto atravessa
módulos fica na pasta do **assunto principal** — o que a docstring de abertura
diz que ele prende; um teste de fluxo entre anéis (pipeline, executor) fica em
`tests/core/aplicacao/`, que é onde o fluxo é orquestrado.

## Onde pôr um teste novo

1. Ache o módulo que ele testa em `core/` ou `app/`.
2. Crie (ou use) a pasta espelho em `tests/` com o mesmo caminho.
3. Nomeie por **assunto**, nunca por fase ou data: `test_<coisa_testada>.py`,
   nunca `test_fase3_algo.py`.

## `tests/apoio/`

Código de apoio compartilhado por vários arquivos de teste — nunca coletado
como teste em si (não começa com `test_`). Hoje: `ifc_falso.py` (modelos IFC
falsos, sem IfcOpenShell), `ifc_real.py` (um modelo IFC real, via
IfcOpenShell, para os poucos testes de integração que precisam dele),
`roteadores.py` (`RoteadorFalso`), `inep.py` (fábricas de dados do INEP).

## `tests/fixtures/`

Dados de teste que não são código: respostas reais gravadas (`ors_*.json`),
artefatos reais gravados pelo próprio protótipo
(`empreendimento_esquema_antigo.json`, do Estrela I, no esquema E0 do
ADR-023; `parecer/E0/` e `parecer/E3/`, os cinco relatórios de dois degraus da
escada gravados por `scripts/rodar_cenario.py` sem rede, entrada do Relatório
de Checagem do ADR-035) e CSVs de exemplo.

## `tests/scripts/`

Espelho de `scripts/`, que não é pacote: cada teste carrega o script pelo
caminho (`importlib`), como `test_inspetores.py` faz. É também onde mora a
**escada de cenários do Estrela I** (`test_cenarios_estrela_i.py`): um teste
de integração por id da lista de cenários, que
roda pelo mesmo `scripts/rodar_cenario.py` usado manualmente e **pula com motivo**
quando o arquivo do cenário ainda não está em `entradas/ifc/estrela_i/`.

## Marcadores

- `integracao` — exige IfcOpenShell real: constrói um modelo IFC de verdade
  ou abre um arquivo real do acervo (a escada de cenários, que pula sem o
  arquivo); os testes com os modelos falsos de `tests/apoio/ifc_falso.py`
  não levam este marcador.
- `interface` — usa `streamlit.testing.v1.AppTest` (renderiza a página
  inteira; mais lento que testar a função diretamente).

Ciclo rápido, sem os dois:

```
pytest -m "not integracao and not interface"
```

## Município nos testes

O código IBGE 3549904 (São José dos Campos/SP) aparece em cerca de 20 testes como
**dado sintético**, e é assim de propósito. O município só
entrou no trabalho por um modelo de teste antigo, e o único recorte de
equipamentos em `config/` é o de Estrela (4307807). Teste que precisa de recorte
monta o seu em `tmp_path`, nunca lê o de outro município do `config/`; recorte
novo em `config/` só nasce com decisão sobre o estudo de caso. As linhas do
município nas bases nacionais permanecem, e por isso as âncoras que leem o
snapshot real de municípios e de zonas seguem valendo. Não trocar esses testes
só para tirar o nome do município.

## Antes de mover ou dividir um arquivo de teste

`grep -n "__file__\|fixtures\|Path(\|os.path" <arquivo>` — caminho de fixture
relativo ao próprio arquivo, ou cálculo de raiz por `dirname`/`parent`, quebra
silenciosamente ao mudar de pasta. `RAIZ` e `FIXTURES`, centralizados em
`tests/conftest.py`, existem para eliminar essa classe de bug — prefira-os a
recalcular a raiz num arquivo novo.
