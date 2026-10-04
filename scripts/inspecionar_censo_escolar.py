"""Inspetor dos microdados do Censo Escolar — **só lê e imprime**.

Irmão do ``inspecionar_inep.py``, e existe pelo mesmo motivo de método: o
adaptador do microdado será escrito contra nomes de coluna **verificados**, não
supostos. A diferença é o tamanho — o arquivo de escolas do Censo tem uma linha
por estabelecimento do país e centenas de colunas, então aqui tudo é lido em
**streaming**, uma linha por vez, sem nunca carregar o arquivo na memória.

**O que este inspetor mostra:** o arquivo
de escola do microdado 2025 **não responde sozinho** nenhuma das duas perguntas
para as quais ele havia sido escolhido.

* Não traz **coordenada**: ``LATITUDE``/``LONGITUDE`` constam do dicionário, mas
  a divulgação pública retirou o bloco de endereço inteiro.
* Não traz **oferta de etapa**: ``IN_INF``/``IN_FUND_AI``/``IN_FUND_AF`` não
  existem nesta safra, e ``IN_COMUM_FUND_AI`` — o candidato de nome parecido — é
  indicador de **educação especial**, não de etapa.

Daí as três fontes: a etapa vem da ``Tabela_Turma`` (``QT_TUR_*``), a coordenada
vem do Catálogo de Escolas, e quem compõe as três é
``core/territorio/de_inep.py``. Este script continua valendo pelo que ele é —
o primeiro a olhar uma safra nova, antes de qualquer suposição virar código.
E a lição que ele deu vale além do caso: **o dicionário oficial não é o
arquivo**, e nome parecido não é semântica parecida.

O que o script responde:

1. **Como o arquivo é** — encoding, separador, número de colunas e de linhas.
2. **Quais das colunas que precisamos existem de fato**, com o nome exato. É a
   pergunta central: nada é assumido daqui em diante.
3. **Que valores cada coluna categórica assume**, com contagem, no recorte pedido
   — é o vocabulário a escrever no ``de_inep.py``.
4. **Cobertura de coordenada** no município do recorte, entre as escolas que
   passariam nos filtros normativos (pública + em atividade). É o número que
   decide se o ``insumo_suspeito`` dispara.
5. **Cruzamento com o export do Catálogo**, por código INEP: escola em uma fonte
   e não na outra, e coordenada que discorda entre as duas. Duas fontes
   independentes sobre o mesmo município é achado de qualidade de dado, e é de
   graça.

Uso::

    python scripts/inspecionar_censo_escolar.py "entradas/inep/microdados_ed_basica_2025.csv" --municipio 4307807
    python scripts/inspecionar_censo_escolar.py <csv> --municipio Estrela --catalogo entradas/gis/escolas_estrela_rs.csv

``--municipio`` não é opcional na prática: sem ele o script para depois do
retrato do arquivo, porque tudo o que vem depois é medido no recorte municipal.
"""

from __future__ import annotations

import argparse
import codecs
import csv
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dominio import equipamentos as eq
from core.infra.gis import csv_equipamentos as leitor

LARGURA = 78
LIMITE_CATEGORICA = 40

