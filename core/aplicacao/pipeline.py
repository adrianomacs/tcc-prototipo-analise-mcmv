"""O caso de uso da verificação: um ``Contexto`` pronto entra, a análise sai.

É o miolo das quatro camadas do fluxo — a Camada III (o motor) e a montagem
do que a Camada IV vai gravar —, sem abrir arquivo nem gravar nada:

    I. Ingestão  ->  II. Georreferenciamento  ->  III. Motor de regras  ->  IV. Saída

Quem abre o IFC, lê as camadas, resolve o território, injeta o ``Roteador`` e
grava o relatório é o módulo de composição, ``core/composicao.py``, fora dos
anéis (ADR-002): ele monta o ``Contexto``, chama ``analisar`` e entrega o
resultado ao exportador. Por isso este módulo importa só ``aplicacao`` e
``dominio`` — a regra da dependência para dentro vale aqui sem exceção.

Ficam aqui também as adaptações da assinatura antiga
(``empreendimento_de_argumentos``, ``conteiner_de_argumentos``) e o
``_instantaneo`` — o empreendimento como a análise o viu —, que são decisões
de caso de uso e não de I/O.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Any

from core.aplicacao.executor import executar
from core.dominio.contratos.regra import Contexto, Resultado
from core.dominio.empreendimento import Empreendimento, Localizacao, ModeloBIM


@dataclass
class Analise:
    """O que o caso de uso devolve: os resultados, o ``meta`` e, se houver, o
    erro de ingestão que impediu a execução. É dado — quem grava é a composição.
    """
    resultados: dict[str, Resultado] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    erro_ingestao: str = ""


def empreendimento_de_argumentos(declaracoes: dict | None = None,
                                 terreno: Any = None,
                                 municipio_ibge: str = "") -> Empreendimento:
    """O ``Empreendimento`` implícito na assinatura antiga de ``rodar``.

    É a "adaptação interna" do ``Empreendimento``: quem ainda
    chama com os argumentos soltos — a CLI e a suíte — continua funcionando, e o
    núcleo passa a raciocinar sobre um objeto só.

    O código IBGE explícito vence o das declarações (a precedência de sempre). A
    consolidação restante — ``tipo_modelo`` nas declarações — fica em
    ``_instantaneo``, igual para os dois caminhos de entrada.

    ``caminho_ifc``/``tipo_modelo`` **saíram desta metade** da adaptação
    (ADR-023): quem chama com argumentos soltos não
    declarou edificação nenhuma, e sintetizar uma só para pendurar o arquivo
    seria a adaptação inventando composição. Os dois viram a âncora da
    execução, em ``conteiner_de_argumentos`` — a outra metade do par. Aceitá-los
    aqui e ignorá-los seria pior que não aceitá-los.
    """
    declaracoes = dict(declaracoes or {})
    return Empreendimento(
        localizacao=Localizacao.de_declaracoes(declaracoes, municipio_ibge),
        declaracoes=declaracoes,
        terreno=terreno)


def conteiner_de_argumentos(caminho_ifc: str | None = None,
                            tipo_modelo: str = "") -> ModeloBIM | None:
    """A âncora da execução implícita na assinatura antiga: o arquivo apresentado.

    ``unidades_representadas`` fica em 0 — a assinatura antiga nunca disse
    quantas UHs o arquivo representa, e a regra dimensional aplica o piso de 1,
    que é o que ela já fazia quando ninguém declarava o número. Sem caminho e
    sem natureza não há contêiner: o fluxo é SEM IFC (o Enquadramento roda
    assim, de propósito).
    """
    if not (caminho_ifc or tipo_modelo):
        return None
    return ModeloBIM(caminho=caminho_ifc or "", natureza=tipo_modelo or "")


def _instantaneo(empreendimento: Empreendimento,
                 conteiner: ModeloBIM | None = None) -> Empreendimento:
    """O empreendimento COMO A ANÁLISE O VIU: mesmo ``id``, mesma ``versao``.

    Duas consolidações acontecem aqui, e nenhuma pode tocar o objeto do
    chamador — uma análise não é uma mudança do empreendimento, e incrementar a
    versão dele por ter sido analisado tornaria "este relatório está
    desatualizado?" impossível de responder:

    1. ``declaracoes[tipo_modelo]`` recebe a natureza do CONTÊINER DA EXECUÇÃO,
       se ausente — o guard de aplicabilidade a lê dali (comportamento anterior
       à 1.5b), e
       ``declaracoes[tipologia]`` recebe a da unidade tipo em análise pela
       mesma razão: desde o ADR-021 a tipologia é da ``UnidadeTipo`` (ADR-023),
       e o guard, que é declarativo e chaveado por nome, continua esperando
       encontrá-la entre as condições da análise. Quem responde é
       ``ancora.tipologia_em_analise``, já com o contêiner da execução na mão:
       é pelos DONOS dele que a tipologia é lida (ADR-023), e sem contêiner
       vale a dedução. Aqui é atribuição, e não ``setdefault``, porque a
       unidade tipo é a DONA do dado: uma tipologia sobrevivente nas
       declarações de um artefato antigo não pode vencer a da entidade. Sem
       tipologia na unidade tipo a chave não é criada nem esvaziada — uma
       dimensão presente e vazia tornaria EDI-001 e EDI-002 inaplicáveis de uma
       vez, que é o oposto de "ninguém declarou", e a declaração antiga segue
       valendo enquanto for tudo o que há;
    2. a ponte do município: sem ``Localizacao``, o código IBGE das declarações
       vira a localização. ``declaracoes`` governa APLICABILIDADE (condições de
       contorno), e um insumo não deve viajar lá — esta é a ponte entre os dois,
       e só ela.

    O ``schema`` lido do arquivo aberto **não** entra aqui: ele
    carimba o contêiner da execução (``Contexto.conteiner``), que é a referência
    ao arquivo efetivamente lido. O agregado guarda o que foi DECLARADO; o
    schema é descoberto ao abrir, e misturar os dois num campo só foi o que o
    legado ``Empreendimento.modelo`` permitia (ADR-023).

    ``dataclasses.replace`` reconstrói com os mesmos ``id``/``versao``: o
    instantâneo É o empreendimento (igualdade por identidade), numa versão que o
    chamador não vê mudar.
    """
    from core.dominio import ancora
    from core.dominio.vocabulario import declaracoes as dec

    natureza = conteiner.natureza if conteiner is not None else ""

    declaracoes = dict(empreendimento.declaracoes or {})
    declaracoes.setdefault(dec.TIPO_MODELO, natureza)
    tipologia = ancora.tipologia_em_analise(empreendimento, conteiner)
    if tipologia:
        declaracoes[dec.TIPOLOGIA] = tipologia

    localizacao = (empreendimento.localizacao
                   or Localizacao.de_declaracoes(declaracoes))

    # Ponte no sentido inverso: regras já validadas — o
    # cross-check municipal do EMP-001 — leem UF/município/código IBGE das
    # declarações. No caminho novo eles moram só na ``Localizacao``; sem
    # espelhá-los aqui o cross-check deixava de rodar em silêncio e o veredito
    # mudava. ``setdefault``: no caminho legado as chaves já vêm preenchidas.
    if localizacao is not None:
        declaracoes.setdefault(dec.UF, localizacao.uf)
        declaracoes.setdefault(dec.MUNICIPIO, localizacao.municipio)
        declaracoes.setdefault(dec.MUNICIPIO_IBGE, localizacao.codigo_ibge)

    return replace(empreendimento, declaracoes=declaracoes,
                   localizacao=localizacao)


def arquivos_consumidos(conteiner: ModeloBIM | None, terreno: Any) -> list[dict]:
    """``[{papel, arquivo, sha256}]`` do modelo aberto e do arquivo de que o
    terreno foi lido (ADR-035). Só o nome do arquivo — o caminho é da máquina
    que rodou, não do insumo. Terreno sem arquivo de origem (desenhado,
    ponto) não entra; arquivo sem impressão entra com ``sha256`` vazio, para
    que o relatório diga que ela não foi registrada em vez de omitir o arquivo.
    """
    arquivos = []
    if conteiner is not None and conteiner.caminho:
        arquivos.append({"papel": "modelo",
                         "arquivo": os.path.basename(conteiner.caminho),
                         "sha256": conteiner.digest})
    proc = getattr(terreno, "procedencia", None) or {}
    if proc.get("arquivo"):
        arquivos.append({"papel": "terreno",
                         "arquivo": os.path.basename(str(proc["arquivo"])),
                         "sha256": proc.get("sha256", "")})
    return arquivos


def analisar(ctx: Contexto, *, ids_selecionados: list[str] | None = None,
             caminho_ifc: str | None = "", pasta_gis: str | None = "",
             tipo_modelo: str = "", roteador_rede: Any = None) -> Analise:
    """Executa o motor sobre um ``Contexto`` pronto e monta o ``meta``.

    ``caminho_ifc``, ``pasta_gis``, ``tipo_modelo`` e ``roteador_rede`` só
    entram no ``meta`` — descrevem a execução, não a mudam. Quem os resolveu e
    montou o ``Contexto`` foi ``core/composicao.py``.
    """
    from core.aplicacao import diagnosticos as diag

    # IFC apresentado e não aberto: NENHUMA regra é executada.
    #
    # A alternativa — rodar tudo e deixar cada regra sair NÃO AVALIÁVEL por falta
    # de modelo — foi recusada: ela produz um relatório de aparência normal cuja
    # cobertura desce por uma causa que não é do modelo analisado, e sim da
    # ausência de análise. "Não pude ler o arquivo" não é um veredito sobre o
    # projeto, e registrá-lo como sete vereditos confunde as duas coisas.
    # Pela mesma razão a composição NÃO sobrescreve o relatório anterior.
    if ctx.erro_ingestao:
        return Analise(meta={"ifc": caminho_ifc, "gis": pasta_gis,
                             "tipo_modelo": tipo_modelo,
                             "empreendimento": ctx.empreendimento.referencia()},
                       erro_ingestao=ctx.erro_ingestao)

    # Camada III
    resultados = executar(ctx, ids_selecionados=ids_selecionados)

    meta = {"ifc": caminho_ifc, "gis": pasta_gis, "tipo_modelo": tipo_modelo,
            "roteador_rede": getattr(roteador_rede, "provedor", None),
            "declaracoes": ctx.empreendimento.declaracoes,
            "georref": ctx.georref.get("mensagem"),
            "municipio_ibge": ctx.empreendimento.codigo_ibge,
            "terreno": (ctx.empreendimento.terreno.to_dict()
                        if ctx.empreendimento.terreno is not None else None),
            # ADR-004: referência estável
            # {id, versao} do empreendimento analisado — é o que permite a
            # uma tela dizer "este relatório está desatualizado" comparando
            # com o empreendimento corrente, sem reabrir o relatório inteiro.
            "empreendimento": ctx.empreendimento.referencia(),
            # ADR-035: os arquivos submetidos que esta análise consumiu, com a
            # impressão digital de cada um — o que amarra o resultado ao insumo.
            "arquivos": arquivos_consumidos(ctx.conteiner,
                                            ctx.empreendimento.terreno)}

    # Os cinco diagnósticos da análise (ADR-023, D-K): o que esta submissão
    # não consegue dizer, sem que nenhum veredito mude. Só nas análises que
    # leem UH — quem decide é a lista de regras EXECUTADAS, não a selecionada:
    # é a execução que diz o que foi lido. Chave ausente quando não há o que
    # diagnosticar, para que o relatório de quem não diagnostica continue
    # sendo o que sempre foi.
    diagnosticos = diag.para_meta(ctx.empreendimento, ctx.conteiner,
                                  list(resultados))
    if diagnosticos:
        meta["diagnosticos"] = diagnosticos

    return Analise(resultados=resultados, meta=meta)
