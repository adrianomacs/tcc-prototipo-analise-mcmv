"""Módulo de composição do núcleo — o único que conhece todos os anéis.

Monta o que o caso de uso precisa e grava o que ele devolve: abre o IFC, lê as
camadas GIS e o CRS do modelo, calcula a impressão digital, resolve o
território, recebe o ``Roteador`` construído pela borda (ADR-011), entrega o
``Contexto`` pronto a ``core.aplicacao.pipeline.analisar`` e passa a análise ao
exportador do relatório. Na taxonomia da Arquitetura Limpa é o "Main": fica
fora dos anéis (ADR-002), pode importar todos eles, e é o único ponto de
entrada para executar a verificação — pela interface (``app/servicos/``) e pela
linha de comando.

As quatro camadas do fluxo passam por aqui na ordem: I e II em
``montar_contexto``, III no caso de uso, IV na gravação ao fim de ``rodar``.

Execução::

    python -m core.composicao
    python -m core.composicao --ifc entradas/ifc/modelo.ifc --gis entradas/gis
"""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from typing import Any

from core.aplicacao import pipeline
from core.dominio.contratos.regra import Contexto
from core.dominio.empreendimento import Empreendimento, ModeloBIM

CACHE_ROTEAMENTO = os.path.join("artefatos", "cache_roteamento", "ors.json")

_log = logging.getLogger(__name__)


def _cache_padrao():
    """Cache de medições em disco, compartilhado entre execuções.

    Fica em ``artefatos/`` (ignorado pelo git) e não tem prazo de validade — ver
    o cabeçalho de ``core/infra/rede/cache_ors.py``. Sem ele, reabrir o mesmo terreno
    gastaria cota de novo para chegar exatamente ao mesmo número.
    """
    from core.infra.rede import cache_ors as ca

    return ca.CacheRoteamento(CACHE_ROTEAMENTO)


def leitura_do_modelo(modelo: Any, georref: dict) -> Any:
    """A ingestão do modelo aberto: a porta ``LeituraModelo`` sobre ele e o
    diagnóstico LoGeoRef em ``georref["logeoref"]`` (ADR-036).

    O LoGeoRef é calculado aqui, uma vez, com o alvo do domínio
    (``LOGEOREF_ALVO``, DN-03); o EMP-001 só o julga. Se o cálculo levantar,
    a ingestão não cai: a causa vai para ``georref["logeoref_erro"]`` e o
    EMP-001 sai NÃO AVALIÁVEL por erro de execução, como sairia se a exceção
    tivesse acontecido dentro dele. Sem modelo não há leitura nem diagnóstico.
    """
    from core.dominio.conhecimento.georreferenciamento import LOGEOREF_ALVO
    from core.infra.ifc.georref import logeoref
    from core.infra.ifc.leitura_ifc import LeituraIFC

    if modelo is None:
        return None
    try:
        georref["logeoref"] = logeoref.avaliar(modelo, alvo=LOGEOREF_ALVO)
    except Exception as exc:                            # noqa: BLE001
        georref["logeoref_erro"] = repr(exc)
    return LeituraIFC(modelo)


def fontes_territoriais():
    """A implementação de produção da porta ``FontesTerritoriais``: os CSVs de
    ``config/`` (ADR-011). É daqui que a interface e o pipeline a recebem.
    """
    from core.infra.gis.fontes_csv import FontesCSV

    return FontesCSV()


def _carregar_config(caminho: str = "config/settings.yaml") -> dict[str, Any]:
    try:
        import yaml
        with open(caminho, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}




