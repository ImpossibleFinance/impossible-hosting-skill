---
name: innstance
description: Deploy applications to Innstance runner VMs. Use when Codex needs to provision an app with innstance, translate project setup into runner commands, transfer source safely, start the process, or verify and troubleshoot the public deployment.
---

# innstance — Deploy to Innstance

Provision an isolated runner VM and HTTPS URL, then install, transfer, start,
and verify the application explicitly. Use [RUNBOOK.md](RUNBOOK.md) for the
ordered deployment and recovery procedure.

## Agent Rules

### 0. Refresh the CLI and these instructions first, every session

The command used to be called `ifhost`. That name still works and runs the same binary, but new installs use `innstance`, and the served installer leaves `ifhost` beside it as a link.

<!-- BEGIN VERIFIED CLI BOOTSTRAP -->
When `innstance` is missing, do not execute either installer served by the release
origin. A compromise of that origin could replace the installer and the public
key embedded in it.
Instead, authenticate the signed release record with the public key committed
in [`release-signers`](release-signers), inspect the authenticated metadata,
verify the selected archive digest, and only then execute the CLI. Never
download or replace the trust anchor from the release origin.

On macOS or Linux:

```bash
set -eu
release_origin=https://innstance.impossibuild.ai
allowed_signer='ifhost ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEv+FR+Wibo0JJPEmmJfqQz2wsoBkrCLatDZ8XwZq2zJ'
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

case "$(uname -s):$(uname -m)" in
  Darwin:x86_64) archive=innstance_darwin_amd64.tar.gz ;;
  Darwin:arm64|Darwin:aarch64) archive=innstance_darwin_arm64.tar.gz ;;
  Linux:x86_64|Linux:amd64) archive=innstance_linux_amd64.tar.gz ;;
  Linux:arm64|Linux:aarch64) archive=innstance_linux_arm64.tar.gz ;;
  *) echo "Unsupported platform: $(uname -s)/$(uname -m)" >&2; exit 1 ;;
esac
for tool in curl ssh-keygen tar awk wc; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing required tool: $tool" >&2; exit 1; }
done

curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --tlsv1.2 --connect-timeout 10 --max-time 60 --max-filesize 1048576 \
  "$release_origin/dl/release.txt" -o "$tmp/release.txt"
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --tlsv1.2 --connect-timeout 10 --max-time 60 --max-filesize 1048576 \
  "$release_origin/dl/release.txt.sshsig" -o "$tmp/release.txt.sshsig"
[ "$(wc -c < "$tmp/release.txt")" -le 1048576 ] || {
  echo "Release metadata exceeds 1 MiB" >&2; exit 1;
}
[ "$(wc -c < "$tmp/release.txt.sshsig")" -le 1048576 ] || {
  echo "Release signature exceeds 1 MiB" >&2; exit 1;
}
printf '%s\n' "$allowed_signer" > "$tmp/release-signers"
ssh-keygen -Y verify -f "$tmp/release-signers" -I ifhost -n ifhost-release \
  -s "$tmp/release.txt.sshsig" < "$tmp/release.txt"
cat "$tmp/release.txt"

signed_value() {
  key=$1
  count=$(awk -F= -v key="$key" '$1 == key { count++ } END { print count+0 }' "$tmp/release.txt")
  [ "$count" -eq 1 ] || { echo "Signed release must contain exactly one $key" >&2; return 1; }
  awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); print }' "$tmp/release.txt"
}
source_repository=$(signed_value source_repository)
expected=$(signed_value "artifact.$archive")
[ "$source_repository" = ImpossibleFinance/impossible-hosting ] || {
  echo "Signed release names an unexpected source repository" >&2; exit 1;
}
case "$expected" in *[!0-9a-f]*|'') echo "Signed digest is malformed" >&2; exit 1 ;; esac
[ "${#expected}" -eq 64 ] || { echo "Signed digest is malformed" >&2; exit 1; }

curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --tlsv1.2 --connect-timeout 10 --max-time 300 --max-filesize 67108864 \
  "$release_origin/dl/$archive" -o "$tmp/$archive"
[ "$(wc -c < "$tmp/$archive")" -le 67108864 ] || {
  echo "Release archive exceeds 64 MiB" >&2; exit 1;
}
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$tmp/$archive" | awk '{ print $1 }')
elif command -v shasum >/dev/null 2>&1; then
  actual=$(shasum -a 256 "$tmp/$archive" | awk '{ print $1 }')
else
  echo "Missing SHA-256 tool (sha256sum or shasum)" >&2
  exit 1
fi
[ "$actual" = "$expected" ] || { echo "Release digest mismatch; nothing installed" >&2; exit 1; }
contents=$(tar -tzf "$tmp/$archive")
printf 'Verified archive contents:\n%s\n' "$contents"
[ "$contents" = innstance ] || { echo "Release archive must contain only innstance" >&2; exit 1; }
tar -xzf "$tmp/$archive" -C "$tmp"
[ -f "$tmp/innstance" ] && [ ! -L "$tmp/innstance" ] || {
  echo "Release binary is not a regular file" >&2; exit 1;
}
mkdir -p "$HOME/.local/bin"
install -m 0755 "$tmp/innstance" "$HOME/.local/bin/innstance"
export PATH="$HOME/.local/bin:$PATH"
innstance version
innstance skill sync
```

On Windows, run this in PowerShell with the OpenSSH Client capability enabled:

```powershell
$ErrorActionPreference = 'Stop'
$ReleaseOrigin = 'https://innstance.impossibuild.ai'
$AllowedSigner = 'ifhost ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEv+FR+Wibo0JJPEmmJfqQz2wsoBkrCLatDZ8XwZq2zJ'
$RawArch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
$Arch = switch ($RawArch) {
  'AMD64' { 'amd64' }
  'ARM64' { 'arm64' }
  default { throw "Unsupported architecture: $RawArch" }
}
$Archive = "innstance_windows_$Arch.zip"
$TempDir = Join-Path ([IO.Path]::GetTempPath()) "ifhost-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $TempDir | Out-Null

function Get-SignedValue([string[]]$Lines, [string]$Name) {
  $Prefix = "$Name="
  $Matches = @($Lines | Where-Object { $_.StartsWith($Prefix, [StringComparison]::Ordinal) })
  if ($Matches.Count -ne 1) { throw "Signed release must contain exactly one $Name" }
  $Matches[0].Substring($Prefix.Length)
}

try {
  $ReleasePath = Join-Path $TempDir 'release.txt'
  $SignaturePath = Join-Path $TempDir 'release.txt.sshsig'
  $SignerPath = Join-Path $TempDir 'release-signers'
  Invoke-WebRequest -Uri "$ReleaseOrigin/dl/release.txt" `
    -MaximumRedirection 0 -TimeoutSec 60 -OutFile $ReleasePath
  Invoke-WebRequest -Uri "$ReleaseOrigin/dl/release.txt.sshsig" `
    -MaximumRedirection 0 -TimeoutSec 60 -OutFile $SignaturePath
  if ((Get-Item -LiteralPath $ReleasePath).Length -gt 1048576 -or
      (Get-Item -LiteralPath $SignaturePath).Length -gt 1048576) {
    throw 'Release metadata exceeds 1 MiB'
  }
  [IO.File]::WriteAllText($SignerPath, "$AllowedSigner`n", [Text.UTF8Encoding]::new($false))

  $SshKeygen = (Get-Command ssh-keygen -ErrorAction Stop).Source
  $Start = [Diagnostics.ProcessStartInfo]::new()
  $Start.FileName = $SshKeygen
  $Start.Arguments = "-Y verify -f `"$SignerPath`" -I ifhost -n ifhost-release -s `"$SignaturePath`""
  $Start.UseShellExecute = $false
  $Start.RedirectStandardInput = $true
  $Start.RedirectStandardOutput = $true
  $Start.RedirectStandardError = $true
  $Process = [Diagnostics.Process]::new()
  $Process.StartInfo = $Start
  [void]$Process.Start()
  $ReleaseBytes = [IO.File]::ReadAllBytes($ReleasePath)
  $Process.StandardInput.BaseStream.Write($ReleaseBytes, 0, $ReleaseBytes.Length)
  $Process.StandardInput.Close()
  $Stdout = $Process.StandardOutput.ReadToEnd()
  $Stderr = $Process.StandardError.ReadToEnd()
  $Process.WaitForExit()
  if ($Process.ExitCode -ne 0) { throw "Release signature verification failed: $Stderr" }

  Get-Content -LiteralPath $ReleasePath
  $Lines = [IO.File]::ReadAllLines($ReleasePath)
  $SourceRepository = Get-SignedValue $Lines 'source_repository'
  $Expected = Get-SignedValue $Lines "artifact.$Archive"
  if ($SourceRepository -cne 'ImpossibleFinance/impossible-hosting') {
    throw 'Signed release names an unexpected source repository'
  }
  if ($Expected -cnotmatch '^[0-9a-f]{64}$') { throw 'Signed digest is malformed' }

  $ZipPath = Join-Path $TempDir $Archive
  Invoke-WebRequest -Uri "$ReleaseOrigin/dl/$Archive" `
    -MaximumRedirection 0 -TimeoutSec 300 -OutFile $ZipPath
  if ((Get-Item -LiteralPath $ZipPath).Length -gt 67108864) {
    throw 'Release archive exceeds 64 MiB'
  }
  $Actual = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($Actual -cne $Expected) { throw 'Release digest mismatch; nothing installed' }

  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $Zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
  try {
    $Files = @($Zip.Entries | Where-Object { -not [string]::IsNullOrEmpty($_.Name) })
    $Files | ForEach-Object { Write-Host "Verified archive content: $($_.FullName)" }
    if ($Files.Count -ne 1 -or $Files[0].FullName -cne 'innstance.exe') {
      throw 'Release archive must contain only innstance.exe'
    }
    $UnixType = (($Files[0].ExternalAttributes -shr 16) -band 0xF000)
    if ($UnixType -ne 0 -and $UnixType -ne 0x8000) {
      throw 'Release archive entry must be a regular file'
    }
  } finally {
    $Zip.Dispose()
  }

  $Unpacked = Join-Path $TempDir 'unpacked'
  Expand-Archive -LiteralPath $ZipPath -DestinationPath $Unpacked
  $InstallDir = Join-Path $env:LOCALAPPDATA 'innstance'
  New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
  Move-Item -LiteralPath (Join-Path $Unpacked 'innstance.exe') `
    -Destination (Join-Path $InstallDir 'innstance.exe') -Force
  $env:Path = "$InstallDir;$env:Path"
  innstance version
  innstance skill sync
} finally {
  Remove-Item -LiteralPath $TempDir -Recurse -Force -ErrorAction SilentlyContinue
}
```
<!-- END VERIFIED CLI BOOTSTRAP -->

When `innstance` already exists, skip the bootstrap and run `innstance version`
followed by `innstance skill sync`.

`skill sync` prints the authoritative cached `SKILL.md` and `RUNBOOK.md`
paths. If this file was loaded from another path, read those refreshed files
now and continue from them. If the sync fails (network, outage), keep working
from the copy you already have and mention the failed refresh to the user — a
slightly stale bundle is safe; guessed instructions are not.

Set `IFHOST_AUTO_UPDATE=0` only when the user explicitly needs a pinned CLI.
`innstance update` remains available for an explicit update.

### Public URLs

Use the exact public URL returned by `innstance deploy`, `innstance publish`, or the resource listing. New apps, static sites, and agent panels receive an assigned `*.fly.dev` URL. The project name does not determine that hostname. Existing shared-host URLs and connected custom domains remain valid: do not migrate or rewrite them. The control API and CLI downloads remain at `https://innstance.impossibuild.ai`.

