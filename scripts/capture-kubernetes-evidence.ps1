param(
    [string]$BaseUrl = 'http://127.0.0.1:8080'
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$evidenceDirectory = Join-Path $repositoryRoot 'evidence\kubernetes'

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw 'kubectl no está instalado o no está disponible en PATH.'
}

$context = kubectl config current-context
if ($LASTEXITCODE -ne 0) {
    throw 'No se pudo determinar el contexto actual de Kubernetes.'
}

$deployment = kubectl get deployment gart-gallery-frontend -n gart-gallery -o json
if ($LASTEXITCODE -ne 0) {
    throw 'No se encontró el Deployment gart-gallery-frontend en el namespace gart-gallery.'
}

$deploymentInfo = $deployment | ConvertFrom-Json
if ($deploymentInfo.status.availableReplicas -ne $deploymentInfo.spec.replicas) {
    throw 'No todas las réplicas del Deployment están disponibles; no se guardaron evidencias.'
}

$checks = @(
    @{ Path = '/'; Label = 'Página principal' },
    @{ Path = '/healthz'; Label = 'Health check' }
)

$httpResults = foreach ($check in $checks) {
    $uri = "$($BaseUrl.TrimEnd('/'))$($check.Path)"
    try {
        $response = Invoke-WebRequest -Uri $uri -Method Get -TimeoutSec 10
    } catch {
        throw "Falló la comprobación HTTP de '$uri': $($_.Exception.Message)"
    }

    if ($response.StatusCode -ne 200) {
        throw "La URL '$uri' respondió HTTP $($response.StatusCode), se esperaba HTTP 200."
    }
    if ($check.Path -eq '/' -and $response.Content -notmatch 'GART Gallery') {
        throw "La URL '$uri' no parece estar sirviendo la página de GART Gallery."
    }

    "$($check.Label): HTTP $($response.StatusCode) - $uri"
}

New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$evidenceFile = Join-Path $evidenceDirectory "kubernetes-$timestamp.txt"

function Get-KubectlEvidence {
    param([string[]]$Arguments)

    $result = & kubectl @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Falló kubectl $($Arguments -join ' ')."
    }
    return $result
}

$evidence = @(
    "Fecha local: $(Get-Date -Format o)"
    "Contexto Kubernetes: $context"
    ''
    '=== Deployment ==='
    (Get-KubectlEvidence @('get', 'deployment', 'gart-gallery-frontend', '-n', 'gart-gallery', '-o', 'wide'))
    ''
    '=== Pods ==='
    (Get-KubectlEvidence @('get', 'pods', '-n', 'gart-gallery', '-l', 'app.kubernetes.io/name=gart-gallery-frontend', '-o', 'wide'))
    ''
    '=== Service y endpoints ==='
    (Get-KubectlEvidence @('get', 'service,endpoints', 'gart-gallery-frontend', '-n', 'gart-gallery', '-o', 'wide'))
    ''
    '=== Comprobaciones HTTP ==='
    $httpResults
)

$evidence | Set-Content -Path $evidenceFile -Encoding utf8
Write-Output "Evidencia guardada en: $evidenceFile"
