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

## Install the CLI

```bash
installer="$(mktemp)"
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --tlsv1.2 --connect-timeout 10 --max-time 60 --max-filesize 1048576 \
  https://host.impossibuild.ai/install -o "$installer"
cat "$installer"                   # inspect the complete file before execution
sh "$installer"
rm -f "$installer"
```

Installs the `ifhost` binary to `~/.local/bin/`. Supports macOS, Linux and
Windows, on both Intel/AMD (x86-64) and ARM.

On Windows, run this in PowerShell instead:

```powershell
$installer = Join-Path ([IO.Path]::GetTempPath()) "ifhost-install-$([guid]::NewGuid()).ps1"
Invoke-WebRequest -Uri https://host.impossibuild.ai/install.ps1 `
  -MaximumRedirection 0 -TimeoutSec 60 -OutFile $installer
Get-Content $installer                # inspect before executing downloaded code
& $installer
Remove-Item $installer
```
The CLI checks hourly, verifies independently signed release metadata and the
artifact digest, updates atomically, and re-runs the requested command. Set
`IFHOST_AUTO_UPDATE=0` to pin a version.

Refresh the agent instructions with:

```bash
ifhost skill sync
```

This verifies `SKILL.md` and `RUNBOOK.md` before replacing the local cached
copies under `~/.impossible/skill/`.

If the installer fails, do not bypass its signature check with a direct
archive pipe. Follow the signed manual-download procedure in the
[`impossible-hosting-cli` repository](https://github.com/ImpossibleFinance/impossible-hosting-cli#manual-download).

Then add to PATH if needed:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

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

- [ifhost CLI](https://github.com/ImpossibleFinance/impossible-hosting)
- [Runner deployment runbook](./RUNBOOK.md)
- [Docs](https://host.impossibuild.ai/docs)
- [llm.txt](https://host.impossibuild.ai/llm.txt)
