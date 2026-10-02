$ErrorActionPreference = 'Stop'
$envFile = Join-Path (Split-Path -Parent $PSScriptRoot) '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    throw 'Arquivo .env não encontrado na raiz do projeto. Nenhum token foi alterado.'
}

function Read-Token([string]$name) {
    $escaped = [regex]::Escape($name)
    $pattern = "^\s*$escaped\s*=\s*(.*?)\s*$"
    $lines = @(Get-Content -LiteralPath $envFile | Where-Object { $_ -match $pattern })
    if ($lines.Count -ne 1) {
        throw "Esperava uma única definição de $name no .env; encontrei $($lines.Count)."
    }
    $value = [regex]::Match($lines[0], $pattern).Groups[1].Value.Trim()
    if ($value.Length -ge 2 -and
        (($value.StartsWith('"') -and $value.EndsWith('"')) -or
         ($value.StartsWith("'") -and $value.EndsWith("'")))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    if (-not $value) { throw "$name está vazio no .env." }
    return $value
}

$previousHost = [Environment]::GetEnvironmentVariable('KARAOKE_E2E_HOST_TOKEN', 'Process')
$previousGuest = [Environment]::GetEnvironmentVariable('KARAOKE_E2E_GUEST_TOKEN', 'Process')
try {
    $env:KARAOKE_E2E_HOST_TOKEN = Read-Token 'KARAOKE_HOST_TOKEN'
    $env:KARAOKE_E2E_GUEST_TOKEN = Read-Token 'KARAOKE_GUEST_TOKEN'
    Push-Location $PSScriptRoot
    try {
        npm run test:e2e
        if ($LASTEXITCODE -ne 0) { throw "Playwright falhou (código $LASTEXITCODE)." }
    } finally { Pop-Location }
} finally {
    [Environment]::SetEnvironmentVariable('KARAOKE_E2E_HOST_TOKEN', $previousHost, 'Process')
    [Environment]::SetEnvironmentVariable('KARAOKE_E2E_GUEST_TOKEN', $previousGuest, 'Process')
}
