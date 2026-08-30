param(
  [int]$Orders = 1000,
  [int]$Seed = 42,
  [double]$AnomalyRate = 0.30
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $repoRoot "apps\api"
$python = Join-Path $apiRoot ".venv\Scripts\python.exe"
$generator = Join-Path $apiRoot ".venv\Scripts\fintrace-generate.exe"
$evaluator = Join-Path $apiRoot ".venv\Scripts\fintrace-evaluate.exe"
$output = Join-Path $apiRoot "data\generated\demo"

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $generator) -or -not (Test-Path -LiteralPath $evaluator)) {
  throw "API virtual environment not found. Run: cd apps/api; pip install -e .[dev]"
}

Push-Location $apiRoot
try {
  & $generator --orders $Orders --seed $Seed --anomaly-rate $AnomalyRate --output $output
  & $evaluator --orders $Orders --seed $Seed --anomaly-rate $AnomalyRate
  Write-Output ""
  Write-Output "Start the API separately with:"
  Write-Output "  .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
  Write-Output "Then open the web app at http://localhost:3000."
} finally {
  Pop-Location
}
