# ifhost — Deploy to Impossible Hosting

Deploy any Dockerized app to the cloud with one command. Each app gets its own isolated VM, HTTPS URL, object storage, and optional auto-scaling.

## Agent Rule: Read --help First

Before running any ifhost command, check its help text:

```bash
ifhost deploy --help
ifhost machines logs --help
ifhost machines console --help
```

The CLI help is always up-to-date and includes examples, flag descriptions, and usage patterns. Use this skill doc for the big picture and decision-making, but trust `--help` for exact syntax and available flags.

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

---

## Command Reference

### ifhost login

Authenticate via GitHub OAuth device flow. Opens a browser. Token is stored at `~/.config/ifhost/token`. If already logged in, skips the flow.

### ifhost logout

Remove stored credentials.

### ifhost status

Show account info: plan tier, apps deployed, resource usage.

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
| `--local` | Force local Docker build (requires Docker Desktop running) |
| `--remote` | Force remote source upload + cloud build |
| `--runner` | Deploy a generic shell image (no Dockerfile needed). For interactive setup via console. |
| `--env KEY=VALUE` | Set env var (repeatable). Merged with [env] in toml. |
| `--secret KEY=VALUE` | Set secret (repeatable, not shown in logs) |
| `--cmd "..."` | Override startup command (replaces Dockerfile CMD) |
| `--port N` | Override container port |
| `--region <code>` | Fly.io region (e.g. iad, sin, lhr). See `ifhost regions`. |
| `--storage cloud\|local` | Override storage mode |
| `--app <name>` | Override app name from toml |
| `--yes` | Skip confirmation prompts |
| `--json` | Output structured JSON |

**Build modes (auto-detected):**
- Local Docker available → builds locally, pushes image (fastest, uses cache)
- No Docker → uploads source to cloud builder (capped at ~30MB source)
- `--runner` → boots a generic shell VM, no build needed

**During deploy:** Streams real-time build logs via SSE. Press Ctrl+C to cancel.

**After deploy:** Prints the live URL (e.g., `https://my-app.fly.dev`).

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

Shows machine IDs, states, regions, and specs.

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

Manual scaling only. Machines still auto-start/stop per traffic. For true auto-scaling, use `ifhost machines autoscale set`.

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

Run a one-off command inside the running container. For commands that finish without stdin.

```bash
ifhost machines exec --app my-app -- ls /data
ifhost machines exec --app my-app -- env
ifhost machines exec --app my-app -- cat /etc/nginx/nginx.conf
ifhost machines exec --app my-app -- python manage.py migrate
ifhost machines exec --app my-app -- sh -c "du -sh /data/*"
```

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
autostop = false                   # false for slow-booting apps
min_machines = 1                   # 1 = no cold starts

[resources]
cpu_kind = "shared"                # "shared" or "performance"
cpus = 2                           # 1, 2, 4, 8
memory_mb = 1024                   # 256, 512, 1024, 2048, 4096

[build]
cmd = "migrate && start"           # Override Dockerfile CMD

[env]
NODE_ENV = "production"
DATABASE_URL = "postgres://..."

[secrets]
API_KEY = "sk-..."                 # Never shown in logs

[autoscale]
min = 1
max = 5
concurrency_target = 25
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
