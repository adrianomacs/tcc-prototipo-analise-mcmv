"""Chaves de `st.session_state` compartilhadas entre páginas de checagem e de
relatório. Concentrá-las aqui evita chaves em texto solto, espalhadas, onde
um erro de digitação é silencioso.

As chaves por checagem (`chave_relatorio`, `chave_mostrar_resultados`,
`chave_caminho_ifc`, `chave_viz_job_id`, `chave_viz_future`) são funções —
cada checagem tem sua própria entrada, prefixada pela CHAVE da tela
("programa", "georref", "enquadramento"). As demais são compartilhadas entre
a tabela de resultados (que abre o relatório) e a própria página de
relatório (que as lê), e por isso são constantes de módulo.
"""

from __future__ import annotations


def chave_relatorio(chave: str) -> str:
    return f"relatorio__{chave}"


def chave_mostrar_resultados(chave: str) -> str:
    return f"mostrar_resultados__{chave}"


def chave_caminho_ifc(chave: str) -> str:
    return f"caminho_ifc__{chave}"


def chave_viz_job_id(chave: str) -> str:
    """Job de conversão 3D de uma checagem. É por `chave`: uma constante global
    faria o job de uma checagem sobrescrever o de outra quando as duas fossem
    abertas na mesma sessão. Segue o mesmo padrão de namespacing que `chave_relatorio`/`chave_caminho_ifc` já usavam."""
    return f"viz_job_id__{chave}"


def chave_viz_future(chave: str) -> str:
    """Future da conversão 3D de uma checagem — ver `chave_viz_job_id`."""
    return f"viz_future__{chave}"


# Compartilhadas entre quem abre o relatório de um requisito e a própria
# página de relatório — não dependem de qual checagem as originou.
REQ_SELECIONADO = "req_selecionado"
# ADR-010:
# guarda o nó da ÁRVORE (`app.navegacao.arvore.Pagina`), não mais uma string
# de caminho solta — quem lê de volta usa `.caminho` com `st.switch_page`.
ORIGEM_RELATORIO = "origem_relatorio"
MEMBROS_SELECIONADOS = "membros_selecionados"
# Diferente das três chaves acima, esta DEPENDE de qual
# checagem originou o requisito aberto — é o que permite à página de
# relatório (`app.paginas.relatorios.relatorio`) carregar a visualização 3D
# (`app.servicos.conversao_3d`) da MESMA checagem que abriu o relatório, em
# vez de uma pasta/job global.
CHAVE_SELECIONADA = "chave_selecionada"

# O `Empreendimento` corrente da sessão (`core.dominio.empreendimento
# .Empreendimento`) — carregado uma vez de `artefatos/empreendimento.json`
# (ou migrado do `terreno.json` legado) e mantido aqui entre reexecuções do
# script.
EMPREENDIMENTO = "empreendimento"
