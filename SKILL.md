---
name: ifhost
description: Deploy any Dockerized app to Impossible Hosting with one command
---

# ifhost — Deploy to Impossible Hosting

Deploy any Dockerized app to the cloud with one command. Each app gets its own isolated VM, HTTPS URL, object storage, and optional auto-scaling.

## Agent Rules

### 1. Understand the project BEFORE deploying

**CRITICAL:** Before running `ifhost init` or `ifhost deploy`, complete this checklist:

**Step A — Read the docs:**
- README.md, INSTALL.md, docs/install/ folder, or any setup guide
- **Look for a published Docker image** (ghcr.io, docker.io, quay.io references).
  If one exists, use `ifhost deploy --image <ref>` — skips the build entirely (~30s).
- docker-compose.yml (shows ports, volumes, env vars, startup commands, image refs)
- .env.example (lists ALL required env vars with descriptions)
- Dockerfile (shows exposed port, build steps, CMD, HEALTHCHECK)
- Any config file templates (config.example.json, etc.)

**Step B — Fill out this mental checklist:**
```
Port:          ___  (check Dockerfile EXPOSE, HEALTHCHECK, docker-compose ports, or app docs.
                     If no EXPOSE in Dockerfile, check docker-compose.yml or app --help.)
RAM:           ___  (512MB for small apps, 1024MB+ for Node/Python, 2048MB+ if build is heavy)
CPUs:          ___  (1 for simple, 2+ for AI/heavy compute)
Autostop:      ___  (false for bots, long-polling services, or apps that take >60s to boot)
Env vars:      ___  (list every KEY=VALUE the app needs)
Secrets:       ___  (API keys, tokens — ask the user, never guess)
Startup cmd:   ___  (setup before serving: config generation, migrations, --bind lan)
Bind address:  ___  (many apps default to localhost — must bind to 0.0.0.0 or use --bind lan)
Storage:       ___  (does the app write config/data to disk? → storage = "local")
Config files:  ___  (does the app need a JSON/YAML config file written before it starts?)
.dockerignore: ___  (does it exist? If not, create one excluding .git, node_modules, etc.
                     Without it, source upload may exceed the 30MB remote build limit.)
```

**Step C — Ask the user for anything missing:**
- API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
- Bot tokens (TELEGRAM_BOT_TOKEN, DISCORD_BOT_TOKEN, etc.)
- Database URLs
- Any credentials you can't find in the docs
- Model preferences (which AI model to use, if applicable)

**Step D — Present your deployment plan to the user BEFORE running any commands.**
Show the impossible.toml you'll generate and the exact deploy command with all flags.
Let the user confirm or correct before proceeding.

Only after the user approves should you run `ifhost init` and `ifhost deploy`.

### 2. Tell the user what's happening

Before starting, outline the steps and estimated time so the user knows what to expect:

```
Deploying my-app to ifhost:
  1. Read project docs and Dockerfile        (~10s)
  2. Configure impossible.toml               (~5s)
  3. Build and deploy                         (~1-3 min)
  4. Verify the app is live                   (~10s)

Estimated total: ~2-4 minutes
```

Update the user at each step. If something takes longer than expected (e.g., build is slow), say so. Never go silent for more than 30 seconds during a deploy.

### 2a. STOP polling once /healthz returns 200

**Common time-waster:** agents repeatedly poll `ifhost machines logs` and `Monitor`
waiting for specific app-internal log strings ("gateway ready", "channel connected",
"polling started"). This wastes 5-20 minutes per deploy.

**Hard rule:** the deploy is DONE when `curl https://<app>.fly.dev/healthz` returns 200
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
If you're at 10+ minutes, you're overpolling. Stop, tell the user it's deployed, move on.

### 3. Read --help for exact syntax

Before running any ifhost command, check its help text:

```bash
ifhost deploy --help
ifhost machines logs --help
```

The CLI help is always up-to-date. Use this skill doc for the big picture and decision-making, but trust `--help` for exact syntax and available flags.

## Install

```bash
curl -fsSL https://impossible-api.fly.dev/install | sh
```

This downloads the correct binary for the current OS/architecture (macOS/Linux, amd64/arm64)
and installs it to `~/.local/bin/ifhost`. If `~/.local/bin` is not in PATH, add it:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Verify installation:

```bash
ifhost --help
```

If the install script fails (e.g., no curl, restricted network), manually download:

