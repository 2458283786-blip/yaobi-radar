# YaoBi Radar - 本地定时扫描脚本
# 用法: powershell -ExecutionPolicy Bypass -File run-and-push.ps1
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 代理配置 (根据实际情况修改端口)
$env:PROXY_URL = "http://127.0.0.1:65532"

# 设置 git 代理
git config http.proxy $env:PROXY_URL
git config https.proxy $env:PROXY_URL

$logFile = Join-Path $scriptDir "run.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-Log {
    param($msg)
    $line = "[$timestamp] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

Write-Log "=== YaoBi Radar Scan Start ==="

try {
    # Pull latest
    Write-Log "Pulling latest from GitHub..."
    git pull origin master --rebase 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Pull failed, continuing with local data..."
    }

    # Run scanner
    Write-Log "Running scanner..."
    $scanOutput = python scanner.py 2>&1
    $scanOutput | ForEach-Object { Write-Host $_ }
    
    # Check if scanner found anything
    $candidatesMatch = $scanOutput | Select-String "Found (\d+) candidates"
    if ($candidatesMatch) {
        Write-Log "Scanner result: $($candidatesMatch.Matches[0].Value)"
    }

    # Push results
    Write-Log "Committing and pushing..."
    git add data/ docs/ data.json history.json backtest.json index.html 2>&1 | Out-Null
    $diffCheck = git diff --staged --quiet 2>&1
    if ($LASTEXITCODE -ne 0) {
        git commit -m "scan: $(Get-Date -Format 'yyyy-MM-dd_HH:mm')" 2>&1 | Out-Null
        git push origin master 2>&1 | Out-Null
        Write-Log "Pushed to GitHub ✓"
    } else {
        Write-Log "No changes to push"
    }

    Write-Log "=== Scan Complete ==="
} catch {
    Write-Log "ERROR: $_"
    Write-Log "=== Scan Failed ==="
}
