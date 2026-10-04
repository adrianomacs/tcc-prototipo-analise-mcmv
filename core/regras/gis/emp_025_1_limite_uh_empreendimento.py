"""EMP-025.1 — número máximo de UH por empreendimento, conforme o porte do município.

Anexo II, Tabela 1, item 4.I.a: *"Deve ser respeitado o número máximo de
unidades habitacionais (UH) por empreendimento e por grupo de empreendimentos
contíguos, de acordo com o porte populacional do município"* — até 20 mil
habitantes, 50 UH; até 50 mil, 100; até 100 mil, 150; até 500 mil, 250; acima,
300. Esta folha é a primeira metade do "e": o limite **por empreendimento**. A
segunda, o grupo de contíguos, é EMP-025.2, remetida (DN-04).

Os dois lados da comparação, e de onde cada um vem
--------------------------------------------------

* **O porte** é fato censitário, nunca declarado (ADR-030): a população do
  Censo 2022 chega pronta em ``ctx.populacao_municipal`` e é classificada pela
  tabela **deste item** — que não é a do Anexo I (ADR-030).
* **A contagem** é ``Empreendimento.unidades_previstas``, o total DECLARADO da
  proposta (ADR-028). A pergunta da norma é sobre o empreendimento inteiro, e
  esse número não é extraível de modelo nenhum: um IFC de 1 UH representando
  um tipo de 300 aprovaria, por construção, um empreendimento que estoura o
  limite. É por isso que esta regra não lê ``unidades_representadas``, ao
  contrário das EDI dimensionais (ADR-021) — e é por isso que ela é GIS, não
  BIM + GIS: declaração × território.

Quando o número declarado não serve
-----------------------------------

Sem ``unidades_previstas`` não há o que comparar. Com ela declarada, mas
contradita por outra declaração do próprio proponente — as unidades tipo somam
mais que o previsto, ou a composição das edificações passa das unidades de um
tipo —, decidir sobre ela seria escolher entre duas declarações; a regra não
escolhe, e sai NÃO AVALIÁVEL por ``inconsistencia_declaratoria`` (ADR-022).
Soma das unidades tipo **menor** que o previsto é declaração incompleta,
legítima, e não bloqueia.
"""

from __future__ import annotations

from core.dominio.conhecimento import porte_municipal as porte
from core.dominio.contratos.regra import Contexto, Dominio, Regra, Resultado, Verbo
from core.dominio.vocabulario import motivos, tipos_diagnostico
from core.regras.registro import registrar

# Chave de despacho do detalhe (o relatório genérico mostra as chaves).
TIPO_DIAGNOSTICO = tipos_diagnostico.PORTE_EMPREENDIMENTO
REF_PORTARIA = "Anexo II, Tab. 1, item 4.I.a"


def _tabela() -> list[dict]:
    return [{"faixa": f.rotulo, "limite_por_empreendimento": f.valores[0]}
            for f in porte.PORTE_EMPREENDIMENTO_4_I_A]


