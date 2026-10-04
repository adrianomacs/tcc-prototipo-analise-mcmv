"""ADR-035 — a impressão digital (SHA-256) do arquivo submetido."""

from __future__ import annotations

import hashlib

from core.infra import impressao_digital


def test_sha256_do_conteudo(tmp_path):
    alvo = tmp_path / "modelo.ifc"
    alvo.write_bytes(b"ISO-10303-21;" * 100_000)
    assert impressao_digital.sha256(str(alvo)) == hashlib.sha256(alvo.read_bytes()).hexdigest()


def test_mesmo_nome_outro_conteudo_outra_impressao(tmp_path):
    """É o caso que o nome não resolve: o mesmo arquivo reexportado."""
    alvo = tmp_path / "E1_georref.ifc"
    alvo.write_bytes(b"primeira rodada")
    antes = impressao_digital.sha256(str(alvo))
    alvo.write_bytes(b"segunda rodada")
    assert impressao_digital.sha256(str(alvo)) != antes


def test_sem_arquivo_devolve_vazio(tmp_path):
    assert impressao_digital.sha256(str(tmp_path / "nao_existe.ifc")) == ""
    assert impressao_digital.sha256("") == ""
    assert impressao_digital.sha256(None) == ""