def montar_contexto(caminho_ifc: str | None, pasta_gis: str | None,
                    config: dict[str, Any], tipo_modelo: str = "",
                    declaracoes: dict | None = None,
                    terreno: Any = None, municipio_ibge: str = "", *,
                    empreendimento: Empreendimento | None = None,
                    conteiner: ModeloBIM | None = None,
                    roteador: Any = None, fontes: Any = None) -> Contexto:
    """Executa as Camadas I e II, devolvendo um Contexto pronto para o motor.

    Recebe o ``empreendimento`` (caminho novo) ou os argumentos soltos (caminho
    antigo, adaptado por ``empreendimento_de_argumentos``) — nunca os dois.

    ``conteiner`` é a âncora da execução (ADR-021/023): o ``ModeloBIM`` que
    corresponde ao IFC aberto aqui, resolvido por quem conhece a submissão.
    ``None`` faz valer a dedução a partir do agregado
    (``ancora.conteiner_em_analise``).
    ``caminho_ifc`` deve vir igual ao caminho do contêiner (``rodar`` garante).

    ``fontes`` é a implementação da porta ``FontesTerritoriais`` que o
    resolvedor consulta; ``None`` é a de produção, ``fontes_territoriais()``.
    """
    from core.aplicacao import completude, resolver_territorio
    from core.dominio import ancora
    from core.infra.gis import leitor_vetorial as leitor_gis
    from core.infra.ifc import leitor_modelo as leitor_ifc
    from core.infra.ifc.georref import leitor_crs

    if empreendimento is None:
        empreendimento = pipeline.empreendimento_de_argumentos(
            declaracoes, terreno, municipio_ibge)
        if conteiner is None:
            conteiner = pipeline.conteiner_de_argumentos(caminho_ifc, tipo_modelo)
    elif conteiner is None:
        conteiner = ancora.conteiner_em_analise(empreendimento)

    # Abertura DEFENSIVA: schema não suportado é diagnóstico de insumo, não
    # traceback. Um IFC4X3_RC2 derrubaria as telas de Georreferenciamento e de Programa de
    # necessidades com um traceback na cara do usuário — num protótipo cuja tese
    # é justamente dizer o que falta no modelo. O erro viaja no Contexto; quem
    # decide o que fazer com ele é ``rodar`` (não executa nada) e a tela (avisa).
    modelo, erro_ingestao = (
        leitor_ifc.abrir_seguro(caminho_ifc)
        if caminho_ifc and os.path.exists(caminho_ifc) else (None, ""))
    camadas = leitor_gis.carregar_pasta(pasta_gis) if pasta_gis else {}
    schema = leitor_ifc.schema(modelo) if modelo is not None else ""

    info_geo = leitor_crs.ler(modelo)
    georref = {
        "valido": info_geo.valido,
        "epsg": info_geo.epsg,
        "nome_crs": info_geo.nome_crs,
        "map_conversion": info_geo.map_conversion,
        "mensagem": info_geo.mensagem,
    }
    # A porta de leitura do modelo e, ao lado do CRS, o LoGeoRef (ADR-036).
    leitura = leitura_do_modelo(modelo, georref)

    rel = completude.avaliar(modelo, camadas, georref)
    if rel.observacoes:
        for obs in rel.observacoes:
            _log.info("[completude] %s", obs)

    # O contêiner da execução carimbado com o schema LIDO do arquivo aberto e a
    # impressão digital do conteúdo consumido (ADR-035) — o que se descobriu e
    # o que se calculou ao abrir, nunca o que foi declarado.
    from core.infra import impressao_digital
    digest = impressao_digital.sha256(caminho_ifc) if modelo is not None else ""
    if conteiner is not None:
        conteiner = replace(conteiner, schema=schema or conteiner.schema,
                            digest=digest or conteiner.digest)
    elif schema:
        conteiner = ModeloBIM(schema=schema, digest=digest)

    analisado = pipeline._instantaneo(empreendimento, conteiner)
    fontes = fontes if fontes is not None else fontes_territoriais()

    return Contexto(modelo_ifc=modelo, camadas_gis=camadas, georref=georref,
                    config=config, erro_ingestao=erro_ingestao,
                    empreendimento=analisado, conteiner=conteiner,
                    # O território é resolvido AQUI, antes do motor — a
                    # regra de distância o recebe pronto e não abre arquivo.
                    recorte_equipamentos=resolver_territorio.para_empreendimento(
                        analisado, fontes),
                    # ADR-030: a zona bioclimática também é resolvida aqui —
                    # derivada do município, nunca declarada pelo usuário.
                    zona_bioclimatica=resolver_territorio.zona_para_empreendimento(
                        analisado, fontes),
                    # ADR-030: a população do Censo, pelo mesmo caminho —
                    # o porte é derivado, nunca declarado.
                    populacao_municipal=(
                        resolver_territorio.populacao_para_empreendimento(
                            analisado, fontes)),
                    # O provedor de rede em campo tipado.
                    roteador=roteador,
                    # ADR-036: as regras BIM leem o modelo pela porta, e o
                    # EMP-001 confere a âncora pela porta do território.
                    leitura_modelo=leitura,
                    fontes_territoriais=fontes)


