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

<!-- BEGIN VERIFIED CLI BOOTSTRAP -->
When `ifhost` is missing, do not execute either installer served by the release
origin. A compromise of that origin could replace the installer and the public
key embedded in it.
Instead, authenticate the signed release record with the public key committed
in [`release-signers`](release-signers), inspect the authenticated metadata,
verify the selected archive digest, and only then execute the CLI. Never
download or replace the trust anchor from the release origin.

On macOS or Linux:

```bash
set -eu
release_origin=https://host.impossibuild.ai
allowed_signer='ifhost ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEv+FR+Wibo0JJPEmmJfqQz2wsoBkrCLatDZ8XwZq2zJ'
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

case "$(uname -s):$(uname -m)" in
  Darwin:x86_64) archive=ifhost_darwin_amd64.tar.gz ;;
  Darwin:arm64|Darwin:aarch64) archive=ifhost_darwin_arm64.tar.gz ;;
  Linux:x86_64|Linux:amd64) archive=ifhost_linux_amd64.tar.gz ;;
  Linux:arm64|Linux:aarch64) archive=ifhost_linux_arm64.tar.gz ;;
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
[ "$contents" = ifhost ] || { echo "Release archive must contain only ifhost" >&2; exit 1; }
tar -xzf "$tmp/$archive" -C "$tmp"
[ -f "$tmp/ifhost" ] && [ ! -L "$tmp/ifhost" ] || {
  echo "Release binary is not a regular file" >&2; exit 1;
}
mkdir -p "$HOME/.local/bin"
install -m 0755 "$tmp/ifhost" "$HOME/.local/bin/ifhost"
export PATH="$HOME/.local/bin:$PATH"
ifhost version
ifhost skill sync
```

On Windows, run this in PowerShell with the OpenSSH Client capability enabled:

```powershell
$ErrorActionPreference = 'Stop'
$ReleaseOrigin = 'https://host.impossibuild.ai'
$AllowedSigner = 'ifhost ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEv+FR+Wibo0JJPEmmJfqQz2wsoBkrCLatDZ8XwZq2zJ'
$RawArch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
$Arch = switch ($RawArch) {
  'AMD64' { 'amd64' }
  'ARM64' { 'arm64' }
  default { throw "Unsupported architecture: $RawArch" }
}
$Archive = "ifhost_windows_$Arch.zip"
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
    if ($Files.Count -ne 1 -or $Files[0].FullName -cne 'ifhost.exe') {
      throw 'Release archive must contain only ifhost.exe'
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
  $InstallDir = Join-Path $env:LOCALAPPDATA 'ifhost'
  New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
  Move-Item -LiteralPath (Join-Path $Unpacked 'ifhost.exe') `
    -Destination (Join-Path $InstallDir 'ifhost.exe') -Force
  $env:Path = "$InstallDir;$env:Path"
  ifhost version
  ifhost skill sync
} finally {
  Remove-Item -LiteralPath $TempDir -Recurse -Force -ErrorAction SilentlyContinue
}
```
<!-- END VERIFIED CLI BOOTSTRAP -->

When `ifhost` already exists, skip the bootstrap and run `ifhost version`
followed by `ifhost skill sync`.

- If `skill sync` prints paths different from the files currently loaded,
  read the refreshed files before continuing. A signature or digest failure is a hard
  stop; do not use a partially updated bundle.
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
- Never put a secret value in argv, chat, or a tracked manifest. Make it
  available through an environment variable, a protected local file, or stdin,
  and pass `KEY=@env:NAME`, `KEY=@file:PATH`, or `KEY=@stdin` with
  `deploy --secret` or `machines secrets set`.
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
ifhost machines install --app <app-name> python3
```

Translate image-internal paths such as `/app` to the runner's durable
`/data/app` path.

`machines install` launches a detached package-manager worker, streams only
new log lines, waits for apt/dpkg locks, and verifies every requested package.
Rerun the same command if a transient request fails. Install all known
dependencies together instead of discovering them one failure at a time.
Only `/data` is durable storage; after a machine restart, confirm any runtime
installed elsewhere still exists before relaunching.

## 5. Transfer source

Choose the lowest-risk available method.

### Public repository or artifact

