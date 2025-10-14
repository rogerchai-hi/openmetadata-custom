Get-Content .env | ForEach-Object {
  $name, $value = $_.split('=', 2)
  if ([string]::IsNullOrWhiteSpace($name) -or $name -match '^#.*') {
    # skip empty or comment line in ENV file
    return
  }
  Set-Item Env:$name $value
}

$jsonFile  = Join-Path $PSScriptRoot "data.json"
$uri = "${Env:OM_URL}/api/v1/dataQuality/testDefinitions"
$headers = @{
    Authorization = "Bearer ${Env:JWT_TOKEN}"
    "Content-Type" = "application/json"
}
$body = Get-Content -Path $jsonFile -Raw

Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $body
