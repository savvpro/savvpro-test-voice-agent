$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot '.venv\Scripts\python.exe'
$ruffPath = Join-Path $repoRoot '.venv\Scripts\ruff.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install backend/requirements-dev.txt first. See README.md.' }
function Invoke-Check([string]$Label, [scriptblock]$Command) {
    Write-Host "Checking $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit $LASTEXITCODE)." }
}
Push-Location $repoRoot
try {
    Invoke-Check 'source secrets' { & $pythonPath scripts/check_secrets.py }
    Invoke-Check 'Python lint' { & $ruffPath check backend scripts }
    Invoke-Check 'Python formatting' { & $ruffPath format --check backend scripts }
    Push-Location backend
    try { Invoke-Check 'backend tests' { & $pythonPath -m pytest -q } } finally { Pop-Location }
    Push-Location frontend
    try {
        Invoke-Check 'frontend formatting' { npm run format:check }
        Invoke-Check 'production build' { npm run build }
        Invoke-Check 'isolated browser tests' { npm run test:e2e }
    } finally { Pop-Location }
    Write-Host 'Automated checks passed. Continue with docs/FINAL_TEST.md for the physical audio acceptance test.'
} finally { Pop-Location }
