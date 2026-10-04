"""Registro de regras com auto-descoberta.

O decorador :func:`registrar` é a "etiqueta" colada no topo de cada regra. Ao
importar o pacote ``regras``, todas as regras se anunciam automaticamente neste
registro central — não há lista manual para manter.

Adicionar uma regra ao protótipo = criar um arquivo em ``regras/<dominio>/`` com
uma classe decorada por ``@registrar``. Nada mais precisa ser editado.

Uso na linha de comando::

    python -m core.regras.registro --listar
"""

from __future__ import annotations

import importlib
import pkgutil

from core.dominio.contratos.regra import Regra

# Registro central: id do requisito -> classe da regra.
_REGISTRO: dict[str, type[Regra]] = {}


def registrar(cls: type[Regra]) -> type[Regra]:
    """Decorador que inscreve uma regra no registro central.

    Exemplo::

        @registrar
        class EDI004(Regra):
            id = "EDI-004"
            ...
    """
    if not getattr(cls, "id", ""):
        raise ValueError(
            f"A regra {cls.__name__} precisa declarar um atributo 'id' não vazio."
        )
    if cls.id in _REGISTRO:
        raise ValueError(
            f"Regra duplicada para o id '{cls.id}': "
            f"{_REGISTRO[cls.id].__name__} e {cls.__name__}."
        )
    _REGISTRO[cls.id] = cls
    return cls


def descobrir() -> dict[str, type[Regra]]:
    """Importa recursivamente todos os módulos de ``core.regras``.

    O simples ato de importar dispara os decoradores ``@registrar``, populando
    o registro. Idempotente: pode ser chamado várias vezes sem efeito colateral.
    """
    from core import regras as pacote_regras

    for mod in pkgutil.walk_packages(pacote_regras.__path__, pacote_regras.__name__ + "."):
        importlib.import_module(mod.name)
    return dict(_REGISTRO)


def regras_registradas() -> dict[str, type[Regra]]:
    """Devolve o registro completo, garantindo a descoberta de todas as regras.

    Chama ``descobrir()`` sempre (é idempotente: módulos já importados não
    re-registram). Importante porque um import isolado de uma única regra pode
    popular parcialmente o registro, e não queremos pular a descoberta total.
    """
    descobrir()
    return dict(_REGISTRO)


def _cli() -> None:
    import argparse
    import importlib

    parser = argparse.ArgumentParser(description="Utilitário do registro de regras.")
    parser.add_argument(
        "--listar", action="store_true",
        help="Lista todas as regras registradas (recupera a rastreabilidade).",
    )
    args = parser.parse_args()

    # Executado via `python -m`, este arquivo roda como `__main__` — um objeto
    # de módulo distinto de `core.regras.registro`. `descobrir()` importa as
    # regras, que por sua vez importam `core.regras.registro` pelo nome
    # canônico; é nesse módulo (não em `__main__`) que os decoradores
    # `@registrar` depositam o registro. Por isso lemos sempre pelo módulo
    # canônico, nunca pelas funções locais deste namespace.
    modulo_canonico = importlib.import_module("core.regras.registro")
    regras = modulo_canonico.regras_registradas()
    if args.listar:
        if not regras:
            print("Nenhuma regra registrada.")
            return
        print(f"{len(regras)} regra(s) registrada(s):\n")
        for rid in sorted(regras):
            cls = regras[rid]
            print(f"  {rid:<14} [{cls.dominio.value:<7}] {cls.descricao}")


if __name__ == "__main__":
    _cli()
