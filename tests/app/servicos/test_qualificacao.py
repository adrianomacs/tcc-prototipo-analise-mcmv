"""`app.servicos.qualificacao` — o território analisado, lido do relatório.

O relatório sai das três regras de verdade (executor + ``relatorio_json.montar``),
para o serviço ser preso às chaves que o núcleo GRAVA. ``_relatorio`` também serve ao teste da página.
"""

from __future__ import annotations

from app.servicos import qualificacao
from core.aplicacao.executor import executar
from core.dominio.conhecimento.porte_municipal import PopulacaoMunicipal
from core.dominio.contratos.regra import Contexto
from core.dominio.empreendimento import Empreendimento, Localizacao
from core.dominio.unidade_tipo import UnidadeTipo
from core.infra.exportadores import relatorio_json

META = {"municipio_ibge": "4307807",
        "declaracoes": {"uf": "RS", "municipio": "Estrela",
                        "municipio_ibge": "4307807"}}
ESTRELA = PopulacaoMunicipal(codigo_ibge="4307807", populacao=32183)


def _relatorio(previstas: int, populacao=ESTRELA, tipos=()) -> dict:
    emp = Empreendimento(localizacao=Localizacao("4307807"),
                         unidades_previstas=previstas, unidades_tipo=list(tipos))
    resultados = executar(Contexto(empreendimento=emp,
                                   populacao_municipal=populacao),
                          ids_selecionados=["EMP-025"])
    return relatorio_json.montar(resultados, meta=META)


def test_municipio_vem_do_meta_do_relatorio():
    assert qualificacao.municipio(_relatorio(300)) == {
        "nome": "Estrela", "uf": "RS", "codigo_ibge": "4307807"}
    assert qualificacao.municipio(None) == {"nome": "", "uf": "", "codigo_ibge": ""}
