Write-Host "=== Python环境检测 ===" -ForegroundColor Cyan

# 检查真实Python路径
$possible = @(
    'C:\Python312\python.exe',
    'C:\Python311\python.exe',
    'C:\Python310\python.exe',
    'C:\Program Files\Python312\python.exe',
    'C:\Program Files\Python311\python.exe',
    'C:\Users\沈强\AppData\Local\Programs\Python\Python312\python.exe',
    'C:\Users\沈强\AppData\Local\Programs\Python\Python311\python.exe',
    'C:\Users\沈强\AppData\Local\Programs\Python\Python310\python.exe'
)

foreach ($p in $possible) {
    if (Test-Path $p) {
        Write-Host "找到: $p" -ForegroundColor Green
        & $p --version 2>&1 | Select-Object -First 1
    }
}

# 尝试用winget安装
Write-Host ""
Write-Host "=== 尝试winget安装Python ===" -ForegroundColor Cyan
try {
    $null = Get-Command winget -ErrorAction Stop
    Write-Host "winget已就绪" -ForegroundColor Green
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent 2>&1 | Select-Object -First 10
} catch {
    Write-Host "winget不可用或安装失败: $_" -ForegroundColor Yellow
}
