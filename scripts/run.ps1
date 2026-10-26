<#
.SYNOPSIS
    Zien Quant - Server Launcher (Windows PowerShell)
.DESCRIPTION
    Loads .env and launches the HTTP terminal server on 127.0.0.1:8765.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

$hostAddr = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$port = if ($env:PORT) { $env:PORT } else { "8765" }

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Starting Zien Quant - Order Block Terminal" -ForegroundColor Cyan
Write-Host " Listening on: http://${hostAddr}:${port}/" -ForegroundColor Green
Write-Host " Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host "==================================================================" -ForegroundColor Cyan

python server.py --host $hostAddr --port $port
