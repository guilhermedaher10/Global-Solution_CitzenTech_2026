<#
.SYNOPSIS
  Aponta o Prometheus local para a Visão publicada na Azure.

.DESCRIPTION
  Lê o endereço da Visão no "terraform output" e grava observabilidade/prometheus/alvos/azure.json
  (o Prometheus relê o arquivo sozinho em até 1 minuto). O token do /metrics fica no .env
  (METRICS_TOKEN), nunca neste arquivo.

  Atenção ao custo: com o Prometheus lendo a nuvem a cada 15 s, a Visão não "dorme"
  (cada leitura é uma requisição). Ligue só nos dias de coletar evidências e rode com -Desligar depois.

.EXAMPLE
  ./alvo-azure.ps1            # liga o monitoramento da nuvem
  ./alvo-azure.ps1 -Desligar  # volta a monitorar só o local
#>
param([switch] $Desligar)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$arquivo = Join-Path $raiz "observabilidade/prometheus/alvos/azure.json"

if ($Desligar) {
  [IO.File]::WriteAllText($arquivo, "[]`n")
  Write-Host "Monitoramento da nuvem desligado (a Visão volta a dormir sem uso)."
  return
}

Push-Location (Join-Path $raiz "terraform")
try { $url = terraform output -raw url_visao } finally { Pop-Location }
if (-not $url) { throw "Sem url_visao no terraform output. Rode o terraform apply antes." }
$hostname = ([Uri]$url).Host

$alvos = "[{`"targets`": [`"${hostname}:443`"], `"labels`": {`"ambiente`": `"azure`"}}]`n"   # PowerShell 5.1 não tem -AsArray
[IO.File]::WriteAllText($arquivo, $alvos)
Write-Host "Prometheus agora lê https://$hostname/metrics (ambiente=azure)."
Write-Host "Confira em http://localhost:9090/targets"
