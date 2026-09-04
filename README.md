# ifhost Deployment Skill

A [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code) that teaches AI agents how to deploy apps using [Impossible Hosting](https://host.impossibuild.ai).

## Usage

Add to your Claude Code project's `.claude/settings.json`:

```json
{
  "skills": ["ImpossibleFinance/impossible-hosting-skill"]
}
```

Or reference directly in a prompt:

```
Use the ifhost skill to deploy this project.
```

## Install the CLI from the signed release channel

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

The CLI checks hourly, verifies independently signed release metadata and the
artifact digest, updates atomically, and re-runs the requested command. Set
`IFHOST_AUTO_UPDATE=0` to pin a version.

If verification fails, stop. Do not fall back to an installer, an unsigned
archive, a checksum downloaded without its signed release record, or a
different public key.

The bootstrap adds the install directory to the current process PATH. Add
`~/.local/bin` (macOS/Linux) or `%LOCALAPPDATA%\ifhost` (Windows) to the user
PATH to make `ifhost` available in future terminals.

## What the agent learns

- How to install and authenticate with ifhost
- How to configure machine specs (`ifhost init`)
- How to deploy (`ifhost deploy`)
- Common patterns (static sites, APIs, heavy apps, interactive setup)
- Non-blocking log monitoring via tmux console
- Traps to avoid (port mismatch, OOM, autostop, env vars)
- Post-deploy management (logs, exec, console, apply, destroy)
- Full command reference with flags and examples

## Example agent interaction

```
User: Deploy this Node.js app

Agent: I'll deploy using ifhost.

$ ifhost init --app my-api --port 3000 --memory 512
$ ifhost deploy --secret DATABASE_URL=@env:DATABASE_URL
$ ifhost machines push . --to /data/app --app my-api --yes-replace
$ ifhost machines exec --app my-api -- sh -c "cd /data/app && setsid nohup <start-command> </dev/null > /tmp/app.log 2>&1 &"
$ curl --fail --silent --show-error --max-time 30 https://my-api.host.impossibuild.ai/

Agent: The app returned HTTP 200 and is live at https://my-api.host.impossibuild.ai
```

## Links

- [ifhost CLI source](https://github.com/ImpossibleFinance/impossible-hosting)
- [Repository release trust anchor](./release-signers)
- [Runner deployment runbook](./RUNBOOK.md)
- [Docs](https://host.impossibuild.ai/docs)
- [llm.txt](https://host.impossibuild.ai/llm.txt)
