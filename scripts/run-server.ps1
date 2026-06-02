# PhantomTalk - запуск сервера (HTTP 9050 + UDP 9051)
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
python server/server.py