def rodar(caminho_ifc: str | None = None, pasta_gis: str | None = None,
          ids_selecionados: list[str] | None = None, tipo_modelo: str = "",
          declaracoes: dict | None = None, terreno: Any = None,
          municipio_ibge: str = "", roteador_rede: Any = None, *,
          empreendimento: Empreendimento | None = None,
          conteiner: ModeloBIM | None = None,
          destino_rel: str | None = None) -> dict:
    """Executa o fluxo completo e grava o relatório; devolve o relatório montado.

    ``ids_selecionados`` restringe a execução às regras escolhidas (ex.: pela
    interface); ``tipo_modelo`` informa a natureza do modelo enviado;
    ``declaracoes`` traz as condições de contorno declaradas (tipologia,
    arranjo) que condicionam a aplicabilidade das regras.

    ``roteador_rede`` é o provedor de distância caminhável em rede, **construído
    por quem chama** — a interface, que conhece o ``st.secrets``, ou o ``main``
    abaixo (``_cli``), que lê o ambiente. A composição apenas o repassa no
    ``config`` e no ``Contexto``; ela não procura chave em lugar nenhum, pelo
    mesmo motivo que a regra não procura: configuração entra pela borda, e um núcleo que lê o ambiente produz
    resultados diferentes em máquinas diferentes. ``None`` faz as regras de
    distância saírem NÃO AVALIÁVEL por métrica insuficiente, que é a degradação
    declarada.

    ``empreendimento`` é a entrada principal: o ``Empreendimento`` traz
    localização, declarações, terreno e a composição declarada, e **substitui**
    ``caminho_ifc``, ``tipo_modelo``, ``declaracoes``, ``terreno`` e
    ``municipio_ibge`` — passar os dois é erro, não precedência. O objeto do
    chamador não é alterado (ver ``pipeline._instantaneo``). A assinatura antiga é
    adaptada internamente e produz o mesmo relatório.

    ``conteiner`` é a ÂNCORA DA EXECUÇÃO (ADR-021/023): qual contêiner esta
    análise lê. Quem conhece a submissão —
    a tela, por ``app/servicos/analise.py`` — o resolve e o passa; é dele que
    saem o IFC a abrir e a natureza do modelo, e é ele que as regras leem por
    ``ancora.conteiner_da_execucao``. Argumento **aditivo**: com ``None`` vale a
    dedução a partir do empreendimento (a unidade tipo em análise, ou o terreno),
    e é o que mantém a CLI funcionando.
    Só faz sentido com ``empreendimento``; junto dos argumentos soltos é erro,
    porque lá o arquivo já vem em ``caminho_ifc``.

    Sem contêiner nenhum o fluxo é SEM IFC (``""``), e não "descubra na pasta":
    a descoberta é conveniência da CLI, e um empreendimento sem contêiner
    declarou que não tem um.

    ``destino_rel`` sobrescreve
    o caminho de gravação do relatório — por padrão (``None``), continua
    sendo ``config["paths"]["relatorio"]`` (``artefatos/relatorio.json``,
    sobrescrito a cada execução, como sempre foi). Quem chama por checagem
    (``app/servicos/analise.py``) passa um caminho por ``chave``
    (``artefatos/relatorios/<chave>.json``) para que cada checagem grave o
    seu próprio relatório em vez de todas sobrescreverem o mesmo arquivo —
    é o que permite às telas de resultados consolidados (2.4.1/2.4.2) lerem
    os relatórios das várias checagens ao mesmo tempo.
    """
    from core.dominio import ancora
    from core.infra.exportadores import relatorio_json

    if empreendimento is not None:
        if (caminho_ifc is not None or tipo_modelo or declaracoes is not None
                or terreno is not None or municipio_ibge):
            raise ValueError(
                "rodar: passe o empreendimento OU os argumentos soltos "
                "(caminho_ifc, tipo_modelo, declaracoes, terreno, "
                "municipio_ibge), não os dois.")
        if conteiner is None:
            conteiner = ancora.conteiner_em_analise(empreendimento)
        caminho_ifc = (conteiner.caminho if conteiner is not None else "") or ""
        tipo_modelo = conteiner.natureza if conteiner is not None else ""
    elif conteiner is not None:
        raise ValueError(
            "rodar: o contêiner âncora acompanha o empreendimento; com os "
            "argumentos soltos o arquivo já vem em caminho_ifc.")

    config = _carregar_config()
    # Legado mantido: o provedor segue também no ``config``, onde contextos
    # montados à mão e testes existentes o procuram. O campo tipado
    # ``Contexto.roteador`` é preenchido por ``montar_contexto``.
    config["roteador_rede"] = roteador_rede
    paths = config.get("paths", {})

    # ``None`` = "descubra um IFC na pasta"; ``""`` = "NÃO há IFC neste fluxo".
    # A distinção existe para o Enquadramento, que roda sem modelo: sem ela, a
    # descoberta abriria um IFC qualquer da pasta — às vezes de centenas de MB —
    # só para as regras GIS o ignorarem.
    if caminho_ifc is None:
        caminho_ifc = _primeiro_ifc(paths.get("entradas_ifc", "entradas/ifc"))
    pasta_gis = pasta_gis or paths.get("entradas_gis", "entradas/gis")
    destino_rel = destino_rel or paths.get("relatorio", "artefatos/relatorio.json")

    # Camadas I e II — a ingestão e o georreferenciamento, aqui na composição
    if empreendimento is None:
        empreendimento = pipeline.empreendimento_de_argumentos(
            declaracoes, terreno, municipio_ibge)
        conteiner = pipeline.conteiner_de_argumentos(caminho_ifc, tipo_modelo)
    ctx = montar_contexto(caminho_ifc, pasta_gis, config,
                          empreendimento=empreendimento, conteiner=conteiner,
                          roteador=roteador_rede)

    analise = pipeline.analisar(ctx, ids_selecionados=ids_selecionados,
                                caminho_ifc=caminho_ifc, pasta_gis=pasta_gis,
                                tipo_modelo=tipo_modelo,
                                roteador_rede=roteador_rede)

    # IFC apresentado e não aberto: o caso de uso não executou regra
    # nenhuma, e o relatório anterior NÃO é sobrescrito — uma análise que não
    # aconteceu não deve apagar a que aconteceu.
    if analise.erro_ingestao:
        _log.warning("[ingestão] %s", analise.erro_ingestao)
        return {"erro_ingestao": analise.erro_ingestao, "resultados": [],
                "resumo": {}, "meta": analise.meta}

    # Camada IV — ordem de EXIBIÇÃO segue a ordem pedida pela interface
    # (ids_selecionados, tipicamente a ordem declarada no grupo em
    # config/grupos_requisitos.yaml); a ordem de EXECUÇÃO permanece
    # topológica. Ver core/infra/exportadores/relatorio_json.py.
    os.makedirs(os.path.dirname(destino_rel), exist_ok=True)
    relatorio = relatorio_json.gravar(analise.resultados, destino_rel,
                                      meta=analise.meta,
                                      ordem_exibicao=ids_selecionados)

    _imprimir_resumo(relatorio)
    return relatorio


