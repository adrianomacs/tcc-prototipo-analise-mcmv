"""Serviço de leitura da base normativa de requisitos.

Fonte da verdade: `config/Base_Requisitos_Portaria_MCID_725.xlsx`, aba "Base
de Requisitos (granular)"; o método da decomposição e as definições de
requisito, desdobramento e nó de agregação estão no Leia-me da própria
planilha, e as contagens que as telas mostram saem de `contar_base` e
`contar_recorte`, nunca de número escrito à mão. O subconjunto ATIVO que o
núcleo de fato executa é o listado em `config/regras_ativas.yaml`, lido por
`carregar_ids_ativos`, sem arquivo derivado no meio. A página 1.2.2
(`app/paginas/pesquisa/consolidacao_requisitos.py`) mostra a base
COMPLETA, com os requisitos do recorte ativo destacados: o propósito da
página é situar o recorte do protótipo dentro
do universo normativo da Portaria, não listar só o que roda (isso já é o
papel de `config/grupos_requisitos.yaml` e da página "Requisitos a serem
validados").

Não importa Streamlit — é `servicos/`, não `componentes/` (`app/servicos/` é o único gateway para o núcleo).
Quem cacheia a leitura (a planilha não muda em tempo de execução) é a
própria página, com `st.cache_data`.
"""

from __future__ import annotations

import os
import re

import openpyxl
import pandas as pd
import yaml

from core.infra.caminhos import CONFIG

XLSX = os.path.join(CONFIG, "Base_Requisitos_Portaria_MCID_725.xlsx")
YAML_ATIVAS = os.path.join(CONFIG, "regras_ativas.yaml")
ABA = "Base de Requisitos (granular)"

_PADRAO_ANEXO = re.compile(r"Anexo\s+[IVXLC]+", re.IGNORECASE)


def extrair_anexo(ref_portaria: str | None) -> str:
    """"Anexo I, Tab.1, item 1.a" -> "Anexo I"; sem padrão reconhecido -> "—".

    Não há coluna "Anexo" própria na planilha-mãe — o anexo mora embutido em
    "Ref. Portaria" ("Anexo I" = enquadramento locacional, "Anexo II" =
    georreferenciamento/EMP, "Anexo III" = programa/dimensões da UH). O
    texto já vem com a capitalização correta na fonte; o regex só extrai o
    trecho, sem recapitalizar (evitaria "Anexo Ii" no lugar de "Anexo II").
    """
    if not ref_portaria:
        return "—"
    m = _PADRAO_ANEXO.search(str(ref_portaria))
    return m.group(0) if m else "—"


def carregar_base_completa() -> pd.DataFrame:
    """Lê a planilha-mãe inteira (todas as linhas da base) como DataFrame.

    Cada coluna vem com o nome tal como está na planilha (ex.: "Ref.
    Portaria", "Classificação", "Aplicabilidade"), sem renomeá-las.
    Devolve um DataFrame vazio, sem lançar, se a planilha não existir neste
    ambiente — a página decide o aviso.
    """
    if not os.path.exists(XLSX):
        return pd.DataFrame()
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    if ABA not in wb.sheetnames:
        return pd.DataFrame()
    ws = wb[ABA]
    linhas = list(ws.iter_rows(values_only=True))
    if not linhas:
        return pd.DataFrame()
    cabecalho, *dados = linhas
    df = pd.DataFrame(dados, columns=list(cabecalho))
    df = df[df["ID"].notna()].copy()
    df["Anexo"] = df["Ref. Portaria"].map(extrair_anexo)
    return df.reset_index(drop=True)


def carregar_ids_ativos() -> set[str]:
    """IDs do recorte ativo do protótipo (`config/regras_ativas.yaml`).

    Lida direto do YAML porque a página precisa marcar os ativos dentro da
    base COMPLETA.
    """
    if not os.path.exists(YAML_ATIVAS):
        return set()
    with open(YAML_ATIVAS, "r", encoding="utf-8") as f:
        dados = yaml.safe_load(f) or {}
    return {str(x).strip() for x in (dados.get("ativas") or [])}


ABA_NAO_CONVERTIDOS = "Dispositivos não convertidos"


def carimbo_da_base() -> float:
    """Data de modificação da planilha-mãe (0 se ausente). A página a usa
    como chave do cache: planilha regravada invalida a leitura em memória,
    sem precisar reiniciar o Streamlit."""
    return os.path.getmtime(XLSX) if os.path.exists(XLSX) else 0.0

# Valores da coluna "Tipo de vínculo" (regra 2 do Leia-me da planilha). A
# comparação é pelo prefixo, porque a atomização tem três subespécies.
_NO_DE_AGREGACAO = "Requisito — nó de agregação"
_ATOMIZACAO = "Atomização"
_AGRUPAMENTO = "Agrupamento"


def _eh_requisito(df: pd.DataFrame) -> pd.Series:
    """Requisito = linha cujo "Grupo (pai)" é o próprio ID (Leia-me, regra 2)."""
    return df["ID"] == df["Grupo (pai)"]


def _vinculo(df: pd.DataFrame) -> pd.Series:
    return df["Tipo de vínculo"].fillna("").astype(str)


def contar_base(df: pd.DataFrame) -> dict[str, int]:
    """As contagens da base pela régua do Leia-me da planilha.

    ``linhas`` = ``requisitos`` + ``atomizacoes`` + ``agrupamentos``; o nó de
    agregação é requisito sem verificação própria, por isso ``verificacoes`` =
    ``linhas`` − ``nos_de_agregacao``.
    """
    vinculo = _vinculo(df)
    nos = int((vinculo == _NO_DE_AGREGACAO).sum())
    return {
        "linhas": len(df),
        "requisitos": int(_eh_requisito(df).sum()),
        "atomizacoes": int(vinculo.str.startswith(_ATOMIZACAO).sum()),
        "agrupamentos": int(vinculo.str.startswith(_AGRUPAMENTO).sum()),
        "nos_de_agregacao": nos,
        "verificacoes": len(df) - nos,
    }


def contar_recorte(df: pd.DataFrame, ids_ativos: set[str]) -> dict[str, int]:
    """As mesmas contagens, restritas às linhas do recorte ativo."""
    return contar_base(df[df["ID"].isin(ids_ativos)])


def contar_nao_convertidos() -> int:
    """Dispositivos da Portaria que não viraram linha (aba própria, com o
    motivo), o que fecha a cobertura da base; 0 se a aba não existir."""
    if not os.path.exists(XLSX):
        return 0
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    if ABA_NAO_CONVERTIDOS not in wb.sheetnames:
        return 0
    linhas = list(wb[ABA_NAO_CONVERTIDOS].iter_rows(values_only=True))[1:]
    return sum(1 for linha in linhas if linha and linha[0])