@registrar
class EMP0251(Regra):
    id = "EMP-025.1"
    dominio = Dominio.GIS
    verbo = Verbo.CONTAGEM
    descricao = ("Número máximo de UH por empreendimento, conforme o porte "
                 "populacional do município")
    alvo = ("UH previstas declaradas na proposta × população municipal do "
            "Censo 2022")
    parametro = {
        "limites_por_faixa": _tabela(),
        "contagem": "Empreendimento.unidades_previstas (declarada)",
        "porte": "população do Censo 2022, SIDRA tabela 4714",
        "ref_portaria": REF_PORTARIA,
    }

    def checar(self, ctx: Contexto) -> Resultado:
        emp = ctx.empreendimento
        populacao = getattr(ctx, "populacao_municipal", None)
        detalhe = {
            "tipo": TIPO_DIAGNOSTICO,
            "ref_portaria": REF_PORTARIA,
            "codigo_ibge": emp.codigo_ibge,
            "unidades_previstas": emp.unidades_previstas,
            "unidades_declaradas_nos_tipos": emp.unidades_declaradas,
            "tabela": _tabela(),
        }

        if populacao is None and not emp.codigo_ibge:
            # Falta uma declaração do proponente, não a população (ADR-033).
            return self.nao_avaliavel(
                motivo=motivos.INSUMO_DO_PROPONENTE_AUSENTE,
                mensagem="Município não declarado em Informações Gerais; sem "
                         "ele não há porte populacional a consultar.",
                detalhe=detalhe)
        if populacao is None:
            causa = (f"o município {emp.codigo_ibge} não tem população do "
                     "Censo 2022 no snapshot")
            return self.nao_avaliavel(
                motivo=motivos.PORTE_INDETERMINADO,
                mensagem=f"Porte populacional indeterminado: {causa}. O limite "
                         "de UH depende do porte, e o porte nunca é chutado "
                         "nem declarado.",
                detalhe=detalhe)

        faixa = porte.faixa(populacao.populacao, porte.PORTE_EMPREENDIMENTO_4_I_A)
        limite = faixa.valores[0]
        detalhe.update({
            "populacao": populacao.populacao,
            "fonte_populacao": populacao.fonte,
            "referencia_populacao": populacao.referencia,
            "faixa": faixa.rotulo,
            "limite": limite,
            # O outro limite da mesma faixa, que EMP-025.2 (remetida) não
            # confere: viaja aqui para a tela mostrar o item inteiro sem
            # reclassificar a população (ADR-001).
            "limite_grupo_contiguos": faixa.valores[1],
        })
        municipio = (f"{populacao.populacao:,} habitantes no Censo 2022"
                     .replace(",", "."))

        if not emp.unidades_previstas:
            return self.nao_avaliavel(
                motivo=motivos.INSUMO_DO_PROPONENTE_AUSENTE,
                mensagem=f"O município tem {municipio} ({faixa.rotulo}): o "
                         f"limite é de {limite} UH por empreendimento. Falta a "
                         "contagem — declare as UH previstas do empreendimento "
                         "em Informações Gerais.",
                valor_esperado=limite, unidade="UH", detalhe=detalhe)

        if not emp.declaracao_consistente:
            partes = []
            if emp.excedente_declarado:
                partes.append(
                    f"as unidades tipo somam {emp.unidades_declaradas} UH, "
                    f"mais que as {emp.unidades_previstas} previstas")
            compostos = [u.nome or u.id for u in emp.unidades_tipo
                         if emp.excedente_composto(u)]
            if compostos:
                partes.append("a composição das edificações passa das unidades "
                              "declaradas em " + ", ".join(compostos))
            detalhe["inconsistencias"] = partes
            return self.nao_avaliavel(
                motivo=motivos.INCONSISTENCIA_DECLARATORIA,
                mensagem="Os números declarados não fecham: "
                         + "; ".join(partes) + ". O limite é de "
                         f"{limite} UH ({faixa.rotulo}), mas a contagem a "
                         "comparar é contradita pela própria declaração — a "
                         "correção é do proponente.",
                valor_esperado=limite, valor_encontrado=emp.unidades_previstas,
                unidade="UH", detalhe=detalhe)

        comuns = {"valor_esperado": limite,
                  "valor_encontrado": emp.unidades_previstas,
                  "unidade": "UH", "detalhe": detalhe}
        texto = (f"{emp.unidades_previstas} UH previstas; o município tem "
                 f"{municipio} ({faixa.rotulo}), e o limite por "
                 f"empreendimento é de {limite} UH.")
        if emp.unidades_previstas <= limite:
            return self.conforme(mensagem=texto, **comuns)
        return self.nao_conforme(
            mensagem=texto + f" Excede em {emp.unidades_previstas - limite} UH.",
            **comuns)