# Candidatos por finalidade, em ordem de preferência. O script reporta qual
# existe — a lista é hipótese a confirmar, não configuração a confiar.
CANDIDATOS: dict[str, tuple[str, ...]] = {
    "codigo_escola": ("CO_ENTIDADE", "CO_ESCOLA", "PK_COD_ENTIDADE"),
    "nome_escola": ("NO_ENTIDADE", "NO_ESCOLA"),
    "codigo_municipio": ("CO_MUNICIPIO", "FK_COD_MUNICIPIO"),
    "nome_municipio": ("NO_MUNICIPIO",),
    "uf": ("SG_UF", "CO_UF"),
    "ano": ("NU_ANO_CENSO", "ANO_CENSO"),
    "dependencia": ("TP_DEPENDENCIA",),
    "situacao": ("TP_SITUACAO_FUNCIONAMENTO", "TP_SITUACAO"),
    "categoria_privada": ("TP_CATEGORIA_ESCOLA_PRIVADA",),
    # Modalidade — é o que o arquivo de escola realmente informa.
    "escolarizacao": ("IN_ESCOLARIZACAO",),
    "regular": ("IN_REGULAR",),
    "especial_exclusiva": ("IN_ESPECIAL_EXCLUSIVA",),
    "eja": ("IN_EJA",),
    "profissionalizante": ("IN_PROFISSIONALIZANTE", "IN_PROF"),
    # Convênio: nesta safra só existe o conceito LARGO (parceria ou convênio).
    "parceria": ("IN_PODER_PUBLICO_PARCERIA",),
    "conveniada": ("IN_CONVENIADA_PP", "TP_CONVENIADA_PP"),
    # AUSENTES de propósito nesta safra — mantidas na lista para o inspetor
    # IMPRIMIR "AUSENTE" e deixar o fato visível em vez de subentendido:
    "latitude": ("LATITUDE", "NU_LATITUDE"),
    "longitude": ("LONGITUDE", "NU_LONGITUDE"),
    "infantil": ("IN_INF",),
    "fundamental_ai": ("IN_FUND_AI",),
    "fundamental_af": ("IN_FUND_AF",),
}
# As indispensáveis — e só as que o arquivo de ESCOLA de fato pode entregar.
#
# Coordenada e etapa NÃO estão aqui, e a ausência é proposital: a
# divulgação pública de 2025 retirou o bloco de endereço (logo, não há
# coordenada) e não traz indicador de oferta de etapa. Exigi-las aqui faria o
# inspetor recusar o arquivo certo. Elas vêm de outras fontes — a etapa da
# ``Tabela_Turma`` (QT_TUR_*), a coordenada do Catálogo de Escolas — e quem
# compõe as três é ``core/territorio/de_inep.py``.
ESSENCIAIS = ("codigo_escola", "nome_escola", "codigo_municipio", "dependencia",
              "situacao", "escolarizacao")
# Colunas categóricas cujos valores queremos ver.
CATEGORICAS = ("ano", "dependencia", "situacao", "categoria_privada",
               "escolarizacao", "regular", "especial_exclusiva", "eja",
               "profissionalizante", "parceria", "conveniada",
               "infantil", "fundamental_ai", "fundamental_af")


def _titulo(texto: str) -> None:
    print()
    print("=" * LARGURA)
    print(texto)
    print("=" * LARGURA)


def _secao(texto: str) -> None:
    print()
    print(texto)
    print("-" * len(texto))


def _utf8_tolerando_corte(bruto: bytes) -> str | None:
    """Decodifica como UTF-8 tolerando um caractere partido no fim do trecho.

    O trecho é um corte arbitrário de 64 KB. Se o corte cair no meio de uma
    sequência multibyte — e num arquivo nacional cheio de acento isso é
    provável, não excepcional — um ``bytes.decode`` cru levanta, e a conclusão
    seria "não é UTF-8": errada, e cara, porque o arquivo inteiro passaria a
    ser lido em latin-1 e todo nome acentuado viraria mojibake. O decodificador
    incremental com ``final=False`` guarda a cauda incompleta em vez de falhar,
    que é exatamente a distinção entre *byte inválido* e *trecho cortado*.
    """
    decodificador = codecs.getincrementaldecoder("utf-8")()
    try:
        return decodificador.decode(bruto, False)
    except UnicodeDecodeError:
        return None


def _encoding_e_separador(caminho: str) -> tuple[str, str]:
    """Decide encoding e separador pelo primeiro trecho, sem abrir o arquivo todo.

    O microdado costuma vir em latin-1 com ';', mas isso já mudou entre anos —
    por isso é decidido, não assumido.
    """
    with open(caminho, "rb") as f:
        inicio = f.read(65536)
    if inicio[:3] == b"\xef\xbb\xbf":
        encoding = "utf-8-sig"
        amostra = inicio.decode("utf-8-sig", errors="replace")
    else:
        texto = _utf8_tolerando_corte(inicio)
        if texto is None:
            encoding, amostra = "latin-1", inicio.decode("latin-1")
        else:
            encoding, amostra = "utf-8", texto
    linha = amostra.splitlines()[0] if amostra.splitlines() else ""
    separador = max((";", ",", "\t", "|"), key=linha.count)
    return encoding, separador


