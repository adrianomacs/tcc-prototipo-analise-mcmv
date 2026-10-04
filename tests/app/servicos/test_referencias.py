"""Testes do serviço da lista de referências (arquivo ``referencias.yaml``)."""

from app.servicos.referencias import carregar_referencias, chave_de_ordem


def test_lista_carrega_e_nao_e_vazia():
    refs = carregar_referencias()
    assert refs
    assert all(r.texto for r in refs)


def test_lista_em_ordem_alfabetica():
    refs = carregar_referencias()
    chaves = [chave_de_ordem(r.texto) for r in refs]
    assert chaves == sorted(chaves)


def test_chaves_unicas():
    refs = carregar_referencias()
    assert len({r.chave for r in refs}) == len(refs)


def test_pendente_explica_o_que_conferir():
    for r in carregar_referencias():
        if r.validar:
            assert r.nota, r.chave


def test_obra_nao_citada_fica_fora_da_lista_mas_no_arquivo():
    """A lista exibida é a do texto vigente: o que está no arquivo com
    ``citada: false`` não aparece, mas continua registrado."""
    exibidas = {r.chave for r in carregar_referencias()}
    todas = carregar_referencias(so_citadas=False)
    nao_citadas = {r.chave for r in todas if not r.citada}
    assert nao_citadas
    assert not nao_citadas & exibidas
    assert exibidas | nao_citadas == {r.chave for r in todas}