```bash
# macOS ARM (Apple Silicon)
curl -fsSL https://impossible-api.fly.dev/dl/ifhost_darwin_arm64.tar.gz | tar xz
mv ifhost ~/.local/bin/

# macOS Intel
curl -fsSL https://impossible-api.fly.dev/dl/ifhost_darwin_amd64.tar.gz | tar xz
mv ifhost ~/.local/bin/

# Linux x86_64
curl -fsSL https://impossible-api.fly.dev/dl/ifhost_linux_amd64.tar.gz | tar xz
mv ifhost ~/.local/bin/

# Linux ARM64
curl -fsSL https://impossible-api.fly.dev/dl/ifhost_linux_arm64.tar.gz | tar xz
mv ifhost ~/.local/bin/
```

## Quick Start

```bash
ifhost login                                          # GitHub OAuth (one-time)
ifhost init --app my-app --port 3000 --memory 512     # Generate impossible.toml
ifhost deploy                                         # Build + deploy
```

## ⚡ FASTEST PATH (always try this first)

If the project publishes a Docker image (most modern OSS projects do — check
`ghcr.io/<org>/<repo>` or look for image refs in their README/docker-compose.yml):

```bash
ifhost init --app my-app --port <PORT> --memory 1024 --autostop=false --min-machines 1
ifhost deploy --image ghcr.io/owner/project:latest \
  --secret API_KEY=... \
  --env CONFIG_VAR=value
```

**~30 seconds total** instead of 5-10 minutes for source builds.

Examples of projects with published images: openclaw (`ghcr.io/openclaw/openclaw:latest`),
most Node/Python web apps, all official Docker Hub images (nginx, redis, postgres, etc.).

**How to check if a project publishes an image:**
1. Look at the README for `docker pull` commands or `image:` lines in docker-compose.yml
2. Visit `https://github.com/<owner>/<repo>/pkgs/container/<repo>` (GitHub Container Registry)
3. Run `gh api /orgs/<owner>/packages?package_type=container 2>/dev/null` to list packages

---

## Command Reference

### ifhost login

Authenticate via GitHub OAuth device flow. Opens a browser. Token is stored at `~/.config/ifhost/token`. If already logged in, skips the flow.

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
    URL:     https://my-api.fly.dev
    Status:  deployed   Region: iad
    Running (1):
      e784160df242e8
    Standby (9):
      56835429c02568
      84409ef2319998
      ...

  my-site
    URL:     https://my-site.fly.dev
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
| `--app` | (required) | App name → becomes `<name>.fly.dev` |
| `--port` | from Dockerfile EXPOSE, else 8080 | Port the app listens on |
| `--memory` | 256 | RAM in MB (256, 512, 1024, 2048, 4096) |
| `--cpus` | 1 | CPU count (1, 2, 4, 8) |
| `--cpu-kind` | shared | `shared` or `performance` |
| `--cmd` | Dockerfile CMD | Startup command override |
| `--autostop` | true | Set `false` for apps that take >60s to boot |
| `--min-machines` | 0 | Set `1` for no cold starts |
| `--storage` | cloud | `cloud` (S3 bucket) or `local` (volume at /data) |

Generates `impossible.toml` in the current directory. Edit it directly after creation — do not re-run init (it errors if the file exists).

---

### ifhost deploy

Build and deploy the app. Requires `impossible.toml` and a `Dockerfile` (unless `--runner`).

```bash
ifhost deploy [flags]
```

