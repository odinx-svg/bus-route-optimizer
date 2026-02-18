param(
    [switch]$SkipBenchmark,
    [string]$InputDir = "ejemplo excel rutas a optimizar"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " TUTTI - Pre Release Smoke Check" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

Push-Location $root
try {
    Write-Host "[1/3] Frontend build..." -ForegroundColor Yellow
    npm --prefix frontend run build

    Write-Host "[2/3] Frontend smoke e2e..." -ForegroundColor Yellow
    npm --prefix frontend run test:e2e:smoke

    if (-not $SkipBenchmark) {
        Write-Host "[3/3] Backend real-excels benchmark..." -ForegroundColor Yellow
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $output = "backend/benchmarks/results/real_excels_pre_release_$timestamp.json"
        .\.venv\Scripts\python -m backend.benchmarks.run_real_excels --input-dir $InputDir --output $output --max-duration-sec 300 --max-iterations 2
        Write-Host "Benchmark report: $output" -ForegroundColor Green
    } else {
        Write-Host "[3/3] Backend real-excels benchmark skipped" -ForegroundColor DarkYellow
    }

    Write-Host ""
    Write-Host "Smoke check completed OK." -ForegroundColor Green
}
finally {
    Pop-Location
}
