"""Faixa de avisos (ADR-034 (c)) e os avisos comuns a mais de uma checagem:
a premissa do IFC4 e a configuração do serviço de cálculo da distância caminhável.

A faixa é o único lugar de uma página onde aviso de **pré-condição** aparece —
o que se sabe antes de o usuário fazer qualquer coisa. Aviso que nasce do
insumo enviado (o IFC2X3 contra a premissa) fica junto do campo, não aqui.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from app.servicos import leitor_ifc
from app.servicos.provedores import roteador_de_rede
from app.servicos.territorio import formatar_numero

# Semântica fechada das quatro caixas (ADR-034 (c)). O veredito NUNCA passa por
# aqui: conforme e não conforme só têm cor no card de verificação.
ERRO = "error"          # a ação não pode seguir
ALERTA = "warning"      # segue, mas o resultado sai limitado ou o dado é incoerente
ORIENTACAO = "info"     # orientação, próximo passo, estado vazio
CONFIRMACAO = "success"  # uma ação do usuário que deu certo

_ICONE = {ERRO: ":material/error:", ALERTA: ":material/warning:",
          ORIENTACAO: ":material/info:", CONFIRMACAO: ":material/check_circle:"}


@dataclass(frozen=True)
class Aviso:
    """Um aviso na forma do ADR-034 (c): o quê (em negrito), a consequência e,
    se houver, o que fazer. ``referencia`` é o detalhe técnico (um arquivo, um
    código) que vai para a legenda abaixo da caixa, fora da mensagem-chave."""

    nivel: str
    chave: str
    consequencia: str = ""
    acao: str = ""
    referencia: str = ""

    def __post_init__(self):
        if self.nivel not in _ICONE:
            raise ValueError(f"nível de aviso desconhecido: {self.nivel!r}")


def texto_do_aviso(aviso: Aviso) -> str:
    """A mensagem montada: 1.ª frase em negrito, depois consequência e ação."""
    partes = [f"**{aviso.chave.strip()}**"]
    partes += [p.strip() for p in (aviso.consequencia, aviso.acao) if p.strip()]
    return " ".join(partes)


def mostrar_aviso(aviso: Aviso) -> None:
    getattr(st, aviso.nivel)(texto_do_aviso(aviso), icon=_ICONE[aviso.nivel])
    if aviso.referencia:
        st.caption(aviso.referencia)


def faixa_de_avisos(avisos: list[Aviso | None]) -> None:
    """Desenha a faixa no topo da página; ``None`` na lista é ignorado, para a
    página montar a lista com condicionais sem filtrar antes."""
    for aviso in avisos:
        if aviso is not None:
            mostrar_aviso(aviso)


def alerta_com_detalhe(aviso: Aviso, detalhes: list[str], *,
                       rotulo: str = "Detalhes técnicos") -> None:
    """Um aviso em linguagem do usuário, com os textos técnicos que o originaram
    num expander logo abaixo (ADR-034, U3: explicar antes do técnico).

    Existe para a pilha de avisos técnicos que um insumo pode gerar — três
    caixas amarelas sobre ``IfcGeographicElement`` e ``IfcBuildingStorey``
    empurram a ação para fora da tela e não dizem ao usuário o que fazer. A
    caixa diz o que fazer; o expander guarda o porquê, para quem audita."""
    if not detalhes:
        return
    mostrar_aviso(aviso)
    with st.expander(f"{rotulo} ({len(detalhes)})", expanded=False,
                     icon=":material/troubleshoot:"):
        for item in detalhes:
            st.markdown(f"- {item}")


def aviso_de_rede() -> Aviso | None:
    """O serviço de cálculo da distância caminhável não configurado, como aviso da faixa — ``None``
    quando está configurado.

    É ``warning``, não ``info`` (ADR-034 (c)): a análise segue, mas os
    requisitos de proximidade sairão NÃO AVALIÁVEL — o usuário precisa saber
    ANTES de analisar que a causa é configuração, e não o projeto.
    """
    if roteador_de_rede() is not None:
        return None
    return Aviso(
        ALERTA, "Serviço de cálculo da distância caminhável não configurado.",
        "A distância será medida em linha reta, que só permite reprovar: os "
        "requisitos de proximidade a equipamento sairão como não avaliáveis.",
        "Para habilitar, informe a chave do OpenRouteService.",
        referencia="A chave vai em `.streamlit/secrets.toml` — modelo em "
                   "`.streamlit/secrets.toml.example`.")


def aviso_consolidado_parcial(faltantes: list[str]) -> Aviso | None:
    """Pré-condição da faixa de 2.4.1/2.4.2 (ADR-034 (c)): o índice só soma
    as checagens já executadas — ``None`` quando não falta nenhuma."""
    if not faltantes:
        return None
    return Aviso(ALERTA, "Consolidado parcial.",
                 "Ainda faltam: " + ", ".join(faltantes) + ".",
                 "Execute essas checagens para completar o resultado.")


def aviso_premissa_ifc4(schema: str = "") -> None:
    """Declara a premissa do IFC4 — e vira ALERTA quando o modelo não a cumpre.

    Dois momentos, de propósito. **Antes** do envio ela é uma linha discreta ao
    lado do uploader: é ali que ela evita trabalho perdido, e é ali que o usuário
    ainda pode reexportar. **Depois**, sobre um modelo que não a cumpre, ela sobe
    a `warning` com o schema nomeado e a consequência concreta — porque o
    resultado que virá (EMP-001 não conforme, regras de poligonal não avaliáveis)
    é indistinguível, na tela, de um defeito do projeto analisado.

    Chamada só pelas telas cujo resultado DEPENDE de georreferenciamento
    (Enquadramento e Georreferenciamento). O Programa de necessidades lê
    ``IfcSpace`` e quantidades, que existem igual nos dois schemas — repetir a
    premissa lá ensinaria o usuário a ignorá-la.
    """
    if not schema:
        st.caption(leitor_ifc.PREMISSA_IFC4)
        return
    if leitor_ifc.georreferencia_estruturada(schema):
        return
    st.warning(f"**O modelo declara {schema}.** {leitor_ifc.PREMISSA_IFC4} "
               f"{leitor_ifc.PREMISSA_IFC4_CONSEQUENCIA}",
               icon=":material/warning:")
    st.caption(leitor_ifc.PREMISSA_IFC4_ALTERNATIVA_RECUSADA)


def aviso_de_metrica() -> None:
    """O aviso de rede fora da faixa, para as telas ainda não migradas ao
    ADR-034 — mesma mensagem e mesmo nível da faixa."""
    faixa_de_avisos([aviso_de_rede()])


def _distancia_legivel(metros: float) -> str:
    if metros >= 1000.0:
        return f"{formatar_numero(metros / 1000.0, 1)} km"
    return f"{formatar_numero(metros, 0)} m"


def aviso_divergencia_posicao(divergencia: dict, *, municipio: str = "",
                              ifcsite_dentro: bool | None = None,
                              mapconversion_dentro: bool | None = None) -> Aviso:
    """Explica ao usuário que o modelo aponta dois lugares para o projeto.

    Nasce do diagnóstico que o extrator grava na procedência do terreno
    (``divergencia_posicao``) quando a coordenada do IfcSite e a origem do
    IfcMapConversion distam acima da tolerância. A precedência da leitura não
    muda: o terreno saiu do IfcSite, e a mensagem diz isso, diz onde cada
    posição cai em relação ao município declarado e o que fazer. O confronto com
    o município vem de fora (``None`` quando não foi possível fazê-lo, sem a
    malha em cache ou sem município declarado), porque este módulo não lê malha.

    Fica ``ERRO`` quando a posição do IfcSite cai fora do município, o que já
    impede a confirmação do terreno, e ``ALERTA`` nos demais casos, em que o
    terreno segue mas o dado é incoerente (ADR-034 (c)). Nunca vira veredito
    (ADR-038).
    """
    distancia = _distancia_legivel(divergencia["distancia_m"])
    site, mapc = divergencia["ifcsite"], divergencia["mapconversion"]
    onde = municipio or "o município declarado"

    frases = [
        "O terreno foi posicionado pela latitude e longitude do **IfcSite**, "
        f"que ficam a {distancia} da origem do **IfcMapConversion**, o ponto em "
        "que o modelo está amarrado ao sistema de coordenadas."]

    if ifcsite_dentro is False:
        if mapconversion_dentro is True:
            frases.append(
                f"A posição do IfcSite cai fora de {onde} e a do IfcMapConversion "
                "cai dentro dele, o que costuma indicar que a localização do "
                "projeto no software de autoria não acompanhou as coordenadas "
                "compartilhadas.")
        elif mapconversion_dentro is False:
            frases.append(f"Nenhuma das duas posições cai em {onde}.")
        else:
            frases.append(
                f"A posição do IfcSite cai fora de {onde}, e a do IfcMapConversion "
                "não pôde ser conferida com os limites do município.")
        frases.append("Nessa posição o terreno não pode ser confirmado.")
        if mapconversion_dentro is False:
            acao = ("Confira o município declarado em Informações Gerais e a "
                    "localização do projeto no software de autoria, ou defina o "
                    "terreno pelo memorial descritivo ou pelo mapa.")
        else:
            acao = ("Corrija a localização do projeto no software de autoria e "
                    "exporte o modelo de novo, ou defina o terreno pelo memorial "
                    "descritivo ou pelo mapa.")
        nivel = ERRO
    else:
        if ifcsite_dentro is True and mapconversion_dentro is True:
            frases.append(f"As duas posições caem dentro de {onde}, mas distantes "
                          "uma da outra.")
        elif ifcsite_dentro is True and mapconversion_dentro is False:
            frases.append(f"A posição do IfcSite cai dentro de {onde} e a do "
                          "IfcMapConversion cai fora dele.")
        frases.append("As distâncias aos equipamentos serão medidas a partir da "
                      "posição do IfcSite.")
        acao = ("Confira no mapa se o ponto está sobre o terreno e, se não "
                "estiver, corrija a localização do projeto no software de "
                "autoria ou defina o terreno pelo memorial descritivo.")
        nivel = ALERTA

    referencia = (
        f"IfcSite {formatar_numero(site['lat'], 6)}, {formatar_numero(site['lon'], 6)}"
        f" · origem do IfcMapConversion {formatar_numero(mapc['lat'], 6)}, "
        f"{formatar_numero(mapc['lon'], 6)} ({mapc.get('epsg') or 'CRS do modelo'}, "
        f"E {formatar_numero(mapc['eastings'], 0)} m, "
        f"N {formatar_numero(mapc['northings'], 0)} m) · distância {distancia} · "
        f"tolerância {formatar_numero(divergencia['tolerancia_m'], 0)} m")
    return Aviso(nivel, "O modelo aponta dois lugares diferentes para o projeto.",
                 " ".join(frases), acao, referencia=referencia)


def aviso_divergencia_do_terreno(terreno, *, municipio: str = "",
                                 dentro_do_municipio) -> Aviso | None:
    """O aviso da divergência para um ``Terreno``, ou ``None`` se o extrator não
    a registrou na procedência dele.

    ``dentro_do_municipio(lat, lon)`` devolve ``True``, ``False`` ou ``None``
    (não foi possível conferir). Quem chama decide quando confrontar, porque a
    malha do município é rede e cache, e o render nunca pode depender de rede.
    """
    divergencia = terreno.procedencia.get("divergencia_posicao")
    if not divergencia:
        return None
    site, mapc = divergencia["ifcsite"], divergencia["mapconversion"]
    return aviso_divergencia_posicao(
        divergencia, municipio=municipio,
        ifcsite_dentro=dentro_do_municipio(site["lat"], site["lon"]),
        mapconversion_dentro=dentro_do_municipio(mapc["lat"], mapc["lon"]))

