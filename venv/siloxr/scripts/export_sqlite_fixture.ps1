param(
    [string]$OutputPath = "C:\Users\HP\Desktop\SiloXR_\docs\data\sqlite_export.json"
)

$ErrorActionPreference = "Stop"

$projectRoot = "C:\Users\HP\Desktop\SiloXR_\venv\siloxr"
$pythonExe = "C:\Users\HP\Desktop\SiloXR_\venv\Scripts\python.exe"

if (!(Test-Path $projectRoot)) {
    throw "Project root not found at $projectRoot"
}

$outputDir = Split-Path -Parent $OutputPath
if ($outputDir -and !(Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

Push-Location $projectRoot
try {
    $json = & $pythonExe manage.py dumpdata `
        --natural-foreign `
        --natural-primary `
        --exclude auth.permission `
        --exclude contenttypes `
        --exclude sessions `
        --indent 2

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($OutputPath, ($json -join [Environment]::NewLine), $utf8NoBom)
}
finally {
    Pop-Location
}

Write-Host "SQLite export written to $OutputPath"