| Flag | Description |
|------|-------------|
| `--image <ref>` | **Skip the build entirely.** Deploy a pre-built image (10x faster). Example: `--image ghcr.io/openclaw/openclaw:latest` |
| `--local` | Force local Docker build (requires Docker Desktop running) |
| `--remote` | Force remote source upload + cloud build |
| `--runner` | Deploy a generic shell image (no Dockerfile needed). For interactive setup via console. |
| `--env KEY=VALUE` | Set env var (repeatable). Merged with [env] in toml. |
| `--secret KEY=VALUE` | Set secret (repeatable, not shown in logs) |
| `--cmd "..."` | Override startup command (replaces image's CMD) |
| `--port N` | Override container port |
| `--region <code>` | Region (e.g. iad, sin, lhr). See `ifhost regions`. |
| `--storage cloud\|local` | Override storage mode |
| `--app <name>` | Override app name from toml |
| `--yes` | Skip confirmation prompts |
| `--json` | Output structured JSON |

**Build modes (in order of preference for speed):**
- `--image <ref>` → No build. Pulls a pre-built image. **~30 seconds total.**
  Check the project's README for `ghcr.io/...` or `docker.io/...` published images.
- Local Docker available → builds locally with layer cache. ~30s-2min after first build.
- `--runner` → boots a generic shell VM, no build needed
- Otherwise → uploads source to cloud builder (capped at ~30MB). 5-10 min for heavy builds.

**Always check first if the project publishes a Docker image** (look for `ghcr.io`, `docker.io`,
or `quay.io` references in README or docker-compose.yml). Using `--image` skips the entire
build step — no source upload, no pnpm install, no compile. Most modern OSS projects publish
images and this is by far the fastest path.

**During deploy:** Streams real-time build logs via SSE. Press Ctrl+C to cancel.

**After deploy:** Prints the live URL (e.g., `https://my-app.fly.dev`).

**Scaled apps:** Deploy automatically propagates the new image to all machines (rolling update).
No need to update standby machines manually — they all get the new code.

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

Shows machines grouped by state with IDs for targeting:

```
my-app  (10 machines)

  Running (1)
  ID               REG  SPEC             NAME
  e784160df242e8   iad  shared/2 1024MB  fragrant-glade-7429

  Standby (9) — wakes on traffic, $0 while idle
  ID               REG  SPEC             NAME
  56835429c02568   iad  shared/2 1024MB  lingering-sky-4328
  ...

  Tip: ifhost machines exec --machine <id> --app my-app -- <cmd>
```

For a cross-project overview, use `ifhost status` — lists all projects with machine IDs.

#### Start / Stop / Restart

```bash
ifhost machines start --app my-app
ifhost machines stop --app my-app       # No cost while stopped
ifhost machines restart --app my-app
```

#### Scale (manual)

```bash
ifhost machines scale 3 --app my-app    # Scale to 3 machines
```

Standby machines cost $0 — they only wake when traffic arrives (~1-2s cold start).
Deploys auto-propagate the new image to all machines (rolling update).

**Critical for scaled apps:** Don't use `exec` for post-deploy setup (migrations, config).
Standby machines won't get exec commands when they wake. Instead, put ALL setup in
`[build] cmd` in impossible.toml — it runs on every machine boot:

```toml
[build]
cmd = "python manage.py migrate && gunicorn app:app"
```

For true auto-scaling, use `ifhost machines autoscale set`.

#### Auto-scale

```bash
ifhost machines autoscale set --min 1 --max 5 --target 25 --app my-app
ifhost machines autoscale off --app my-app
```

| Flag | Default | Description |
|------|---------|-------------|
| `--min` | 0 | Minimum always-running machines (0 = scale to zero) |
| `--max` | 3 | Maximum machines under load |
| `--target` | 25 | Concurrent requests per machine before scaling |

Run `ifhost deploy` after changing autoscale settings to apply.

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
ifhost machines logs --app my-app --grep "GET" --lines 50  # Combined filters
```

| Flag | Description |
|------|-------------|
| `--since <duration>` | Show logs from this duration ago (e.g., 1h, 30m, 2h30m). Exits after showing historical logs. |
| `--lines <N>` | Show last N lines then exit (no follow) |
| `--grep "<pattern>"` | Filter: only show lines containing this substring (case-insensitive) |
| `--level <level>` | Filter by level: `error` (includes fatal/panic), `warn`, `info` |
| `--json` | Output structured JSON per line (timestamp, region, message, level) |
| `--raw` | Alias for --json |

**Behavior:**
- No flags → streams live indefinitely (tail -f mode)
- `--since` or `--lines` → fetch historical, then exit
- `--grep` and `--level` → client-side filtering on the stream
- Filters stack: `--grep "payment" --level error --lines 10` shows last 10 error lines containing "payment"

**For agents debugging issues:**
```bash
# Check if app is crashing
ifhost machines logs --app my-app --level error --lines 20

# Watch for specific request patterns
ifhost machines logs --app my-app --grep "POST /api" --lines 50

# Get full recent context
ifhost machines logs --app my-app --since 5m --json
```

**Non-blocking log monitoring (tmux mode):**

The default `ifhost machines logs` blocks until Ctrl+C — fine for humans, but agents
can't do other work while streaming. Use a console session to tail logs in the background:

```bash
# 1. Start a console session
ifhost machines console start --app my-app
# Returns session-id, e.g. ifhost-01abc

# 2. Start tailing logs inside the container
ifhost machines console input --app my-app ifhost-01abc "tail -f /var/log/app.log"
ifhost machines console input --app my-app ifhost-01abc --key Enter

# 3. Do other work...

# 4. Come back later and read what accumulated
ifhost machines console output --app my-app ifhost-01abc --lines 200

# 5. Filter the output for errors
ifhost machines console output --app my-app ifhost-01abc --lines 200 | grep -i error
```

This lets agents "attach" to logs, walk away, and check back — like tmux detach/attach.
Works with any log file or process output inside the container.

---

### ifhost machines exec

Run a one-off command inside a running container. For commands that finish without stdin.

```bash
ifhost machines exec --app my-app -- ls /data
ifhost machines exec --app my-app -- env
ifhost machines exec --app my-app --machine e784160df242e8 -- cat /var/log/app.log
ifhost machines exec --app my-app -- python manage.py migrate
```

| Flag | Description |
|------|-------------|
| `--machine <id>` | Target a specific machine (default: first running). Get IDs from `ifhost status`. |

**Important for scaled apps:** Without `--machine`, exec picks an arbitrary running machine.
Use `ifhost status` to get machine IDs, then pass `--machine <id>` to target the right one.
This matters for volume-mounted apps (each machine has its own disk) and debugging specific instances.

Timeout: 120 seconds. If no machines are running, start the app first.

**When to use exec vs console:**
- `exec` → command finishes on its own, no stdin, <120s
- `console` → command prompts for input, runs a REPL, needs follow-up, or >120s

---

### ifhost machines console

Interactive tmux-backed console for commands that need stdin or take a long time.

#### Start a session

```bash
ifhost machines console start --app my-app              # Default: bash
ifhost machines console start --app my-app -- bash      # Explicit shell
ifhost machines console start --app my-app --cmd "python3"  # Start Python REPL
```

Returns a `session-id` (e.g., `ifhost-01abc`).

#### Send input

```bash
ifhost machines console input --app my-app <session-id> "npm install"
ifhost machines console input --app my-app <session-id> --key Enter
ifhost machines console input --app my-app <session-id> --key C-c     # Ctrl+C
ifhost machines console input --app my-app <session-id> "yes" --key Enter
```

#### Read output

```bash
ifhost machines console output --app my-app <session-id>
ifhost machines console output --app my-app <session-id> --lines 100
```

**Agent patterns:**

```bash
# Install + poll for completion
ifhost machines console input --app a $SID "apt-get install -y nginx; echo __DONE__"
ifhost machines console input --app a $SID --key Enter
# Poll until marker appears:
ifhost machines console output --app a $SID | grep __DONE__

# Launch long-lived daemon (survives disconnect)
ifhost machines console input --app a $SID "tmux new-session -d -s app 'node server.js 2>&1 | tee /data/app.log'"

# Non-blocking log monitoring (tail -f without blocking the agent)
ifhost machines console input --app a $SID "tail -f /data/app.log"
ifhost machines console input --app a $SID --key Enter
# ... do other work ...
ifhost machines console output --app a $SID --lines 100   # check logs anytime
```

---

### ifhost machines env

Manage environment variables. Changes take effect on next deploy or restart.

```bash
ifhost machines env set KEY=VALUE --app my-app          # Set (repeatable)
ifhost machines env list --app my-app                   # List all
ifhost machines env rm KEY --app my-app                 # Remove
```

### ifhost machines secrets

Manage encrypted secrets. Values are never shown in logs or status.

```bash
ifhost machines secrets set API_KEY=sk-... --app my-app
ifhost machines secrets list --app my-app               # Shows key names only
ifhost machines secrets rm API_KEY --app my-app
```

---

### ifhost machines volumes

Manage persistent disk volumes. Only for `storage = "local"` apps.

```bash
ifhost machines volumes list --app my-app
ifhost machines volumes create my-data --size 3 --mount /data --app my-app
ifhost machines volumes rm my-data --app my-app --yes
```

Volume apps are pinned to one machine (no horizontal scaling). Use for SQLite or file-based storage only.

---

### ifhost machines domains

Manage custom domains.

```bash
ifhost machines domains add myapp.com --app my-app      # Returns CNAME target
ifhost machines domains list --app my-app
ifhost machines domains rm myapp.com --app my-app
```

After adding, create a DNS CNAME record pointing to the returned target. TLS is automatic.

---

### ifhost machines destroy

Delete a machine or the entire app.

```bash
ifhost machines destroy --app my-app --yes              # Delete entire app + resources
ifhost machines destroy <machine-id> --app my-app       # Delete single machine
```

---

### ifhost regions

List available deployment regions.

### ifhost plans upgrade

View and upgrade subscription plan.

---

## impossible.toml Reference

Full example with all fields:

```toml
app = "my-app"
storage = "cloud"                  # "cloud" (S3) or "local" (/data volume)

[service]
internal_port = 3000               # Port app listens on (MUST match app)
autostop = false                   # false for bots / slow-booting apps
min_machines = 1                   # 1 = no cold starts

[resources]
cpu_kind = "shared"                # "shared" or "performance"
cpus = 2                           # 1, 2, 4, 8
memory_mb = 1024                   # 256, 512, 1024, 2048, 4096

[build]
cmd = "migrate && start"           # Startup command (see notes below)

[env]
NODE_ENV = "production"
DATABASE_URL = "postgres://..."

[autoscale]
min = 1
max = 5
concurrency_target = 25
```

**About `[build] cmd`:** Despite its name, this is a RUNTIME startup command, NOT a
build-time step. It replaces the Dockerfile CMD and runs via `sh -c "<cmd>"` on every
machine boot (including standby wakes). Shell features work: pipes, `&&`, `$ENV_VARS`.

**Secrets and env vars in `[build] cmd`:** All secrets set via `--secret` and env vars
from `[env]` are available as environment variables when `[build] cmd` runs. You can
reference them: `echo "$API_KEY" > /data/config.json && node start.js`.

**Apps that need a config file at boot:** Use `[build] cmd` to generate it from env vars.
The trick is `printf '%s' "$VAR"` — `printf` is the safest way to inject env values into JSON
without shell-escape hell:

```toml
[build]
cmd = """mkdir -p /data && printf '{"token":"%s","model":"%s"}' "$BOT_TOKEN" "$MODEL" > /data/config.json && exec node server.js"""
```

Notes for writing this safely:
- Use TOML triple-quotes `"""..."""` to avoid escaping `"` characters in the cmd
- Use `printf '%s' "$VAR"` for any value that could contain special chars
- End with `exec <real_cmd>` so the app process gets PID 1 (clean signals)
- Test the `printf` locally first if escaping gets tricky

For very complex configs, write a `setup.sh` script in your repo and run it:
```toml
[build]
cmd = "bash /app/setup.sh && exec node server.js"
```

**Secrets:** Pass via `--secret` on the deploy command, NOT in the toml file:
```bash
ifhost deploy --secret API_KEY=sk-... --secret BOT_TOKEN=123:ABC
```

---

## Common Deployment Patterns

### Static site (nginx)
```bash
ifhost init --app my-site --port 80 --memory 256
ifhost deploy
```

### Node.js / Python API
```bash
ifhost init --app my-api --port 3000 --memory 512
ifhost deploy --env DATABASE_URL=postgres://...
```

### Heavy app (AI agent, ML model, slow boot)
```bash
ifhost init --app my-agent --port 3000 --memory 1024 --cpus 2 --autostop=false --min-machines 1
ifhost deploy --env OPENAI_API_KEY=sk-...
```

### Complex app (custom port, config generation, multiple env vars)

Many real-world apps need: a non-standard port, bind to 0.0.0.0, config files written
before startup, and multiple API keys. Use `[build] cmd` to handle all setup:

```toml
app = "my-gateway"
storage = "local"

[service]
internal_port = 18789
autostop = false
min_machines = 1

[resources]
cpu_kind = "shared"
cpus = 2
memory_mb = 2048

[build]
cmd = "mkdir -p /data/config && echo '{\"setting\":\"value\"}' > /data/config/app.json && node dist/index.js --bind lan --port 18789"

[env]
NODE_ENV = "production"
STATE_DIR = "/data"
```

**Workflow for complex apps:**
1. Run `ifhost init --app <name> --port <port> --memory <mb> --cpus <n> --autostop=false --min-machines 1 --storage local`
2. Edit the generated `impossible.toml` to add `[build] cmd` and `[env]` sections
   (`ifhost init` creates the file but doesn't support all fields)
3. Run `ifhost deploy --secret KEY1=val1 --secret KEY2=val2`

Key points:
- `[build] cmd` runs on EVERY machine boot (including standby wakes) — put all setup here
- Use `storage = "local"` if the app writes config/data to disk
- `--bind lan` or `0.0.0.0` is required — apps binding to localhost are unreachable
- Set `memory_mb = 2048` if the Docker build is heavy (Node.js pnpm install OOMs at 1GB)
- Secrets are available as `$ENV_VAR` in `[build] cmd` — use them to generate config files
- If Dockerfile has no EXPOSE, check docker-compose.yml or app docs for the port

**Put env vars that `[build] cmd` references in `[env]`, not `--env`:** If your `[build] cmd`
expands `$MY_VAR`, that variable MUST be in the `[env]` block of impossible.toml. Previously
`--env KEY=VAL` on the deploy command line could be wiped on machine rebuild, leaving your
`printf` to produce empty values (e.g. `allowFrom: [""]` → validator crash loop). The CLI
now persists `--env` through deploys, but `[env]` in the toml is still the safest option
because it's version-controlled and visible.

**Fail loud on missing env vars in `[build] cmd`:** Use bash's `${VAR:?missing}` guard so
the shell exits if a required variable is empty, instead of silently writing a broken config:
```toml
cmd = """printf '{"id":"%s"}' "${CHAT_ID:?CHAT_ID not set}" > /data/config.json && exec ..."""
```

### Messaging bot (Telegram, Discord, Slack, etc.)

**Region matters:** Telegram bots MUST NOT deploy to `iad` (US East). The `iad` region has
broken IPv6/persistent-connection routing to `api.telegram.org` — `getUpdates` hangs for
120s+ and `sendMessage` fails with "Network request failed" even though one-shot `curl`
from the same container works. Use `ams` (Amsterdam) or `fra` (Frankfurt) — they're
colocated with Telegram's DC2/DC4 and work first try.

**CRITICAL: Region locks at app creation time.** Once you create an app in a region,
subsequent `ifhost deploy --region ...` calls DO NOT move it. The flag only matters on
the very first deploy (when the app is created). To change region: destroy and recreate.

Set region in impossible.toml BEFORE the first deploy:
```toml
app = "my-bot"
region = "ams"    # NOT primary_region — the field is just "region"
```

Or on first deploy:
```bash
ifhost deploy --region ams --image ghcr.io/...
```

Bots that use long polling or WebSocket connections MUST stay running at all times.
Autostop will kill the process when there's no HTTP traffic, breaking the bot.

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

[build]
cmd = "node server.js --bind lan --port 3000"

[env]
NODE_ENV = "production"
```

Deploy with bot tokens as secrets:
```bash
ifhost deploy \
  --secret TELEGRAM_BOT_TOKEN=123456:ABC... \
  --secret OPENAI_API_KEY=sk-... \
  --env TELEGRAM_CHAT_ID=623508703
```

**Key rules for bots:**
- `autostop = false` + `min_machines = 1` — the bot must NEVER stop
- Bot tokens go in `--secret`, not `--env` (secrets are encrypted, not shown in logs)
- Secrets are injected as environment variables into the running process automatically
- If the app generates a config file on boot, use `[build] cmd` to write it BEFORE starting
- After deploy, verify with `ifhost machines logs --app <name> --lines 20` — look for
  channel connection messages, NOT by exec/console probing

**Do NOT debug bots with exec/console.** Instead:
1. Check logs: `ifhost machines logs --app <name> --lines 50`
2. Check health: `curl https://<name>.fly.dev/healthz`
3. If something is wrong, fix the config and redeploy — don't try to patch a running container

### SQLite app (single machine, persistent disk)
```bash
ifhost init --app my-db-app --port 8080 --memory 512 --storage local
ifhost deploy
# Data persists at /data inside the container
```

### Interactive setup (no Dockerfile)
```bash
ifhost init --app my-project --port 3000 --memory 1024
ifhost deploy --runner
# Then use console for setup:
ifhost machines console start --app my-project -- bash
ifhost machines console input --app my-project $SID "git clone ... && npm install; echo __DONE__"
# Poll output, then start the app in a detached tmux session
```

---

## Agent Decision Tree

```
Does the project have a Dockerfile?
├── YES → ifhost init + ifhost deploy
│   ├── Simple web app → --memory 256, default settings
│   ├── API with DB → --memory 512, pass DB_URL via --env
│   ├── Heavy/AI app → --memory 1024+, --autostop=false, --min-machines 1
│   └── SQLite app → --storage local (disables scaling)
└── NO
    ├── Can you write a Dockerfile? → Write it, then deploy normally
    └── Complex interactive setup? → ifhost deploy --runner + console
```

---

## Traps to Avoid

| Trap | Symptom | Fix |
|------|---------|-----|
| PORT mismatch | App boots but 502 errors | Check Dockerfile EXPOSE, set `[service] internal_port` to match |
| Low RAM | App killed silently (OOM) | Node.js needs 512MB+, AI/ML needs 1024MB+ |
| Autostop kills slow apps | App never becomes reachable | `autostop = false` + `min_machines = 1` |
| Env vars in config files | Values lost on restart | Use `--env` or `[env]` in impossible.toml |
| Startup needs setup | App crashes on boot | Use `[build] cmd = "migrate && serve"` |
| Scaled app needs setup | Standby machines wake unconfigured | Put ALL setup in `[build] cmd`, not in exec. cmd runs on every boot. |
| Console hits wrong machine | Input goes to machine A, session is on B | Always pass `machine_id` from ConsoleStart response to Input/Output |
| Bot killed by autostop | Telegram/Discord bot stops responding after idle | `autostop = false` + `min_machines = 1` for ANY long-polling service |
| Secrets not in process env | App can't read API keys at runtime | Secrets ARE injected as env vars. Check with `ifhost machines logs`, not exec |
| Debugging spiral | Agent spends 20 min exec/console probing | Check logs first. If wrong, fix config and redeploy. Don't patch running containers. |
| Lock files from crash | App hangs on restart | Prepend `rm -f /tmp/*.lock &&` to cmd |
| Source too large (>30MB) | Remote build fails/slow | Use `--local` with Docker Desktop, or add .dockerignore |
| No .dockerignore | Upload takes forever | Create .dockerignore excluding node_modules, .git, etc. |

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

# 6. Run a command inside the container
ifhost machines exec --app my-app -- env
ifhost machines exec --app my-app -- cat /var/log/app.log

# 7. If app won't start, check the deploy
ifhost describe --app my-app --json | jq '.deployments[0]'
```

---

## Known Projects Cheat Sheet

Pre-verified configs for popular projects. Saves you discovery time.

### OpenClaw (Telegram/Discord/Slack AI bot)

> **Known upstream issue (as of 2026-04-22):** OpenClaw's Telegram webhook handler calls the LLM synchronously before returning 200 to Telegram, which blows Telegram's webhook read timeout on slow responses. Symptom: `last_error_message: "Read timeout expired"` in `getWebhookInfo`, pending updates pile up, replies lag 1-5 min. This is in OpenClaw's code (grammY's `webhookCallback` is called without `onTimeout: "return"`), not in ifhost. A Cloudflare Worker webhook relay (see "Production reliability" below) fully works around it.

**Use webhook mode, not long-polling.** Long-lived HTTPS polling connections (which `getUpdates` uses) are unreliable on most cloud/edge infrastructure — they stall every few minutes because edge proxies drop idle TCP. Webhook mode uses short HTTPS calls in both directions and avoids that entire class of failure.

**Port-swap trick:** ifhost's `[service]` block only exposes a single internal port. Run the OpenClaw gateway on an internal-only port (19001) and bind the Telegram webhook listener to the exposed port (18789). Incoming `https://<app-url>/telegram-webhook` requests from Telegram route straight to grammY's webhook handler inside OpenClaw.

**Complete `impossible.toml`:**

```toml
app = "my-claw"
storage = "local"
region = "ams"

[service]
internal_port = 18789  # exposed to internet; webhook listener binds here
autostop = false
min_machines = 1

[resources]
cpu_kind = "shared"
cpus = 2
memory_mb = 2048

[build]
cmd = """mkdir -p /home/node/.openclaw && printf '{"agents":{"defaults":{"model":{"primary":"openai/gpt-5-nano"}}},"gateway":{"controlUi":{"enabled":false}},"channels":{"telegram":{"dmPolicy":"allowlist","allowFrom":["%s"],"webhookUrl":"https://%s/telegram-webhook","webhookSecret":"%s","webhookHost":"0.0.0.0","webhookPort":18789}}}' "${TELEGRAM_CHAT_ID:?TELEGRAM_CHAT_ID not set}" "${APP_URL:?APP_URL not set}" "${TG_WEBHOOK_SECRET:?TG_WEBHOOK_SECRET not set}" > /home/node/.openclaw/openclaw.json && exec node /app/openclaw.mjs gateway --bind lan --port 19001 --allow-unconfigured"""

[env]
NODE_ENV = "production"
TELEGRAM_CHAT_ID = "<TG_USER_ID>"
APP_URL = "<app-public-hostname>"   # the hostname printed by 'ifhost deploy', e.g. my-claw.<ifhost-domain>
NODE_OPTIONS = "--dns-result-order=ipv4first"
```

**Deploy:**
```bash
ifhost deploy --image ghcr.io/openclaw/openclaw:latest \
  --secret OPENAI_API_KEY=sk-... \
  --secret TELEGRAM_BOT_TOKEN=... \
  --secret TG_WEBHOOK_SECRET=$(openssl rand -hex 24) \
  --yes
```

The deploy prints `Your app is live at: https://<app-public-hostname>` — use that hostname as `APP_URL` in the toml.

**Prime the webhook immediately (don't wait for OpenClaw's slow internal setWebhook):**

After deploy, poll the webhook endpoint until it returns 401 (listener up, rejecting unauthenticated), then call Telegram's `setWebhook` from your laptop to register your URL with Telegram directly. This cuts 3-5 minutes of wait time:

```bash
APP_URL=<app-public-hostname>
TG_WEBHOOK_SECRET=<same-secret-you-deployed-with>

# Wait for webhook listener to come up
until [ "$(curl -s -o /dev/null -w "%{http_code}" -X POST -d '{}' https://$APP_URL/telegram-webhook)" = "401" ]; do sleep 5; done

# Register the webhook with Telegram
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  --data-urlencode "url=https://$APP_URL/telegram-webhook" \
  --data-urlencode "secret_token=$TG_WEBHOOK_SECRET"

# Verify it's registered
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo" | jq .result.url
```

Once the webhook URL is registered, messages from the user arrive in seconds.

**Gotchas:**
- **Port-swap is mandatory.** Gateway must be on a different internal port (19001) than the webhook listener (18789). They're separate HTTP servers inside OpenClaw and can't share a port.
- Gateway's `/healthz` won't be reachable on the public URL (it's on internal :19001). That's fine — the default TCP check on 18789 passes because the webhook listener is there. To validate end-to-end health, use `curl .../getWebhookInfo` on Telegram's side instead of hitting `/healthz` directly.
- Config root key is `agents` (plural) — Zod schema overrides docs.
- `--bind lan` activates the gateway's HTTP/Control UI — set `controlUi.enabled = false`.
- `dmPolicy: "allowlist"` + numeric user ID in `allowFrom` skips pairing.
- Put `TELEGRAM_CHAT_ID` and `APP_URL` in `[env]`, NOT `--env` CLI flag — `--env` doesn't survive machine rebuilds (ifhost limitation).
- Use `${VAR:?missing}` guards so empty env vars fail loudly instead of writing a broken config.
- "Config write anomaly" and "Config overwrite" log lines are NORMAL — OpenClaw rewrites its config on boot to add meta/auth token. Your settings survive.
- `last_error_message: "Read timeout expired"` in `getWebhookInfo` is the signature of the upstream handler-latency issue described at the top of this section, NOT an infra problem. See "Production reliability" below for the fix.

**Production reliability — Cloudflare Worker relay (recommended for any user-facing deploy):**

Because OpenClaw's webhook handler blocks on LLM calls, Telegram's webhook pushes time out and retry, cascading into multi-minute reply lag in the worst case. Put a Cloudflare Worker in front as a relay: the Worker acks 200 to Telegram in <100ms at Cloudflare's edge, then forwards the payload to OpenClaw asynchronously — OpenClaw can take 30s to think and it no longer matters.

1. Point `webhookUrl` in your OpenClaw config at the Worker's URL (e.g. `https://<your-worker>.workers.dev/telegram-webhook`) instead of `<app-public-hostname>`.
2. Have the Worker forward to `https://<app-public-hostname>/telegram-webhook` with the same secret token header.

Public starting points:
- [`tuanpb99/cf-worker-telegram`](https://github.com/tuanpb99/cf-worker-telegram) — transparent Bot API proxy on Workers
- [`cvzi/telegram-bot-cloudflare`](https://github.com/cvzi/telegram-bot-cloudflare) — minimal webhook handler on Workers

Setup is ~15 minutes if you have a Cloudflare account.

**Isolation test (for future debugging):** if you're seeing slow Telegram replies from an ifhost bot and want to rule out the infra, deploy a minimal Python or Node echo bot on the same `impossible.toml` template with webhook mode. A minimal bot does 300-600ms round trips in steady state — if your echo bot is fast and OpenClaw is slow, it's an application-layer problem.

**Why NOT long-polling mode:** `getUpdates` stalls 120s+ every few minutes because cloud edge infrastructure drops long-lived HTTPS connections. Log signature: `[telegram] Polling stall detected (active getUpdates stuck for 122s); forcing restart`. Webhook mode flips the direction — Telegram initiates short HTTPS POSTs to us, and our replies are short outbound HTTPS to `api.telegram.org/sendMessage`. No long-lived connections anywhere.

---

## Pricing

| Plan | Price | RAM | CPUs | Projects | Storage |
|------|-------|-----|------|----------|---------|
| Free | $0/mo | 256MB | 1 shared | 1 | 1 GB |
| Hobby | $10/mo | 1GB | 2 shared | 5 | 10 GB |
| Pro | $25/mo | 4GB | 2 perf | 20 | 100 GB |
| Team | $50/mo | 8GB | 4 perf | 50 | 1 TB |

Upgrade: `ifhost plans upgrade`

---

## Global Flags

| Flag | Description |
|------|-------------|
| `--json` | Output structured JSON (available on all commands) |
| `--app <name>` | Override app name (on deploy and machines subcommands) |
| `--yes` | Skip confirmation prompts (on deploy and destroy) |
