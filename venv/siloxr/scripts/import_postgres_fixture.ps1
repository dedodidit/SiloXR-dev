param(
    [string]$FixturePath = "C:\Users\HP\Desktop\SiloXR_\docs\data\sqlite_export.json"
)

$ErrorActionPreference = "Stop"

$projectRoot = "C:\Users\HP\Desktop\SiloXR_\venv\siloxr"
$pythonExe = "C:\Users\HP\Desktop\SiloXR_\venv\Scripts\python.exe"

if (!(Test-Path $FixturePath)) {
    throw "Fixture file not found at $FixturePath"
}

Push-Location $projectRoot
try {
    $env:DB_BACKEND = "postgres"

    & $pythonExe manage.py migrate --settings=siloxr.settings.production
    & $pythonExe ".\\scripts\\load_fixture_without_signals.py" $FixturePath
    & $pythonExe manage.py sqlsequencereset core inventory notifications billing engine api auth | & $pythonExe manage.py dbshell --settings=siloxr.settings.production
}
finally {
    Pop-Location
}

Write-Host "PostgreSQL import completed from $FixturePath"
