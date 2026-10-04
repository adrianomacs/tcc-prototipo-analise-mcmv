# ADR-010 — Navegação como dado: árvore de três níveis com renderizador nativo
**Status:** Aceita

## Contexto
O menu tem três níveis (Seção → Grupo → Página) e 19 páginas.
Antes desta decisão, cada informação de página vivia num lugar diferente: o caminho do
arquivo aparecia como string em `switch_page`, a largura de tela numa lista de
`url_path` no `main.py`, o ícone no menu, o título na própria página. Renomear
ou mover uma página exigia caçar essas menções. Considerou-se a biblioteca
`streamlit-option-menu` / `streamlit-antd-components` para o visual.

## Decisão
A estrutura do menu é **dado**, num módulo só: `app/navegacao/arvore.py`
define `Pagina`, `Grupo` e `Secao` (dataclasses congeladas) com rótulo, ícone,
caminho, `default`, `larga` e as páginas `OCULTAS`. Esse módulo não importa
Streamlit e não desenha nada. `app/main.py` é o **único** lugar do projeto que
cria um `st.Page`, deriva `st.navigation(position="hidden")` da árvore e
obtém dali a largura da página; `app/navegacao/sidebar.py` desenha os três
níveis com widgets nativos (`segmented_control` → `expander` → `page_link`),
sem dependência nova. Bibliotecas de menu foram **recusadas**: o menu é o
único componente que, ao quebrar, inutiliza todas as páginas de uma vez, e a
última release avaliada antecedia duas gerações do Streamlit. A árvore como
dado deixa a porta aberta a um segundo renderizador (Strategy) sem tocar nela.

## Consequências
Fica fácil mover, renomear ou ocultar página — muda um arquivo — e `switch_page`
passa a receber um nó, não uma string. Fica fácil testar a navegação sem
Streamlit (varredura sobre o dado). Fica difícil mudar o visual do menu para
algo que os widgets nativos não fazem: é o preço de não depender de biblioteca
de terceiro. Não se pode criar `st.Page` fora do `main.py`, nem escrever
caminho de arquivo de página em qualquer outro módulo.

## Evidência
- `app/navegacao/arvore.py` (`ARVORE`, `OCULTAS`, `Pagina/Grupo/Secao`);
  `app/navegacao/sidebar.py`; `app/main.py:43–57`.
- `tests/app/navegacao/test_arvore.py` (integridade da árvore) e `test_casco.py`
  (o casco de `st.navigation`); `tests/app/paginas/test_paginas_renderizam.py`
  (`AppTest` por página); `tests/app/componentes/test_icones_material.py`
  (ícones Material válidos).
