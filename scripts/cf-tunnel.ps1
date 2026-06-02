# Запустить Cloudflare Quick Tunnel поверх локального сервера PhantomTalk.
# Получишь публичный URL вида https://<random>.trycloudflare.com → твой http://127.0.0.1:9050
# UDP-голос так пробросить нельзя; для UDP открой порт 9051 на роутере или возьми VPS.

param(
    [int]$Port = 9050
)

$exe = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $exe) {
    Write-Host "cloudflared не найден. Установи: winget install Cloudflare.cloudflared"
    exit 1
}

Write-Host "Поднимаю tunnel: https://*.trycloudflare.com -> http://127.0.0.1:$Port"
& $exe tunnel --url "http://127.0.0.1:$Port"
