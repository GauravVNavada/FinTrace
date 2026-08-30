$ErrorActionPreference = "Stop"

$apiBase = if ($env:FINTRACE_API_BASE_URL) { $env:FINTRACE_API_BASE_URL } else { "http://127.0.0.1:8001" }
$headers = @{
  "X-Organization-Id" = "ORG-001"
  "X-Actor-Id" = "e2e-controller"
  "X-Actor-Role" = "CONTROLLER"
}

$ready = Invoke-RestMethod "$apiBase/ready"
if ($ready.storage_backend -ne "postgres") { throw "Expected the API to run with STORAGE_BACKEND=postgres" }
$summary = Invoke-RestMethod "$apiBase/api/v1/dashboard/summary" -Headers $headers
$exceptions = Invoke-RestMethod "$apiBase/api/v1/exceptions" -Headers $headers
$exceptionIds = @($exceptions.id)
if ($exceptionIds.Count -lt 1) { throw "Expected seeded exceptions" }

$exceptionId = [string]$exceptionIds[0]
$investigationHeaders = $headers.Clone()
$investigationHeaders["Idempotency-Key"] = "e2e-investigation-$exceptionId"
$investigation = Invoke-RestMethod "$apiBase/api/v1/exceptions/$exceptionId/investigations" -Method Post -Headers $investigationHeaders -Body "{}"
$replay = Invoke-RestMethod "$apiBase/api/v1/exceptions/$exceptionId/investigations" -Method Post -Headers $investigationHeaders -Body "{}"

[pscustomobject]@{
  backend = $ready.storage_backend
  lifecycles = $summary.lifecycle_count
  exceptions = $exceptionIds.Count
  investigation = $investigation.investigation_id
  idempotent_replay = ($investigation.investigation_id -eq $replay.investigation_id)
} | ConvertTo-Json
