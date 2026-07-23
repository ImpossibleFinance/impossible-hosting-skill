# ifhost Runner Deployment Runbook

This runbook is the ordered procedure for deploying an application with
ifhost runner mode. `SKILL.md` remains the full reference; this file is the
short operational path and recovery guide.

## Definition of done

A deployment is complete only when:

1. The app process is running independently of the `machines exec` session.
2. The process listens on the configured port and a non-loopback address.
3. The public health or root route returns HTTP `200`.
4. Any user-requested representative routes also return their expected
   status and content type.

`ifhost deploy` provisioning a VM is not evidence that the app is live.

## Guardrails

- Refresh the CLI before every deployment session:

  ```bash
  curl -fsSL https://host.impossi.build/install | sh
  ifhost version
  ```

- Use the freshly updated CLI's `--help` to confirm command syntax and
  available flags. Do not infer runner lifecycle from generic examples:
  `[build]` is ignored and the app must be started explicitly.
- Run `ifhost status` before changing anything.
- Get explicit approval for the app name, machine specification, region,
  storage, environment variables, and secrets.
- Treat an existing Dockerfile as a setup recipe. Runner deploys do not build
  it.
- Do not rely on `[build]` to start the process. Start the app explicitly
  after the VM is provisioned.
- If unattended automatic recovery after a machine restart is required, stop
  and report that the runner workflow does not provide it.
- Never expose Git credentials or application secrets to move source files.
- If the source repository must remain untouched, create `impossible.toml`
  and all packaging artifacts in a temporary directory outside it.
- Do not declare success without a real HTTP `200`.

## 1. Inspect the project

Read the project documentation and deployment inputs:

```text
README.md
INSTALL.md
Dockerfile
docker-compose.yml
.env.example
config templates
```

Record:

```text
App name:
Region:
Internal port:
Bind address:
RAM:
CPUs:
Autostop:
Minimum machines:
Storage:
Environment variables:
Secrets:
Install command:
Start command:
Health route:
Representative routes:
Source-transfer method:
```

Resolve missing secrets with the user. Never guess them.

## 2. Prepare the deployment manifest

For a small static or lightweight HTTP service:

```bash
ifhost init \
  --app <app-name> \
  --port 8080 \
  --memory 256 \
  --cpus 1 \
  --cpu-kind shared \
  --autostop=false \
  --min-machines 1 \
  --storage local
```

Expected manifest:

```toml
app = "<app-name>"
storage = "local"

[service]
internal_port = 8080
autostop = false
min_machines = 1

[resources]
cpu_kind = "shared"
cpus = 1
memory_mb = 256
```

Use more memory for Node.js, Python APIs, local compilation, or compute-heavy
applications. Runner deploys with no explicit storage or declared volumes
currently provision a 1 GB local volume at `/data` automatically. Declare
`storage = "local"` explicitly so the manifest records that dependency. Use a
larger declared volume when the install will exceed 1 GB. Local volumes pin the
app to one machine.

Present the manifest and exact deploy command to the user before proceeding.

## 3. Provision the runner

```bash
ifhost deploy --region <region> --yes
```

The resulting URL may return an error until the app is installed and started.
This is expected.

Immediately record the machine ID:

```bash
ifhost machines --app <app-name> --json
ifhost describe --app <app-name> --json
```

Pin later commands with `--machine <machine-id>` whenever the command supports
it.

## 4. Install runtime dependencies

Translate the existing Dockerfile into runner commands. For example:

```dockerfile
FROM python:3.12-slim
COPY . /app
EXPOSE 8080
CMD ["python3", "-m", "http.server", "8080", "--directory", "/app"]
```

becomes:

```bash
ifhost machines exec \
  --app <app-name> \
  --machine <machine-id> \
  -- sh -c "apt-get update -qq && apt-get install -y python3"
```

Translate image-internal paths such as `/app` to the runner's durable
`/data/app` path.

Install all known dependencies together instead of discovering them one
failure at a time. Only `/data` is durable storage; after a machine restart,
confirm any runtime installed elsewhere still exists before relaunching.

## 5. Transfer source

Choose the lowest-risk available method.

### Public repository or artifact

Prefer downloading inside the VM. This avoids the control-plane upload limit
and per-chunk request overhead:

```bash
ifhost machines exec \
  --app <app-name> \
  --machine <machine-id> \
  -- sh -c "git clone --depth 1 <public-repo-url> /data/app"
```

For release archives, use a trusted HTTPS URL and verify its checksum before
extracting it.

### Small local source tree

Use `push` when its compressed archive is at most 10 MiB. It uploads in
32 KiB chunks and does not accept `--machine`:

```bash
ifhost machines push . --to /data/app --app <app-name>
```

`push` honors `.gitignore`, `.dockerignore`, and `.impignore`, applies built-in
exclusions such as `.git`, `node_modules`, and `.env*`, and skips symlinks and
individual files larger than 50 MB. Inspect the staged file set so required
files are present and secrets are absent.

### Individual small files

Use `write` for an individual file of at most 10 MiB and pin the machine.
Files larger than 32 KiB are split into chunks automatically:

```bash
ifhost machines write \
  ./server.js \
  --to /data/app/server.js \
  --app <app-name> \
  --machine <machine-id>
```

### Private repository

Do not copy local Git credentials into the runner.

