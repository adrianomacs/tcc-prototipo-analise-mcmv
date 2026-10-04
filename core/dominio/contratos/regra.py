"""Contrato comum a todas as regras de checagem.

Define a "forma" de uma regra e o "formato" de um resultado. E o unico ponto
que todas as regras compartilham — mudancas aqui afetam o protótipo inteiro.

Cada regra e uma subclasse de :class:`Regra` que declara seu metadado como
atributos de classe e implementa um unico metodo, ``checar``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Enumeracoes de dominio
# ---------------------------------------------------------------------------

class Estado(str, Enum):
    """Os tres estados de saida previstos no Passo 3.

    ``NAO_AVALIAVEL`` e distinto de ``NAO_CONFORME``: reservado a requisitos
    cujo pre-requisito nao foi satisfeito, evitando contaminar as metricas.
    """

    CONFORME = "conforme"
    NAO_CONFORME = "nao_conforme"
    NAO_AVALIAVEL = "nao_avaliavel"


class Dominio(str, Enum):
    GIS = "GIS"
    BIM = "BIM"
    GIS_BIM = "GIS_BIM"


class Verbo(str, Enum):
    EXISTENCIA = "existencia"
    CONTAGEM = "contagem"
    DIMENSIONAL = "dimensional"
    ATRIBUTO = "atributo"
    ESPACIAL = "espacial"
    DOCUMENTAL = "documental"
    # Requisito decidido a partir dos resultados de outros requisitos, e não de
    # insumo próprio. A planilha-mãe já classificava ENQ-010 e ENQ-011 como
    # "Agregação", e o enum era o único lado do par que faltava. Ver
    # ``core/regras/base/agregacao.py``.
    AGREGACAO = "agregacao"


# ---------------------------------------------------------------------------
# Resultado de uma checagem
# ---------------------------------------------------------------------------

@dataclass
class Resultado:
    """Saida de uma checagem de regra para um requisito.

    ``elementos`` lista os GlobalId envolvidos — chave que liga este resultado
    a geometria na visualizacao. ``detalhe`` carrega diagnosticos estruturados
    opcionais (ex.: a escada LoGeoRef).
    """

    regra_id: str
    estado: Estado
    descricao: str = ""
    valor_esperado: Any = None
    valor_encontrado: Any = None
    unidade: str = ""
    elementos: list[str] = field(default_factory=list)
    mensagem: str = ""
    detalhe: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "requisito": self.regra_id,
            "estado": self.estado.value,
            "descricao": self.descricao,
            "valor_esperado": self.valor_esperado,
            "valor_encontrado": self.valor_encontrado,
            "unidade": self.unidade,
            "elementos": self.elementos,
            "mensagem": self.mensagem,
            "detalhe": self.detalhe,
        }


# ---------------------------------------------------------------------------
# Declaracao de insumos que uma regra exige do usuario
# ---------------------------------------------------------------------------

@dataclass
class InsumoSpec:
    """Insumo adicional que uma regra precisa para ser avaliada.

    Declarado pela propria regra (atributo ``insumos``). A interface usa esta
    declaracao para renderizar genericamente um uploader ao lado da regra. O
    arquivo enviado e salvo em ``destino`` com o nome ``chave``.
    """

    chave: str
    rotulo: str
    formatos: list[str] = field(default_factory=list)
    destino: str = "entradas/gis"
    obrigatorio: bool = True


# ---------------------------------------------------------------------------
# Contexto de execucao compartilhado
# ---------------------------------------------------------------------------

class Contexto:
    """Tudo que uma regra pode precisar para se avaliar.

    **``Contexto = Empreendimento + serviços + resultados``** (ADR-004): as
    duas metades têm nome:

    * **o que a análise é** — ``empreendimento`` (``core.dominio.empreendimento``):
      localização, declarações, terreno e a referência ao modelo;
    * **com o que ela roda** — ``modelo_ifc`` (o modelo aberto), ``conteiner``
      (a referência ao contêiner que ele É — a âncora da execução, ADR-021/023),
      ``camadas_gis``, ``georref``, ``recorte_equipamentos`` (resolvido pela
      aplicação), ``zona_bioclimatica`` (idem, ADR-030), ``populacao_municipal`` (idem,
      ADR-030), ``roteador`` (o
      provedor de rede tipado), ``config``, ``resultados`` e
      ``erro_ingestao``.

    Sem ``empreendimento=`` explícito, o construtor monta um vazio
    (``Empreendimento()``) — nunca a partir de campos soltos: essa ponte, para
    quem ainda tem só ``declaracoes``/``terreno``/``municipio_ibge``, é
    ``pipeline.empreendimento_de_argumentos``; o ``caminho_ifc``/``tipo_modelo``
    da mesma assinatura antiga atravessa por ``conteiner_de_argumentos``, e vira
    o ``conteiner`` abaixo.

    Os campos ``terreno``, ``municipio_ibge``, ``declaracoes``, ``tipo_modelo``
    e ``schema`` que antes eram aceitos aqui como propriedades delegadas
    (retrocompatibilidade, ADR-004) foram removidos: todo chamador lê e grava
    via ``Contexto.empreendimento``. Quem precisar deles lê ``ctx.empreendimento.terreno``,
    ``ctx.empreendimento.codigo_ibge``, ``ctx.empreendimento.declaracoes`` e o
    contêiner da execução por ``core.dominio.ancora.conteiner_da_execucao``.
    """

    def __init__(self, modelo_ifc: Any = None,
                 camadas_gis: dict[str, Any] | None = None,
                 georref: dict[str, Any] | None = None,
                 config: dict[str, Any] | None = None,
                 resultados: dict[str, Resultado] | None = None,
                 erro_ingestao: str = "", *,
                 empreendimento: Any = None,
                 conteiner: Any = None,
                 recorte_equipamentos: Any = None,
                 zona_bioclimatica: Any = None,
                 populacao_municipal: Any = None,
                 roteador: Any = None,
                 leitura_modelo: Any = None,
                 fontes_territoriais: Any = None) -> None:
        from core.dominio import empreendimento as emp

        self.empreendimento = (empreendimento if empreendimento is not None
                                else emp.Empreendimento())
        self.modelo_ifc = modelo_ifc
        # A ÂNCORA DA EXECUÇÃO (ADR-021/023): o ``ModeloBIM`` que
        # corresponde ao ``modelo_ifc`` aberto acima. ``None`` = ninguém a
        # passou, e quem precisa dela cai na dedução a partir do agregado —
        # ver ``core.dominio.ancora.conteiner_da_execucao``, o ponto único
        # onde as duas origens se encontram. Aqui só o campo: o contrato não
        # deduz, e não deve; quem deduz é o serviço de domínio ao lado.
        self.conteiner = conteiner
        self.camadas_gis = camadas_gis if camadas_gis is not None else {}
        self.georref = georref if georref is not None else {}
        self.config = config if config is not None else {}
        self.resultados = resultados if resultados is not None else {}
        # Por que o IFC não pôde ser aberto — vazio quando abriu, e vazio também
        # quando NÃO HÁ IFC neste fluxo (o Enquadramento roda assim, de
        # propósito). Preenchido só quando um arquivo foi apresentado e a
        # abertura falhou: ``modelo_ifc is None`` sozinho não distingue os dois
        # casos, e a diferença decide se a análise deve seguir ou parar. Ver
        # ``core.composicao.rodar``.
        self.erro_ingestao = erro_ingestao
        # Equipamentos do município, resolvidos pela aplicação ANTES de executar
        # (``core.aplicacao.resolver_territorio``, ADR-011). ``None`` = não
        # resolvido, e a regra de distância sai NÃO AVALIÁVEL sem ler arquivo.
        self.recorte_equipamentos = recorte_equipamentos
        # A zona bioclimática do município, resolvida pela aplicação antes de
        # executar (ADR-030), no mesmo lugar e pelo mesmo motivo que o recorte.
        # ``None`` = município não declarado, ausente da base ou base ilegível —
        # e a regra que a consome sai NÃO AVALIÁVEL, nunca com zona chutada.
        # Ela é DERIVADA: não há caminho por ``declaracoes``, de propósito.
        self.zona_bioclimatica = zona_bioclimatica
        # A população do município no Censo 2022 (``PopulacaoMunicipal``),
        # resolvida pela aplicação pelo mesmo caminho da zona (ADR-030). É dela
        # que cada regra tira o porte, pela tabela do próprio item da Portaria.
        # ``None`` = município não declarado, sem linha, instalado depois do
        # Censo ou base ilegível — e a regra sai NÃO AVALIÁVEL, nunca com uma
        # faixa chutada. Derivada: não há caminho por ``declaracoes``.
        self.populacao_municipal = populacao_municipal
        # Provedor de distância em rede (``dominio.contratos.roteador.Roteador``)
        # ou ``None``. Substitui ``config["roteador_rede"]``, que continua
        # sendo lido como legado pela regra de distância.
        self.roteador = roteador
        # A porta de leitura do modelo aberto (``contratos.leitura_modelo``,
        # ADR-036), construída pela composição sobre ``modelo_ifc``. As regras
        # BIM leem o modelo por ela, e não pelos leitores do anel externo.
        # ``None`` sem modelo; um Contexto montado à mão com modelo precisa
        # trazê-la, como traz o recorte (ADR-011).
        self.leitura_modelo = leitura_modelo
        # A porta do território (``contratos.fontes_territoriais``, ADR-011),
        # para a regra que precisa perguntar algo que depende do próprio
        # modelo — o EMP-001 confere a âncora contra a malha do município.
        self.fontes_territoriais = fontes_territoriais

    # -- consultas ------------------------------------------------------------

    def prerequisito_conforme(self, regra_id: str) -> bool:
        r = self.resultados.get(regra_id)
        return r is not None and r.estado is Estado.CONFORME

    def __repr__(self) -> str:
        return (f"Contexto(empreendimento={self.empreendimento!r}, "
                f"conteiner={self.conteiner!r}, "
                f"modelo_ifc={self.modelo_ifc!r}, "
                f"resultados={sorted(self.resultados)!r}, "
                f"erro_ingestao={self.erro_ingestao!r})")


# ---------------------------------------------------------------------------
# Classe-base de toda regra
# ---------------------------------------------------------------------------

class Regra:
    """Classe-base de toda regra de checagem."""

    id: str = ""
    dominio: Dominio = Dominio.BIM
    descricao: str = ""
    depende_de: list[str] = []
    # Requisitos que ESTA regra agrega (alternativas de um "ou", itens de uma
    # contagem mínima). O executor o lê para DUAS coisas — puxar os membros
    # junto com o pai e rodá-los antes dele — e para NENHUMA terceira: ele
    # **não** gateia.
    #
    # É por isso que `agrega` não pode ser `depende_de`. O passo 1 de
    # ``executor._executar_uma`` transforma dependência não-conforme em
    # NÃO AVALIÁVEL por `prerequisito_falho` sem executar a regra — exatamente o
    # caso que o agregador existe para julgar. Com `depende_de`, o pai de um "ou"
    # sairia não avaliável sem intervalo e com a causa errada quando a
    # alternativa A reprovasse, e ficaria impedido de aprovar pela alternativa B
    # no dia em que ela existisse. Ver ``core/regras/base/agregacao.py``.
    agrega: list[str] = []
    # Quando preenchido com um motivo de ``core.dominio.vocabulario.motivos``, declara que esta
    # regra **não avalia por concepção** e a quem a matéria é remetida. A tela lê
    # daqui para não chamar de "implementada" uma regra que nunca produz
    # veredito. Ver ``core/regras/base/remessa.py``.
    remete_a: str = ""
    ids_spec: str | None = None
    alvo: str = ""
    verbo: Verbo = Verbo.ATRIBUTO
    parametro: dict[str, Any] = {}
    insumos: list[InsumoSpec] = []
    # Nível de terreno exigido pela regra: "" (não exige) | "ponto" |
    # "poligonal". Gate ATÔMICO por regra no executor — uma regra dimensional
    # não é bloqueada porque outra exigia geometria (lição da atomização do
    # EDI-004).
    exige_terreno: str = ""
    # True quando o relatório da regra exibe o modelo 3D — o botão "Verificar
    # relatório" espera a conversão em segundo plano (gating de visualização).
    usa_visualizacao: bool = False
    # Condições declarativas em que a regra se aplica: dimensão -> valores
    # permitidos. Vazio (padrão) = aplica-se a qualquer declaração. Vocabulário
    # em ``core.dominio.vocabulario.declaracoes``.
    aplicabilidade: dict[str, list[str]] = {}

    @classmethod
    def motivo_inaplicavel(cls, declaracoes: dict) -> tuple[str, str] | None:
        """Primeira dimensão que torna a regra inaplicável, ou None se aplicável.

        Uma dimensão só reprova quando é declarada (valor não nulo) e o valor
        declarado não está entre os permitidos. Dimensões que a regra não
        restringe — ou ainda não declaradas — não reprovam.
        """
        for dimensao, permitidos in (cls.aplicabilidade or {}).items():
            valor = (declaracoes or {}).get(dimensao)
            if permitidos and valor is not None and valor not in permitidos:
                return dimensao, valor
        return None

    @classmethod
    def aplicavel(cls, declaracoes: dict) -> bool:
        """True se a regra é aplicável às declarações informadas."""
        return cls.motivo_inaplicavel(declaracoes) is None

    def checar(self, ctx: Contexto) -> Resultado | list[Resultado]:
        raise NotImplementedError(f"A regra {self.id} nao implementou checar().")

    def _resultado(self, estado: Estado, **kw) -> Resultado:
        kw.setdefault("descricao", self.descricao)
        return Resultado(regra_id=self.id, estado=estado, **kw)

    def conforme(self, **kw) -> Resultado:
        return self._resultado(Estado.CONFORME, **kw)

    def nao_conforme(self, **kw) -> Resultado:
        return self._resultado(Estado.NAO_CONFORME, **kw)

    def nao_avaliavel(self, motivo: str = "", **kw) -> Resultado:
        """Resultado não avaliável, opcionalmente com a CAUSA declarada.

        ``motivo`` usa o vocabulário de ``core.dominio.vocabulario.motivos`` e viaja em
        ``detalhe``, para que o relatório possa agrupar por causa e dizer o que
        destrava cada pendência — sem precisar de um quarto valor em ``Estado``.
        """
        if motivo:
            from core.dominio.vocabulario import motivos

            detalhe = dict(kw.pop("detalhe", None) or {})
            detalhe.setdefault(motivos.CHAVE, motivo)
            kw["detalhe"] = detalhe
        return self._resultado(Estado.NAO_AVALIAVEL, **kw)
