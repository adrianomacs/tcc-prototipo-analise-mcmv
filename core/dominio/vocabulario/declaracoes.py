"""Vocabulário das declarações do usuário (condições de contorno do projeto).

Como o protótipo ainda não possui *requisitos de informação de projeto* que
permitam inferir automaticamente a natureza da unidade, algumas condições são
**declaradas** pelo usuário na interface e passam a condicionar quais regras são
aplicáveis. Este módulo é a fonte única dessas dimensões e seus valores
canônicos — consumido pelas regras (metadado ``aplicabilidade``), pela interface
(rótulos dos seletores) e pelo executor (guard de aplicabilidade).

A dimensão que deixou de ser declaração
---------------------------------------

O ADR-021 tirou daqui os dois números que não eram condição de contorno:
``num_uhs`` saiu inteiro (quantas UHs o contêiner representa é propriedade da
entrega, ``ModeloBIM.unidades_representadas``, e escalar parâmetro normativo
com ele era declaração governando insumo) e ``tipologia`` deixou de ser
declarada pelo usuário — passou a ser da unidade tipo (``UnidadeTipo``,
ADR-023), que é o que torna o empreendimento misto exprimível.

A **dimensão** ``tipologia`` continua aqui porque o guard de aplicabilidade é
declarativo e chaveado por nome (``Regra.aplicabilidade``): o que mudou é a
origem do valor, não a pergunta. Quem monta as condições de uma análise
(``core.aplicacao.pipeline`` e o gateway da interface) lê a tipologia da
unidade tipo em análise e a entrega ao guard junto das declarações de fato.

Dimensões:
  * ``tipo_modelo`` — natureza do modelo enviado (já existente na seção 1).
  * ``tipologia``   — casa vs. apartamento/casa sobreposta. **Não é declarada**:
    vem da ``UnidadeTipo`` (ADR-021, ADR-023); ver o bloco acima.
  * ``arranjo``     — condomínio vs. loteamento (implantação).
  * ``uf`` / ``municipio`` / ``municipio_ibge`` — localização declarada do
    empreendimento (texto/código IBGE; fora do guard de aplicabilidade —
    alimentam o confronto âncora × município do EMP-001).

Chaves internas são sem acento/estáveis; os rótulos legíveis ficam em
``ROTULO_DIMENSAO`` / ``ROTULO_VALOR`` para mensagens e para a UI.
"""

from __future__ import annotations

# --- Dimensões declarativas ------------------------------------------------
TIPO_MODELO = "tipo_modelo"
# Dimensão do guard, não declaração: o valor vem de ``UnidadeTipo.tipologia``
# (ADR-021, ADR-023). Ver o cabeçalho do módulo.
TIPOLOGIA = "tipologia"
ARRANJO = "arranjo"
# Origem do terreno no Enquadramento: participa do guard de aplicabilidade e é
# o que torna o EMP-001 inaplicável quando não há modelo (entrada por CSV ou
# mapa) — sem alterar o executor.
ORIGEM_TERRENO = "origem_terreno"
UF = "uf"                        # sigla da UF declarada (fora do guard)
MUNICIPIO = "municipio"          # nome do município declarado (fora do guard)
MUNICIPIO_IBGE = "municipio_ibge"  # código IBGE do município declarado (fora do guard)

# --- Valores: natureza do modelo -------------------------------------------
TERRENO = "terreno"
EDIFICACAO_ISOLADA = "edificacao_isolada"
TERRENO_COM_EDIFICACOES = "terreno_com_edificacoes"
# Naturezas que contêm uma edificação (UH) — pré-condição das regras EDI.
COM_EDIFICACAO = [EDIFICACAO_ISOLADA, TERRENO_COM_EDIFICACOES]

# --- Valores: tipologia da UH ----------------------------------------------
CASA = "casa"
APARTAMENTO = "apartamento"  # apartamento ou casa sobreposta (multifamiliar)

# --- Valores: implantação --------------------------------------------------
CONDOMINIO = "condominio"
LOTEAMENTO = "loteamento"

# --- Valores: origem do terreno (Enquadramento) ----------------------------
TERRENO_DE_IFC = "ifc"
TERRENO_DE_CSV = "csv"
TERRENO_DESENHADO = "desenhada"
TERRENO_DE_PONTO = "ponto"
# Origens que trazem um modelo IFC — pré-condição das regras que o leem.
COM_MODELO_IFC = [TERRENO_DE_IFC]

# --- Rótulos legíveis (mensagens e interface) ------------------------------
ROTULO_DIMENSAO = {
    TIPO_MODELO: "natureza do modelo",
    TIPOLOGIA: "tipologia",
    ARRANJO: "implantação",
    UF: "UF do empreendimento",
    MUNICIPIO: "município do empreendimento",
    MUNICIPIO_IBGE: "código IBGE do município",
    ORIGEM_TERRENO: "origem do terreno",
}

ROTULO_VALOR = {
    TERRENO: "terreno",
    EDIFICACAO_ISOLADA: "edificação isolada",
    TERRENO_COM_EDIFICACOES: "terreno com edificações",
    CASA: "casa",
    APARTAMENTO: "apartamento / casa sobreposta",
    CONDOMINIO: "condomínio",
    LOTEAMENTO: "loteamento",
    TERRENO_DE_IFC: "modelo IFC (IfcSite)",
    TERRENO_DE_CSV: "CSV de poligonal",
    TERRENO_DESENHADO: "poligonal desenhada no mapa",
    TERRENO_DE_PONTO: "coordenada informada",
}


def rotulo(dimensao: str, valor: str) -> str:
    """Frase legível 'dimensão: valor' para mensagens de (in)aplicabilidade."""
    dim = ROTULO_DIMENSAO.get(dimensao, dimensao)
    val = ROTULO_VALOR.get(valor, valor)
    return f"{dim}: {val}"
