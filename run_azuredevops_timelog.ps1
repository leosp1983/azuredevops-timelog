# Wrapper pro Task Scheduler: roda o script e grava a saída num log,
# já que uma tarefa agendada não tem console visível pra você ler.
$ErrorActionPreference = "Continue"

$root = "F:\Automation\GitHub\myprojects\azuredevops-timelog"
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir "azuredevops_timelog.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logFile -Value "`n=== $timestamp ==="

Set-Location $root
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
python azuredevops_timelog.py 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
