# azuredevops-timelog

Script que loga 4 horas por dia útil na Task mensal do PBI "Automação" no Azure DevOps (org `sysmanagerdevops`, projeto `Petrobras`), criando a Task do mês quando ela não existe e fechando a Task do mês anterior quando chega a hora.

Feito pra qualquer pessoa do time usar. Cada um roda com o próprio Personal Access Token, e o script descobre sozinho quem está rodando, sem nenhum usuário fixo no código.

## O que ele faz

Sem precisar abrir o navegador nem clicar em nada, o script:

1. Descobre automaticamente a identidade de quem está rodando (nome, email, id) a partir do próprio token.
2. Localiza ou cria a Task mensal (`Automação - <Mês>/<Ano>`) sob o PBI Automação, com Activity, Original Estimate e datas preenchidas seguindo o padrão histórico. Essa Task é compartilhada por todo o time, então só é criada uma vez por mês.
3. Confere dia a dia, do dia 1 do mês atual até hoje, se a própria pessoa já lançou horas naquele dia. Se não, lança 4 horas (tipo `01-Projeto Padrão`).
4. Pula automaticamente fim de semana e feriado nacional brasileiro.
5. Fecha a Task do mês anterior se ela ainda estiver aberta.
6. Pode rodar sozinho todo dia útil via Task Scheduler do Windows (cada pessoa configura a própria, se quiser).

## Como funciona por dentro

Não usa navegador nem Playwright. São duas chamadas HTTP diretas:

- **API oficial do Azure DevOps** (`azdo_client.py`), autenticada por Personal Access Token, para localizar ou criar a Task mensal, para fechar a Task do mês anterior e para descobrir a identidade de quem está rodando.
- **API interna da extensão TimeLog** (`timelog_client.py`), que é a mesma chamada que o próprio widget da extensão faz no navegador. Não é documentada publicamente, foi descoberta inspecionando o tráfego de rede do formulário de Time Log. Se a TimeLog mudar o backend dela sem aviso, é aqui que quebra primeiro.

O histórico completo de como cada decisão foi tomada, incluindo os erros reais encontrados na primeira execução, está em [`docs/superpowers/plans/2026-08-24-azuredevops-timelog.md`](docs/superpowers/plans/2026-08-24-azuredevops-timelog.md).

## Pré-requisitos

- Python 3.10 ou mais novo
- Acesso ao projeto Petrobras no Azure DevOps (org `sysmanagerdevops`)

## Instalação

```powershell
git clone https://github.com/leosp1983/azuredevops-timelog.git
cd azuredevops-timelog
pip install -r requirements.txt
```

## Configuração

O script precisa de duas variáveis de ambiente. Nenhuma das duas fica dentro de arquivo nenhum do projeto.

**1. `AZDO_PAT`, o seu token pessoal**

Gere em `https://dev.azure.com/sysmanagerdevops/_usersSettings/tokens`, com escopo **Work Items (Read & Write)**. É pessoal, não compartilhe com ninguém.

```powershell
setx AZDO_PAT "<seu token aqui>"
```

**2. `TIMELOG_FUNCTIONS_KEY`, a chave da extensão TimeLog**

Essa não é pessoal, é a mesma chave que a extensão já carrega no navegador de qualquer pessoa da organização quando abre a aba Time Log. Peça a chave a quem já usa o script, ou capture de novo assim:

1. Abra uma Task qualquer no Azure DevOps e vá na aba Time Log.
2. Abra as Ferramentas do Desenvolvedor do navegador (F12), aba Network.
3. Recarregue a página. Vai aparecer uma chamada pra `boznet-timelogapi.azurewebsites.net`.
4. Nos headers da requisição, copie o valor de `x-functions-key`.

```powershell
setx TIMELOG_FUNCTIONS_KEY "<a chave que voce capturou>"
```

Depois de definir as duas, feche e abra um terminal novo para as variáveis ficarem disponíveis.

## Uso

```powershell
# Cobre automaticamente do dia 1 do mês atual até hoje, preenchendo só o que falta
python azuredevops_timelog.py

# Backfill de um período específico
python azuredevops_timelog.py --from 2026-08-01 --to 2026-08-15

# Mostra o que seria enviado, sem gravar nada de verdade
python azuredevops_timelog.py --dry-run
```

Rodar o comando sem argumentos é seguro em qualquer dia. Ele sempre confere o que a própria pessoa já lançou antes de tentar lançar de novo, então não duplica entradas mesmo com várias pessoas usando a mesma Task do mês.

## Agendamento automático

Dá pra deixar o script rodando sozinho, sem precisar lembrar de executar todo dia. No exemplo abaixo, a tarefa roda toda segunda a sexta às 18h30, usando o `AZDO_PAT` e o `TIMELOG_FUNCTIONS_KEY` já definidos no ambiente do usuário.

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -File "<caminho onde voce clonou>\run_azuredevops_timelog.ps1"'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 18:30
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
Register-ScheduledTask -TaskName "AzureDevOpsTimeLog" -Action $action -Trigger $trigger -Settings $settings -Description "Loga 4h diarias no Azure DevOps (PBI Automacao)"
```

Antes de registrar, ajuste o `$root` dentro de `run_azuredevops_timelog.ps1` para o caminho onde você clonou o repositório. A saída de cada execução fica em `logs/azuredevops_timelog.log`, que não vai para o repositório.

## Testes

```powershell
python -m pytest tests/ -v
```

Toda a lógica de datas e as chamadas HTTP (mockadas com `unittest.mock`) são cobertas por testes automatizados, sem dado pessoal real nas fixtures. As interações reais com o Azure DevOps foram validadas manualmente contra o ambiente de produção.

## Estrutura do projeto

```
azuredevops_timelog/
  config.py          constantes da organização e do projeto, leitura das variáveis de ambiente
  dates.py           lógica pura de datas, dias úteis e feriados
  azdo_client.py      API oficial do Azure DevOps (localizar/criar/fechar Task, identidade do usuário)
  timelog_client.py   API interna da extensão TimeLog (ler/gravar horas)
  cli.py              orquestração do fluxo completo
azuredevops_timelog.py   ponto de entrada
run_azuredevops_timelog.ps1   wrapper opcional pro Task Scheduler
tests/               testes automatizados (pytest)
docs/                plano de implementação completo, com premissas e decisões
```

## Limitações conhecidas

- A API da extensão TimeLog não é documentada publicamente. Se a TimeLog mudar o formato das chamadas, o lançamento de horas para de funcionar até alguém capturar o novo formato de novo (inspecionando o tráfego de rede do navegador).
- Só considera feriados nacionais fixos do Brasil. Pontos facultativos e feriados municipais não são levados em conta.
- Quando o seu PAT expirar, a execução falha (ou, se estiver agendada, falha silenciosamente, só aparece no log). Gere um token novo e rode `setx AZDO_PAT` de novo.
- Fechar a Task no fim do mês é automático, mas revisar se as horas lançadas no mês estão corretas continua sendo responsabilidade de quem usa o script.
- Como a Task do mês é compartilhada, ela só pode ser criada por quem tem permissão de escrita no PBI Automação. Se o seu usuário não tiver, peça pra alguém do time criar a Task do mês uma vez, ou ajuste o PBI de origem em `config.py`.
