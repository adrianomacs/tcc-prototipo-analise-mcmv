"""Testes de `app/servicos/requisitos.py`. Puramente unitários, sem Streamlit
(é um teste de `servicos/`, não de página)."""

from __future__ import annotations

import pytest

from app.servicos import requisitos as reqs


class TestExtrairAnexo:

    def test_extrai_anexo_romano_da_referencia(self):
        assert reqs.extrair_anexo("Anexo I, Tab.1, item 1.a") == "Anexo I"
        assert reqs.extrair_anexo("Anexo II, Tab.1, item 1.d") == "Anexo II"
        assert reqs.extrair_anexo("Anexo III, Tab.1, item 2.I.a.i") == "Anexo III"

    def test_sem_padrao_reconhecido_devolve_travessao(self):
        assert reqs.extrair_anexo("Art. 4º, III") == "—"
        assert reqs.extrair_anexo("") == "—"
        assert reqs.extrair_anexo(None) == "—"


class TestCarregarBaseCompleta:

    def test_le_a_planilha_mae_com_335_linhas_e_202_requisitos(self):
        # 299 requisitos de base; o ADR-026 fez de EDI-024 e EDI-019 pais de ramos
        # (301), a decomposição de EMP-025 em EMP-025.1/025.2 levou a 303 e a
        # inclusão dos 32 dispositivos da Portaria que não tinham
        # linha (335 linhas, 202 requisitos) — a contagem muda por decisão
        # registrada na base (Leia-me), nunca para passar.
        df = reqs.carregar_base_completa()
        if df.empty:
            pytest.skip("planilha-mãe não disponível neste ambiente")
        assert len(df) == 335
        assert (df["ID"] == df["Grupo (pai)"]).sum() == 202
        assert "Tipo de vínculo" in df.columns
        assert "ID" in df.columns
        assert "Anexo" in df.columns
        assert df["ID"].is_unique

    def test_coluna_anexo_e_derivada_de_ref_portaria(self):
        df = reqs.carregar_base_completa()
        if df.empty:
            pytest.skip("planilha-mãe não disponível neste ambiente")
        linha = df[df["ID"] == "ENQ-001"].iloc[0]
        assert linha["Anexo"] == "Anexo I"


class TestCarregarIdsAtivos:

    def test_ids_ativos_batem_com_o_csv_derivado(self):
        ativos = reqs.carregar_ids_ativos()
        if not ativos:
            pytest.skip("regras_ativas.yaml não disponível neste ambiente")
        # EMP-001 é a porta da trilha espacial — sempre ativa (ver
        # config/regras_ativas.yaml).
        assert "EMP-001" in ativos
        assert "EDI-004" in ativos

    def test_todo_id_ativo_existe_na_base_completa(self):
        ativos = reqs.carregar_ids_ativos()
        df = reqs.carregar_base_completa()
        if not ativos or df.empty:
            pytest.skip("planilha-mãe ou regras_ativas.yaml indisponíveis neste ambiente")
        ids_na_base = set(df["ID"])
        ausentes = ativos - ids_na_base
        assert not ausentes, f"IDs ativos sem correspondência na base-mãe: {ausentes}"


class TestContagens:
    """A régua do Leia-me da planilha (regra 2): requisito é a linha cujo
    pai é ela mesma; o nó de agregação não tem verificação própria."""

    def test_contagens_da_base_fecham_com_o_leia_me(self):
        df = reqs.carregar_base_completa()
        if df.empty:
            pytest.skip("planilha-mãe não disponível neste ambiente")
        c = reqs.contar_base(df)
        assert c["linhas"] == c["requisitos"] + c["atomizacoes"] + c["agrupamentos"]
        assert c["verificacoes"] == c["linhas"] - c["nos_de_agregacao"]
        assert (c["requisitos"], c["atomizacoes"], c["agrupamentos"],
                c["nos_de_agregacao"], c["verificacoes"]) == (202, 68, 65, 11, 324)

    def test_recorte_conta_requisitos_pela_mesma_regua(self):
        df = reqs.carregar_base_completa()
        ativos = reqs.carregar_ids_ativos()
        if df.empty or not ativos:
            pytest.skip("planilha-mãe ou regras_ativas.yaml indisponíveis neste ambiente")
        c = reqs.contar_recorte(df, ativos)
        assert (c["requisitos"], c["linhas"], c["nos_de_agregacao"]) == (14, 25, 5)

    def test_dispositivos_nao_convertidos_fecham_a_cobertura(self):
        if reqs.carregar_base_completa().empty:
            pytest.skip("planilha-mãe não disponível neste ambiente")
        assert reqs.contar_nao_convertidos() == 29

