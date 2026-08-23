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
curl -fsSL https://host.impossibuild.ai/install | sh
```

Installs the `ifhost` binary to `~/.local/bin/`. Supports macOS, Linux and
Windows, on both Intel/AMD (x86-64) and ARM.

On Windows, run this in PowerShell instead:

```powershell
irm https://host.impossibuild.ai/install.ps1 | iex
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
$ ifhost deploy --env DATABASE_URL=postgres://...

Deployed! Live at: https://my-api.host.impossibuild.ai
```

## Links

- [ifhost CLI](https://github.com/ImpossibleFinance/impossible-hosting)
- [Runner deployment runbook](./RUNBOOK.md)
- [Docs](https://host.impossibuild.ai/docs)
- [llm.txt](https://host.impossibuild.ai/llm.txt)
