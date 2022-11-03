
$API='https://dev.azure.com/ORGANIZATION/PROJECT/_apis/pipelines/ID/runs?api-version=6.0-preview.1'

$headers = @{
    'Content-Type'='application/json'
    'Authorization'='Basic <Token>'
    }

$payload= @"
{"templateParameters": {
    "key": "val",
    "boolean": "true"
}}
"@
Invoke-WebRequest -Method 'Post' -Uri $API -Body $payload -Headers $headers
