$codes = @('sz159329','sz159100','sz159980','sz159985')
foreach ($c in $codes) {
    $uri = 'http://hq.sinajs.cn/list=' + $c
    $headers = @{
        'Referer' = 'http://finance.sina.com.cn'
        'User-Agent' = 'Mozilla/5.0'
    }
    try {
        $r = Invoke-WebRequest -Uri $uri -Headers $headers -TimeoutSec 5 -UseBasicParsing
        $t = [System.Text.Encoding]::GetEncoding('GB2312').GetString($r.Content)
        if ($t -match 'name="([^"]+)"') {
            $f = $t -split '='
            $nameStr = ($f[1] -replace '";','') -replace '"',''
            $parts = $nameStr.Split(',')
            Write-Host ($c.ToUpper() + ': ' + $parts[0] + ' | 昨收=' + $parts[2] + ' 当前=' + $parts[3])
        } elseif ($t -match '"([^"]{4,})"') {
            $parts = $matches[1].Split(',')
            Write-Host ($c.ToUpper() + ': ' + $parts[0] + ' | 昨收=' + $parts[2] + ' 当前=' + $parts[3])
        } else {
            Write-Host $c ': nodata - ' $t.Substring(0, [Math]::Min(80, $t.Length))
        }
    } catch {
        Write-Host $c ': 请求失败 - ' $_.Exception.Message
    }
    Start-Sleep -Milliseconds 300
}

# Also try East Money for remaining codes
Write-Host ''
Write-Host '===== EM核实159980/159985 ====='
foreach ($code in @('159980','159985')) {
    try {
        $r2 = Invoke-WebRequest -Uri ('http://fundgz.1234567.com.cn/js/'+$code+'.js?rt=1') -TimeoutSec 5 -UseBasicParsing
        Write-Host $code 'EM: ' $r2.Content
    } catch {
        Write-Host $code 'EM: 失败'
    }
    Start-Sleep -Milliseconds 300
}
