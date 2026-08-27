@echo off
rem SniperSight read-only Site bridge. This is intentionally separate from
rem the local cockpit on 8422: every request on 8424 requires the bridge token.
cd /d "%~dp0"

for /f "usebackq delims=" %%T in (`powershell -NoProfile -NonInteractive -Command "[Environment]::GetEnvironmentVariable('SNIPERSIGHT_BRIDGE_TOKEN','User')"`) do set "SNIPERSIGHT_BRIDGE_TOKEN=%%T"
if not defined SNIPERSIGHT_BRIDGE_TOKEN (
    echo SNIPERSIGHT_BRIDGE_TOKEN is not configured for this Windows user.
    exit /b 1
)

set "SNIPERSIGHT_BRIDGE_ONLY=1"
echo Starting token-only SniperSight Site bridge on 127.0.0.1:8424
python -X utf8 -m uvicorn server:app --port 8424 --host 127.0.0.1