In verification examples below, set `IFHOST_PUBLIC_URL` to that returned URL, without a trailing slash. Never guess it from the app name. Agent compute stays on AWS behind its assigned public gateway.

### 0b. Deploy ≠ live — never declare success without a 200

`innstance deploy` succeeding means the VM is provisioned, NOTHING more. The
VM boots as a bare shell with no app process; the CLI prints "Runner VM
ready — your app is NOT live yet". You are done only when ALL of:

1. You installed and STARTED the app (survives the exec session:
   `innstance machines exec --app X -- sh -c "setsid nohup <cmd> </dev/null > /tmp/app.log 2>&1 &"`)
2. `curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "${IFHOST_PUBLIC_URL}/"`
   printed `200` (or the app's health endpoint did)

Until then, NEVER tell the user "deployed", "live", or "running" — a
declared-but-dead deployment is the single worst outcome for a customer.
If you cannot get a 200, report exactly what state things are in.

**No Dockerfile or build deploys.** A `[build]` section in impossible.toml
(dockerfile or cmd) is IGNORED — the platform never builds images and never
runs a configured start command. Deploys boot the bare runner VM; you drive
setup and startup yourself as above. The CLI warns when it sees `[build]`.
Never CREATE a Dockerfile for an innstance deploy — it will not be built. But
if the repo already has one (local dev, other platforms), leave it alone;
it simply isn't used here — and DO read it: it's the project's own setup
recipe. See "Deriving runner steps from an existing Dockerfile" below.

**Persistence and restart contract.** Runner deploys with no explicit storage
or volumes currently provision a 1 GB local volume at `/data`. Put application
source and durable install state under `/data/app`; do not rely on `/app` or
other root-filesystem paths surviving a machine restart. A detached process
survives the `machines exec` session, but it does NOT auto-start after a
machine restart. After any restart or redeploy, reinstall anything missing,
start the app again, and repeat the public HTTP check.
If unattended automatic recovery after a machine restart is a requirement,
stop and report it as unsupported by the current runner workflow.

### 0c. Cookie-based authentication on an Innstance URL

When an application uses a browser cookie for sign-in or authorization on its
Innstance-provided URL, configure the application or framework itself so that:

- the exact session-cookie name begins with `__Host-`;
- the cookie uses `Secure`, `HttpOnly`, and an explicit `Path=/`;
- the cookie has no `Domain` attribute; and
- the server accepts only that exact cookie name, with no unprefixed fallback.

Do not rename or rewrite a customer's cookies at the proxy. The application
owns its cookie semantics and must opt into this contract explicitly.

For static publishing, the publish result warns when the uploaded HTML directly
references the browser cookie APIs. Treat that as a review prompt, not a
complete scan: runtime and externally loaded scripts may not be visible. A
static page cannot create an `HttpOnly` cookie from JavaScript; cookie-based
authentication for a static page therefore needs a backend or authentication
provider to issue it.

### 1. Understand the project BEFORE deploying

**CRITICAL:** Before running `innstance init` or `innstance deploy`, complete this checklist:

**Step A — Read the docs:**
- README.md, INSTALL.md, docs/install/ folder, or any setup guide
- An existing Dockerfile or docker-compose.yml — never built here, but it IS
  the setup recipe (see "Deriving runner steps from an existing Dockerfile")
- .env.example (lists ALL required env vars with descriptions)
- Any config file templates (config.example.json, etc.)

**Step B — Fill out this mental checklist:**
```
Port:          ___  (check app docs, docker-compose ports, or app --help)
RAM:           ___  (512MB for small Node/Python apps, 1024MB+ for builds/background work, 2048MB+ if heavy)
CPUs:          ___  (1 for simple, 2+ for AI/heavy compute)
Autostop:      ___  (false for bots, long-polling services, or apps that take >60s to boot)
Env vars:      ___  (list every non-secret KEY=VALUE the app needs)
Secrets:       ___  (list key names and protected sources only; never paste values here)
Startup cmd:   ___  (setup before serving: config generation, migrations, --bind lan)
Bind address:  ___  (many apps default to localhost — must bind to 0.0.0.0 or use --bind lan)
Storage:       ___  (runner default: 1 GB local /data; is that enough, and must state be shared?)
Config files:  ___  (does the app need a JSON/YAML config file written before it starts?)
```

**Step C — ALWAYS ask the user these two questions (even if you think you know the answer):**

```
1. What app name / domain do you want? (becomes <name>.<platform-domain>, must be
   globally unique across the platform)

2. Should I pick the machine specs, or do you want to customize them?

   RECOMMENDED: let me decide. I've read the docs for this specific project
   and picked specs that match what it actually needs. Going too low (e.g. 256MB
   for a Node.js app) causes silent OOM kills, crash loops, or slow boots — the
   app will deploy "successfully" but not work.

   My proposed specs for this project:
     - RAM: <picked based on app type>
     - CPUs: <picked>
     - Always-on: <yes/no based on bot vs static>
     - Region: iad (US East)

   Type 'go' to accept (recommended), or tell me specifically what to change.
```

Even if the user said something like "deploy this", still ask. The user may want a specific
domain name. For specs, nudge them toward accepting your picks — you've actually read the
project; they haven't. Accepting defaults should be a one-word reply ("go", "ok", "yes").

**Step D — Resolve credentials/missing info:**
- Ask for the names of required API keys, bot tokens, and database credentials,
  but do not ask the user to paste secret values into chat.
- Have the user expose each value through an environment variable, a protected
  local file, or stdin. Pass only a reference such as `KEY=@env:KEY`,
  `KEY=@file:/run/secrets/key`, or `KEY=@stdin` to Innstance.
- Never guess credentials or place them in `impossible.toml`, a command
  argument, a transcript, or a source archive.
- Model preferences (which AI model to use, if applicable)

**Step E — Present the full deployment plan for final approval.**
Show the impossible.toml you'll generate and the exact deploy command with all flags.
Let the user confirm or correct before proceeding.

Only after the user approves should you run `innstance init` and `innstance deploy`.
If the user says not to modify the source repository, run both commands from
a temporary workspace: `init` creates `impossible.toml`, and `deploy` may
update it with the resolved app name or port.

### 2. Tell the user what's happening (observability)

**HARD RULE: always start any multi-step task with a step list and ETA.** No exceptions,
no matter how short the task seems. Users looking at a blank chat don't know if you're
thinking, working, or stuck. The step list is the contract — you'll do these N things,
it'll take ~X minutes.

Before running ANY innstance command that takes more than a few seconds, print:

```
Deploying my-app to Innstance — plan:
  Step 1/4: Read project docs                          (~10s)
  Step 2/4: Configure impossible.toml                  (~5s)
  Step 3/4: Deploy                                     (~1-2 min)
  Step 4/4: Verify the app is live                     (~10s)

Total ETA: ~2-3 minutes
```

Then announce each step AS you start it: "Step 3/4 — deploying (1-2 min)…"

Even for a 2-step task ("install innstance then login"), say so:
```
Setting up Innstance — plan:
  Step 1/2: Install CLI                            (~15s)
  Step 2/2: Sign in                                (~30s, browser opens)
Total: ~45s
```

Update the user at each step. Never go silent for more than 30 seconds during a deploy.

**Concrete rules for observable progress (every rule here came from a real user-confusion moment):**

1. **Heartbeat every 60s max, no exceptions.** If an upstream installer (pip, npm, apt) goes silent for 5+ min (Playwright's Chromium install is the classic example), emit `"[heartbeat +Ns] still running: <last visible line>"` every minute anyway. Users staring at a quiet chat assume you're hung — and they're right to give up at 5 min. A minute-by-minute "still at: Installing Node.js dependencies..." is infinitely better than silence.
2. **Announce before running.** "Installing xz-utils…" should appear in chat BEFORE the command fires, not just "Sent 83 bytes". Every non-trivial console/Bash call gets a one-line preamble.
3. **Stream long commands, don't poll-and-check.** For anything expected to run >30s (installers, Chromium downloads, console installs), attach a `Monitor` with a diff-based tail that emits NEW lines as they appear AND a heartbeat when no new lines for 60s. `tail -1` + sleep 15 is a bug — you see one line per minute and miss errors.
4. **Pipes hide failures.** `cmd | tee file; echo __DONE_$?__` reports the exit of `tee`, not `cmd`. If the installer bails halfway, you get `__DONE_0__` and falsely conclude success. Use `set -o pipefail` in the shell snippet, or check for the expected artifact (`test -x /root/.local/bin/hermes`) instead of trusting `$?`.
5. **Report in human units.** "Downloading Chromium (~250 MB, 1-2 min)" beats "Sent 163 bytes". Convert bytes to MB, seconds to "min:ss", phases to "Phase 3/5".
6. **On retry or recovery, narrate.** If you see 412/408 and retry, say "hit transient 412, retrying" — don't silently loop. Users seeing a 2-minute hang with no explanation assume the worst.
7. **Cold exit 0 ≠ success.** A container that exits code 0 after 30s may have run the wrong command (e.g., interactive CLI exiting on no-TTY). Verify by hitting the app's actual endpoint or reading logs, not by trusting the exit code.
8. **Name the phase before entering it.** Before starting a multi-minute phase, tell the user: "Phase 4/6: Installing Python deps (2-5 min) — this is the longest part; Playwright downloads a Chromium". When the user knows what to expect, 3 minutes of silence is tolerable. When they don't, 30s is infuriating.
9. **NEVER tail/cat/dump files that could contain secrets** from a live container back into the chat transcript. `.env`, `config.yaml`, `/etc/*secret*`, anything written via `--secret` or echoed from `env | grep KEY` — all off-limits for buffer-dumping even to "verify the write succeeded". If you MUST verify, grep for the variable name only and echo a boolean (`grep -q '^OPENAI_API_KEY=' .env && echo OK`). Once secrets land in a chat transcript they are compromised — the user has to rotate them. One lapse costs the user real money and time.

### 2b. First-start of an app can take 5-15 minutes — plan for it

A fresh deploy is NOT "ready to serve" the moment `innstance deploy` returns. Expect, on top of the control-plane deploy (10-60s):

- **Image pull to the VM** (30s-2min, depending on image size + region network)
- **Volume init / encrypt / format** (5-15s, one-time per volume)
- **App cold start** (highly variable)
  - Trivial web app (echo bot, static site): **1-5s**
  - Node/Python web service: **5-30s**
  - Agent frameworks with plugins (openclaw, hermes, similar): **5-15 min** — they install runtime deps, fetch model pricing, initialize browser/voice/channel subsystems, call out to `api.telegram.org`/`api.openai.com` which can themselves stall. Not a bug; that's their actual startup cost on a cold volume.
- **First-message cold-start for LLM-backed bots**: add another 30s-5min the very first time a user messages the bot — the agent's identity/memory scaffolding runs on-demand.

Implications for you as the agent driving the deploy:

- A single "HTTP probe failed after 60s" is **not sufficient evidence** to conclude the deploy is broken. Only conclude broken if the logs show crash signatures (`Exec format error`, `max restart count`, `Main child exited with code: 1`, OOM kill, port-mismatch refused-connection that persists >3 min after the app should have started).
- When the probe comes back "no response yet" for a known-slow stack (anything with "plugin" or "agent" or "gateway" in its name), print a friendly **"still initializing, this can take up to 15 min for <stack>; watch with `innstance machines logs --app X --follow`"** — not a failure.
- The `innstance deploy` command distinguishes "still starting" (exit 0, warn) from "broken" (exit 1, error). Trust its exit code; don't treat every warning as a deploy failure.
- Ask the user to wait 10-15 min before concluding "the bot doesn't work" on the first message. Subsequent messages are fast.
- Retry loops inside the app (e.g. openclaw's setWebhook call to Telegram) can compound the wait. A single outbound flake from the host region can reset app init by 30s. That's an app-level issue, not ours — document it, don't treat it as our deploy being broken.

### 2a. STOP polling once /healthz returns 200

**Common time-waster:** agents repeatedly poll `innstance machines logs` and `Monitor`
waiting for specific app-internal log strings ("gateway ready", "channel connected",
"polling started"). This wastes 5-20 minutes per deploy.

**Hard rule:** the deploy is DONE when `curl --fail --show-error --max-time 30 "${IFHOST_PUBLIC_URL}/healthz"` returns 200
(or the app's equivalent health endpoint). Internal subsystems (Telegram polling, Discord
WebSocket, agent initialization) may take another 30-90 seconds to come up — that's the
APP's problem, not the deploy.

What to do instead:
1. After deploy completes, hit the health endpoint ONCE to confirm liveness
2. Tell the user "Deploy succeeded. App is live at https://X. Bot/integration may take
   another 1-3 min to fully connect. Messaging bots (Telegram/Discord) typically
   take 2-3 min between 'gateway ready' and actually polling — this is the app's
   startup, not the deploy. Try messaging it in ~3 min."
3. **Don't set up Monitor tasks waiting for specific log strings unless asked**
4. If the user reports the integration didn't work, THEN check logs

Time budget: a deploy task should take **~3-5 minutes total** (init + deploy + verify).
If you're at 10+ minutes, you're overpolling — stop polling and report the actual
verified state: "app returned 200, done" or "no 200 yet, here's the last log line".
Never round an unverified deploy up to "it's deployed".

### 3. Read --help for command syntax

Before running any innstance command, check its help text:

```bash
innstance deploy --help
innstance machines logs --help
```

Use the freshly updated CLI help to confirm command syntax and available
flags. Do not infer runner lifecycle from generic examples in help output:
`[build]` remains ignored, and applications must be started explicitly.

## Install / Update

When `innstance` is missing, use the signed-channel bootstrap in Rule 0 exactly as
written. Do not substitute either release-origin installer, another public
key, an unsigned archive, or a checksum that is not authenticated by the
SSHSIG release record.

For an existing installation, invoking `innstance` performs its independently
signed automatic update check. Run this at the start of every session:

```bash
innstance version
innstance skill sync
```

On macOS/Linux, add `~/.local/bin` to PATH if needed. On Windows, the Rule 0
PowerShell block adds `%LOCALAPPDATA%\innstance` to the current process PATH; add
that directory to the user PATH for future terminals. If OpenSSH Client is
missing, run `Add-WindowsCapability -Online -Name
OpenSSH.Client~~~~0.0.1.0` in an elevated PowerShell, then repeat the verified
bootstrap.

Verify installation:

```bash
innstance --help
```

If any signature or digest check fails, stop without installing. Do not bypass
the Rule 0 trust anchor or use a direct archive pipe.

## Quick Start

```bash
innstance login                                          # Browser device authorization (one-time)
innstance init --app my-app --port 3000 --memory 512 --storage local
innstance deploy                                         # Provision the runner
# Then install, transfer to /data/app, start, and verify an HTTP 200.
```

## How Deploys Work (runner mode)

Every deploy boots a generic Debian shell VM (the "runner"). You then drive
setup step-by-step — install dependencies, write config, start the app —
via `exec`, `write`, `push`, and `console`. There is no image build and no
stack detection: you run the project's own install steps.

**Why it works this way:** deploy typically finishes quickly because there is
no image build. Files under `/data` survive machine restarts, so keep source
and other durable state there. Changes made elsewhere in the root filesystem
may need to be recreated after a restart, and the application process must
always be started again.

```bash
innstance deploy --secret KEY=@env:KEY --yes
innstance machines console start --app <app> -- bash
# download, authenticate against an upstream-published key or pinned digest,
# and inspect upstream installers before executing; never run unauthenticated code
```

See "Interactive setup" in Common Deployment Patterns for the full console workflow.

### Deriving runner steps from an existing Dockerfile

If the repo has a Dockerfile, it will NOT be built — but don't ignore it:
it is the project's own setup recipe, written by someone who knew the app.
Read it FIRST and translate line-by-line into runner commands:

| Dockerfile | Runner equivalent |
|------------|-------------------|
| `FROM python:3.12-slim` | `machines install --app X python3` (runner is already Debian; install the language runtime the base image implies) |
| `FROM node:20` | install Node via apt or the project's preferred method |
| `RUN <cmd>` | `machines exec -- sh -c "<cmd>"` verbatim |
| `COPY . /app` | `machines push ./ --to /data/app --app X --yes-replace` |
| `WORKDIR /app` | prefix later commands with `cd /data/app &&` |
| `ENV K=V` | `[env]` in impossible.toml, or `--env K=V` on deploy |
| secrets in ENV | `--secret K=@env:K` / `machines secrets set K=@env:K` |
| `EXPOSE 8080` | `[service] internal_port = 8080` |
| `CMD` / `ENTRYPOINT` | start it persistently: `machines exec -- sh -c "cd /data/app && setsid nohup <cmd> </dev/null > /tmp/app.log 2>&1 &"` |
| `HEALTHCHECK` | your Rule 0b verify curl |
| multi-stage builds | run the build-stage steps too; they may need a bigger volume (`volumes extend`) or more memory during install |

Worked example — a static site whose Dockerfile is
`FROM python:3.12-slim` + `COPY . .` + `CMD python3 -m http.server 8080 --directory /app`:

```bash
innstance machines install --app my-site python3
printf '%s\n' 'state/data.db' > .ifhost-state-paths  # only when the app owns this runtime path
innstance machines push ./ --to /data/app --app my-site --yes-replace
innstance machines exec --app my-site -- sh -c "setsid nohup python3 -m http.server 8080 --bind 0.0.0.0 --directory /data/app > /tmp/app.log 2>&1 < /dev/null &"
curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "${IFHOST_PUBLIC_URL}/"   # must print 200
```

**Gotchas that burn tokens on runner deploys (learned the hard way):**

- **Front-load system deps before running the project's install script.** The runner base image is minimal — only `tmux` and `ca-certificates` are preinstalled; no `curl`, `xz-utils`, `procps`, or `git` out of the box. Use the detached, verified installer:
  ```
  innstance machines install --app X curl xz-utils procps git
  ```
  Discovering each missing tool one failure at a time wastes 30s+ per round trip.
- **Set `HOME` explicitly before running install scripts.** Many installers use `$HOME/.local/bin` etc; if `HOME` is unset the script installs to `//.local/bin` (double-slash) or bails. `export HOME=/root` before running an authenticated and inspected installer.
- **tmux `new-session "<cmd>"` does NOT inherit exported PATH.** The spawned shell starts fresh. Use absolute paths or set an explicit administrative `PATH` inside `/bin/sh`; do not assume `bash -lc` exists.
- **Drive interactive wizards, don't bypass them.** If a project ships a `setup` / `init` / `configure` wizard, run it and drive it via console. Killing it with Ctrl+C and reverse-engineering the config layout burns 10x more tokens than just answering arrow-key prompts.
- **Read the project's provider/config source before guessing IDs.** Hermes's `auth add` rejects bare `"openai"` because their `providers.py` routes that to OpenRouter; valid options are listed only in the wizard. `grep -n 'provider' /path/to/providers.py` takes 5 seconds; guessing 6 wrong IDs takes 5 minutes.
- **PID files may be JSON, not integers.** Hermes writes `{"pid": 9249, "kind": "hermes-gateway", ...}` to `gateway.pid`. `kill $(cat pidfile)` fails with "arguments must be process or job IDs". Parse with `grep -oE '"pid":\s*[0-9]+' file | grep -oE '[0-9]+'`.

---

## Command Reference

### innstance login

Authenticate through browser device authorization. The CLI prints a short
sign-in code, opens the approval page, and polls until you approve it. The
approval page can be opened on any browser-capable device; it does not need a
browser or loopback listener on the machine running `innstance`. Sign in through
the providers configured in the dashboard, verify the displayed machine, and
approve it. Credentials are stored at `~/.impossible/credentials.json`
(`%USERPROFILE%\.impossible\credentials.json` on Windows). If
already logged in, the account picker still lets you switch or add an account.

| Flag | Description |
|------|-------------|
| `--token -` | Read an API token from stdin; literal values are refused so they cannot leak through argv or shell history |
| `--from-file <path>` | Read the token from a local secret file (`-` = stdin) — avoids shell history and `ps` exposure |
| `--switch` | Select a saved account |

If `IMPOSSIBLE_API_TOKEN` is set, requests use that token instead of saved
credentials. `--switch` still selects a saved account; unset the override only
when you intend subsequent commands to use that account.

### innstance logout

Remove stored credentials.

### innstance status

Overview of all projects with machine IDs. **Run this first** to understand what's deployed.

```
Logged in as: user@example.com
Plan:         pro
CLI:          20260421-123154

Projects (2):

  my-api
    URL:     https://ifh-app-0123456789abcdef0123456789abcdef.fly.dev
    Status:  deployed   Region: iad
    Running (1):
      e784160df242e8

  my-site
    URL:     https://ifh-site-fedcba9876543210fedcba9876543210.fly.dev
    Status:  deployed   Region: iad
    Running (1):
      d8930e1c063d58
```

Use machine IDs from this output with `--machine` on exec/console commands.

---

### innstance init

Generate `impossible.toml` — required before `innstance deploy`.

```bash
innstance init --app <name> --port <port> --memory <mb> [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--app` | (required) | Resource name. Use the assigned public URL returned by the CLI |
| `--port` | 8080 | Port the app listens on |
| `--memory` | 256 | RAM in MB (256, 512, 1024, 2048, 4096) |
| `--cpus` | 1 | CPU count (1, 2, 4, 8) |
| `--cpu-kind` | shared | `shared` or `performance` |
| `--cmd` | (none) | DEPRECATED — writes `[build] cmd`, which deploys ignore. Start apps via `machines exec` instead |
| `--autostop` | false | Always-on is the platform default. Only set `true` for apps that may die on idle — runner apps do NOT survive an idle-stop (VM wakes with no app process) |
| `--min-machines` | 0 | With the always-on default this rarely needs setting; pairs with explicit autostop |
| `--storage` | (empty) | `local` records an explicit local-storage request. An empty init value omits storage from the manifest, but runner deploys with no declared volumes currently still provision a 1 GB `/data` volume. Volumes are per-machine. |

Generates `impossible.toml` in the current directory. Edit it directly after creation — do not re-run init (it errors if the file exists).

---

### innstance deploy

Deploy the app. Requires `impossible.toml`.

```bash
innstance deploy [flags]
```

| Flag | Description |
|------|-------------|
| `--env KEY=VALUE` | Set env var (repeatable). Merged with [env] in toml. |
| `--secret KEY=@env:NAME` | Set a secret by protected reference. Also accepts `KEY=@file:PATH` or one `KEY=@stdin`; literal values are refused |
| `--port N` | Override container port |
| `--region <code>` | Region (e.g. iad, sin, lhr). See `innstance regions`. |
| `--storage local` | Explicitly provision a `/data` volume on first deploy. With no storage flag or declared volumes, runner deploys currently provision a 1 GB `/data` volume automatically. |
| `--app <name>` | Override app name from toml |
| `--yes` | Skip confirmation prompts |
| `--json` | Output structured JSON |
| `--recreate-app` | Silences the advisory shown when impossible.toml names an app the server has no record of. Deploy proceeds either way. |

Deploy boots a generic Debian runner VM without building the application.
Drive setup via `exec`/`write`/`console` after deploy.

**After deploy:** Prints the public URL (e.g.,
`https://ifh-app-0123456789abcdef0123456789abcdef.fly.dev`). The application is not live until you
start it and verify HTTP `200`.

#### Redeploying is safe — the app keeps its address

Deploying again to an app that already exists **reuses** it; the output says
`Reusing app "<name>"`. The app keeps its network address, so any custom domain
pointed at it keeps working. Shipping new code never changes an address.

(It does kill any running process — re-run your install and start steps, then
re-verify the 200.)

#### One error that means stop, and one note that does not

**STOP — existence could not be verified**

```
could not verify whether app "my-app" exists: API error (500): ...
  Not creating a new app — a new app would get new addresses and break any
  custom domain pointing here.
```

The API errored, so the CLI does not know whether the app already exists. It
refuses rather than risk creating a second app alongside a live one.

This is transient. Wait, then re-run the identical command. **Never respond by
renaming the app** — a different name strands the user's custom domain on an
app nobody deploys to any more. If it persists, report it; do not work around it.

**NOT an error — the toml names an app the server doesn't have**

```
Note: impossible.toml already names "my-app" but the server has no record of it.
  If this app existed before, it is being created fresh and gets new addresses —
  update any custom domain DNS afterwards.
```

This is an advisory and the deploy proceeds. It appears on the **normal first
deploy** after `innstance init` (the toml names the app before it exists), and it
also appears if an app was previously destroyed. The CLI cannot tell those
apart, so it tells you rather than guessing.

Nothing to do in the common case. Only if the app genuinely existed before and
had a custom domain, tell the user its DNS now points at a released address and
check with `innstance machines domains list --app <name>`.

`--recreate-app` only silences this note. It does not change what happens.

---

### innstance describe --app \<name\>

Full app context in one call. Aggregates: app status, machines, env vars, secret key names, domains, persistent volumes, recent deploys, and recent platform logs.

```bash
innstance describe --app my-app         # Human-readable summary
innstance describe --app my-app --json  # Structured JSON (for programmatic use)
```

Output includes:
- URL, status, region
- Machine IDs, states, specs
- Environment variables (values truncated at 30 chars)
- Secret key names (values hidden)
- Custom domains with TLS status
- Persistent volumes with size, mount path and status
- Up to 20 recent platform log entries from a non-following read; JSON includes
  `logs_truncated` when earlier returned entries were omitted. A failed or malformed
  log read, or a failed volume read, fails the description instead of printing a
  misleading complete report. These are platform logs, not arbitrary files inside
  a runner.
- Last 5 deployments with status and timestamps. A completed runner deployment
  reports `staged`: the machine is ready for setup, not proof that an app is
  serving. Install/start the app and verify its URL separately.

---

### innstance machines

All app-specific commands live under `machines`. Requires `--app <name>` or an `impossible.toml` in the current directory.

#### List machines

```bash
innstance machines --app my-app
```

Shows machines grouped by state with IDs for targeting.

#### Start / Stop / Restart

```bash
innstance machines start --app my-app
innstance machines stop --app my-app       # No cost while stopped
innstance machines restart --app my-app
```

Apps run on a single machine. Multi-machine scaling is on the roadmap.
`restart` does not relaunch a process previously started with `setsid` or
`nohup`; run the start command again and repeat the public HTTP check.

---

### innstance machines logs

Stream or tail runtime logs from your app. **Default mode is live streaming (tail -f)** — runs indefinitely until Ctrl+C.

```bash
innstance machines logs --app my-app                      # Live stream (tail -f)
innstance machines logs --app my-app --since 1h           # Last hour, then exit
innstance machines logs --app my-app --lines 20           # Last 20 lines, then exit
innstance machines logs --app my-app --grep "ERROR"       # Only lines containing ERROR
innstance machines logs --app my-app --level error        # Only error/fatal/panic lines
innstance machines logs --app my-app --json               # Structured JSON per line
```

| Flag | Description |
|------|-------------|
| `--since <duration>` | Show logs from this duration ago (e.g., 1h, 30m). Exits after. |
| `--lines <N>` | Show last N lines then exit (no follow) |
| `--grep "<pattern>"` | Filter: only show lines containing this substring (case-insensitive) |
| `--level <level>` | Filter by level: `error` (includes fatal/panic), `warn`, `info` |
| `--json` | Output structured JSON per line |
| `--raw` | Alias for `--json` |
| `--wait-for-match <str>` | Exit 0 when a line contains this substring (case-insensitive) |
| `--wait-timeout <dur>` | Timeout for `--wait-for-match` (default 5m, e.g. 60s, 2m) |

---

### innstance machines exec

Run a one-off command inside a running machine. For commands that finish without stdin.

```bash
innstance machines exec --app my-app -- ls /data
innstance machines exec --app my-app -- sh -c 'test -n "$NODE_ENV" && echo NODE_ENV=set || echo NODE_ENV=unset'
innstance machines exec --app my-app --machine e784160df242e8 -- cat /var/log/app.log
```

Timeout: 10 minutes (enforced server-side, cannot be raised). For longer-running
commands use the fire-and-poll pattern — launch via `nohup ... &` in one exec, then
poll completion in later execs — or use `console`. Use `console` for anything
interactive (prompts, wizards, REPLs).

---

### innstance machines console

Interactive tmux-backed console for commands that need stdin or take a long time.

#### Start a session

```bash
innstance machines console start --app my-app -- bash
```

Returns a `session-id` (e.g., `ifhost-01abc`).

#### Send input / Read output / End session

```bash
innstance machines console input --app my-app <session-id> "npm install"
innstance machines console input --app my-app <session-id> --key Enter
innstance machines console output --app my-app <session-id> --lines 100
innstance machines console end --app my-app <session-id>
```

---

### innstance machines env / secrets

**API parity:** Environment and secret writes/deletes also save without
restarting. Use `?restart=true` only when an immediate restart is intended.
The dashboard Settings action uses the same endpoints and defaults.

**Important:** `env set` and `secrets set` do NOT restart the machine by
default. Configure them before starting the app when possible. If you pass
`--restart` or run `machines restart`, start the application again afterward
and repeat the public HTTP check.
Replacing existing values non-interactively requires `--yes-replace`.

```bash
innstance machines env set KEY=VALUE --app my-app              # Set (no restart)
innstance machines env set KEY=VALUE --restart --app my-app    # Set + restart immediately
innstance machines env list --app my-app
innstance machines env rm KEY --app my-app                     # Remove env var
innstance machines secrets set API_KEY=@env:API_KEY --app my-app
innstance machines secrets set API_KEY=@file:/run/secrets/api-key --app my-app
printf '%s' "$API_KEY" | innstance machines secrets set API_KEY=@stdin --app my-app
innstance machines secrets list --app my-app                   # Shows key names only
innstance machines secrets rm KEY --app my-app                 # Remove secret
```

### innstance machines volumes

```bash
innstance machines volumes list --app my-app
innstance machines volumes create my-data --size 3 --mount /data --app my-app
innstance machines volumes extend my-data --to 10 --app my-app   # Grow only, cannot shrink
innstance machines volumes rm my-data --app my-app --yes
```

**Volumes are per-machine** (one machine, one disk). Shared volumes are on
the roadmap; for shared state today use a managed database.

Growing an attached volume makes the new space available online; a restart
is not required. New volumes still need a deployment to attach them.

### innstance machines domains

```bash
innstance machines domains add myapp.com --app my-app
innstance machines domains check myapp.com --app my-app
innstance machines domains list --app my-app
innstance machines domains rm myapp.com --app my-app       # Remove custom domain
```

`domains add` claims the hostname only after the user proves they control
its DNS. It prints the two records to add — a CNAME from the hostname to
the platform (an ALIAS at a bare domain) and one TXT proof record
(`_hostimpossibuild-verify.<hostname>`), values from the command output —
and exits with a pending-verification result. Add the records, then run
the same command again to finish claiming the hostname. Pass `--wait` to
wait up to two minutes for the proof to appear. There are no address records to add. Tell the user to
keep the TXT record after setup.

DNS requirements are returned by the current platform and may change. Never
infer a CNAME or copy record values or provider URLs from this skill. Run
`domains check` and treat its complete Option 1 configuration as authoritative.

Follow the two options printed by `domains check` exactly. Keep the manual
records visible even when offering the agent-assisted option. For agent-assisted
setup, find and verify the provider's current official token-creation page; do
not guess a URL or request a password or global API key. Change only the records
listed by the command. After all required records are saved, run the printed
check command once and respect any retry time instead of polling. End the final
response with the complete configuration and check result requested by the CLI.

If the command cannot identify a DNS provider, do not invent a token workflow.
Surface its manual configuration and explain that an unpurchased domain must be
registered first, while an owned domain may need its nameservers configured.
TLS issuance is automatic after the required records are correct.

### innstance publish and innstance sites

`publish` puts files on the web with no machine and no config: live in
seconds at the tenant URL the command prints.

```bash
innstance publish --name my-page page.html         # one HTML file, served as the page
innstance publish --name menu cover.pdf body.pdf   # PDFs combined into ONE document
innstance publish --name gallery hero.png pic.jpg  # images stacked into one scrolling page
innstance sites list                               # name, URL, mode, size, updated
innstance sites rm my-page                         # delete a site
```

File order is the order typed: PDF pages merge in that order, images stack
top-to-bottom. Re-running `publish` with the same `--name` replaces the
site's entire content — that is also how to rearrange. A single PDF or
image is served directly at `/`.

Rules that change what an agent should do:
- Site names are GLOBAL across every account. First claim wins, and
  `sites rm` frees the name for ANYONE to take. Deletion is immediate and
  irreversible — say so to the user before confirming.
- `sites rm` asks interactively. Agents and scripts must pass `--yes`, or
  the command refuses and prints the flag instead of hanging on a prompt.
- `publish` is one HTML file or PDFs/images, never both. A multi-file
  website (HTML plus assets) is `innstance deploy` territory.
- Site count and size limits are plan-dependent; run `innstance billing`
  rather than quoting numbers from memory.

Custom domains on a published site: see the next section.

### innstance sites domains

Published static sites take custom domains too, with the identical flow —
prove control, add the printed records, certificate issues on its own. The
site is named as the first argument (sites have no `--app` context):

```bash
innstance sites domains add my-page myapp.com
innstance sites domains check my-page myapp.com
innstance sites domains list my-page
innstance sites domains rm my-page myapp.com
```

Everything in the `machines domains` section above — the proof record, the
two-minute wait and re-run behavior, treating `domains check` output as
authoritative, never inventing provider workflows — applies to these
commands unchanged.

### innstance machines write / push

```bash
innstance machines write <local-file> --to <remote-path> --app my-app                  # Write a single file
innstance machines write <local-file> --to <remote-path> --machine <id> --app my-app   # Target specific machine
innstance machines push <local-dir> --to <remote-dir> --app my-app                     # Push a directory tree
```

`write` caps each file at 10 MiB. `push` has no arbitrary total archive cap.
Both use verified 8 MiB raw chunks, resume from the last acknowledged chunk,
and verify the complete file/archive before changing the destination. `write`
accepts `--machine`; `push` does not.

Pause processes that can write project state before pushing, then restart them
after deployment. File copying is not an application-consistent database backup.
If push reports open protected state, pause those processes before retrying.
`--override-running` only allows protected archive entries; it does not make
live state safe to replace.

Before `push`, create `.ifhost-state-paths` in the local source root with
relative paths the running app owns, one per line (for example
`state/data.db` or `uploads/`). On redeploy those paths are snapshotted outside
the target and restored byte-for-byte. An empty/missing declaration means no
runtime state is protected and produces a warning. Review the manifest, then
pass `--yes-replace` for non-interactive replacement.

`push` honors `.gitignore`, `.dockerignore`, and `.impignore`, applies built-in
exclusions such as `.git`, `node_modules`, and `.env*`, and skips symlinks and
individual files larger than 50 MB. It checks target free space before upload.
Never copy private Git credentials into the runner.

### innstance machines pull

Download a directory from the running VM as a `.tar.gz` backup.

```bash
innstance machines pull /data/app --app my-app                             # Prompts before downloading
innstance machines pull /data/app --to backup.tar.gz --yes-egress --app my-app   # Non-interactive
```

The download is METERED as outbound traffic on the account, the same as
visitor traffic to the apps. Every pull first archives the directory on
the VM and prints a manifest with the exact archive size, its SHA-256,
and the account's current traffic standing — read it before approving.
Nothing is downloaded or metered until approved.

The confirmation prompt refuses in non-interactive sessions. Pass
`--yes-egress` only after the manifest is acceptable; it is explicit
consent to the metered traffic. Do not pass it habitually — on a large
data directory the download can be a meaningful share of the month's
allowance, and the manifest is where that is visible.

The downloaded file is verified against the archive's SHA-256 and written
atomically: an interrupted or corrupted download never replaces an
existing file. If a pull is interrupted, rerun the same command. Archives
are staged under the VM's `/tmp`, so the VM needs about the directory's
size in free space; if archiving fails or times out, pull a smaller
subdirectory instead.

### innstance machines wait-for

Block until a substring appears in a file inside the VM. Useful for waiting on app readiness.

```bash
innstance machines wait-for --file /var/log/app.log --match "listening on" --app my-app
innstance machines wait-for --file /data/startup.log --match "ready" --timeout 2m --app my-app
```

| Flag | Default | Description |
|------|---------|-------------|
| `--file` | (required) | Absolute path inside the VM to tail |
| `--match` | (required) | Substring to wait for |
| `--timeout` | 5m | Timeout (e.g. 60s, 2m) |

### innstance machines destroy

```bash
innstance machines destroy --yes-irreversible --app my-app                # Delete entire app + resources
innstance machines destroy --yes-irreversible <machine-id> --app my-app   # Delete single machine
```

### innstance apply

Push stored CPU, memory, environment and secret configuration to existing machines without rebuilding. Apply preserves each machine's image, service configuration and volume mounts. When `impossible.toml` supplies resource settings, the CLI saves those settings before applying them.

Inspect `applied` and `failed_machines` in JSON output. Partial failures return HTTP 207 and the CLI currently exits zero while listing the failures; exit zero alone does not establish that every machine was updated. Retry the failed rollout and verify the application process and public URL after the machine transition completes.

```bash
innstance apply --app my-app
```

### innstance tokens

```bash
innstance tokens create --name "ci-bot"     # Create a new API token (default name: "cli")
innstance tokens list                       # List all API tokens
innstance tokens revoke <token-id> --yes    # Revoke a token without a prompt
```

Use tokens for CI pipelines or agent auth without putting the credential in an
argument:

```bash
printf '%s' "$IFHOST_TOKEN" | innstance login --token -
innstance login --from-file /run/secrets/ifhost-token
```

For application secrets, pass a source reference to `deploy --secret` or
`machines secrets set`: `KEY=@env:NAME`, `KEY=@file:PATH`, or (for one secret
per command) `KEY=@stdin`. Literal secret values are refused. Only the resolved
value is sent to the platform; local files stay local.

### innstance auth

```bash
innstance auth bind-wallet <address>        # Bind an EVM wallet for USDC top-ups (polls for verification)
innstance auth wallets                      # List bound wallets (pending + verified)
innstance auth unbind-wallet <address>      # Remove a wallet binding
```

### innstance regions

List available deployment regions.

### innstance version / update

```bash
innstance version                           # Show CLI version and check for updates
innstance update                            # Update CLI to the latest version
```

Automatic-check failures are recorded in
`~/.impossible/update-check.json` (under `%USERPROFILE%` on Windows) while
the requested command continues. Set
`IFHOST_AUTO_UPDATE_DEBUG=1` when you need the same failure on stderr; never
treat a quiet background check as proof that an update was available or
installed.

### innstance billing (alias: sub)

```bash
innstance billing status                     # Current subscription status
innstance billing subscribe hobby            # Subscribe to a plan (hobby, pro, team)
innstance billing subscribe --plan pro --pay crypto   # Specify payment method
innstance billing cancel                     # Cancel subscription
innstance billing cancel-change              # Call off a queued plan change, keep the current plan
innstance billing invoices                   # Payments: what the card was charged, and when
innstance billing plan                       # Show current plan and usage
innstance billing alert set --max 20         # Set spend alert at $20
innstance billing alert show                 # Show current alert
innstance billing alert off                  # Disable spend alert
innstance billing usage                      # Month-to-date traffic per app/site
innstance billing topup-traffic 100          # Buy traffic credit (USDC)
```

### Traffic: seeing it, and paying before it bites

Every plan includes a monthly traffic allowance — read the account's own from
`innstance status`, never from memory. It is an **origin** allowance, and apps and
published sites draw on the **same pool**. Past it, apps and sites serve a 429 limit
page instead of content — the site stays up, the content does not.

Check before a launch you expect to spike, not after:

```bash
innstance status                             # allowance, used, and any credit
innstance billing usage                      # month-to-date, per app and site
```

If they expect heavy traffic, buy credit ahead of time; unused credit never
expires. The rate, the step size and the minimum are printed by the command
itself — run its help rather than quoting a price:

```bash
innstance billing topup-traffic --help       # current rate, minimum, and step size
test -n "$IFHOST_TOPUP_SIGNING_KEY"       # load it out-of-band; never type it into shell history
innstance billing topup-traffic <GB>         # cost is quoted before it charges
```

Without the signing key, `--json` prints the raw payment challenge so an
agent can drive its own payment loop. In the dashboard the same controls
live at `/dashboard/app` under the plan card.

**Two things worth knowing before you diagnose a 429:**

- The only warning before a block is an amber note in the dashboard at 80%.
  There is no email and no CLI warning, so a customer who does not open the
  dashboard gets no notice at all.
- Sites also have a **per-day** ceiling separate from the monthly pool.
  A 429 from that one is not fixed by buying traffic credit — check
  `innstance status` to see which limit was hit before recommending a purchase.

`subscribe` opens a hosted checkout page (pick card or crypto there). Card
payments are coming soon; crypto (USDC) works today. `--pay crypto` is a
compatibility spelling that still lands on the same hosted checkout.

Already subscribed? The same `innstance billing subscribe <plan>` switches
plans in place: an upgrade applies immediately and charges the saved
payment method only the prorated difference for the rest of the paid
period; a downgrade takes effect when the paid period ends and charges
nothing until then. An upgrade asks for confirmation with the estimated
charge before anything is billed — in `--json` mode pass `--yes` to
authorize it, or the switch is refused. Leaving for free is
`innstance billing cancel`. A queued downgrade can be called off before it lands
with `innstance billing cancel-change`, which keeps the current plan. Before a
downgrade, run `innstance billing fit <plan>` to see whether everything you
run fits the target and what deleting each resource would free — apps that
do not fit when the change lands are paused, newest first.

---

## impossible.toml Reference

Full example with all fields:

```toml
app = "my-app"
storage = "local"                  # Explicit /data volume dependency; single-machine app

[service]
internal_port = 3000               # Port app listens on (MUST match app)
autostop = false                   # Always-on (the platform default). Never
min_machines = 1                   #   set true for runner apps that must stay
                                   #   reachable — they don't survive idle-stop

[resources]
cpu_kind = "shared"                # "shared" or "performance"
cpus = 2                           # 1, 2, 4, 8
memory_mb = 1024                   # 256, 512, 1024, 2048, 4096

# NOTE: no [build] section — Dockerfiles and build/start commands are not
# supported and are ignored if present. Start the app via machines exec.

[env]
NODE_ENV = "production"
DATABASE_URL = "postgres://..."

```

There is no manifest startup hook. If an app needs a generated config file,
create it explicitly with `machines exec` or `machines write` before starting
the process. Repeat that setup after a restart when the generated file is not
under `/data`.

**Secrets:** Pass a protected reference via `--secret`, not a literal value or
a tracked TOML file:
```bash
innstance deploy --secret API_KEY=@env:API_KEY --secret BOT_TOKEN=@file:/run/secrets/bot-token
```

---

## Common Deployment Patterns

### Node.js / Python API
```bash
innstance init --app my-api --port 3000 --memory 512 --storage local
innstance deploy --env DATABASE_URL=postgres://...
innstance machines install --app my-api curl git nodejs npm
innstance machines push ./ --to /data/app --app my-api --yes-replace
innstance machines exec --app my-api -- sh -c "cd /data/app && npm install"
innstance machines exec --app my-api -- sh -c "cd /data/app && setsid nohup node server.js </dev/null > /tmp/app.log 2>&1 &"
curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "${IFHOST_PUBLIC_URL}/"   # must print 200
```

### Heavy app (AI agent, ML model, slow boot)
```bash
innstance init --app my-agent --port 3000 --memory 1024 --cpus 2 --autostop=false --min-machines 1 --storage local
innstance deploy --secret OPENAI_API_KEY=@env:OPENAI_API_KEY
# Then drive the project's own install via exec/console (see Interactive setup)
```

### Messaging bot (Telegram, Discord, Slack, etc.)

Bots that use long polling or WebSocket connections MUST stay running at all times.

```toml
app = "my-bot"
storage = "local"

[service]
internal_port = 3000
autostop = false
min_machines = 1

[resources]
cpu_kind = "shared"
cpus = 2
memory_mb = 1024

[env]
NODE_ENV = "production"
```

```bash
innstance deploy \
  --secret TELEGRAM_BOT_TOKEN=@env:TELEGRAM_BOT_TOKEN \
  --secret OPENAI_API_KEY=@env:OPENAI_API_KEY \
  --env TELEGRAM_CHAT_ID=623508703
innstance machines push ./ --to /data/app --app my-bot --yes-replace
innstance machines exec --app my-bot -- sh -c "cd /data/app && npm install"
innstance machines exec --app my-bot -- sh -c "cd /data/app && setsid nohup node server.js --bind lan --port 3000 > /tmp/app.log 2>&1 < /dev/null &"
```

### Interactive setup (runner mode)
```bash
innstance init --app my-project --port 3000 --memory 1024 --storage local
innstance deploy
# Then use console for setup:
innstance machines console start --app my-project -- bash
innstance machines console input --app my-project $SID "git clone ... /data/app && cd /data/app && npm install; echo __DONE__"
# Poll output, then start the app in a detached tmux session
```

---

## Ready-made agents (`innstance agents`)

Separate from deploying your own code, Innstance hosts **ready-made AI agents**
from a catalog. One of these is not an app you write: it is an agent that
gets its own machine, its own storage and its own control panel, and talks
to its owner in a chat app — Telegram, Discord, and on hermes also
WhatsApp; each recipe names its own channels. You spawn it and
hand it over.

Use this when the user asks for "an AI assistant / a chatbot I can message"
rather than for a website or an API. Everything else in this document is
about `innstance deploy`, which is a different product surface.

### First: read what the catalog actually asks

```bash
innstance agents list            # names, one line each
innstance agents list --json     # THE source of truth for every flag name below
```

`--json` is what you read before spawning. It carries, per agent:

- `selections[].id` and each `options[].id` — the values for `--choose`
- `inputs[].key` — the values for `--set` / `--set-from-env`
- `inputs[].steps[]` — where the owner gets each key, in their own words
- `selections[].requires` — a question that only applies to another answer

Never hardcode these names from this document or from memory. Recipes gain
providers, models and channels without warning; the JSON is current and this
page is not.

### Names are global, and two refusals mean different things

An agent's name is its permanent address and is unique across the whole
platform, so `spawn` can refuse for two opposite reasons:

- `agent_name_yours` — you already have one by that name. Spawning again
  resumes that setup where it stopped; the refusal says what state it is in.
  Remove it instead with `innstance agents destroy <name> --yes-irreversible`.
- `agent_name_taken` — the name is not available for an agent. A page, an app
  and an agent each answer at `<name>.<our domain>`, so all three draw from one
  set of names: the holder may be another account, or one of THIS account's own
  pages or apps. Run `innstance status`, which lists both, before telling the user
  a stranger has it. Remove yours, or pick a different name.

Spawning in a loop or in CI, use a name that carries the run into it
(`ci-wa-<run-id>`) and destroy it in a step that always runs. A fixed name
collides with your own leftover from the previous run.

### Spawning, when the owner is present (default, preferred)

```bash
innstance agents list                       # what's spawnable today — hermes and openclaw, and growing
innstance agents spawn hermes --name my-assistant
innstance agents spawn openclaw --name my-claw
```

This prints a one-time setup link and waits. The owner opens it on any
device and pastes their own keys straight into encrypted storage.
OpenClaw is the larger of the two — if the plan's pool doesn't fit it,
`spawn` says so before anything starts, so nothing is half-created.

**Prefer this.** The keys are the owner's — their AI provider account, their
bot token, their bill. When you take the default path, you never hold them,
they never enter your context, and they cannot end up in a transcript or a
log. Send the link to the user and wait.

### Spawning unattended (no browser, no terminal)

When you are the key holder — the keys are already in your environment, or
the user handed them to you deliberately — spawn without a person present:

```bash
innstance agents spawn hermes --name my-assistant \
  --choose channel=telegram \
  --choose llm=openai \
  --choose openai-model=other \
  --set-from-env TELEGRAM_BOT_TOKEN \
  --set-from-env OPENAI_API_KEY \
  --set OPENAI_MODEL=gpt-5-mini
```

- `--choose <question>=<answer>` answers a setup question. Repeatable.
- `--set-from-env KEY` supplies a value by naming the environment variable
  holding it. **Prefer this for every secret**: a value passed with `--set`
  is visible to every process on the machine and lands in shell history.
- `--set KEY=value` supplies a value directly. Fine for non-secrets like a
  model name.
- `--extra KEY=value` sets an optional integration variable, when the agent
  offers an extras section. It needs a submission to ride along with, so use
  it alongside the answers above (or with `--type-here`); on the default
  browser path the owner sets extras in the form and the flag is refused
  rather than quietly dropped.

Any of `--choose` / `--set` / `--set-from-env` switches spawn to this path.
It never prompts and never needs a terminal.

**Refusals are complete.** If something is missing, the command names every
remaining key, its title and where the owner gets it — so you can fix it in
one more command rather than guessing. A wrong question name or a value for
a question that was not asked is rejected by name, at the terminal, before
anything is built.

`--type-here` is the third path: interactive prompts in this terminal. It
needs a real TTY and is for humans who prefer typing; do not use it.

### Linking WhatsApp

Only for agents whose recipe offers the WhatsApp channel — today hermes and
openclaw. An agent spawned without it has nothing to link, and the API says
so plainly rather than pretending a code is coming.

WhatsApp carries no key to paste — the owner links an account they already
have by scanning a code with their phone. That step needs a human with a
phone, but everything around it works from the terminal:

```bash
innstance agents whatsapp pair my-assistant     # prints a scannable QR, waits, switches the agent on
```

Codes expire every few seconds; the command draws fresh ones and starts a
new session by itself if one lapses, so leave it running while the phone is
found. On the phone: WhatsApp → Settings → Linked devices → Link a device.

A code that sits unchanged for a few minutes gets replaced automatically, and
the command says so ("getting a fresh one"). That is routine: a healthy session
was measured holding one code for sixty-six seconds while its socket was
replaced underneath, so an unchanged code proves nothing on its own.

If the command reaches its deadline it says no scan landed and names both
possibilities, because they cannot be told apart from outside: either nobody
scanned, or a scan did land and the session had already gone. If the owner says
they DID scan, restart the agent with `innstance agents reconfigure <name>` — which
keeps everything it remembers — and run the pair command again. Do NOT destroy
and respawn the agent for this, and do not report the spawn as failed.

Until a scan lands, a WhatsApp agent is up but not listening. That is not a
failure: `spawn` completes, status reaches `running`, and the verify result
says "WhatsApp isn't linked yet" as a warning. You can scan later, scan a
different number, or move the agent to another channel with `reconfigure`,
and it keeps everything it remembers either way.

What "up but not listening" means differs by recipe, and neither is a fault
to chase. Hermes keeps its gateway DOWN while WhatsApp is selected and
unpaired, so the scan is what starts it. OpenClaw runs normally with the
channel switched on and simply unlinked, and it answers nobody until the
scan says who its owner is — its allowlist is deliberately empty until then,
so an agent nobody has scanned is an agent nobody can talk to.

### After it is spawned

```bash
innstance agents status                    # all your agents
innstance agents status my-assistant       # one agent, with its verify result
innstance agents logs my-assistant         # its recent log, credentials redacted
innstance agents logs my-assistant --lines 500
```

**One line in that log looks like a break and is not.** Shortly after an agent
starts you will see:

```
[ws] unauthorized ... reason=password_mismatch
[ws] closed before connect ... code=1008 reason=unauthorized: gateway password mismatch
```

That is the platform's own checkup trying a WRONG password against the agent's
control panel and requiring it to be refused. The panel faces the internet and
its sign-in is the only thing guarding it, so the check proves the door is shut
by walking into it. A successful `health` line a few seconds earlier is the same
checkup getting in with the RIGHT password — seeing both, in that order, means
the panel is working correctly.

Do not report this as a fault, do not tell the owner to reset anything, and do
not rebuild the agent over it.

```bash
innstance agents reconfigure my-assistant  # change model, keys or channel
innstance agents panel my-assistant --private   # take the control panel off the web
innstance agents panel my-assistant --public    # put it back
innstance agents pull my-assistant              # download its memory as a backup
innstance agents destroy my-assistant --yes-irreversible
```

`agents pull` archives the agent's state (memory, conversations,
workspace) LIVE — the agent keeps running — and downloads it as a
tar.gz, SHA-256 verified. The download is METERED as outbound traffic,
exactly like `machines pull`: the exact size and the account's traffic
standing print first, nothing is downloaded or metered until approved,
and `--yes-egress` is the explicit non-interactive consent. Key material
is left out by the recipe, so the archive is safe to store; restoring
elsewhere means re-entering provider keys and re-pairing channels. Pull
a backup BEFORE `agents destroy` — destroy deletes the machine and
everything the agent remembers.

### A shell on the agent's machine

```bash
innstance agents ssh my-assistant                      # interactive shell
innstance agents ssh my-assistant -- docker ps         # run one command and exit
innstance agents ssh my-assistant -- docker exec agent sh -c 'ls /opt/data'
innstance agents ssh my-assistant --print-config >> ~/.ssh/config   # once
scp file.txt my-assistant.agent.ifhost:                          # then any ssh tool
innstance agents exec my-assistant -- docker ps                     # no ssh client needed
innstance agents exec my-assistant --in-agent -- openclaw config get agents.defaults.model
```

`agents exec` is the shape for you: no ssh client, no key, no terminal — the
command goes over the platform's own channel, runs as root on the machine
(`--in-agent`: inside the agent's container), and its output and exit
status come back. Captured output is limited to about 24 KB and one run
to ten minutes (`--timeout`, default 120 s); start anything longer
detached and poll, or use `agents ssh`, which streams without limit.

### An OpenClaw agent that thinks through Claude Code (`claude -p`)

OpenClaw can use Claude Code itself as its brain, signed in with the
owner's Claude subscription — nothing billed separately. It is a choice
of the `llm` question, so it is set up like any other provider:

```bash
# the owner runs this on THEIR computer, where Claude Code is signed in:
#   claude setup-token        → prints a long token once
export CLAUDE_CODE_OAUTH_TOKEN=...      # in your shell, never in argv
innstance agents spawn openclaw --name my-claw \
  --choose channel=telegram --choose llm=claude-code \
  --set CLAUDE_MODEL=claude-opus-5 \
  --set-from-env TELEGRAM_BOT_TOKEN --set-from-env TELEGRAM_ALLOWED_USERS \
  --set-from-env CLAUDE_CODE_OAUTH_TOKEN
```

The recipe installs Claude Code into the agent's own storage on first boot
(so it survives every restart and reconfigure), points the agent at the
`claude-cli` runtime for `anthropic/<model>`, and the token travels in the
agent's environment like any other key. The verify checkup then asks the
agent a real question through it. The token is the owner's — treat it as
you treat their password: it comes from their machine, and it is never
something you mint or type for them.

This is your own ssh client, so everything after `--` is a remote command
and its exit status comes back to you — the unattended path. Nothing on the
machine listens for it: your public key (made once, in `~/.impossible/ssh/`)
is accepted for sixty seconds per connection and the connection rides a
tunnel the platform opens, so there is no port to find, no key on the
machine to rotate, and the session is encrypted end to end by ssh. The
agent itself runs in a container called `agent`; `docker exec -it agent sh`
gets inside it, and its state lives on the machine under `/state`.

Needs the agent to be `running`, and an `ssh` binary where the CLI runs.
Whatever you change on the machine by hand is yours: the next
`reconfigure` rewrites the environment file and replaces the container,
and the verify checkup still reports on the result.

Spawn is not finished when the machine boots. The platform runs the recipe's
own verify probe — it asks the agent a real question and waits for a real
answer — and only then reports `running`. `spawn` already waits for that, so
its success means the agent genuinely replied, not merely that a machine
exists. The probe can also check the messaging gateway and public control
panel. `verify-failed` means a verification check failed; it does not identify
the cause. Read the report printed by spawn, or run `innstance agents status <name>`,
before changing credentials or restarting the agent. Follow the failed check's
recovery instructions.

### Traps

| Trap | What happens | What to do |
|------|--------------|------------|
| Spawning WhatsApp unattended | Setup completes, but the agent cannot hear anyone | WhatsApp is linked by scanning a code with a phone, so it cannot be finished headlessly. Everything around the scan does work from the terminal: `innstance agents whatsapp pair <name>` draws the code and waits. A human with the phone still has to scan it. |
| The agent is slow, or answered nothing | You cannot tell whether it is thinking, stuck, or never received the message | `innstance agents logs <agent>` reads its recent log with anything credential-shaped redacted. Measured 2026-08-20 on a healthy agent: a chat message through the control panel came back in ~3.5s, while the SAME agent on Telegram took 11-19s, and one message in five got no reply at all. So slowness on a messaging channel is not evidence of a broken agent, and "it never replied" is a real thing that happens — check the log before rebuilding anything. |
| Asking for the panel password | You will not find it, and you should not | The control panel's sign-in is provisioned automatically and we do not hand it over — a product that produces your password on demand teaches you it is not really yours. The owner asks their own agent in chat: "what is my dashboard password?" Do not try to retrieve it for them. If the agent cannot be asked (a WhatsApp agent has no chat until it is linked, and an agent whose key stopped working answers nothing), run `innstance agents panel <name> --reset-password`, or press "Give it a new password" on the agent's row in the dashboard. That replaces the password and shows you nothing: the agent restarts carrying the new one and the owner asks it as before. It is the way out of that loop, not a way to read a secret. |
| The panel refuses the first browser | "pairing required: device is not approved yet" | Only for agents whose panel asks each device for approval — `innstance agents status <agent>` says which those are, and most recipes do not. For those that do, this is expected exactly once: the approval cannot exist until a browser has knocked, so the first load is refused and the agent admits it a moment later. Wait a couple of seconds and reload. A second computer or phone needs `innstance agents panel <agent> --approve`. On a panel that does NOT ask for device approval, a refusal or a blank page is a real fault — do not wait it out. |
| Hunting for openclaw's panel username | There is one password field and no username anywhere | That agent's sign-in is a password alone — the dashboard and CLI both say so. Same flow otherwise: the owner asks their agent in chat. |
| Spawn sits on "installing" for minutes | Nothing is wrong: that step fetches and starts the agent, and it is the longest part of a spawn | Wait it out. The step after it ("checking your keys") is short. A spawn that has genuinely stalled stops moving between steps, and the dashboard says so rather than sitting on one. |
| One-shot question to openclaw over exec | `openclaw agent exec` refuses or hangs on a state lock | The running gateway owns the real state dir exclusively. Omit `--state-dir` (isolated temp state) — or for a pure "can it think" check, `openclaw infer model run --gateway --prompt "..."`. Never `--local`: the embedded path can't see models the gateway discovered and calls a healthy agent's model unknown. |
| Picking openclaw's model from a live list | The agent boots, then refuses every message with "Unknown model" | Model names resolve through the agent's own gateway. `openclaw models list --provider <id>` inside the agent shows what it accepts right now; a newer name from a provider's public list may not be there yet. |
| Guessing model names | The agent boots and then refuses every message | A model name is written verbatim into the agent's config. Use a name the provider really serves, from `innstance agents list --json`. |
| Assuming a free spawn is permanent | The agent disappears | An agent successfully spawned on Free carries a destruction timestamp. `spawn` prints the server's current destruction notice before setup starts — relay that notice. If the exact time matters, run `innstance agents status <name> --json` and read `expires_at`; never copy a duration into this skill. |
| Supplying two providers | The API rejects the whole submission | Answer the provider question once and supply only that provider's key. |

---

## Agent Decision Tree

**First fork: is the user asking for an app, or for an assistant?** A
website, API or bot they wrote is `innstance deploy`, below. "An AI I can
message" is a catalog agent — see *Ready-made agents* above, and do not
build one by hand.

```
innstance deploy (runner VM with a default 1 GB /data volume), then:
├── Simple web app        → --memory 256, transfer to /data/app, start the app
├── API with managed DB   → --memory 512, pass DB_URL via --env
├── Heavy/AI app          → --memory 1024+, --autostop=false, --min-machines 1
├── SQLite/file-cache app → keep state under /data and stay single-machine
└── Complex interactive setup → console session, drive the wizard
```

**Storage rule:** volumes are per-machine (one machine, one disk). Keep
shared state in a managed service: Supabase, Neon, Upstash, Turso.
Shared volumes are on the roadmap.

---

## Traps to Avoid

| Trap | Symptom | Fix |
|------|---------|-----|
| PORT mismatch | App boots but 502 errors | Set `[service] internal_port` to match what the app listens on |
| Low RAM | App killed silently (OOM) | Node.js needs 512MB+, AI/ML needs 1024MB+ |
| Autostop stops the VM | App worked, then hangs forever after idle (runner apps don't survive a stop) | `autostop = false` + `min_machines = 1` |
| Env vars in config files | Values lost on restart | Use `--env` or `[env]` in impossible.toml |
| Expecting `[build]` to run | App never starts — the section is ignored | Start via `machines exec` with `setsid nohup` |
| Expecting restart to relaunch the app | `/data` survives but the public URL fails | Reinstall anything missing, rerun the start command, and verify HTTP `200` |
| Bot killed by autostop | Bot stops responding after idle | `autostop = false` + `min_machines = 1` |
| Declaring success at deploy | Customer opens a dead page | Deploy is done ONLY when curl returns 200 (Rule 0b) |
| Secrets not in process env | App can't read API keys | Secrets ARE injected as env vars. Check logs, not exec |
| Debugging spiral | Agent spends 20 min probing | Check logs first. Fix config and redeploy. |

---

## Debugging Workflow

```bash
# 1. Get full app context
innstance describe --app my-app

# 2. Check recent errors
innstance machines logs --app my-app --level error --lines 20

# 3. Check if app is running
innstance machines --app my-app

# 4. If stopped, start it
innstance machines start --app my-app

# 5. Watch live logs
innstance machines logs --app my-app

# 6. Check one non-secret variable without dumping the process environment
innstance machines exec --app my-app -- sh -c 'test -n "$NODE_ENV" && echo NODE_ENV=set || echo NODE_ENV=unset'

# 7. If app won't start, check the deploy
innstance describe --app my-app --json | jq '.deployments[0]'
```

---

## Pricing

Prices, pool sizes and limits are NOT written here. They change, and a copy in
this file goes stale unnoticed: this section once understated a plan's RAM pool
for weeks after the catalog moved, and called a capped limit unlimited.

Read them live instead, from the source the biller itself uses:

```bash
curl --fail --silent --show-error --max-time 30 https://innstance.impossibuild.ai/billing/plans  # every plan, no auth needed
innstance status                                              # the signed-in account's plan and usage
curl --fail --silent --show-error --max-time 30 https://innstance.impossibuild.ai/llms.txt  # agent guide, pricing block rendered from the catalog
```

Quote the account's own plan from `innstance status`, never a remembered number.

Upgrade: `innstance billing subscribe <plan>` (or `innstance sub subscribe <plan>`)

---

## Global Flags

| Flag | Description |
|------|-------------|
| `--json` | Output structured JSON (available on all commands) |
| `--app <name>` | Override app name (on deploy, apply, describe, and all machines subcommands) |
| `--yes` | Skip confirmation prompts (on deploy and all machines subcommands) |
