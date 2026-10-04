"""Regras que declaram a própria não avaliabilidade — e por quê.

Há requisito que a Portaria exige, que o protótipo reconhece, e que **nenhum
insumo disponível permite avaliar** — não por lacuna de implementação, mas porque
o dado não existe em forma pública. ENQ-010.2 e ENQ-011.2 são o caso: a
alternativa por transporte depende do itinerário do transporte público escolar
municipal, que é dado administrativo da secretaria de educação, não publicado, e
frequentemente comprovado por declaração da Prefeitura peça por peça.

Três razões para a regra EXISTIR em vez de simplesmente faltar:

1. **A agregação precisa do membro.** Sem ele, ``n_pot`` igualaria ``n_conf`` e o
   pai reprovaria quando a alternativa A não atendesse — falso não-conforme
   produzido pela ausência de uma alternativa que a própria norma admite. É a mesma
   sanidade do insumo, na camada da agregação.
2. **O usuário precisa saber.** Requisito ausente da tela é indistinguível de
   requisito esquecido. Requisito presente, com estado NÃO AVALIÁVEL e causa
   declarada, diz o que fazer com ele.
3. **O texto precisa declarar.** Uma limitação que aparece como resultado do
   protótipo é limitação declarada; a mesma limitação fora da lista de requisitos
   é lacuna escondida.

Não é "em implementação" e não é "pendente": as duas palavras prometem uma versão
futura que não vem. É **remetida** — a ferramenta delimita a análise humana em vez
de substituí-la. A planilha-mãe já dizia
isso antes de nós: ENQ-010.2 e ENQ-011.2 são as únicas linhas do recorte com
"Julg. humano complementar: Sim".

Vale a distinção que estas regras materializam: a planilha classifica as duas
como *geoprocessáveis* ("Isócrona de transporte + caminhada"), e isso continua
verdade. Verificabilidade do MÉTODO e disponibilidade do INSUMO são coisas
diferentes, e é a segunda que falta.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Contexto, Regra, Resultado
from core.dominio.vocabulario import motivos, tipos_diagnostico

# Chave de despacho do relatório dedicado destas regras.
TIPO_DIAGNOSTICO = tipos_diagnostico.REMETIDA


class RegraRemetida(Regra):
    """Base das regras que não avaliam e dizem a quem a matéria é remetida.

    A subclasse declara ``remete_a`` (um motivo de ``core.dominio.vocabulario.motivos``),
    ``insumo`` (o que faltaria para avaliar), ``porque`` (por que não está
    disponível) e ``fundamento`` (a referência normativa). O resultado é sempre
    NÃO AVALIÁVEL, e é determinístico: não depende de insumo, de rede nem de
    configuração.
    """

    remete_a: str = ""
    insumo: str = ""
    porque: str = ""
    fundamento: str = ""

    # Nenhum gate. Em particular **não** exige terreno: a regra não mede nada, e
    # exigir terreno faria o executor devolver `terreno_ausente` sempre que a
    # tela ainda não tivesse um — escondendo a causa verdadeira atrás de uma
    # causa da moldura, que é o oposto do que estas regras existem para fazer.
    depende_de: list[str] = []
    exige_terreno = ""

    def checar(self, ctx: Contexto) -> Resultado:
        if not self.remete_a:
            raise ValueError(
                f"A regra remetida {self.id} não declarou 'remete_a'.")
        return self.nao_avaliavel(
            motivo=self.remete_a,
            mensagem=self._mensagem(),
            detalhe={
                "tipo": TIPO_DIAGNOSTICO,
                "remetido_a": self.remete_a,
                "rotulo_remessa": motivos.rotulo(self.remete_a),
                # Lido pelo agregador (``agregacao.RegraAgregacao._membro``) para
                # calcular o teto de reprovabilidade, e pela tela para não
                # chamar esta regra de "implementada". Viaja no resultado em vez
                # de ser deduzido de uma lista de ids em outro lugar.
                "automatizavel": False,
                "insumo": self.insumo,
                "porque": self.porque,
                "fundamento": self.fundamento,
                "acao": motivos.ACAO.get(self.remete_a, ""),
            })

    def _mensagem(self) -> str:
        partes = [p for p in (self.porque,
                              motivos.ACAO.get(self.remete_a, "")) if p]
        return " ".join(partes)