def _primeiro_ifc(pasta: str) -> str | None:
    if not os.path.isdir(pasta):
        return None
    for nome in sorted(os.listdir(pasta)):
        if nome.lower().endswith(".ifc"):
            return os.path.join(pasta, nome)
    return None


def _imprimir_resumo(relatorio: dict) -> None:
    resumo = relatorio.get("resumo", {})
    norm = resumo.get("normativo") or {}
    conformidade = resumo.get("conformidade")
    agregadas = len(norm.get("membros") or [])
    linhas = [
        "",
        "=== Relatório de conformidade ===",
        f"  Verificações executadas : {resumo.get('total_requisitos', 0)}",
        f"    conformes             : {resumo.get('conforme', 0)}",
        f"    não conformes         : {resumo.get('nao_conforme', 0)}",
        f"    não avaliáveis        : {resumo.get('nao_avaliavel', 0)}",
    ]
    # Os dois números do §3.1 contam REQUISITOS da Portaria, não as linhas acima:
    # alternativa de um "ou" é evidência do requisito, não requisito à parte.
    linhas.append(
        f"  Requisitos da Portaria  : {norm.get('total', 0)}"
        + (f" ({agregadas} alternativa(s) agregada(s))" if agregadas else ""))
    linhas.append(
        "  Conformidade            : "
        + (f"{conformidade * 100:.1f}%" if conformidade is not None
           else "— (nenhum requisito avaliado)"))
    linhas.append(f"  Cobertura               : {resumo.get('cobertura', 0) * 100:.1f}%")
    _log.info("\n".join(linhas))


def _cli() -> None:
    import argparse

    from core.infra.rede import ors

    parser = argparse.ArgumentParser(description="Executa o fluxo de verificação.")
    parser.add_argument("--ifc", default=None, help="Caminho do modelo IFC.")
    parser.add_argument("--gis", default=None, help="Pasta com as camadas GIS.")
    parser.add_argument("--sem-rede", action="store_true",
                        help="Não usar roteamento em rede mesmo com chave "
                             "configurada (as regras de distância saem NÃO "
                             "AVALIÁVEL por métrica insuficiente).")
    args = parser.parse_args()

    # A BORDA: é aqui, e na interface, que o ambiente é lido. O caso de uso e
    # as regras não procuram chave em lugar nenhum.
    rede = None if args.sem_rede else ors.de_configuracao(cache=_cache_padrao())
    if rede is None and not args.sem_rede:
        print("[roteamento] Sem chave do OpenRouteService "
              f"({ors.VARIAVEL_AMBIENTE} ou .streamlit/secrets.toml). As regras "
              "de distância sairão NÃO AVALIÁVEL por métrica insuficiente.")
    rodar(args.ifc, args.gis, roteador_rede=rede)


if __name__ == "__main__":
    _cli()
