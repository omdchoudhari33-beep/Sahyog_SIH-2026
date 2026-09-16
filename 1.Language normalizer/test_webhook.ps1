
$secret = "dev-secret-123"

$body = '{"request_id":"test-001","input_type":"text","text":"My name is Ravi and my phone number is 9876543210."}'

$hmac = [System.Security.Cryptography.HMACSHA256]::new(
    [System.Text.Encoding]::UTF8.GetBytes($secret)
)

$hash = $hmac.ComputeHash(
    [System.Text.Encoding]::UTF8.GetBytes($body)
)

$signature = (
    [BitConverter]::ToString($hash) -replace "-", ""
).ToLower()

$hmac.Dispose()

Write-Host "Header: X-Signature"
Write-Host "Signature: $signature"

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/api/v1/webhook" `
    -Method Post `
    -Headers @{ "X-Signature" = $signature } `
    -ContentType "application/json" `
    -Body $body