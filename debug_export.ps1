$base    = "http://localhost:8000"
$term    = "38429685-5aec-4bbd-b384-e7be6b36c611"
$token   = (Get-Content "$env:APPDATA\.timetabler_token" -ErrorAction SilentlyContinue) ?? ""

# If token file doesn't exist, prompt
if (-not $token) {
    $token = Read-Host "Paste your timetabler_token"
}

$headers = @{ Authorization = "Token $token" }

Write-Host "`n=== Testing each export format ===" -ForegroundColor Cyan

foreach ($fmt in @("xlsx", "pdf", "docx", "html")) {
    $url = "$base/api/export/master/?term=$term&fmt=$fmt"
    Write-Host "`n--- fmt=$fmt ---" -ForegroundColor Yellow
    try {
        $resp = Invoke-WebRequest -Uri $url -Headers $headers -Method GET -ErrorAction Stop
        Write-Host "OK  $($resp.StatusCode)  Content-Type: $($resp.Headers['Content-Type'])  Size: $($resp.Content.Length) bytes" -ForegroundColor Green
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        Write-Host "FAIL  HTTP $code" -ForegroundColor Red

        # Try to read the response body for the Django traceback
        try {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = [System.IO.StreamReader]::new($stream)
            $body   = $reader.ReadToEnd()
            # Print first 2000 chars (enough to see the traceback)
            Write-Host ($body.Substring(0, [Math]::Min(2000, $body.Length))) -ForegroundColor DarkRed
        } catch {
            Write-Host "(could not read response body)" -ForegroundColor DarkGray
        }
    }
}
