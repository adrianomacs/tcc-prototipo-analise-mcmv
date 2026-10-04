"""Equipamentos públicos de educação — objeto canônico, filtros e sanidade.

Segundo objeto de domínio do Enquadramento a seguir o padrão do ``Terreno``:
**um objeto canônico, vários construtores**. Aqui as origens são o snapshot do
INEP e o CSV do usuário, e o modo mais útil é o dos dois juntos (o INEP
costuma trazer a maioria e faltarem duas ou três escolas — obrigar a redigitar
quarenta linhas para corrigir três seria desenho ruim).

**Dois filtros normativos são obrigatórios** (a partir da Portaria e das
instruções de análise da CAIXA): somente equipamentos
**públicos** e somente em situação **ativa** — paralisada, extinta, em reforma e
em construção não entram. Por isso ``rede`` e ``situacao`` são **chave da
avaliação, não metadado**: linha sem esses campos é descartada, porque assumir
"pública e ativa" por conveniência criaria conformidade falsa.

E o descarte é **contabilizado e reportado**, nunca silencioso: um "não
conforme" cuja escola mais próxima foi excluída por ser privada precisa ser
auditável — quem lê o parecer tem de poder ver que a escola existe e por que
não contou.

Duas regras de descarte, derivadas de exports reais do cadastro de
escolas: escola **sem matrícula de escolarização**
(cadastrada como exclusiva de atividade complementar) e escola de **atendimento
exclusivo a alunos com deficiência** não contam para a cobertura exigida, e cada
uma tem seu motivo de descarte; e a escola privada **conveniada ao poder
público** continua fora da avaliação — a regra é a rede pública estrita — mas é
marcada e contada, porque em educação infantil é por convênio que muitos
municípios entregam a vaga, e medir esse efeito é melhor do que escondê-lo numa
premissa (ver ``sensibilidade_conveniadas``).

O terceiro pilar é a **desconfiança do próprio insumo** (``sanidade``). Sem
ela, um cadastro incompleto produz o pior erro possível nesta ferramenta: o
requisito é reprovado por ausência de REGISTRO, não por ausência de escola — e
um "não conforme" convence, ainda que errado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- Ciclos exigidos pela Portaria (ENQ-009, 010.1, 011.1) -----------------
CICLO_INFANTIL = "infantil"          # educação infantil, 0 a 5 anos
CICLO_FUND_I = "fundamental_i"       # ensino fundamental, ciclo I, 6 a 10
CICLO_FUND_II = "fundamental_ii"     # ensino fundamental, ciclo II, 11 a 15
CICLOS = (CICLO_INFANTIL, CICLO_FUND_I, CICLO_FUND_II)

ROTULO_CICLO = {
    CICLO_INFANTIL: "educação infantil (0 a 5 anos)",
    CICLO_FUND_I: "ensino fundamental — ciclo I (6 a 10 anos)",
    CICLO_FUND_II: "ensino fundamental — ciclo II (11 a 15 anos)",
}

# --- Rede (dependência administrativa) -------------------------------------
REDE_MUNICIPAL = "municipal"
REDE_ESTADUAL = "estadual"
REDE_FEDERAL = "federal"
REDE_PRIVADA = "privada"
REDES_PUBLICAS = frozenset({REDE_MUNICIPAL, REDE_ESTADUAL, REDE_FEDERAL})
REDES = REDES_PUBLICAS | {REDE_PRIVADA}

# --- Situação de funcionamento ---------------------------------------------
SITUACAO_ATIVA = "ativa"
SITUACAO_PARALISADA = "paralisada"
SITUACAO_EXTINTA = "extinta"
SITUACAO_EM_REFORMA = "em_reforma"
SITUACAO_EM_CONSTRUCAO = "em_construcao"
SITUACOES = (SITUACAO_ATIVA, SITUACAO_PARALISADA, SITUACAO_EXTINTA,
             SITUACAO_EM_REFORMA, SITUACAO_EM_CONSTRUCAO)

# --- Restrição de atendimento ----------------------------------------------
# Dimensão **separada** da situação, e a separação foi aprendida na marra: a
# coluna "Restrição de Atendimento" do Catálogo de Escolas mistura os dois
# fatos ("ESCOLA PARALISADA" ao lado de "ESCOLA EXCLUSIVA DE ATIVIDADE
# COMPLEMENTAR"), mas eles respondem a perguntas diferentes — *a escola está
# funcionando?* e *ela atende a demanda escolar do entorno?*. Fundi-los num só
# campo repetiria o erro de capacidade × conformidade do CRS.
ATENDIMENTO_GERAL = "geral"
ATENDIMENTO_SEM_ESCOLARIZACAO = "sem_escolarizacao"
ATENDIMENTO_EXCLUSIVO_DEFICIENCIA = "exclusivo_deficiencia"
ATENDIMENTOS = (ATENDIMENTO_GERAL, ATENDIMENTO_SEM_ESCOLARIZACAO,
                ATENDIMENTO_EXCLUSIVO_DEFICIENCIA)
# Só o atendimento geral conta para a cobertura exigida pela Portaria: escola
# sem matrícula de escolarização não escolariza
# ninguém, e escola de atendimento exclusivo não atende a família que chega ao
# empreendimento sem uma criança com deficiência. As duas são descartadas com
# motivo próprio — visível no relatório, nunca somidas na conta.
ATENDIMENTOS_CONSIDERADOS = frozenset({ATENDIMENTO_GERAL})

# --- Fonte e precisão ------------------------------------------------------
FONTE_INEP = "inep"
FONTE_CSV = "csv"
PRECISAO_OFICIAL = "oficial"
PRECISAO_DECLARADA = "declarada"

# --- Motivos de descarte (reportados, nunca silenciosos) -------------------
DESCARTE_REDE_PRIVADA = "rede_privada"
DESCARTE_REDE_INDEFINIDA = "rede_indefinida"
DESCARTE_SITUACAO_INATIVA = "situacao_inativa"
DESCARTE_SITUACAO_INDEFINIDA = "situacao_indefinida"
DESCARTE_SEM_COORDENADA = "sem_coordenada"
DESCARTE_CICLO_DIVERSO = "ciclo_diverso"
DESCARTE_SEM_ESCOLARIZACAO = "sem_escolarizacao"
DESCARTE_ATENDIMENTO_EXCLUSIVO = "atendimento_exclusivo"

ROTULO_DESCARTE = {
    DESCARTE_REDE_PRIVADA: "rede privada",
    DESCARTE_REDE_INDEFINIDA: "rede não informada",
    DESCARTE_SITUACAO_INATIVA: "situação não ativa",
    DESCARTE_SITUACAO_INDEFINIDA: "situação não informada",
    DESCARTE_SEM_COORDENADA: "sem coordenada",
    DESCARTE_CICLO_DIVERSO: "não atende ao ciclo exigido",
    DESCARTE_SEM_ESCOLARIZACAO: "sem matrícula de escolarização",
    DESCARTE_ATENDIMENTO_EXCLUSIVO: "atendimento exclusivo a alunos com deficiência",
}

# --- Sinais de suspeita do insumo (viram motivo `insumo_suspeito`) ---------
SUSPEITA_SEM_ETAPA = "sem_equipamento_da_etapa"
SUSPEITA_CONTAGEM_IMPLAUSIVEL = "contagem_implausivel"
SUSPEITA_COORDENADAS_IDENTICAS = "coordenadas_identicas"
SUSPEITA_DISTANCIA_ABSURDA = "distancia_absurda"

# --- O que cada suspeita impede CONCLUIR -------------------------
#
# Os sinais acima têm naturezas diferentes, e tratá-los igual desperdiça
# conclusão de um lado ou produz conformidade falsa do outro. A separação tem a
# mesma forma da assimetria da euclidiana (``core/dominio/mobilidade.py``): nos
# dois casos a pergunta é *de que lado esta imprecisão erra?*
#
# * **Lacuna** só pode ESCONDER escolas. Achar uma dentro do limiar continua
#   sendo prova válida — ela existe, está cadastrada e está perto. Mas NÃO achar
#   nenhuma pode ser ausência de registro, não de escola; por isso trava a
#   reprovação.
# * **Coordenada duvidosa** pode APROXIMAR FALSAMENTE. Várias escolas na mesma
#   coordenada parecem estar a 300 m do terreno sem estar. Aqui nem a
#   aprovação se sustenta.
#
# Não existe o sinal "coordenada igual ao centróide do município": nunca
# disparou em dado real, e o pipeline nunca entregou o centróide.
#
# A classificação mora aqui, e não em ``if``s dentro das regras, porque ela é
# propriedade do sinal — do mesmo modo que ``Medicao.limite_inferior`` é
# propriedade da medição.
SUSPEITAS_DE_LACUNA = frozenset({
    SUSPEITA_SEM_ETAPA, SUSPEITA_CONTAGEM_IMPLAUSIVEL, SUSPEITA_DISTANCIA_ABSURDA})
SUSPEITAS_DE_COORDENADA = frozenset({SUSPEITA_COORDENADAS_IDENTICAS})

ROTULO_CLASSE_SUSPEITA = {
    "lacuna": "lacuna de cadastro (impede reprovar)",
    "coordenada": "coordenada duvidosa (impede reprovar e aprovar)",
}


def classe_da_suspeita(codigo: str) -> str:
    """``"lacuna"`` | ``"coordenada"`` | ``""`` para sinal desconhecido."""
    if codigo in SUSPEITAS_DE_LACUNA:
        return "lacuna"
    if codigo in SUSPEITAS_DE_COORDENADA:
        return "coordenada"
    return ""


def impede_reprovar(suspeitas) -> bool:
    """Qualquer suspeita trava a reprovação """
    return bool(suspeitas)


def impede_aprovar(suspeitas) -> bool:
    """Só as de coordenada travam a aprovação.

    ``suspeitas`` é uma lista de :class:`Suspeita` ou de códigos.
    """
    return any(getattr(s, "codigo", s) in SUSPEITAS_DE_COORDENADA
               for s in suspeitas or ())


def sinais_inativos(*, populacao_municipal: int | None = None) -> dict[str, str]:
    """Sinais que NÃO puderam ser verificados, com a razão de cada um.

    Existe para que o relatório distinga "o sinal não disparou" de "o sinal não
    foi verificado" — confundir os dois transforma ausência de checagem em
    aparência de aprovação.
    """
    inativos: dict[str, str] = {}
    if not populacao_municipal:
        inativos[SUSPEITA_CONTAGEM_IMPLAUSIVEL] = (
            "população municipal indisponível no snapshot de municípios")
    return inativos


# Piso deliberadamente generoso: serve para detectar LACUNA DE CADASTRO, não
# para auditar cobertura educacional. Um município de 900 mil habitantes com
# cinco escolas públicas é cadastro incompleto, não política pública.
HABITANTES_POR_ESCOLA_ESPERADO = 20_000
# Um ponto a mais de 10 km do terreno, em município com população urbana, é
# quase sempre coordenada errada ou cadastro de outro lugar.
RAIO_DE_SANIDADE_M = 10_000.0


@dataclass
class Equipamento:
    """Um equipamento público de educação, pronto para as regras ENQ."""

    nome: str
    lat: float
    lon: float
    ciclos: list[str] = field(default_factory=list)
    rede: str = ""
    situacao: str = ""
    atendimento: str = ATENDIMENTO_GERAL
    conveniada: bool | None = None
    fonte: str = FONTE_CSV
    precisao: str = PRECISAO_DECLARADA
    codigo_inep: str | None = None
    endereco: str | None = None
    procedencia: dict = field(default_factory=dict)

    @property
    def publico(self) -> bool:
        return self.rede in REDES_PUBLICAS

    @property
    def ativo(self) -> bool:
        return self.situacao == SITUACAO_ATIVA

    @property
    def escolariza_demanda_geral(self) -> bool:
        return self.atendimento in ATENDIMENTOS_CONSIDERADOS

    @property
    def oferta_publica_ampliada(self) -> bool:
        """Público em sentido estrito **ou** privado conveniado ao poder público.

        Não é usado na avaliação — a regra fixada é a rede pública estrita. Serve
        ao estudo de sensibilidade, porque em educação infantil é por convênio
        que muitos municípios entregam a vaga, e esconder isso numa premissa
        seria pior do que medir e declarar.
        """
        return self.publico or bool(self.conveniada)

    def atende(self, ciclo: str) -> bool:
        return ciclo in self.ciclos

    def to_dict(self) -> dict:
        return {"nome": self.nome, "lat": self.lat, "lon": self.lon,
                "ciclos": list(self.ciclos), "rede": self.rede,
                "situacao": self.situacao, "atendimento": self.atendimento,
                "conveniada": self.conveniada, "fonte": self.fonte,
                "precisao": self.precisao, "codigo_inep": self.codigo_inep,
                "endereco": self.endereco, "procedencia": self.procedencia}

    @classmethod
    def from_dict(cls, d: dict) -> Equipamento:
        return cls(nome=d.get("nome", ""), lat=float(d["lat"]), lon=float(d["lon"]),
                   ciclos=list(d.get("ciclos") or []), rede=d.get("rede", ""),
                   situacao=d.get("situacao", ""),
                   atendimento=d.get("atendimento") or ATENDIMENTO_GERAL,
                   conveniada=d.get("conveniada"),
                   fonte=d.get("fonte", FONTE_CSV),
                   precisao=d.get("precisao", PRECISAO_DECLARADA),
                   codigo_inep=d.get("codigo_inep"), endereco=d.get("endereco"),
                   procedencia=dict(d.get("procedencia") or {}))


# ---------------------------------------------------------------------------
# Filtragem normativa
# ---------------------------------------------------------------------------

@dataclass
class Filtragem:
    """Resultado dos filtros: o que passou, o que caiu e **por quê**."""

    aceitos: list[Equipamento] = field(default_factory=list)
    descartados: list[tuple[Equipamento, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.aceitos) + len(self.descartados)

    @property
    def contagem_por_motivo(self) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for _, motivo in self.descartados:
            contagem[motivo] = contagem.get(motivo, 0) + 1
        return contagem

    def resumo(self) -> str:
        """Frase para o relatório — é o que torna um não conforme auditável."""
        if not self.descartados:
            return f"{self.total} equipamento(s) considerado(s); nenhum descartado."
        partes = ", ".join(
            f"{n} {ROTULO_DESCARTE.get(m, m)}"
            for m, n in sorted(self.contagem_por_motivo.items(),
                               key=lambda kv: -kv[1]))
        return (f"{self.total} equipamento(s) no conjunto; {len(self.aceitos)} "
                f"considerado(s); {len(self.descartados)} descartado(s) — {partes}.")

    def to_dict(self) -> dict:
        return {"total": self.total, "aceitos": len(self.aceitos),
                "descartados": len(self.descartados),
                "por_motivo": self.contagem_por_motivo,
                "resumo": self.resumo()}


def filtrar(equipamentos: list[Equipamento], *, ciclo: str | None = None) -> Filtragem:
    """Aplica os filtros normativos **antes** de qualquer cálculo de distância.

    Ordem dos testes é deliberada: coordenada, rede, situação, restrição de
    atendimento, ciclo. Assim o motivo reportado é o mais básico — dizer "não
    atende ao ciclo" de uma linha que não tem nem coordenada confundiria o
    usuário. A restrição de atendimento vem depois da situação porque só faz
    sentido perguntar *quem* a escola atende depois de saber que ela funciona.
    """
    resultado = Filtragem()
    for e in equipamentos:
        if e.lat is None or e.lon is None:
            resultado.descartados.append((e, DESCARTE_SEM_COORDENADA))
        elif not e.rede:
            resultado.descartados.append((e, DESCARTE_REDE_INDEFINIDA))
        elif not e.publico:
            resultado.descartados.append((e, DESCARTE_REDE_PRIVADA))
        elif not e.situacao:
            resultado.descartados.append((e, DESCARTE_SITUACAO_INDEFINIDA))
        elif not e.ativo:
            resultado.descartados.append((e, DESCARTE_SITUACAO_INATIVA))
        elif e.atendimento == ATENDIMENTO_SEM_ESCOLARIZACAO:
            resultado.descartados.append((e, DESCARTE_SEM_ESCOLARIZACAO))
        elif e.atendimento == ATENDIMENTO_EXCLUSIVO_DEFICIENCIA:
            resultado.descartados.append((e, DESCARTE_ATENDIMENTO_EXCLUSIVO))
        elif ciclo and not e.atende(ciclo):
            resultado.descartados.append((e, DESCARTE_CICLO_DIVERSO))
        else:
            resultado.aceitos.append(e)
    return resultado


def sensibilidade_conveniadas(equipamentos: list[Equipamento], *,
                              ciclo: str | None = None) -> dict:
    """Mede o efeito da regra "somente rede pública" sobre o resultado.

    A regra avaliada é e continua sendo a pública estrita. Mas em educação
    infantil a vaga costuma ser entregue por **convênio** com entidade privada,
    e uma creche conveniada fica a 300 m do terreno tanto quanto uma municipal.
    Então o número que a avaliação usa vem acompanhado do número que ela
    deixaria de usar — e a diferença é resultado, não nota de rodapé.
    """
    estrito = filtrar(equipamentos, ciclo=ciclo)
    conveniadas = [e for e, m in estrito.descartados
                   if m == DESCARTE_REDE_PRIVADA and e.conveniada
                   and (not ciclo or e.atende(ciclo))]
    return {
        "considerados": len(estrito.aceitos),
        "conveniadas_excluidas": len(conveniadas),
        "considerados_se_incluisse": len(estrito.aceitos) + len(conveniadas),
        "nomes": [e.nome for e in conveniadas],
        "regra_aplicada": "somente rede pública (municipal, estadual, federal)",
    }


# ---------------------------------------------------------------------------
# Mesclagem INEP × CSV (modo complementar)
# ---------------------------------------------------------------------------

def mesclar(oficiais: list[Equipamento],
            declarados: list[Equipamento]) -> tuple[list[Equipamento], dict]:
    """Une o snapshot oficial com o CSV do usuário, deduplicando por código INEP.

    O CSV **vence** no conflito: ele existe justamente para corrigir e
    complementar o cadastro. O que substituiu e o que acrescentou é contado,
    para o relatório poder dizer de onde veio cada evidência.
    """
    por_codigo = {e.codigo_inep: e for e in oficiais if e.codigo_inep}
    sem_codigo = [e for e in oficiais if not e.codigo_inep]

    substituidos, acrescentados = 0, 0
    extras: list[Equipamento] = []
    for e in declarados:
        if e.codigo_inep and e.codigo_inep in por_codigo:
            por_codigo[e.codigo_inep] = e
            substituidos += 1
        else:
            extras.append(e)
            acrescentados += 1

    conjunto = list(por_codigo.values()) + sem_codigo + extras
    procedencia = {
        "oficiais": len(oficiais), "declarados": len(declarados),
        "substituidos": substituidos, "acrescentados": acrescentados,
        "total": len(conjunto),
    }
    return conjunto, procedencia


# ---------------------------------------------------------------------------
# Sanidade do insumo — para lacuna de cadastro não virar falso não-conforme
# ---------------------------------------------------------------------------

@dataclass
class Suspeita:
    codigo: str
    mensagem: str

    def to_dict(self) -> dict:
        return {"codigo": self.codigo, "mensagem": self.mensagem}


def sanidade(aceitos: list[Equipamento], *, ciclo: str,
             populacao_municipal: int | None = None,
             total_no_conjunto: int | None = None) -> list[Suspeita]:
    """Sinais de que o insumo pode estar incompleto — **antes** de reprovar.

    Nenhum destes sinais afirma que o requisito é atendido: eles afirmam que a
    base não permite reprovar com segurança. Reprovar só é permitido quando o
    insumo passou por aqui.
    """
    sinais: list[Suspeita] = []
    rotulo = ROTULO_CICLO.get(ciclo, ciclo)

    if not aceitos:
        if total_no_conjunto:
            sinais.append(Suspeita(
                SUSPEITA_SEM_ETAPA,
                f"Nenhum equipamento público e ativo de {rotulo} restou no "
                f"município após os filtros, apesar de {total_no_conjunto} "
                "registro(s) no conjunto. Pode ser cadastro incompleto **ou** "
                "município cujos equipamentos dessa etapa são todos privados "
                "ou inativos — situações diferentes, e só a vistoria distingue."))
        else:
            sinais.append(Suspeita(
                SUSPEITA_SEM_ETAPA,
                f"Nenhum equipamento de {rotulo} no cadastro do município. "
                "Cadastro provavelmente incompleto."))
        return sinais

    if populacao_municipal:
        esperado = max(1, int(populacao_municipal // HABITANTES_POR_ESCOLA_ESPERADO))
        if len(aceitos) < esperado:
            sinais.append(Suspeita(
                SUSPEITA_CONTAGEM_IMPLAUSIVEL,
                f"Apenas {len(aceitos)} equipamento(s) de {rotulo} para "
                f"{populacao_municipal:,} habitantes".replace(",", ".") +
                f" — abaixo do piso de plausibilidade ({esperado}). O cadastro "
                "aparenta estar incompleto para este município."))

    if len(aceitos) > 1:
        primeiro = (round(aceitos[0].lat, 4), round(aceitos[0].lon, 4))
        if all((round(e.lat, 4), round(e.lon, 4)) == primeiro for e in aceitos[1:]):
            sinais.append(Suspeita(
                SUSPEITA_COORDENADAS_IDENTICAS,
                f"Os {len(aceitos)} equipamentos têm a mesma coordenada "
                f"({primeiro[0]}, {primeiro[1]}) — artefato conhecido de "
                "cadastro: a coordenada não é do estabelecimento."))

    return sinais


def suspeita_por_distancia(distancia_m: float | None,
                           limite_m: float = RAIO_DE_SANIDADE_M) -> Suspeita | None:
    """Sinal de suspeita quando o mais próximo está absurdamente longe.

    Fica separado porque a distância só existe depois do roteamento (R5), e o
    princípio é o mesmo: um valor absurdo acusa o insumo, não o terreno.
    """
    if distancia_m is None or distancia_m <= limite_m:
        return None
    return Suspeita(
        SUSPEITA_DISTANCIA_ABSURDA,
        f"O equipamento mais próximo está a {distancia_m/1000:.1f} km — acima "
        f"do raio de sanidade ({limite_m/1000:.0f} km). Antes de reprovar, "
        "verifique se o cadastro do município está completo.")


# ---------------------------------------------------------------------------
# Recorte municipal resolvido
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecorteMunicipal:
    """Os equipamentos de um município, já resolvidos pela camada de aplicação.

    Existe para que a regra de distância **pergunte ao contexto** quais são os
    equipamentos do município, em vez de abrir ``config/equipamentos_<ibge>.csv``
    por conta própria (D1 do ADR-011). Pertence ao
    território, não ao empreendimento: o empreendimento só aponta o município.

    ``leitura`` é a ``Leitura`` do CSV (``infra/gis/csv_equipamentos.py``), ou
    ``None`` quando o recorte não existe. ``origem`` é de onde ele veio — só para
    diagnóstico: é o caminho que a mensagem de "recorte ausente" mostra.
    """

    codigo_ibge: str
    origem: str = ""
    leitura: Any = None
    procedencia: dict = field(default_factory=dict)

    @property
    def disponivel(self) -> bool:
        """Há recorte, e ele tem as colunas obrigatórias."""
        return self.leitura is not None and not self.leitura.faltando

    @property
    def equipamentos(self) -> list:
        return list(self.leitura.equipamentos) if self.leitura is not None else []