def _resolver(cabecalho: list[str]) -> tuple[dict[str, str], dict[str, int], list[str]]:
    """``(finalidade -> coluna real, finalidade -> posição, essenciais ausentes)``.

    A posição sai daqui junto com o nome, e não de um ``cabecalho.index(nome)``
    posterior: o nome guardado é o **normalizado** (``strip``), e procurá-lo na
    lista crua levanta ``ValueError`` se o cabeçalho real tiver espaço em volta
    do rótulo. Casar por posição elimina a classe inteira.

    A ordem dos ``CANDIDATOS`` é preferência declarada — pelo mesmo motivo: a
    detecção não pode ser decidida pela ordem das colunas no arquivo.
    """
    posicoes: dict[str, int] = {}
    for i, bruto in enumerate(cabecalho):
        chave = (bruto or "").strip().lstrip("﻿").upper()
        if chave and chave not in posicoes:      # duplicata fica com a 1ª
            posicoes[chave] = i
    achadas: dict[str, str] = {}
    indice: dict[str, int] = {}
    for finalidade, nomes in CANDIDATOS.items():
        for nome in nomes:
            if nome in posicoes:
                i = posicoes[nome]
                achadas[finalidade] = cabecalho[i].strip()
                indice[finalidade] = i
                break
    ausentes = [f for f in ESSENCIAIS if f not in achadas]
    return achadas, indice, ausentes


def _bandeira(valor: str) -> bool:
    return str(valor or "").strip() in {"1", "1.0"}


