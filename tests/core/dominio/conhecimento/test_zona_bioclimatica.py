"""ADR-030 — a zona é valor de domínio com procedência junto, e vocabulário fechado.

Duas coisas se prendem aqui, e as duas são decisão, não conveniência:

1. **Doze classes, não oito.** A edição vigente (ABNT TR 15220-3-1:2024) não
   tem zona 7 nem 8. Aceitar ``"7"`` seria deixar entrar, pela porta dos fundos,
   a tradução entre edições que a DN-08 proíbe.
2. **Herança não é silenciosa.** Zona herdada do município de origem se
   identifica pelo próprio valor — quem monta o relatório não precisa reabrir a
   base para saber que herdou.
"""

from __future__ import annotations

import pytest

from core.dominio.conhecimento.zona_bioclimatica import (
    CLASSES,
    FONTE_HERANCA,
    FONTE_NORMA,
    ZonaBioclimatica,
)


def test_as_doze_classes_da_edicao_vigente():
    assert CLASSES == ("1M", "1R", "2M", "2R", "3A", "3B",
                       "4A", "4B", "5A", "5B", "6A", "6B")
    assert "7" not in CLASSES and "8" not in CLASSES


@pytest.mark.parametrize("invalida", ["7", "8", "Z3", "3", "", "3C", "1"])
def test_classe_fora_do_vocabulario_e_erro(invalida):
    with pytest.raises(ValueError):
        ZonaBioclimatica(classe=invalida, codigo_ibge="4307807")


def test_zona_da_norma_nao_e_herdada():
    zona = ZonaBioclimatica(classe="2R", codigo_ibge="4307807")
    assert zona.fonte == FONTE_NORMA
    assert zona.herdada is False
    assert zona.origens == ()
    assert str(zona) == "2R"


def test_zona_herdada_se_declara_e_nomeia_as_origens():
    zona = ZonaBioclimatica(classe="5B", codigo_ibge="5101837",
                            fonte=FONTE_HERANCA,
                            origens=("5107925", "5106240"))
    assert zona.herdada is True
    assert zona.origens == ("5107925", "5106240")