Downloading inside the VM remains useful when the source is already a trusted
public artifact:

```bash
ifhost machines exec \
  --app <app-name> \
  --machine <machine-id> \
  -- sh -c "git clone --depth 1 <public-repo-url> /data/app"
```

For release archives, use a trusted HTTPS URL and verify its checksum before
extracting it.

### Local source tree

Declare every path the running application owns before the first push:

```bash
printf '%s\n' 'state/data.db' 'uploads/' > .ifhost-state-paths
```

Paths are relative to the push target. An empty or missing declaration means
no runtime state is protected and produces a loud warning.

`push` spools a tarball locally, uploads verified 8 MiB chunks, resumes from
the last acknowledged chunk after interruption, verifies the complete archive
SHA-256, then replaces the target under a lock. There is no arbitrary total
archive cap; target free space is checked before upload. `push` does not accept
`--machine`:

```bash
ifhost machines push . --to /data/app --app <app-name> --yes-replace
```

`push` honors `.gitignore`, `.dockerignore`, and `.impignore`, applies built-in
exclusions such as `.git`, `node_modules`, and `.env*`, and skips symlinks and
individual files larger than 50 MB. Inspect the staged file set so required
files are present and secrets are absent. On redeploy, declared state paths are
snapshotted outside the target and restored byte-for-byte. Automatic rollback
is not claimed; if the transaction fails, stop and inspect the recovery paths
printed by the CLI.

### Individual small files

Use `write` for an individual file of at most 10 MiB and pin the machine.
It uses the same verified 8 MiB resumable chunks, verifies the complete file
beside the target, and performs a same-filesystem atomic rename:

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

1. `machines push` for a local source tree.
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
remote_hash=$(curl --fail --silent --show-error --location \
  --proto '=https' --proto-redir '=https' --tlsv1.2 \
  --connect-timeout 10 --max-time 60 --max-filesize 1048576 \
  https://trusted.example/assets/app.js | sha256sum | cut -d' ' -f1)
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
  https://<app-name>.host.impossibuild.ai/
```

Then test representative routes and important assets:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" --max-time 30 \
  https://<app-name>.host.impossibuild.ai/docs/

curl -sS -o /dev/null -w "%{http_code}\n" --max-time 30 \
  https://<app-name>.host.impossibuild.ai/assets/app.js
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
| `name already taken` | One name covers pages, apps and agents, so the holder may be any of the three, on any account including this one | Run `ifhost status` (apps and pages) and `ifhost agents list` first: if this account holds it, remove that or pick another name. Otherwise ask the user for a different name |
| Deploy succeeds but URL fails | The runner exists but no app is listening | Install, transfer, start, and verify the process |
| Persistent `502` | No listener, wrong port, loopback-only bind, or crashed process | Check the configured port, bind address, process, and recent logs |
| Upload reports a rate-limit wait | The CLI exhausted the current request window | Let its bounded wait/resume finish; do not start a second manual retry loop |
| `gzip: stdin: not in gzip format` | Uploaded archive may be incomplete or corrupt | Compare local and remote byte counts before retrying |
| Deterministic upload `400`/`409` | Identity, checksum, or cursor state is inconsistent | Do not retry-loop; report the exact error. The destination was not replaced |
| Transient upload fails after bounded retries | Network, SFTP, or remote commit stayed unavailable | Rerun the same command; acknowledged chunks are not retransmitted |
| Session expired | Authentication is stale | Run `ifhost login`, then re-run `ifhost status` |

### Current uploader recovery contract

The obsolete exec/base64 uploader and its 32 KiB chunks are no longer the
project-transfer path. Current `push` and non-empty `write` commands use raw,
verified 8 MiB chunks through an authenticated backend endpoint, which
transfers them to the machine. The checksum headers are integrity metadata
between the CLI and the ifhost backend; they are not secrets and are never
forwarded beyond it.

Safe recovery is branch-specific:

1. Interruption or exhausted transient failure: rerun the exact same command.
2. The CLI queries the remote cursor and skips acknowledged chunks.
3. A full checksum is mandatory before extraction or target replacement.
4. A deterministic identity/cursor/checksum rejection must be reported, not
   looped.
5. On successful push, tarball, cursor, and parts are removed; lock files may
   remain harmlessly.

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