def inspecionar(caminho: str, *, municipio: str | None, catalogo: str | None,
                amostra: int) -> None:
    _titulo(f"MICRODADO: {os.path.basename(caminho)}")
    encoding, separador = _encoding_e_separador(caminho)
    print(f"  bytes      : {os.path.getsize(caminho):,}".replace(",", "."))
    print(f"  encoding   : {encoding}")
    print(f"  separador  : {separador!r}")

    with open(caminho, encoding=encoding, errors="replace", newline="") as f:
        leitor_csv = csv.reader(f, delimiter=separador)
        try:
            cabecalho = next(leitor_csv)
        except StopIteration:
            print("\n  ARQUIVO VAZIO.")
            return
        print(f"  colunas    : {len(cabecalho)}")

        achadas, indice, ausentes = _resolver(cabecalho)
        _secao("COLUNAS QUE PRECISAMOS")
        for finalidade in CANDIDATOS:
            col = achadas.get(finalidade)
            marca = " (essencial)" if finalidade in ESSENCIAIS else ""
            print(f"  {finalidade:<18}{marca:<12} "
                  f"{'-> ' + col if col else '-> AUSENTE'}")
        if ausentes:
            print(f"\n  ESSENCIAIS AUSENTES: {', '.join(ausentes)}")
            print("  O adaptador não pode ser escrito sem estas. Confira se o "
                  "arquivo é o de ESCOLAS do microdado (uma linha por "
                  "estabelecimento), e não o de matrículas, turmas ou docentes.")
            return

        def campo(linha: list[str], finalidade: str) -> str:
            i = indice.get(finalidade)
            if i is None or i >= len(linha):
                return ""
            return (linha[i] or "").strip()

        # ---- varredura em streaming ------------------------------------
        total = 0
        no_recorte = 0
        valores: dict[str, Counter] = defaultdict(Counter)
        municipios_vistos: Counter = Counter()
        do_recorte: list[dict] = []
        alvo = (municipio or "").strip().lower()

        for linha in leitor_csv:
            if not any((c or "").strip() for c in linha):
                continue
            total += 1
            cod_mun = campo(linha, "codigo_municipio")
            nome_mun = campo(linha, "nome_municipio")
            municipios_vistos[f"{cod_mun} {nome_mun}".strip()] += 1

            # Sem recorte, nada é acumulado: o vocabulário, a cobertura e o
            # cruzamento são medidos POR MUNICÍPIO, e guardar o país inteiro em
            # memória contraria a razão de o script ler em streaming.
            if not alvo:
                continue
            if alvo not in (cod_mun.lower(), nome_mun.lower()):
                continue
            no_recorte += 1
            for finalidade in CATEGORICAS:
                if finalidade in indice:
                    valores[finalidade][campo(linha, finalidade) or "(vazio)"] += 1
            do_recorte.append({
                "codigo": campo(linha, "codigo_escola"),
                "nome": campo(linha, "nome_escola"),
                "dependencia": campo(linha, "dependencia"),
                "situacao": campo(linha, "situacao"),
                "conveniada": campo(linha, "conveniada") or campo(linha, "parceria"),
                "escolariza": _bandeira(campo(linha, "escolarizacao")),
                "lat": leitor._numero(campo(linha, "latitude")),
                "lon": leitor._numero(campo(linha, "longitude")),
            })

    _secao("VOLUME")
    print(f"  linhas no arquivo          : {total:,}".replace(",", "."))
    print(f"  municípios distintos       : {len(municipios_vistos):,}"
          .replace(",", "."))
    if not alvo:
        print("\n  Sem --municipio o inspetor para aqui, de propósito: o"
              " vocabulário, a\n  cobertura de coordenada e o cruzamento com o"
              " Catálogo são medidos no\n  recorte municipal. Rode de novo com"
              " --municipio <código IBGE de 7 dígitos>.")
        return
    if alvo:
        print(f"  linhas no recorte '{municipio}' : {no_recorte}")
        if not no_recorte:
            print("\n  RECORTE VAZIO. Municípios cujo nome contém o texto pedido:")
            for chave in sorted(municipios_vistos):
                if alvo in chave.lower():
                    print(f"    {chave}  ({municipios_vistos[chave]} escola(s))")
            print("  Use o código IBGE de 7 dígitos para não depender do nome.")
            return

    _secao("VALORES DISTINTOS NO RECORTE")
    for finalidade in CATEGORICAS:
        contagem = valores.get(finalidade)
        if not contagem:
            continue
        col = achadas[finalidade]
        if len(contagem) > LIMITE_CATEGORICA:
            print(f"  {col}: {len(contagem)} valores distintos (texto livre)")
            continue
        resumo = "  ".join(f"{v}={n}" for v, n in sorted(contagem.items()))
        print(f"  {col:<28} {resumo}")

    # ---- filtros normativos -------------------------------------------
    _secao("FILTROS NORMATIVOS")
    print("  (dependência 1/2/3 = federal/estadual/municipal; situação 1 = em"
          " atividade — confirmar contra os valores impressos acima)")
    publicas_ativas = [e for e in do_recorte
                       if e["dependencia"] in {"1", "2", "3"}
                       and e["situacao"] == "1"]
    com_coord = [e for e in publicas_ativas
                 if e["lat"] is not None and e["lon"] is not None]
    print(f"\n  no recorte                      : {len(do_recorte)}")
    print(f"  públicas e em atividade         : {len(publicas_ativas)}")
    print(f"  dessas, que escolarizam         : "
          f"{sum(1 for e in publicas_ativas if e['escolariza'])}")

    if not com_coord:
        print("\n  COORDENADA: nenhuma neste arquivo — e isso é o esperado.")
        print("  A divulgação pública de 2025 retirou o bloco de endereço inteiro")
        print("  (DS_ENDERECO, CO_CEP, NO_BAIRRO, LATITUDE, LONGITUDE). A")
        print("  coordenada vem do Catálogo de Escolas.")
    else:
        pct = 100.0 * len(com_coord) / len(publicas_ativas) if publicas_ativas else 0.0
        print(f"  dessas, com coordenada          : {len(com_coord)} ({pct:.1f}%)")

    if not any(f in achadas for f in ("infantil", "fundamental_ai", "fundamental_af")):
        print("\n  ETAPA: este arquivo não informa oferta de etapa.")
        print("  IN_INF / IN_FUND_AI / IN_FUND_AF não existem nesta safra, e")
        print("  IN_COMUM_FUND_AI, apesar do nome, é indicador de EDUCAÇÃO")
        print("  ESPECIAL — não de etapa ofertada. A etapa vem da Tabela_Turma")
        print("  (QT_TUR_INF_CRE, QT_TUR_INF_PRE, QT_TUR_FUND_AI, QT_TUR_FUND_AF).")

    print("\n  Quem compõe as três fontes é core/territorio/de_inep.py, e quem")
    print("  grava o recorte municipal é scripts/gerar_equipamentos.py. Este")
    print("  inspetor serve para CONFERIR uma safra nova antes de confiar nela.")

    # ---- cruzamento com o Catálogo ------------------------------------
    if not catalogo:
        return
    _secao("CRUZAMENTO COM O EXPORT DO CATÁLOGO")
    if not os.path.exists(catalogo):
        print(f"  NÃO ENCONTRADO: {catalogo}")
        return

    lido = leitor.ler(catalogo, fonte=eq.FONTE_INEP)
    if lido.faltando:
        print(f"  O export não pôde ser lido (faltando: {', '.join(lido.faltando)}).")
        return

    do_catalogo = {e.codigo_inep: e for e in lido.equipamentos if e.codigo_inep}
    do_censo = {e["codigo"]: e for e in do_recorte if e["codigo"]}
    print(f"  microdado: {len(do_censo)} escola(s) · "
          f"catálogo: {len(do_catalogo)} escola(s) com coordenada legível")

    so_censo = sorted(set(do_censo) - set(do_catalogo))
    so_catalogo = sorted(set(do_catalogo) - set(do_censo))
    print(f"\n  só no microdado : {len(so_censo)}")
    for c in so_censo[:amostra]:
        print(f"    {c}  {do_censo[c]['nome'][:50]}")
    print(f"  só no catálogo  : {len(so_catalogo)}")
    for c in so_catalogo[:amostra]:
        print(f"    {c}  {do_catalogo[c].nome[:50]}")

    divergentes = []
    for c in sorted(set(do_censo) & set(do_catalogo)):
        a, b = do_censo[c], do_catalogo[c]
        if a["lat"] is None or a["lon"] is None:
            continue
        d = max(abs(a["lat"] - b.lat), abs(a["lon"] - b.lon))
        if d > 1e-4:                      # ~11 m em latitude
            divergentes.append((c, b.nome, d))
    print(f"\n  coordenada divergente (> ~11 m): {len(divergentes)}")
    for c, nome, d in sorted(divergentes, key=lambda t: -t[2])[:amostra]:
        print(f"    {c}  {nome[:44]:<44} Δ≈{d * 111_000:.0f} m")
    print("\n  Divergência entre duas fontes oficiais não é erro de leitura: é"
          "\n  qualidade de dado, e vale como resultado do TCC.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Inspeciona o arquivo de ESCOLAS dos microdados do Censo "
                    "Escolar (somente leitura).")
    p.add_argument("arquivo", help="CSV de escolas do microdado")
    p.add_argument("--municipio", default=None,
                   help="código IBGE de 7 dígitos (preferível) ou nome do município")
    p.add_argument("--catalogo", default=None,
                   help="export do Catálogo de Escolas do mesmo município, para cruzar")
    p.add_argument("--amostra", type=int, default=10,
                   help="quantos itens listar em cada lista (padrão: 10)")
    args = p.parse_args(argv)

    if not os.path.exists(args.arquivo):
        print(f"NÃO ENCONTRADO: {args.arquivo}")
        return 1
    inspecionar(args.arquivo, municipio=args.municipio, catalogo=args.catalogo,
                amostra=args.amostra)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
