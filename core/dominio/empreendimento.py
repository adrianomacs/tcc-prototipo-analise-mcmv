"""Empreendimento — a raiz de agregado da análise (ADR-004).

Responde à pergunta que o código não tinha como responder até aqui: *a análise
é de quê?* O ``Contexto`` já era Empreendimento e execução fundidos num
dataclass só (ADR-004); este módulo dá nome à
metade "Empreendimento" e o ``Contexto`` passa a delegar a ela.

O que pertence ao agregado
--------------------------

* ``Localizacao`` (VO) — UF, município e código IBGE. A chave pela qual a
  camada de aplicação resolve o território (malha, recorte de equipamentos).
* ``declaracoes`` — as condições de contorno declaradas. Continua um ``dict``
  com as chaves canônicas de ``vocabulario/declaracoes.py``: é o formato que o
  guard de aplicabilidade e o ``relatorio.json`` já consomem.
* ``Terreno`` (entidade, ``dominio/terreno.py``) — opcional,
  com um ``ModeloBIM`` próprio, também opcional (ADR-023).
* ``UnidadeTipo`` (entidade, ``dominio/unidade_tipo.py``) — 0..n, o grupo de
  UH que se repete, cada uma com o seu ``ModeloBIM`` opcional (ADR-023; é a
  antiga ``Edificacao`` com o nome certo).
* ``Edificacao`` (entidade, ``dominio/edificacao.py``) — 0..n, o prédio
  FÍSICO, com ``ModeloBIM`` opcional e uma **composição** em unidades tipo
  (ADR-023). Opcional de propósito: o loteamento de 150 casas não enumera
  150 prédios.
* ``unidades_previstas`` — o primeiro dos três números de UH do ADR-021.

O que NÃO pertence
------------------

* **Os equipamentos.** Pertencem ao território (ao município). O empreendimento
  só aponta para o município; quem deriva o recorte é
  ``core/aplicacao/resolver_territorio.py``.
* **O modelo aberto** (o objeto do IfcOpenShell). É serviço de execução e vive
  no ``Contexto``; aqui fica só a referência (caminho, schema, natureza).

Os três números de UH (ADR-021)
-------------------------------

``unidades_previstas`` é fato declarado sobre a **proposta** — quantas UHs o
empreendimento terá. Nunca é extraível de modelo, porque não é propriedade de
arquivo nenhum, e **não entra em veredito dimensional**: o denominador de uma
regra é o ``unidades_representadas`` do contêiner efetivamente lido, porque é
sobre aquela geometria que a regra pergunta. O terceiro número, o
``UnidadeTipo.unidades``, é por quantas UHs o veredito fala.

Confrontar a soma das unidades tipo com o previsto — e, desde o ADR-023, a
soma das composições com as ``unidades`` de cada tipo — é a única aritmética
que o agregado faz entre números de dono diferente, e ela produz diagnóstico
(ADR-022), nunca insumo de regra nem exceção: declaração incompleta é legítima.

A composição e os invariantes da raiz (ADR-023)
-----------------------------------------------

A ``Edificacao`` só conhece ids; quem sabe o que eles significam é o agregado,
e por isso dois invariantes são garantidos AQUI, com ``ValueError`` como a
unicidade de ids: uma composição só cita unidades tipo do empreendimento, e as
unidades tipo citadas têm uma única tipologia — um prédio casa + apartamento
não existe na Portaria. Daí também as derivações morarem aqui:
``tipologia_de(edificacao)`` (a dos tipos compostos, ou ``""`` se a composição
está vazia — ausência, e não valor: o guard não bloqueia) e
``unidades_compostas(tipo)``. Remover uma unidade tipo limpa as composições
que a citam, com a versão andando **uma** vez.

O contêiner não pertence mais ao empreendimento
-----------------------------------------------

O ADR-023 tira o ``ModeloBIM`` daqui: ele passa a ser anexado à unidade tipo
ou ao ``Terreno``, conforme a natureza declarada. O campo ``modelo`` deixou de existir: a âncora da execução chega por
argumento nomeado de ``composicao.rodar``, e o pipeline não precisa de um
campo fixo. Um artefato gravado com a chave ``modelo`` continua legível — quem a
reconhece é a migração, em ``infra/persistencia/empreendimento_json.py``, que é
quem sabe estar lendo um arquivo velho.

Identidade e versão
-------------------

``id`` é gerado (uuid4, 12 hex, ``dominio/identidade.py``) e não muda; ``nome``
é livre. ``versao`` começa em 1 e é incrementada por **toda** mudança feita
pelos métodos do agregado — é o que permite que um relatório gravado para a
versão *n* seja reconhecido como desatualizado quando o empreendimento estiver
na *n+1*. Mudar o ``dict`` de declarações, ou uma ``UnidadeTipo`` ou
``Edificacao`` já na coleção, por fora dos métodos não incrementa a versão: é a
mesma fronteira de qualquer objeto mutável, e está declarada aqui para não ser
descoberta depois. É também por isso que uma unidade tipo muda por
``atualizar_unidade_tipo`` (e uma edificação por ``atualizar_edificacao``), e
não no lugar.

Anel: domínio. Nenhum I/O — a serialização (``to_dict``/``from_dict``) produz e
consome dicionários; quem grava é ``infra/persistencia/empreendimento_json.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from core.dominio.edificacao import Edificacao
from core.dominio.identidade import novo_id
from core.dominio.modelo_bim import ModeloBIM, contagem_de_uh
from core.dominio.terreno import Terreno
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec

# ``ModeloBIM`` e ``novo_id`` mudaram de módulo (ADR-023) mas seguem exportados
# daqui: é por este nome que o pipeline, as regras e a persistência os importam,
# e trocar o import de todos eles é mudança de outra fase, não desta.
__all__ = ["Empreendimento", "Localizacao", "ModeloBIM", "UnidadeTipo",
           "Edificacao", "novo_id"]

_CODIGO_IBGE = re.compile(r"\d{7}")


# ---------------------------------------------------------------------------
# Localizacao (Value Object)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Localizacao:
    """Onde o empreendimento está declarado. Imutável.

    ``codigo_ibge`` é a identidade do VO (7 dígitos); ``uf`` e ``municipio`` são
    rótulos para exibição e podem vir vazios — o recorte e a malha são chaveados
    só pelo código.
    """

    codigo_ibge: str
    uf: str = ""
    municipio: str = ""

    def __post_init__(self):
        codigo = str(self.codigo_ibge or "").strip()
        if not _CODIGO_IBGE.fullmatch(codigo):
            raise ValueError(
                f"Código IBGE de município deve ter 7 dígitos; recebido "
                f"{self.codigo_ibge!r}.")
        object.__setattr__(self, "codigo_ibge", codigo)
        object.__setattr__(self, "uf", str(self.uf or "").strip())
        object.__setattr__(self, "municipio", str(self.municipio or "").strip())

    @classmethod
    def de_declaracoes(cls, declaracoes: dict | None,
                       codigo_ibge: str = "") -> Localizacao | None:
        """A localização contida nas declarações da tela, ou ``None``.

        ``codigo_ibge`` explícito prevalece sobre o das declarações — a mesma
        precedência que ``composicao.montar_contexto`` sempre aplicou. Sem código,
        não há localização (o Programa de necessidades roda assim).
        """
        declaracoes = declaracoes or {}
        codigo = str(codigo_ibge or declaracoes.get(dec.MUNICIPIO_IBGE)
                     or "").strip()
        if not codigo:
            return None
        return cls(codigo_ibge=codigo, uf=declaracoes.get(dec.UF) or "",
                   municipio=declaracoes.get(dec.MUNICIPIO) or "")

    def to_dict(self) -> dict:
        return {"codigo_ibge": self.codigo_ibge, "uf": self.uf,
                "municipio": self.municipio}

    @classmethod
    def from_dict(cls, dados: dict | None) -> Localizacao | None:
        if not dados:
            return None
        return cls(codigo_ibge=dados.get("codigo_ibge", ""),
                   uf=dados.get("uf", ""), municipio=dados.get("municipio", ""))


# ---------------------------------------------------------------------------
# Empreendimento (raiz de agregado)
# ---------------------------------------------------------------------------

@dataclass(eq=False)
class Empreendimento:
    """Raiz de agregado da análise. Igualdade por identidade (``id``)."""

    nome: str = ""
    localizacao: Localizacao | None = None
    declaracoes: dict[str, Any] = field(default_factory=dict)
    terreno: Terreno | None = None
    unidades_tipo: list[UnidadeTipo] = field(default_factory=list)
    edificacoes: list[Edificacao] = field(default_factory=list)
    unidades_previstas: int = 0
    id: str = field(default_factory=novo_id)
    versao: int = 1

    def __post_init__(self):
        self.unidades_previstas = contagem_de_uh(self.unidades_previstas,
                                                 "unidades_previstas")
        self._exigir_unidades_tipo_distintas(self.unidades_tipo)
        self._exigir_edificacoes_distintas(self.edificacoes)
        self._exigir_composicoes_integras(self.unidades_tipo, self.edificacoes)

    def __eq__(self, outro: object) -> bool:
        return isinstance(outro, Empreendimento) and outro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    # -- comportamento: toda mudança passa por aqui e incrementa a versão ----

    def _mudar(self, atributo: str, valor) -> None:
        if getattr(self, atributo) is valor or getattr(self, atributo) == valor:
            return
        setattr(self, atributo, valor)
        self.versao += 1

    def renomear(self, nome: str) -> None:
        self._mudar("nome", str(nome or "").strip())

    def localizar(self, localizacao: Localizacao | None) -> None:
        self._mudar("localizacao", localizacao)

    def declarar(self, declaracoes: dict | None) -> None:
        self._mudar("declaracoes", dict(declaracoes or {}))

    def definir_terreno(self, terreno: Terreno | None) -> None:
        self._mudar("terreno", terreno)

    def prever_unidades(self, quantidade) -> None:
        """Declara quantas UHs o empreendimento terá (ADR-021)."""
        self._mudar("unidades_previstas",
                    contagem_de_uh(quantidade, "unidades_previstas"))

    # -- comportamento: a coleção de unidades tipo ---------------------------
    #
    # A igualdade de ``UnidadeTipo`` é por identidade, então comparar as listas
    # diretamente diria "nada mudou" quando uma unidade tipo da coleção tivesse
    # sido renomeada ou tivesse ganhado contêiner — e a versão pararia de andar
    # exatamente no caso em que o relatório gravado ficou desatualizado. Daí a
    # comparação pelo conteúdo serializado, e não por ``_mudar``.

    @staticmethod
    def _exigir_unidades_tipo_distintas(unidades_tipo) -> list[UnidadeTipo]:
        novas = list(unidades_tipo or [])
        ids = [u.id for u in novas]
        if len(set(ids)) != len(ids):
            raise ValueError(
                "A mesma unidade tipo não pode aparecer duas vezes no "
                "empreendimento: cada UH pertence a exatamente uma.")
        return novas

    def _trocar_unidades_tipo(self, novas: list[UnidadeTipo]) -> None:
        """Troca a coleção de tipos e faz o CASCADE nas composições (ADR-023).

        Uma unidade tipo que sai leva consigo as entradas de composição que a
        citam — a alternativa seria uma composição apontando para um id que o
        agregado não conhece, e o invariante proíbe. Tipo que muda de tipologia
        e torna mista uma composição é recusado (``ValueError``): o invariante
        não é reparável por adivinhação. A versão anda **uma** vez, por tudo.
        """
        ids = {u.id for u in novas}
        edificacoes = [
            replace(e, composicao={i: q for i, q in e.composicao.items() if i in ids})
            if any(i not in ids for i in e.composicao) else e
            for e in self.edificacoes]
        self._exigir_composicoes_integras(novas, edificacoes)
        if ([u.to_dict() for u in novas] == [u.to_dict() for u in self.unidades_tipo]
                and [e.to_dict() for e in edificacoes]
                == [e.to_dict() for e in self.edificacoes]):
            return
        self.unidades_tipo = novas
        self.edificacoes = edificacoes
        self.versao += 1

    def definir_unidades_tipo(self, unidades_tipo) -> None:
        """Substitui a coleção inteira."""
        self._trocar_unidades_tipo(
            self._exigir_unidades_tipo_distintas(unidades_tipo))

    def acrescentar_unidade_tipo(self, unidade_tipo: UnidadeTipo) -> None:
        """Acrescenta uma unidade tipo ao empreendimento.

        Recusa a que já está lá: uma unidade tipo repetida contaria as mesmas
        UHs duas vezes na soma, e o confronto com ``unidades_previstas``
        passaria a acusar inconsistência onde não há.
        """
        self._trocar_unidades_tipo(self._exigir_unidades_tipo_distintas(
            [*self.unidades_tipo, unidade_tipo]))

    def atualizar_unidade_tipo(self, unidade_tipo: UnidadeTipo) -> bool:
        """Substitui, pela identidade, a unidade tipo correspondente.

        É por aqui que uma unidade tipo muda — mudá-la no lugar não faz a
        versão andar. Devolve ``False`` se ela não estiver no empreendimento.
        """
        if unidade_tipo not in self.unidades_tipo:
            return False
        self._trocar_unidades_tipo(
            [unidade_tipo if u.id == unidade_tipo.id else u
             for u in self.unidades_tipo])
        return True

    def remover_unidade_tipo(self, id_unidade_tipo: str) -> bool:
        """Remove pela identidade; devolve ``False`` se não havia o que remover."""
        restantes = [u for u in self.unidades_tipo if u.id != id_unidade_tipo]
        if len(restantes) == len(self.unidades_tipo):
            return False
        self._trocar_unidades_tipo(restantes)
        return True

    # -- comportamento: a coleção de edificações físicas (ADR-023) -----------

    @staticmethod
    def _exigir_edificacoes_distintas(edificacoes) -> list[Edificacao]:
        novas = list(edificacoes or [])
        ids = [e.id for e in novas]
        if len(set(ids)) != len(ids):
            raise ValueError(
                "A mesma edificação não pode aparecer duas vezes no "
                "empreendimento.")
        return novas

    @staticmethod
    def _exigir_composicoes_integras(unidades_tipo, edificacoes) -> None:
        """Os dois invariantes da composição, de uma vez (ADR-023)."""
        tipologia_por_id = {u.id: u.tipologia for u in unidades_tipo}
        for e in edificacoes:
            desconhecidos = [i for i in e.composicao if i not in tipologia_por_id]
            if desconhecidos:
                raise ValueError(
                    f"A composição da edificação {e.nome!r} cita unidade tipo "
                    f"que não é do empreendimento: {desconhecidos}.")
            tipologias = {tipologia_por_id[i] for i in e.composicao}
            if len(tipologias) > 1:
                raise ValueError(
                    f"A edificação {e.nome!r} compõe unidades tipo de tipologias "
                    f"diferentes ({sorted(tipologias)}): um prédio casa + "
                    f"apartamento não existe na Portaria.")

    def _trocar_edificacoes(self, novas: list[Edificacao]) -> None:
        self._exigir_composicoes_integras(self.unidades_tipo, novas)
        if [e.to_dict() for e in novas] == [e.to_dict() for e in self.edificacoes]:
            return
        self.edificacoes = novas
        self.versao += 1

    def definir_edificacoes(self, edificacoes) -> None:
        """Substitui a coleção inteira."""
        self._trocar_edificacoes(self._exigir_edificacoes_distintas(edificacoes))

    def acrescentar_edificacao(self, edificacao: Edificacao) -> None:
        """Acrescenta uma edificação; recusa a que já está lá."""
        self._trocar_edificacoes(self._exigir_edificacoes_distintas(
            [*self.edificacoes, edificacao]))

    def atualizar_edificacao(self, edificacao: Edificacao) -> bool:
        """Substitui, pela identidade, a edificação correspondente.

        Devolve ``False`` se ela não estiver no empreendimento.
        """
        if edificacao not in self.edificacoes:
            return False
        self._trocar_edificacoes(
            [edificacao if e.id == edificacao.id else e for e in self.edificacoes])
        return True

    def remover_edificacao(self, id_edificacao: str) -> bool:
        """Remove pela identidade; devolve ``False`` se não havia o que remover.

        Nada cai em cascata: a edificação cita tipos, e ninguém cita a
        edificação.
        """
        restantes = [e for e in self.edificacoes if e.id != id_edificacao]
        if len(restantes) == len(self.edificacoes):
            return False
        self._trocar_edificacoes(restantes)
        return True

    # -- leitura ------------------------------------------------------------

    def unidade_tipo_por_id(self, id_unidade_tipo: str) -> UnidadeTipo | None:
        return next((u for u in self.unidades_tipo if u.id == id_unidade_tipo), None)

    def tipologia_de(self, edificacao: Edificacao) -> str:
        """A tipologia derivada da composição, ou ``""`` se ela está vazia.

        Derivada aqui, e não na edificação, porque ela só tem ids. ``""`` é
        ausência (ADR-023): o guard não bloqueia, e EDI-001 e EDI-002 rodam
        ambas, como quando ninguém declara; a interface não oferece como alvo
        uma edificação sem composição, e o diagnóstico nomeia "tipologia
        indeterminada" se ela chegar à análise por outra via.
        """
        for id_unidade_tipo in edificacao.composicao:
            unidade_tipo = self.unidade_tipo_por_id(id_unidade_tipo)
            if unidade_tipo is not None:
                return unidade_tipo.tipologia
        return ""

    def unidades_compostas(self, unidade_tipo) -> int:
        """Quantas UH deste tipo as edificações declaram conter, somadas.

        Aceita a entidade ou o id. É a segunda aritmética do ADR-022: o
        confronto com ``UnidadeTipo.unidades`` é diagnóstico, nunca exceção.
        """
        id_unidade_tipo = getattr(unidade_tipo, "id", unidade_tipo)
        return sum(e.composicao.get(id_unidade_tipo, 0) for e in self.edificacoes)

    def excedente_composto(self, unidade_tipo) -> int:
        """Quanto a composição passa das ``unidades`` do tipo; 0 se não passa."""
        id_unidade_tipo = getattr(unidade_tipo, "id", unidade_tipo)
        tipo = self.unidade_tipo_por_id(id_unidade_tipo)
        if tipo is None:
            return 0
        return max(0, self.unidades_compostas(tipo) - tipo.unidades)

    @property
    def codigo_ibge(self) -> str:
        """Código IBGE declarado, ou ``""`` sem localização."""
        return self.localizacao.codigo_ibge if self.localizacao else ""

    @property
    def unidades_declaradas(self) -> int:
        """Soma das unidades das unidades tipo — por quantas UHs os vereditos falam.

        Cada unidade tipo entra uma única vez: a coleção não admite repetição.
        """
        return sum(u.unidades for u in self.unidades_tipo)

    @property
    def excedente_declarado(self) -> int:
        """Quanto a soma das unidades tipo passa de ``unidades_previstas``; 0 se não passa.

        Sem previsão declarada (``unidades_previstas == 0``) não há confronto a
        fazer, e o excedente é 0 — ausência de declaração não é inconsistência.
        """
        if not self.unidades_previstas:
            return 0
        return max(0, self.unidades_declaradas - self.unidades_previstas)

    @property
    def declaracao_consistente(self) -> bool:
        """``False`` quando o proponente declarou, em dois lugares, números que
        não fecham — a situação que o ADR-022 nomeia na taxonomia do não
        avaliável, nas duas aritméticas (tipos × previsto; composição ×
        ``unidades`` do tipo). Aqui é só a aritmética; emitir o motivo é da
        aplicação."""
        return (self.excedente_declarado == 0
                and all(self.excedente_composto(u) == 0 for u in self.unidades_tipo))

    def referencia(self) -> dict:
        """O que um relatório grava para dizer de que empreendimento é."""
        return {"id": self.id, "versao": self.versao}

    # -- serialização (sem I/O) ---------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "versao": self.versao,
            "localizacao": self.localizacao.to_dict() if self.localizacao else None,
            "declaracoes": dict(self.declaracoes),
            "terreno": self.terreno.to_dict() if self.terreno is not None else None,
            "unidades_previstas": self.unidades_previstas,
            # SEMPRE gravada, mesmo vazia: é a chave que distingue o esquema
            # E2 (este) do E1, que gravava ``edificacoes`` com os campos de
            # unidade tipo — e que a persistência migra (ADR-023).
            "unidades_tipo": [u.to_dict() for u in self.unidades_tipo],
            "edificacoes": [e.to_dict() for e in self.edificacoes],
        }

    @classmethod
    def from_dict(cls, dados: dict) -> Empreendimento:
        """Reconstrói o empreendimento gravado.

        Um artefato sem ``unidades_tipo`` volta **sem** unidades tipo, e a
        chave ``modelo`` de um artefato do esquema E0 (ADR-023) é simplesmente
        IGNORADA aqui: sintetizar a unidade tipo e reconhecer o contêiner
        legado são migração, e migração é da persistência (ADR-021, ADR-023),
        que é quem sabe que está lendo um arquivo velho. O mesmo vale para a
        ``edificacoes`` do esquema E1 (ADR-023), que guardava unidades tipo com o
        nome antigo: aqui ela é lida como o que a chave significa HOJE (a
        edificação física, cujo ``from_dict`` ignora os campos que não são
        dela), e é a persistência que reconhece o esquema e move os itens. O
        domínio não inventa o que não foi escrito nem guarda o que deixou de
        ser seu.
        """
        terreno = dados.get("terreno")
        return cls(
            id=dados.get("id") or novo_id(),
            nome=dados.get("nome", ""),
            versao=int(dados.get("versao") or 1),
            localizacao=Localizacao.from_dict(dados.get("localizacao")),
            declaracoes=dict(dados.get("declaracoes") or {}),
            terreno=Terreno.from_dict(terreno) if terreno else None,
            unidades_previstas=dados.get("unidades_previstas", 0),
            unidades_tipo=[u for u in
                           (UnidadeTipo.from_dict(d)
                            for d in (dados.get("unidades_tipo") or []))
                           if u is not None],
            edificacoes=[e for e in
                         (Edificacao.from_dict(d)
                          for d in (dados.get("edificacoes") or []))
                         if e is not None],
        )
