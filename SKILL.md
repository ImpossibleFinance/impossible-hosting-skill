---
name: ifhost
description: Deploy applications to Impossible Hosting runner VMs. Use when Codex needs to provision an app with ifhost, translate project setup into runner commands, transfer source safely, start the process, or verify and troubleshoot the public deployment.
---

# ifhost — Deploy to Impossible Hosting

Provision an isolated runner VM and HTTPS URL, then install, transfer, start,
and verify the application explicitly. Use [RUNBOOK.md](RUNBOOK.md) for the
ordered deployment and recovery procedure.

## Agent Rules

### 0. Refresh the CLI and these instructions first, every session

The platform evolves quickly. Before ANY ifhost work, install the CLI if it is
missing; otherwise invoking it performs its signature-verified automatic update.
Then sync the latest skill bundle:

```bash
if ! command -v ifhost >/dev/null 2>&1; then
  installer="$(mktemp)"
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    --tlsv1.2 --connect-timeout 10 --max-time 60 --max-filesize 1048576 \
    https://host.impossibuild.ai/install -o "$installer" &&
    cat "$installer" && sh "$installer"
  rc=$?; rm -f "$installer"; [ "$rc" -eq 0 ] || exit "$rc"
fi
ifhost version
ifhost skill sync
```

On Windows, use the same download-inspect-execute boundary in PowerShell:

