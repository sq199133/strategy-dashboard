Write-Host "下载Python 3.12安装包..." -ForegroundColor Cyan
$url = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
$out = "D:\QClaw_Trading\python-installer.exe"
try {
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($url, $out)
    Write-Host "下载完成" -ForegroundColor Green
    $size = (Get-Item $out).Length / 1MB
    Write-Host "文件大小: $([math]::Round($size,1)) MB" -ForegroundColor Green
} catch {
    Write-Host "下载失败: $_" -ForegroundColor Red
    exit 1
}
Write-Host "开始静默安装..." -ForegroundColor Cyan
try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $out
    $psi.Arguments = "/quiet InstallAllUsers=1 PrependPath=1"
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    $proc.WaitForExit()
    Write-Host "安装完成，退出代码: $($proc.ExitCode)" -ForegroundColor Green
} catch {
    Write-Host "安装失败: $_" -ForegroundColor Red
    exit 1
}
