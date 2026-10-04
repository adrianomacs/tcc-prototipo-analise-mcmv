"""Medicao e o veredito assimetrico que ela sustenta — Value Object de dominio.

A Portaria exige
distancia caminhavel em rede; a linha reta e, por construcao, um limite
inferior demonstravel dela — nunca uma aproximacao. Essa assimetria vive no
campo Medicao.limite_inferior, e nao em ifs espalhados pelas regras.

A porta Roteador (Protocol) e as constantes de provedor/metrica foram para
core/dominio/contratos/roteador.py — este modulo so descreve o que uma
medicao e e o que ela autoriza concluir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Vereditos de uma comparacao contra o limiar ----------------------------
VEREDITO_ATENDE = "atende"
VEREDITO_NAO_ATENDE = "nao_atende"
VEREDITO_INCONCLUSIVO = "inconclusivo"

# --- Classificacao de UMA medicao contra o limiar ---------------------------
CLASSIF_ATENDE_PROVADO = "atende_provado"
CLASSIF_DENTRO_DO_PISO = "dentro_do_piso"
CLASSIF_FORA_PROVADO = "fora_provado"
CLASSIF_NAO_MEDIDA = "nao_medida"

ROTULO_CLASSIFICACAO = {
    CLASSIF_ATENDE_PROVADO: "atende — medido em rede",
    CLASSIF_DENTRO_DO_PISO: "dentro do limiar em linha reta — não comprova",
    CLASSIF_FORA_PROVADO: "acima do limiar — comprovado",
    CLASSIF_NAO_MEDIDA: "sem medição",
}

EXPLICACAO_CLASSIFICACAO = {
    CLASSIF_ATENDE_PROVADO:
        "Distância caminhável em rede, dentro do limiar: prova de atendimento.",
    CLASSIF_DENTRO_DO_PISO:
        "Distância em linha reta abaixo do limiar. Como a linha reta é um piso "
        "da distância caminhável, o valor real pode ultrapassá-lo — este "
        "equipamento não comprova o atendimento.",
    CLASSIF_FORA_PROVADO:
        "Distância acima do limiar. Medida em linha reta, isso é definitivo: o "
        "caminho real só pode ser maior.",
    CLASSIF_NAO_MEDIDA:
        "Não foi possível medir (coordenada ausente ou erro do provedor). Um "
        "candidato sem número impede reprovar o conjunto.",
}


@dataclass
class Medicao:
    """Uma distância medida entre o terreno e **um** equipamento.

    ``limite_inferior`` é o campo que decide o que esta medição autoriza: quando
    True, o número é um piso do valor real, então serve para reprovar e não para
    aprovar.
    """

    destino: str
    metros: float | None
    provedor: str
    metrica: str
    limite_inferior: bool
    rotulo: str = ""
    segundos: float | None = None
    snap_m: float | None = None
    obtido_em: str = ""
    erro: str | None = None
    detalhe: dict = field(default_factory=dict)

    @property
    def valida(self) -> bool:
        return self.metros is not None and self.erro is None

    @property
    def conclusiva(self) -> bool:
        """True quando a medição pode, sozinha, **aprovar** um requisito."""
        return self.valida and not self.limite_inferior

    def to_dict(self) -> dict:
        return {"destino": self.destino, "rotulo": self.rotulo,
                "metros": self.metros,
                "segundos": self.segundos, "provedor": self.provedor,
                "metrica": self.metrica, "limite_inferior": self.limite_inferior,
                "snap_m": self.snap_m, "obtido_em": self.obtido_em,
                "erro": self.erro, "detalhe": self.detalhe}


def classificar(medicao: Medicao | None, limiar_m: float) -> str:
    """O que ESTA medição prova sobre ESTE equipamento, em relação ao limiar."""
    if medicao is None or not medicao.valida:
        return CLASSIF_NAO_MEDIDA
    if medicao.metros > limiar_m:
        return CLASSIF_FORA_PROVADO
    return CLASSIF_ATENDE_PROVADO if medicao.conclusiva else CLASSIF_DENTRO_DO_PISO


_VEREDITO_DA_CLASSIFICACAO = {
    CLASSIF_ATENDE_PROVADO: VEREDITO_ATENDE,
    CLASSIF_FORA_PROVADO: VEREDITO_NAO_ATENDE,
    CLASSIF_DENTRO_DO_PISO: VEREDITO_INCONCLUSIVO,
    CLASSIF_NAO_MEDIDA: VEREDITO_INCONCLUSIVO,
}


def confrontar(medicao: Medicao | None, limiar_m: float) -> str:
    """Veredito de UMA medição contra o limiar."""
    return _VEREDITO_DA_CLASSIFICACAO[classificar(medicao, limiar_m)]


def melhor_por_destino(medicoes: list[Medicao]) -> dict[str, Medicao]:
    """Uma medição por equipamento, preferindo a que conclui."""
    melhor: dict[str, Medicao] = {}
    for m in medicoes:
        atual = melhor.get(m.destino)
        if atual is None:
            melhor[m.destino] = m
            continue
        if m.conclusiva and not atual.conclusiva or m.conclusiva == atual.conclusiva and m.valida and (
                not atual.valida or m.metros < atual.metros):
            melhor[m.destino] = m
    return melhor


def por_metrica(medicoes: list[Medicao]) -> dict[str, dict[str, Medicao]]:
    """``destino -> métrica -> medição``, preservando as duas medições do par."""
    fora: dict[str, dict[str, Medicao]] = {}
    for m in medicoes:
        do_destino = fora.setdefault(m.destino, {})
        atual = do_destino.get(m.metrica)
        if atual is None or (m.valida and (not atual.valida
                                           or m.metros < atual.metros)):
            do_destino[m.metrica] = m
    return fora


def confrontar_conjunto(medicoes: list[Medicao],
                        limiar_m: float) -> tuple[str, Medicao | None]:
    """``(veredito, medição determinante)`` para o CONJUNTO de equipamentos."""
    if not medicoes:
        return VEREDITO_INCONCLUSIVO, None

    unicas = list(melhor_por_destino(medicoes).values())
    validas = [m for m in unicas if m.valida]
    if not validas:
        return VEREDITO_INCONCLUSIVO, None

    dentro = [m for m in validas if m.conclusiva and m.metros <= limiar_m]
    if dentro:
        return VEREDITO_ATENDE, min(dentro, key=lambda m: m.metros)

    mais_proxima = min(validas, key=lambda m: m.metros)
    if len(validas) == len(unicas) and all(m.metros > limiar_m for m in validas):
        return VEREDITO_NAO_ATENDE, mais_proxima
    return VEREDITO_INCONCLUSIVO, mais_proxima
