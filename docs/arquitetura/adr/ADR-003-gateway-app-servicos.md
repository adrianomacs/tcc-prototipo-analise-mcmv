# ADR-003 — `app/servicos/` é o único importador de `core/` dentro de `app/`
**Status:** Aceita

## Contexto
Antes desta decisão, `app/` era um módulo-Deus: as páginas de checagem importavam
`core.territorio.*`, `core.georref.malha_municipal`, `core.motor.declaracoes`
e até o módulo interno de uma regra (`_distancia_equipamento`) para reaproveitar
um aviso. Com isso, qualquer reorganização do núcleo quebrava telas, e a
fronteira entre "desenhar" e "analisar" não existia em lugar nenhum.

## Decisão
`app/servicos/` é o gateway: o único lugar de `app/` que importa `core.`.
`app/paginas/` e `app/componentes/` importam apenas `app.servicos.*` e entre si.
`servicos/` não importa `streamlit` para desenhar — com duas exceções
declaradas, ambas de infraestrutura da sessão do Streamlit e não de desenho:
`conversao_3d.py` (usa `st.cache_resource`/`session_state` para o job em
segundo plano) e `provedores.py`, que é a borda dos segredos: o único módulo
que lê `st.secrets` e constrói o `Roteador` (ADR-011).

## Consequências
Fica fácil mover um módulo do núcleo — uma reorganização de 71 arquivos de
`core/` mexeu apenas em `servicos/` e em `tests/`. Fica fácil, também,
testar decisão de tela sem Streamlit, porque as funções puras
(`vereditos.py`, `grupos.py`) saíram das páginas. Fica difícil o atalho: uma
página que precise de algo novo do núcleo tem de acrescentar a função no
serviço, e não importar direto — é uma linha a mais de trabalho por uma
fronteira verificável.
Não se pode importar `core.` em `app/paginas` ou `app/componentes`: o teste
reprova a suíte inteira.

## Evidência
- `tests/arquitetura/test_fronteira_app_core.py` — varredura por regex sobre `app/paginas` e
  `app/componentes`; falha com qualquer `import core` / `from core… import`.
- `app/servicos/` (15 módulos), com `provedores.py` como borda dos segredos.
- `core/composicao.py:rodar` recebe `roteador_rede` construído por
  quem chama, e não procura chave em lugar nenhum.
