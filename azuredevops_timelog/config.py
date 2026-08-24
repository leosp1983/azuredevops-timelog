"""Constantes confirmadas ao vivo contra o Azure DevOps real (ver tabela
de premissas no plano de implementação). Se a TimeLog mudar o backend
interno dela, é aqui que se conserta primeiro.
"""
import os

ORG = "sysmanagerdevops"
PROJECT = "Petrobras"
PROJECT_ID = "b58a29b5-c60b-44d2-bb3c-80663c8d38a6"
TENANT_ID = "40264be6-1998-420f-8cb2-0bdb5d42adf6"

PBI_AUTOMACAO_ID = 119880
AREA_PATH = "Petrobras\\Plataforma"
ITERATION_PATH = "Petrobras\\Plataforma"
ACTIVITY_VALUE = "30-Desenvolvimento"
ORIGINAL_ESTIMATE_VALUE = 168

# Brasil não observa horário de verão desde 2019 — offset fixo o ano todo.
LOCAL_UTC_OFFSET = "-03:00"

AZDO_API_BASE = f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit"
AZDO_API_VERSION = "7.1"

TIMELOG_API_BASE = f"https://boznet-timelogapi.azurewebsites.net/api/{TENANT_ID}"
TIMELOG_TYPE_ID = "40477e4d-a54c-41a3-730c-08de8429016f"  # "01-Projeto Padrão"
TIMELOG_TYPE_DESCRIPTION = "01-Projeto Padrão"


def azdo_pat() -> str:
    """Lê o Personal Access Token da variável de ambiente AZDO_PAT.

    Cada pessoa usa o próprio token, nunca compartilhado. Gere em
    https://dev.azure.com/sysmanagerdevops/_usersSettings/tokens
    com escopo "Work Items (Read & Write)".
    """
    pat = os.environ.get("AZDO_PAT")
    if not pat:
        raise RuntimeError(
            "Variável de ambiente AZDO_PAT não definida. Gere um Personal "
            "Access Token em "
            "https://dev.azure.com/sysmanagerdevops/_usersSettings/tokens "
            "(escopo 'Work Items (Read & Write)') e defina AZDO_PAT antes "
            "de rodar, ex.: $env:AZDO_PAT = '<token>'"
        )
    return pat


def timelog_functions_key() -> str:
    """Lê a function key do backend da extensão TimeLog da variável de
    ambiente TIMELOG_FUNCTIONS_KEY.

    Não é um segredo pessoal (é a mesma chave que qualquer usuário da
    organização já carrega no navegador ao abrir a aba Time Log), mas
    mesmo assim não fica hardcoded no código — trate como configuração.
    Peça a chave a quem já rodou o script antes, ou capture de novo
    inspecionando o tráfego de rede da aba Time Log no navegador
    (ver README, seção "De onde vem a function key").
    """
    key = os.environ.get("TIMELOG_FUNCTIONS_KEY")
    if not key:
        raise RuntimeError(
            "Variável de ambiente TIMELOG_FUNCTIONS_KEY não definida. "
            "Peça a chave a quem já usa o script, ou capture de novo "
            "inspecionando a rede da aba Time Log (ver README) e defina "
            "com $env:TIMELOG_FUNCTIONS_KEY = '<chave>'"
        )
    return key
