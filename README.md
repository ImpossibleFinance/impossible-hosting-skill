# ifhost Deployment Skill

A [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code) that teaches AI agents how to deploy apps using [Impossible Hosting](https://impossible-api.fly.dev).

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
curl -fsSL https://impossible-api.fly.dev/install | sh
```

Installs the `ifhost` binary to `~/.local/bin/`. Supports macOS and Linux (amd64/arm64).

If the script fails, download directly:

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
- Post-deploy management (logs, exec, console, scale, destroy)
- Full command reference with flags and examples

## Example agent interaction

```
User: Deploy this Node.js app

Agent: I'll deploy using ifhost.

$ ifhost init --app my-api --port 3000 --memory 512
$ ifhost deploy --env DATABASE_URL=postgres://...

Deployed! Live at: https://my-api.fly.dev
```

## Links

- [ifhost CLI](https://github.com/ImpossibleFinance/impossible-hosting)
- [Docs](https://impossible-api.fly.dev/docs)
- [llm.txt](https://impossible-api.fly.dev/llm.txt)