Use one of:

1. `machines push` when the source fits and the uploader is healthy.
2. A user-approved, short-lived signed artifact URL.
3. An existing public artifact only after every required file has been proven
   byte-identical to the approved local source.

If none is available, stop and report the transfer blocker. Do not weaken
repository access controls to finish the deployment.

### Hash-verified public artifact recovery

This is a recovery path, not the default.

1. Hash every required local file.
2. Fetch the corresponding public file and compare its hash locally.
3. Continue only if every file matches.
4. Download those files inside the runner.
5. Verify the same hash manifest inside the runner before starting.

Example:

```bash
local_hash=$(sha256sum ./assets/app.js | cut -d' ' -f1)
remote_hash=$(curl -fsSL https://trusted.example/assets/app.js | sha256sum | cut -d' ' -f1)
test "$local_hash" = "$remote_hash"
```

Do not infer equivalence from filenames, sizes, timestamps, or a few sampled
files.

## 6. Start the application

The process must outlive `machines exec`:

```bash
ifhost machines exec \
  --app <app-name> \
  --machine <machine-id> \
  -- sh -c "setsid nohup python3 -m http.server 8080 --bind 0.0.0.0 --directory /data/app > /tmp/app.log 2>&1 < /dev/null &"
```

Use the project's real start command. Bind to `0.0.0.0`, `::`, or another
non-loopback address.

The detached process survives the `machines exec` session, not a machine
restart. `machines env set` and `machines secrets set` stage changes without
restarting by default. If you pass `--restart`, run `machines restart`, apply a
change that restarts the machine, or redeploy, then:

1. Confirm the source and durable state still exist under `/data`.
2. Reinstall any missing system dependencies.
3. Run the start command again.
4. Repeat the public route checks below.

## 7. Verify the public routes

Test the health or root route first:

```bash
curl -sS -o /dev/null \
  -w "%{http_code} %{content_type} %{size_download}\n" \
  --max-time 30 \
  https://<app-name>.host.impossi.build/
```

Then test representative routes and important assets:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" --max-time 30 \
  https://<app-name>.host.impossi.build/docs/

curl -sS -o /dev/null -w "%{http_code}\n" --max-time 30 \
  https://<app-name>.host.impossi.build/assets/app.js
```

For a static site, verify at least:

- `/`
- one nested HTML route
- one JavaScript or CSS asset
- one large media asset, if present

Stop once the required health and route checks pass. Do not wait for unrelated
internal log messages.

## Failure recovery

| Symptom | Likely meaning | Action |
|---|---|---|
| `404 page not found` before creation | The app name is probably unassigned, but this is not an availability guarantee | Confirm by creating the app; handle `name already taken` explicitly |
| `name already taken` | App names are globally unique | Ask the user for another name |
| Deploy succeeds but URL fails | The runner exists but no app is listening | Install, transfer, start, and verify the process |
| Persistent `502` | No listener, wrong port, loopback-only bind, or crashed process | Check the configured port, bind address, process, and recent logs |
| `429 ... rate limit exceeded` | Too many machine API requests in the current window | Stop retrying, honor `Retry-After`, then reduce request count |
| `gzip: stdin: not in gzip format` | Uploaded archive may be incomplete or corrupt | Compare local and remote byte counts before retrying |
| `cannot stat ...partial` | The uploader reported a staging write that did not persist | Minimize to one small file and use a pinned `machines write` test |
| Session expired | Authentication is stale | Run `ifhost login`, then re-run `ifhost status` |

### Uploader incident observed on CLI build `20260723-124804`

The following is incident evidence, not a permanent API contract:

- The machine API allowed 20 exec requests per minute.
- An 8.6 MB `machines push` hit HTTP `429` at chunk `20/264`.
- A 38,733-byte compressed archive reached the VM as only its final
  6,957-byte chunk.
- An 11,253-byte text write succeeded.
- A 14,349-byte archive staging write disappeared before rename.
- The app had one machine, and marker files persisted across exec calls in
  `/tmp`, `/app`, and `/data`.

That evidence ruled out machine drift and a generally ephemeral filesystem.
It was consistent with a mismatch between the CLI's 32 KiB upload chunks and
a smaller effective command-transport limit, but did not prove that cause.

When these symptoms appear:

1. Update the CLI and retry one minimized file.
2. Do not repeatedly retry a large `push`; it compounds rate limiting.
3. Prefer an in-VM public clone or trusted artifact download.
4. For a private source, request an approved signed artifact instead of
   exposing credentials.
5. If using a pre-existing public artifact, require complete SHA-256
   equivalence before and after transfer.
6. If no safe transfer path remains, report the deployment as provisioned but
   not live.

## Handoff record

Capture:

```text
CLI build:
Account:
App:
URL:
Region:
Machine ID:
Deployment ID:
Machine specification:
Start command:
Health route and HTTP result:
Representative route results:
Source revision or hash manifest:
Repository worktree status:
Known follow-up:
```

Do not include secret values in the handoff.

## Cleanup

- Remove diagnostic markers and temporary remote archives.
- Leave application logs needed for later diagnosis.
- Confirm the source worktree has only the changes the user authorized.
- Do not destroy a working app as cleanup.
- Do not commit or push documentation or source changes until the user has
  reviewed and approved them.
