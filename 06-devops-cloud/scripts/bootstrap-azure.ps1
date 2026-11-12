<#
.SYNOPSIS
  Prepara a assinatura Azure para o Terraform e o pipeline (rodar UMA vez, por quem é Owner).

.DESCRIPTION
  O Terraform precisa de dois pré-requisitos que ele não consegue criar para si mesmo:
    1. um lugar seguro para guardar o state, FORA do repositório (Storage Account);
    2. uma identidade para o GitHub Actions publicar SEM senha guardada (OIDC).
  Este script cria só isso. Tudo o mais (Container Apps, logs, orçamento) é Terraform.

  É idempotente: rodar de novo não duplica nada.

  O que cria (região padrão: eastus, uma das liberadas para Azure for Students):
    - rg-ruasescuras-tfstate  -> Storage Account do state (TLS 1.2, sem acesso anônimo,
                                 SEM chave compartilhada: só login Entra ID; versionamento ligado)
    - rg-ruasescuras          -> grupo da aplicação (o Terraform cria os recursos dentro)
    - App registration "gh-ruasescuras-deploy" com credenciais federadas (OIDC) para:
        branch main (deploy) e pull_request (plan)
      Permissões MÍNIMAS: Contributor só no rg-ruasescuras e Storage Blob Data Contributor
      só no container do state. Não enxerga o resto da assinatura e NÃO pode conceder papéis:
      o 1º "terraform apply" (que cria o papel AcrPull do container) é feito pelo Owner.

.EXAMPLE
  ./bootstrap-azure.ps1 -SubscriptionId e0cab8e8-... -Repo guilhermedaher10/Global-Solution_CitzenTech_2026
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string] $SubscriptionId,
  [Parameter(Mandatory)] [string] $Repo,
  [string] $Location = "eastus",
  [string] $Prefixo = "ruasescuras"
)
$ErrorActionPreference = "Stop"

function AzOk { # roda o az e para o script se der erro
  $saida = & az @args
  if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') falhou" }
  return $saida
}

function AzTalvez { # consulta que pode "não achar" (ex.: recurso ainda não existe): não para o script
  $ErrorActionPreference = "Continue"
  $saida = & az @args 2>$null
  return $saida
}

$rgState = "rg-$Prefixo-tfstate"
$rgApp   = "rg-$Prefixo"
$sa      = ("st$Prefixo" + "tf" + $SubscriptionId.Substring(0, 6)).ToLower()   # nome global único, <= 24
$cont    = "tfstate"
$appNome = "gh-$Prefixo-deploy"

Write-Host "==> Assinatura $SubscriptionId" -ForegroundColor Cyan
AzOk account set --subscription $SubscriptionId | Out-Null
$tenant = AzOk account show --query tenantId -o tsv
$euId   = AzOk ad signed-in-user show --query id -o tsv

Write-Host "==> Provedores de recurso (assinatura nova vem com eles desligados)" -ForegroundColor Cyan
foreach ($p in "Microsoft.App", "Microsoft.OperationalInsights", "Microsoft.Storage", "Microsoft.Consumption",
               "Microsoft.ContainerRegistry", "Microsoft.ManagedIdentity") {
  AzOk provider register --namespace $p --wait | Out-Null
  Write-Host "    $p registrado"
}

Write-Host "==> Grupos de recursos" -ForegroundColor Cyan
foreach ($rg in $rgState, $rgApp) {
  AzOk group create -n $rg -l $Location --tags projeto=ruas-escuras gerenciado-por=bootstrap -o none
  Write-Host "    $rg"
}

Write-Host "==> Storage do state do Terraform: $sa" -ForegroundColor Cyan
$existe = AzTalvez storage account show -n $sa -g $rgState --query name -o tsv
if (-not $existe) {
  AzOk storage account create -n $sa -g $rgState -l $Location --sku Standard_LRS --kind StorageV2 `
    --min-tls-version TLS1_2 --allow-blob-public-access false --allow-shared-key-access false `
    --https-only true -o none
}
AzOk storage account blob-service-properties update -n $sa -g $rgState --enable-versioning true -o none
$saId = AzOk storage account show -n $sa -g $rgState --query id -o tsv
# quem roda o script também precisa ler/gravar o state (Owner não inclui o plano de dados)
AzTalvez role assignment create --assignee-object-id $euId --assignee-principal-type User `
  --role "Storage Blob Data Contributor" --scope $saId -o none
Start-Sleep -Seconds 20   # propagação da permissão antes de criar o container via Entra ID
AzOk storage container create -n $cont --account-name $sa --auth-mode login -o none

Write-Host "==> Identidade do GitHub Actions (OIDC, sem segredo): $appNome" -ForegroundColor Cyan
$appId = AzTalvez ad app list --display-name $appNome --query "[0].appId" -o tsv
if (-not $appId) { $appId = AzOk ad app create --display-name $appNome --query appId -o tsv }
$spId = AzTalvez ad sp show --id $appId --query id -o tsv
if (-not $spId) { $spId = AzOk ad sp create --id $appId --query id -o tsv }

$federadas = @(
  @{ name = "github-main"; subject = "repo:${Repo}:ref:refs/heads/main" },
  @{ name = "github-pr";   subject = "repo:${Repo}:pull_request" }
)
$atuais = AzOk ad app federated-credential list --id $appId --query "[].name" -o tsv
foreach ($f in $federadas) {
  if ($atuais -notcontains $f.name) {
    $json = @{ name = $f.name; issuer = "https://token.actions.githubusercontent.com"; subject = $f.subject;
               audiences = @("api://AzureADTokenExchange") } | ConvertTo-Json -Compress
    $tmp = New-TemporaryFile; [IO.File]::WriteAllText($tmp, $json)   # UTF-8 sem BOM
    AzOk ad app federated-credential create --id $appId --parameters "@$tmp" -o none
    Remove-Item $tmp
  }
  Write-Host "    federada: $($f.subject)"
}

Write-Host "==> Permissões mínimas do robô" -ForegroundColor Cyan
$rgAppId = AzOk group show -n $rgApp --query id -o tsv
$escopoState = "$saId/blobServices/default/containers/$cont"
AzTalvez role assignment create --assignee-object-id $spId --assignee-principal-type ServicePrincipal `
  --role Contributor --scope $rgAppId -o none
AzTalvez role assignment create --assignee-object-id $spId --assignee-principal-type ServicePrincipal `
  --role "Storage Blob Data Contributor" --scope $escopoState -o none
# confere (a criação acima é silenciosa para ser idempotente)
$papeis = AzOk role assignment list --assignee $spId --all --query "[].[roleDefinitionName, scope]" -o tsv
if (-not ($papeis -match "Contributor\s+$([regex]::Escape($rgAppId))$")) { throw "Contributor no $rgApp não foi atribuído" }
if (-not ($papeis -match "Storage Blob Data Contributor")) { throw "permissão no state não foi atribuída" }
$papeis | ForEach-Object { Write-Host "    $_" }

Write-Host ""
Write-Host "==> Pronto. Cadastre no GitHub (Settings > Secrets and variables > Actions):" -ForegroundColor Green
[ordered]@{
  AZURE_CLIENT_ID       = $appId
  AZURE_TENANT_ID       = $tenant
  AZURE_SUBSCRIPTION_ID = $SubscriptionId
  TFSTATE_RG            = $rgState
  TFSTATE_STORAGE       = $sa
} | Format-Table -HideTableHeaders | Out-String | Write-Host
