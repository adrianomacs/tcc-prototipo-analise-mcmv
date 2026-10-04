"""Confere a camada de roteamento contra o recorte real — **só lê e imprime**.

Existe para uma coisa que teste unitário não faz: pôr o número ao lado da
realidade. Ele toma uma coordenada, carrega o recorte municipal versionado e
mostra, por ciclo, os equipamentos mais próximos com o **piso** da distância e o
veredito que a regra emitiria hoje — antes de a regra existir.

O que se ganha olhando a saída:

* dá para conferir duas ou três linhas contra a régua do Google Maps (medir em
  linha reta, não a rota) e ver se o piso bate;
* dá para ver quantos requisitos ficam **inconclusivos** sem provedor de rede,
  que é o custo declarado do rigor assimétrico e o objeto do R7;
* dá para flagrar coordenada absurda no recorte antes de ela virar veredito.

Uso::

    python scripts/conferir_distancias.py --municipio 4307807 --lat -29.5013 --lon -51.9650
    python scripts/conferir_distancias.py --municipio 4307807 --lat -29.5013 --lon -51.9650 --quantos 8
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dominio import equipamentos as eq
from core.dominio import euclidiana as eu
from core.dominio import mobilidade as ct
from core.dominio.vocabulario import motivos
from core.infra.gis import csv_equipamentos as leitor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Limiares da Portaria para o recorte de equipamentos de educação.
LIMIAR_M = {
    eq.CICLO_INFANTIL: 1000.0,
    eq.CICLO_FUND_I: 1500.0,
    eq.CICLO_FUND_II: 1500.0,
}
REQUISITO = {
    eq.CICLO_INFANTIL: "ENQ-009",
    eq.CICLO_FUND_I: "ENQ-010.1",
    eq.CICLO_FUND_II: "ENQ-011.1",
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--municipio", required=True, help="código IBGE de 7 dígitos")
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--quantos", type=int, default=5,
                   help="quantos equipamentos listar por ciclo (padrão: 5)")
    p.add_argument("--recorte", default=None, help="CSV alternativo do recorte")
    args = p.parse_args(argv)

    caminho = args.recorte or os.path.join(
        RAIZ, "config", f"equipamentos_{args.municipio}.csv")
    if not os.path.exists(caminho):
        print(f"RECORTE AUSENTE: {caminho}")
        print("Gere com: python scripts/gerar_equipamentos.py --municipio "
              f"{args.municipio}")
        print(f"Na regra, isso é NÃO AVALIÁVEL com motivo "
              f"'{motivos.INSUMO_AUSENTE}'.")
        return 1

    lido = leitor.ler(caminho, fonte=eq.FONTE_INEP, precisao=eq.PRECISAO_OFICIAL)
    if lido.faltando:
        print(f"Recorte ilegível (faltando: {', '.join(lido.faltando)}).")
        return 1

    origem = (args.lat, args.lon)
    print("=" * 78)
    print(f"ORIGEM {origem[0]:.6f}, {origem[1]:.6f}   ·   recorte "
          f"{os.path.basename(caminho)}   ·   {len(lido.equipamentos)} linha(s)")
    print("=" * 78)
    print("  Distâncias em LINHA RETA — piso da distância caminhável, nunca ela.")
    print("  Confira contra a régua do Google Maps (linha reta, não a rota).")

    roteador = eu.RoteadorEuclidiano()
    for ciclo in eq.CICLOS:
        limiar = LIMIAR_M[ciclo]
        filtragem = eq.filtrar(lido.equipamentos, ciclo=ciclo)
        print(f"\n{'-' * 78}\n{REQUISITO[ciclo]} · {eq.ROTULO_CICLO[ciclo]} · "
              f"limiar {limiar:.0f} m\n{'-' * 78}")
        print(f"  {filtragem.resumo()}")

        if not filtragem.aceitos:
            print(f"  -> NÃO AVALIÁVEL ({motivos.INSUMO_SUSPEITO}): nenhum "
                  "equipamento restou após os filtros.")
            continue

        # O conjunto INTEIRO é medido em linha reta — é de graça, e é o que
        # sustenta a reprovação. O pré-filtro abaixo serve só para dizer a quem
        # se pediria a rede no R5c.
        medicoes = roteador.medir(origem, filtragem.aceitos)
        dentro, raio = eu.candidatos(origem, filtragem.aceitos, limiar)
        print(f"  raio de busca: {raio:.0f} m · iriam ao roteador de rede: "
              f"{len(dentro)} de {len(filtragem.aceitos)}")
        for m in sorted([x for x in medicoes if x.valida],
                        key=lambda x: x.metros)[:args.quantos]:
            marca = "✓" if m.metros <= limiar else " "
            print(f"    {marca} {m.metros:7.0f} m  {m.rotulo[:46]:<46} "
                  f"{m.destino}")

        veredito, determinante = ct.confrontar_conjunto(medicoes, limiar)
        # CONFORME é inalcançável aqui, e de propósito: o único provedor deste
        # script é a linha reta, que não aprova. Se esta linha algum dia
        # imprimir, a assimetria foi quebrada em algum lugar.
        if veredito == ct.VEREDITO_ATENDE:
            print("  -> ERRO: veredito de conformidade a partir de linha reta. "
                  "A assimetria foi quebrada — ver core/roteamento/contrato.py.")
        elif veredito == ct.VEREDITO_NAO_ATENDE:
            print(f"  -> NÃO CONFORME · o mais próximo está a "
                  f"{determinante.metros:.0f} m, acima do limiar mesmo em linha "
                  "reta — a distância caminhável só pode ser maior.")
        else:
            proximo = (f" (o mais próximo tem piso de {determinante.metros:.0f} m)"
                       if determinante else "")
            print(f"  -> NÃO AVALIÁVEL ({motivos.METRICA_INSUFICIENTE}){proximo}")
            print(f"     {motivos.ACAO[motivos.METRICA_INSUFICIENTE]}")

    print(f"\n{'=' * 78}")
    print("  Lembrete: nenhum CONFORME acima é legítimo sem roteamento em rede —")
    print("  a linha reta reprova, não aprova. O que o R5c destrava é o veredito")
    print("  positivo; o negativo já é definitivo aqui.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
