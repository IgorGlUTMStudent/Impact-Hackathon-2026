# Host-proof laptop fallback (Windows, synthetic data only)

This is a rehearsal for the isolated probe, not the product. The full phone↔laptop test remains **NOT RUN**. Use one trusted Wi-Fi or phone hotspot; never disable the firewall globally or forward a port to the internet. Local HTTP does not prove HTTPS, PWA installation, or secure offline behavior.

## Start on the laptop

Use a checkout containing this probe. In a fresh PowerShell window, from the repository root, run the following. It clears inherited Render connection variables **in this process only**, then explicitly points to a local SQLite file outside Git. Existing data in that local file is reused, not deleted. Choose a disposable local password; do not send it to chat or commit it.

```powershell
$root = (Get-Location).Path
$local = Join-Path $env:LOCALAPPDATA 'impact-host-proof-local'
New-Item -ItemType Directory -Force -Path $local | Out-Null
python -m venv (Join-Path $local '.venv')
$py = Join-Path $local '.venv\Scripts\python.exe'
& $py -m pip install -r (Join-Path $root 'experiments\host-proof\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
Remove-Item Env:DATABASE_URL,Env:RENDER,Env:RENDER_EXTERNAL_HOSTNAME,Env:RENDER_EXTERNAL_URL,Env:CSRF_TRUSTED_ORIGINS -ErrorAction SilentlyContinue
$dbPath = (Join-Path $local 'fallback.sqlite3').Replace('\','/')
$env:DATABASE_URL = "sqlite:///$dbPath"
$env:DJANGO_SECRET_KEY = [guid]::NewGuid().ToString() + [guid]::NewGuid().ToString()
$env:PROOF_USERNAME = 'synthetic'
$env:PROOF_PASSWORD = Read-Host 'Choose a disposable local password'
if (-not $env:PROOF_PASSWORD) { throw 'A disposable local password is required' }
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } | Select-Object InterfaceAlias,IPAddress
$lan = Read-Host 'Enter the laptop IPv4 on the phone network'
$env:ALLOWED_HOSTS = "127.0.0.1,localhost,$lan"
& $py experiments/host-proof/smoke.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Local migrations failed' }
& $py experiments/host-proof/smoke.py init-value
if ($LASTEXITCODE -ne 0) { throw 'Local initialization failed' }
& $py experiments/host-proof/smoke.py runserver "${lan}:8000" --noreload
```

The network address and password stay local. The laptop's local `fallback.sqlite3` persists after the server stops. Do not run these commands in Render or supply a PostgreSQL URL. Avoid real users' data.

## One physical acceptance check

1. Connect phone and laptop to the same network. On the phone open `http://<LAN-IP>:8000/health/`, then `/login/`. Sign in with the temporary local credentials, open `/value/` and save `35`.
2. On the laptop open the same `/login/`, sign in and verify `/value/` displays `35`. In the PowerShell window press Ctrl+C, then run `& $py experiments/host-proof/smoke.py runserver "${lan}:8000" --noreload` again in **the same session**. Refresh the laptop value page and confirm `35` remains. Sessions may require sign-in again after configuration changes.
3. Report only date/time, phone/browser, Wi-Fi vs hotspot and pass/fail for phone save, laptop read and post-restart read. Do not publish IPs, passwords, cookies or screenshots containing them.

If the phone cannot connect, check the selected IPv4, binding address, same network, client isolation and the firewall's specific rule. Try the phone's hotspot if the Wi-Fi isolates clients; do not disable the firewall globally. If neither works, use a laptop-only local demonstration or a pre-recorded demonstration **if one exists**; a video has not been created by this proof.

## Optional: remote save latency

When no other tester is writing, use `python experiments/host-proof/verify_latency.py` with the isolated Render test credentials. It reads the existing `35`, requests explicit confirmation, writes the same `35` once and reports POST plus redirect GET duration; credentials and CSRF/session data remain in memory and are not printed. It aborts before a write if the read value differs from 35. Do not use this to measure the product or run repeated load tests.