```powershell
if (-not (Get-Command ifhost -ErrorAction SilentlyContinue)) {
  $installer = Join-Path ([IO.Path]::GetTempPath()) "ifhost-install-$([guid]::NewGuid()).ps1"
  try {
    Invoke-WebRequest -Uri https://host.impossibuild.ai/install.ps1 `
      -MaximumRedirection 0 -TimeoutSec 60 -OutFile $installer
    Get-Content $installer
    & $installer
  } finally { Remove-Item $installer -ErrorAction SilentlyContinue }
}
ifhost version
ifhost skill sync
```

`skill sync` prints the authoritative cached `SKILL.md` and `RUNBOOK.md`
paths. If this file was loaded from another path, read those refreshed files
now and continue from them. If the sync fails (network, outage), keep working
from the copy you already have and mention the failed refresh to the user — a
slightly stale bundle is safe; guessed instructions are not.

Set `IFHOST_AUTO_UPDATE=0` only when the user explicitly needs a pinned CLI.
`ifhost update` remains available for an explicit update.

### 0b. Deploy ≠ live — never declare success without a 200

`ifhost deploy` succeeding means the VM is provisioned, NOTHING more. The
VM boots as a bare shell with no app process; the CLI prints "Runner VM
ready — your app is NOT live yet". You are done only when ALL of:

1. You installed and STARTED the app (survives the exec session:
   `ifhost machines exec --app X -- sh -c "setsid nohup <cmd> </dev/null > /tmp/app.log 2>&1 &"`)
2. `curl -sS -o /dev/null -w '%{http_code}' --max-time 30 https://<app>.host.impossi.build/`
   printed `200` (or the app's health endpoint did)

Until then, NEVER tell the user "deployed", "live", or "running" — a
declared-but-dead deployment is the single worst outcome for a customer.
If you cannot get a 200, report exactly what state things are in.

**No Dockerfile or build deploys.** A `[build]` section in impossible.toml
(dockerfile or cmd) is IGNORED — the platform never builds images and never
runs a configured start command. Deploys boot the bare runner VM; you drive
setup and startup yourself as above. The CLI warns when it sees `[build]`.
Never CREATE a Dockerfile for an ifhost deploy — it will not be built. But
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

### 1. Understand the project BEFORE deploying

**CRITICAL:** Before running `ifhost init` or `ifhost deploy`, complete this checklist:

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
  `KEY=@file:/run/secrets/key`, or `KEY=@stdin` to ifhost.
- Never guess credentials or place them in `impossible.toml`, a command
  argument, a transcript, or a source archive.
- Model preferences (which AI model to use, if applicable)

**Step E — Present the full deployment plan for final approval.**
Show the impossible.toml you'll generate and the exact deploy command with all flags.
Let the user confirm or correct before proceeding.

Only after the user approves should you run `ifhost init` and `ifhost deploy`.
If the user says not to modify the source repository, run both commands from
a temporary workspace: `init` creates `impossible.toml`, and `deploy` may
update it with the resolved app name or port.

### 2. Tell the user what's happening (observability)

**HARD RULE: always start any multi-step task with a step list and ETA.** No exceptions,
no matter how short the task seems. Users looking at a blank chat don't know if you're
thinking, working, or stuck. The step list is the contract — you'll do these N things,
it'll take ~X minutes.

Before running ANY ifhost command that takes more than a few seconds, print:

```
Deploying my-app to ifhost — plan:
  Step 1/4: Read project docs                          (~10s)
  Step 2/4: Configure impossible.toml                  (~5s)
  Step 3/4: Deploy                                     (~1-2 min)
  Step 4/4: Verify the app is live                     (~10s)

Total ETA: ~2-3 minutes
```

Then announce each step AS you start it: "Step 3/4 — deploying (1-2 min)…"

Even for a 2-step task ("install ifhost then login"), say so:
```
Setting up ifhost — plan:
  Step 1/2: Install CLI                            (~15s)
  Step 2/2: Login via Google                       (~30s, browser opens)
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

A fresh deploy is NOT "ready to serve" the moment `ifhost deploy` returns. Expect, on top of the control-plane deploy (10-60s):

- **Image pull to the VM** (30s-2min, depending on image size + region network)
- **Volume init / encrypt / format** (5-15s, one-time per volume)
- **App cold start** (highly variable)
  - Trivial web app (echo bot, static site): **1-5s**
  - Node/Python web service: **5-30s**
  - Agent frameworks with plugins (openclaw, hermes, similar): **5-15 min** — they install runtime deps, fetch model pricing, initialize browser/voice/channel subsystems, call out to `api.telegram.org`/`api.openai.com` which can themselves stall. Not a bug; that's their actual startup cost on a cold volume.
- **First-message cold-start for LLM-backed bots**: add another 30s-5min the very first time a user messages the bot — the agent's identity/memory scaffolding runs on-demand.

Implications for you as the agent driving the deploy:

- A single "HTTP probe failed after 60s" is **not sufficient evidence** to conclude the deploy is broken. Only conclude broken if the logs show crash signatures (`Exec format error`, `max restart count`, `Main child exited with code: 1`, OOM kill, port-mismatch refused-connection that persists >3 min after the app should have started).
- When the probe comes back "no response yet" for a known-slow stack (anything with "plugin" or "agent" or "gateway" in its name), print a friendly **"still initializing, this can take up to 15 min for <stack>; watch with `ifhost machines logs --app X --follow`"** — not a failure.
- The `ifhost deploy` command distinguishes "still starting" (exit 0, warn) from "broken" (exit 1, error). Trust its exit code; don't treat every warning as a deploy failure.
- Ask the user to wait 10-15 min before concluding "the bot doesn't work" on the first message. Subsequent messages are fast.
- Retry loops inside the app (e.g. openclaw's setWebhook call to Telegram) can compound the wait. A single outbound flake from the host region can reset app init by 30s. That's an app-level issue, not ours — document it, don't treat it as our deploy being broken.

### 2a. STOP polling once /healthz returns 200

**Common time-waster:** agents repeatedly poll `ifhost machines logs` and `Monitor`
waiting for specific app-internal log strings ("gateway ready", "channel connected",
"polling started"). This wastes 5-20 minutes per deploy.

**Hard rule:** the deploy is DONE when `curl --fail --show-error --max-time 30 https://<app>.host.impossi.build/healthz` returns 200
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

Before running any ifhost command, check its help text:

```bash
ifhost deploy --help
ifhost machines logs --help
```

Use the freshly updated CLI help to confirm command syntax and available
flags. Do not infer runner lifecycle from generic examples in help output:
`[build]` remains ignored, and applications must be started explicitly.

## Install / Update

```bash
installer="$(mktemp)"
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --tlsv1.2 --connect-timeout 10 --max-time 60 --max-filesize 1048576 \
  https://host.impossibuild.ai/install -o "$installer"
cat "$installer"
sh "$installer"
rm -f "$installer"
```

Run this at the start of EVERY session, not just the first (Rule 0) — it
updates an existing binary in place. It downloads the correct binary for the
current OS/architecture (macOS/Linux, amd64/arm64)
and installs it to `~/.local/bin/ifhost`. If `~/.local/bin` is not in PATH, add it:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Verify installation:

```bash
ifhost --help
```

If the installer fails, do not bypass its signature check with a direct
archive pipe. Follow the signed manual-download procedure in the
[`impossible-hosting-cli` repository](https://github.com/ImpossibleFinance/impossible-hosting-cli#manual-download).

## Quick Start

```bash
ifhost login                                          # Browser device authorization (one-time)
ifhost init --app my-app --port 3000 --memory 512 --storage local
ifhost deploy                                         # Provision the runner
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
ifhost deploy --secret KEY=@env:KEY --yes
ifhost machines console start --app <app> -- bash
# download and inspect upstream installers before executing them, then configure
# and launch the daemon in detached tmux inside /data
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
ifhost machines install --app my-site python3
printf '%s\n' 'state/data.db' > .ifhost-state-paths  # only when the app owns this runtime path
ifhost machines push ./ --to /data/app --app my-site --yes-replace
ifhost machines exec --app my-site -- sh -c "setsid nohup python3 -m http.server 8080 --bind 0.0.0.0 --directory /data/app > /tmp/app.log 2>&1 < /dev/null &"
curl -sS -o /dev/null -w '%{http_code}' --max-time 30 https://my-site.host.impossi.build/   # must print 200
```

**Gotchas that burn tokens on runner deploys (learned the hard way):**

- **Front-load system deps before running the project's install script.** The runner base image is minimal — only `tmux` and `ca-certificates` are preinstalled; no `curl`, `xz-utils`, `procps`, or `git` out of the box. Use the detached, verified installer:
  ```
  ifhost machines install --app X curl xz-utils procps git
  ```
  Discovering each missing tool one failure at a time wastes 30s+ per round trip.
- **Set `HOME` explicitly before running install scripts.** Many installers use `$HOME/.local/bin` etc; if `HOME` is unset the script installs to `//.local/bin` (double-slash) or bails. `export HOME=/root` before running a downloaded and inspected installer.
- **tmux `new-session "<cmd>"` does NOT inherit exported PATH.** The spawned shell starts fresh. Use absolute paths or set an explicit administrative `PATH` inside `/bin/sh`; do not assume `bash -lc` exists.
- **Drive interactive wizards, don't bypass them.** If a project ships a `setup` / `init` / `configure` wizard, run it and drive it via console. Killing it with Ctrl+C and reverse-engineering the config layout burns 10x more tokens than just answering arrow-key prompts.
- **Read the project's provider/config source before guessing IDs.** Hermes's `auth add` rejects bare `"openai"` because their `providers.py` routes that to OpenRouter; valid options are listed only in the wizard. `grep -n 'provider' /path/to/providers.py` takes 5 seconds; guessing 6 wrong IDs takes 5 minutes.
- **PID files may be JSON, not integers.** Hermes writes `{"pid": 9249, "kind": "hermes-gateway", ...}` to `gateway.pid`. `kill $(cat pidfile)` fails with "arguments must be process or job IDs". Parse with `grep -oE '"pid":\s*[0-9]+' file | grep -oE '[0-9]+'`.

---

## Command Reference

### ifhost login

Authenticate through browser device authorization. The CLI prints a short
sign-in code, opens the approval page, and polls until you approve it. The
approval page can be opened on any browser-capable device; it does not need a
browser or loopback listener on the machine running `ifhost`. Sign in through
the providers configured in the dashboard, verify the displayed machine, and
approve it. Credentials are stored at `~/.impossible/credentials.json`. If
already logged in, the account picker still lets you switch or add an account.

| Flag | Description |
|------|-------------|
| `--token -` | Read an API token from stdin; literal values are refused so they cannot leak through argv or shell history |
| `--from-file <path>` | Read the token from a local secret file (`-` = stdin) — avoids shell history and `ps` exposure |
| `--switch` | Switch between existing accounts |

### ifhost logout

Remove stored credentials.

### ifhost status

Overview of all projects with machine IDs. **Run this first** to understand what's deployed.

```
Logged in as: user@example.com
Plan:         pro
CLI:          20260421-123154

Projects (2):

  my-api
    URL:     https://my-api.host.impossi.build
    Status:  deployed   Region: iad
    Running (1):
      e784160df242e8

  my-site
    URL:     https://my-site.host.impossi.build
    Status:  deployed   Region: iad
    Running (1):
      d8930e1c063d58
```

Use machine IDs from this output with `--machine` on exec/console commands.

---

### ifhost init

Generate `impossible.toml` — required before `ifhost deploy`.

```bash
ifhost init --app <name> --port <port> --memory <mb> [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--app` | (required) | App name — becomes `<name>.host.impossi.build` |
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

### ifhost deploy

Deploy the app. Requires `impossible.toml`.

```bash
ifhost deploy [flags]
```

| Flag | Description |
|------|-------------|
| `--env KEY=VALUE` | Set env var (repeatable). Merged with [env] in toml. |
| `--secret KEY=@env:NAME` | Set a secret by protected reference. Also accepts `KEY=@file:PATH` or one `KEY=@stdin`; literal values are refused |
| `--port N` | Override container port |
| `--region <code>` | Region (e.g. iad, sin, lhr). See `ifhost regions`. |
| `--storage local` | Explicitly provision a `/data` volume on first deploy. With no storage flag or declared volumes, runner deploys currently provision a 1 GB `/data` volume automatically. |
| `--app <name>` | Override app name from toml |
| `--yes` | Skip confirmation prompts |
| `--json` | Output structured JSON |
| `--recreate-app` | Silences the advisory shown when impossible.toml names an app the server has no record of. Deploy proceeds either way. |

Deploy boots a generic Debian runner VM without building the application.
Drive setup via `exec`/`write`/`console` after deploy.

**After deploy:** Prints the public URL (e.g.,
`https://my-app.host.impossi.build`). The application is not live until you
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
deploy** after `ifhost init` (the toml names the app before it exists), and it
also appears if an app was previously destroyed. The CLI cannot tell those
apart, so it tells you rather than guessing.

Nothing to do in the common case. Only if the app genuinely existed before and
had a custom domain, tell the user its DNS now points at a released address and
check with `ifhost machines domains list --app <name>`.

`--recreate-app` only silences this note. It does not change what happens.

---

### ifhost describe --app \<name\>

Full app context in one call. Aggregates: app status, machines, env vars, secrets, domains, and recent deploys.

```bash
ifhost describe --app my-app         # Human-readable summary
ifhost describe --app my-app --json  # Structured JSON (for programmatic use)
```

Output includes:
- URL, status, region
- Machine IDs, states, specs
- Environment variables (values truncated at 30 chars)
- Secret key names (values hidden)
- Custom domains with TLS status
- Last 5 deployments with status and timestamps

---

### ifhost machines

All app-specific commands live under `machines`. Requires `--app <name>` or an `impossible.toml` in the current directory.

#### List machines

```bash
ifhost machines --app my-app
```

Shows machines grouped by state with IDs for targeting.

#### Start / Stop / Restart

```bash
ifhost machines start --app my-app
ifhost machines stop --app my-app       # No cost while stopped
ifhost machines restart --app my-app
```

Apps run on a single machine. Multi-machine scaling is on the roadmap.
`restart` does not relaunch a process previously started with `setsid` or
`nohup`; run the start command again and repeat the public HTTP check.

---

### ifhost machines logs

Stream or tail runtime logs from your app. **Default mode is live streaming (tail -f)** — runs indefinitely until Ctrl+C.

```bash
ifhost machines logs --app my-app                      # Live stream (tail -f)
ifhost machines logs --app my-app --since 1h           # Last hour, then exit
ifhost machines logs --app my-app --lines 20           # Last 20 lines, then exit
ifhost machines logs --app my-app --grep "ERROR"       # Only lines containing ERROR
ifhost machines logs --app my-app --level error        # Only error/fatal/panic lines
ifhost machines logs --app my-app --json               # Structured JSON per line
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

### ifhost machines exec

Run a one-off command inside a running machine. For commands that finish without stdin.

```bash
ifhost machines exec --app my-app -- ls /data
ifhost machines exec --app my-app -- sh -c 'test -n "$NODE_ENV" && echo NODE_ENV=set || echo NODE_ENV=unset'
ifhost machines exec --app my-app --machine e784160df242e8 -- cat /var/log/app.log
```

Timeout: 10 minutes (enforced server-side, cannot be raised). For longer-running
commands use the fire-and-poll pattern — launch via `nohup ... &` in one exec, then
poll completion in later execs — or use `console`. Use `console` for anything
interactive (prompts, wizards, REPLs).

---

### ifhost machines console

Interactive tmux-backed console for commands that need stdin or take a long time.

#### Start a session

```bash
ifhost machines console start --app my-app -- bash
```

Returns a `session-id` (e.g., `ifhost-01abc`).

#### Send input / Read output / End session

```bash
ifhost machines console input --app my-app <session-id> "npm install"
ifhost machines console input --app my-app <session-id> --key Enter
ifhost machines console output --app my-app <session-id> --lines 100
ifhost machines console end --app my-app <session-id>
```

---

### ifhost machines env / secrets

**Important:** `env set` and `secrets set` do NOT restart the machine by
default. Configure them before starting the app when possible. If you pass
`--restart` or run `machines restart`, start the application again afterward
and repeat the public HTTP check.
Replacing existing values non-interactively requires `--yes-replace`.

```bash
ifhost machines env set KEY=VALUE --app my-app              # Set (no restart)
ifhost machines env set KEY=VALUE --restart --app my-app    # Set + restart immediately
ifhost machines env list --app my-app
ifhost machines env rm KEY --app my-app                     # Remove env var
ifhost machines secrets set API_KEY=@env:API_KEY --app my-app
ifhost machines secrets set API_KEY=@file:/run/secrets/api-key --app my-app
printf '%s' "$API_KEY" | ifhost machines secrets set API_KEY=@stdin --app my-app
ifhost machines secrets list --app my-app                   # Shows key names only
ifhost machines secrets rm KEY --app my-app                 # Remove secret
```

### ifhost machines volumes

```bash
ifhost machines volumes list --app my-app
ifhost machines volumes create my-data --size 3 --mount /data --app my-app
ifhost machines volumes extend my-data --to 10 --app my-app   # Grow only, cannot shrink
ifhost machines volumes rm my-data --app my-app --yes
```

**Volumes are per-machine** (one machine, one disk). Shared volumes are on
the roadmap; for shared state today use a managed database.

### ifhost machines domains

```bash
ifhost machines domains add myapp.com --app my-app
ifhost machines domains check myapp.com --app my-app
ifhost machines domains list --app my-app
ifhost machines domains rm myapp.com --app my-app       # Remove custom domain
```

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

### ifhost machines write / push

```bash
ifhost machines write <local-file> --to <remote-path> --app my-app                  # Write a single file
ifhost machines write <local-file> --to <remote-path> --machine <id> --app my-app   # Target specific machine
ifhost machines push <local-dir> --to <remote-dir> --app my-app                     # Push a directory tree
```

`write` caps each file at 10 MiB. `push` has no arbitrary total archive cap.
Both use verified 8 MiB raw chunks, resume from the last acknowledged chunk,
and verify the complete file/archive before changing the destination. `write`
accepts `--machine`; `push` does not.

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

### ifhost machines wait-for

Block until a substring appears in a file inside the VM. Useful for waiting on app readiness.

```bash
ifhost machines wait-for --file /var/log/app.log --match "listening on" --app my-app
ifhost machines wait-for --file /data/startup.log --match "ready" --timeout 2m --app my-app
```

| Flag | Default | Description |
|------|---------|-------------|
| `--file` | (required) | Absolute path inside the VM to tail |
| `--match` | (required) | Substring to wait for |
| `--timeout` | 5m | Timeout (e.g. 60s, 2m) |

### ifhost machines destroy

```bash
ifhost machines destroy --yes-irreversible --app my-app                # Delete entire app + resources
ifhost machines destroy --yes-irreversible <machine-id> --app my-app   # Delete single machine
```

### ifhost apply

Push current config (memory, cpus, env, secrets, services) to existing machines without redeploying.

```bash
ifhost apply --app my-app
```

### ifhost tokens

```bash
ifhost tokens create --name "ci-bot"     # Create a new API token (default name: "cli")
ifhost tokens list                       # List all API tokens
ifhost tokens revoke <token-id>          # Revoke a token
```

Use tokens for CI pipelines or agent auth without putting the credential in an
argument:

```bash
printf '%s' "$IFHOST_TOKEN" | ifhost login --token -
ifhost login --from-file /run/secrets/ifhost-token
```

For application secrets, pass a source reference to `deploy --secret` or
`machines secrets set`: `KEY=@env:NAME`, `KEY=@file:PATH`, or (for one secret
per command) `KEY=@stdin`. Literal secret values are refused. Only the resolved
value is sent to the platform; local files stay local.

### ifhost auth

```bash
ifhost auth bind-wallet <address>        # Bind an EVM wallet for USDC top-ups (polls for verification)
ifhost auth wallets                      # List bound wallets (pending + verified)
ifhost auth unbind-wallet <address>      # Remove a wallet binding
```

### ifhost regions

List available deployment regions.

### ifhost version / update

```bash
ifhost version                           # Show CLI version and check for updates
ifhost update                            # Update CLI to the latest version
```

### ifhost billing (alias: sub)

```bash
ifhost billing status                     # Current subscription status
ifhost billing subscribe hobby            # Subscribe to a plan (hobby, pro, team)
ifhost billing subscribe --plan pro --pay crypto   # Specify payment method
ifhost billing cancel                     # Cancel subscription
ifhost billing invoices                   # Billing history
ifhost billing plan                       # Show current plan and usage
ifhost billing alert set --max 20         # Set spend alert at $20
ifhost billing alert show                 # Show current alert
ifhost billing alert off                  # Disable spend alert
ifhost billing usage                      # Month-to-date traffic per app/site
ifhost billing topup-traffic 100          # Buy traffic credit (USDC)
```

### Traffic: seeing it, and paying before it bites

Every plan includes a monthly traffic allowance — read the account's own from
`ifhost status`, never from memory. It is an **origin** allowance, and apps and
published sites draw on the **same pool**. Past it, apps and sites serve a 429 limit
page instead of content — the site stays up, the content does not.

Check before a launch you expect to spike, not after:

```bash
ifhost status                             # allowance, used, and any credit
ifhost billing usage                      # month-to-date, per app and site
```

If they expect heavy traffic, buy credit ahead of time; unused credit never
expires. The rate, the step size and the minimum are printed by the command
itself — run its help rather than quoting a price:

```bash
ifhost billing topup-traffic --help       # current rate, minimum, and step size
export IFHOST_TOPUP_SIGNING_KEY=<hex private key of the paying wallet>
ifhost billing topup-traffic <GB>         # cost is quoted before it charges
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
  `ifhost status` to see which limit was hit before recommending a purchase.

`subscribe` opens a hosted checkout page (pick card or crypto there). Card
payments are coming soon; crypto (USDC) works today. `--pay crypto` is a
compatibility spelling that still lands on the same hosted checkout.

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
ifhost deploy --secret API_KEY=@env:API_KEY --secret BOT_TOKEN=@file:/run/secrets/bot-token
```

---

## Common Deployment Patterns

### Node.js / Python API
```bash
ifhost init --app my-api --port 3000 --memory 512 --storage local
ifhost deploy --env DATABASE_URL=postgres://...
ifhost machines install --app my-api curl git nodejs npm
ifhost machines push ./ --to /data/app --app my-api --yes-replace
ifhost machines exec --app my-api -- sh -c "cd /data/app && npm install"
ifhost machines exec --app my-api -- sh -c "cd /data/app && setsid nohup node server.js </dev/null > /tmp/app.log 2>&1 &"
curl -sS -o /dev/null -w '%{http_code}' --max-time 30 https://my-api.host.impossi.build/   # must print 200
```

### Heavy app (AI agent, ML model, slow boot)
```bash
ifhost init --app my-agent --port 3000 --memory 1024 --cpus 2 --autostop=false --min-machines 1 --storage local
ifhost deploy --secret OPENAI_API_KEY=@env:OPENAI_API_KEY
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
ifhost deploy \
  --secret TELEGRAM_BOT_TOKEN=@env:TELEGRAM_BOT_TOKEN \
  --secret OPENAI_API_KEY=@env:OPENAI_API_KEY \
  --env TELEGRAM_CHAT_ID=623508703
ifhost machines push ./ --to /data/app --app my-bot --yes-replace
ifhost machines exec --app my-bot -- sh -c "cd /data/app && npm install"
ifhost machines exec --app my-bot -- sh -c "cd /data/app && setsid nohup node server.js --bind lan --port 3000 > /tmp/app.log 2>&1 < /dev/null &"
```

### Interactive setup (runner mode)
```bash
ifhost init --app my-project --port 3000 --memory 1024 --storage local
ifhost deploy
# Then use console for setup:
ifhost machines console start --app my-project -- bash
ifhost machines console input --app my-project $SID "git clone ... /data/app && cd /data/app && npm install; echo __DONE__"
# Poll output, then start the app in a detached tmux session
```

---

## Ready-made agents (`ifhost agents`)

Separate from deploying your own code, ifhost hosts **ready-made AI agents**
from a catalog. One of these is not an app you write: it is an agent that
gets its own machine, its own storage and its own control panel, and talks
to its owner in a chat app — Telegram, Discord, and on hermes also
WhatsApp; each recipe names its own channels. You spawn it and
hand it over.

Use this when the user asks for "an AI assistant / a chatbot I can message"
rather than for a website or an API. Everything else in this document is
about `ifhost deploy`, which is a different product surface.

### First: read what the catalog actually asks

```bash
ifhost agents list            # names, one line each
ifhost agents list --json     # THE source of truth for every flag name below
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
  Remove it instead with `ifhost agents destroy <name> --yes-irreversible`.
- `agent_name_taken` — the name belongs to another account. Nothing you can
  do but pick a different one.

Spawning in a loop or in CI, use a name that carries the run into it
(`ci-wa-<run-id>`) and destroy it in a step that always runs. A fixed name
collides with your own leftover from the previous run.

### Spawning, when the owner is present (default, preferred)

```bash
ifhost agents list                       # what's spawnable today — hermes and openclaw, and growing
ifhost agents spawn hermes --name my-assistant
ifhost agents spawn openclaw --name my-claw
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
ifhost agents spawn hermes --name my-assistant \
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
ifhost agents whatsapp pair my-assistant     # prints a scannable QR, waits, switches the agent on
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
they DID scan, restart the agent with `ifhost agents reconfigure <name>` — which
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
ifhost agents status                    # all your agents
ifhost agents status my-assistant       # one agent, with its verify result
ifhost agents logs my-assistant         # its recent log, credentials redacted
ifhost agents logs my-assistant --lines 500

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
ifhost agents reconfigure my-assistant  # change model, keys or channel
ifhost agents panel my-assistant --private   # take the control panel off the web
ifhost agents panel my-assistant --public    # put it back
ifhost agents destroy my-assistant --yes-irreversible
```

Spawn is not finished when the machine boots. The platform runs the recipe's
own verify probe — it asks the agent a real question and waits for a real
answer — and only then reports `running`. `spawn` already waits for that, so
its success means the agent genuinely replied, not merely that a machine
exists. Treat `verify-failed` as "a key was rejected", not as a crash.

### Traps

| Trap | What happens | What to do |
|------|--------------|------------|
| Spawning WhatsApp unattended | Setup completes, but the agent cannot hear anyone | WhatsApp is linked by scanning a code with a phone, so it cannot be finished headlessly. Everything around the scan does work from the terminal: `ifhost agents whatsapp pair <name>` draws the code and waits. A human with the phone still has to scan it. |
| The agent is slow, or answered nothing | You cannot tell whether it is thinking, stuck, or never received the message | `ifhost agents logs <agent>` reads its recent log with anything credential-shaped redacted. Measured 2026-08-20 on a healthy agent: a chat message through the control panel came back in ~3.5s, while the SAME agent on Telegram took 11-19s, and one message in five got no reply at all. So slowness on a messaging channel is not evidence of a broken agent, and "it never replied" is a real thing that happens — check the log before rebuilding anything. |
| Asking for the panel password | You will not find it, and you should not | The control panel's sign-in is provisioned automatically and we do not hand it over — a product that produces your password on demand teaches you it is not really yours. The owner asks their own agent in chat: "what is my dashboard password?" Do not try to retrieve it for them. If the agent cannot be asked (a WhatsApp agent has no chat until it is linked, and an agent whose key stopped working answers nothing), run `ifhost agents panel <name> --reset-password`, or press "Give it a new password" on the agent's row in the dashboard. That replaces the password and shows you nothing: the agent restarts carrying the new one and the owner asks it as before. It is the way out of that loop, not a way to read a secret. |
| The panel refuses the first browser | "pairing required: device is not approved yet" | Only for agents whose panel asks each device for approval — `ifhost agents status <agent>` says which those are, and most recipes do not. For those that do, this is expected exactly once: the approval cannot exist until a browser has knocked, so the first load is refused and the agent admits it a moment later. Wait a couple of seconds and reload. A second computer or phone needs `ifhost agents panel <agent> --approve`. On a panel that does NOT ask for device approval, a refusal or a blank page is a real fault — do not wait it out. |
| Hunting for openclaw's panel username | There is one password field and no username anywhere | That agent's sign-in is a password alone — the dashboard and CLI both say so. Same flow otherwise: the owner asks their agent in chat. |
| Spawn sits on "installing" for minutes | Nothing is wrong: that step fetches and starts the agent, and it is the longest part of a spawn | Wait it out. The step after it ("checking your keys") is short. A spawn that has genuinely stalled stops moving between steps, and the dashboard says so rather than sitting on one. |
| One-shot question to openclaw over exec | `openclaw agent exec` refuses or hangs on a state lock | The running gateway owns the real state dir exclusively. Omit `--state-dir` (isolated temp state) — or for a pure "can it think" check, `openclaw infer model run --gateway --prompt "..."`. Never `--local`: the embedded path can't see models the gateway discovered and calls a healthy agent's model unknown. |
| Picking openclaw's model from a live list | The agent boots, then refuses every message with "Unknown model" | Model names resolve through the agent's own gateway. `openclaw models list --provider <id>` inside the agent shows what it accepts right now; a newer name from a provider's public list may not be there yet. |
| Guessing model names | The agent boots and then refuses every message | A model name is written verbatim into the agent's config. Use a name the provider really serves, from `ifhost agents list --json`. |
| Assuming a free spawn is permanent | The agent disappears | An agent successfully spawned on Free carries a destruction timestamp. `spawn` prints the server's current destruction notice before setup starts — relay that notice. If the exact time matters, run `ifhost agents status <name> --json` and read `expires_at`; never copy a duration into this skill. |
| Supplying two providers | The API rejects the whole submission | Answer the provider question once and supply only that provider's key. |

---

## Agent Decision Tree

**First fork: is the user asking for an app, or for an assistant?** A
website, API or bot they wrote is `ifhost deploy`, below. "An AI I can
message" is a catalog agent — see *Ready-made agents* above, and do not
build one by hand.

```
ifhost deploy (runner VM with a default 1 GB /data volume), then:
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
ifhost describe --app my-app

# 2. Check recent errors
ifhost machines logs --app my-app --level error --lines 20

# 3. Check if app is running
ifhost machines --app my-app

# 4. If stopped, start it
ifhost machines start --app my-app

# 5. Watch live logs
ifhost machines logs --app my-app

# 6. Check one non-secret variable without dumping the process environment
ifhost machines exec --app my-app -- sh -c 'test -n "$NODE_ENV" && echo NODE_ENV=set || echo NODE_ENV=unset'

# 7. If app won't start, check the deploy
ifhost describe --app my-app --json | jq '.deployments[0]'
```

---

## Pricing

Prices, pool sizes and limits are NOT written here. They change, and a copy in
this file goes stale unnoticed: this section once understated a plan's RAM pool
for weeks after the catalog moved, and called a capped limit unlimited.

Read them live instead, from the source the biller itself uses:

```bash
curl --fail --silent --show-error --max-time 30 https://host.impossibuild.ai/billing/plans  # every plan, no auth needed
ifhost status                                              # the signed-in account's plan and usage
curl --fail --silent --show-error --max-time 30 https://host.impossibuild.ai/llms.txt  # agent guide, pricing block rendered from the catalog
```

Quote the account's own plan from `ifhost status`, never a remembered number.

Upgrade: `ifhost billing subscribe <plan>` (or `ifhost sub subscribe <plan>`)

---

## Global Flags

| Flag | Description |
|------|-------------|
| `--json` | Output structured JSON (available on all commands) |
| `--app <name>` | Override app name (on deploy, apply, describe, and all machines subcommands) |
| `--yes` | Skip confirmation prompts (on deploy and all machines subcommands) |
