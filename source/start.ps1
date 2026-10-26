# One-click launcher for Windows (PowerShell 7 or later).
# Usage: .\start.ps1 [-Port 8412] [-Python python]
param(
    [int]$Port = 8412,
    [string]$Python = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not $Python) {
    foreach ($candidate in @('python', 'py')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) { $Python = $candidate; break }
    }
}

if (-not $Python) {
    Write-Error "Python 3.11+ was not found on PATH. Install it or pass -Python <path>."
    exit 3
}

Write-Host "C2M craft prototype -> http://127.0.0.1:$Port"
Write-Host "Press Ctrl+C to stop."
& $Python -m c2m_craft serve --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
