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

## What the agent learns

- How to install and authenticate with ifhost
- How to configure machine specs (`ifhost init`)
- How to deploy (`ifhost deploy`)
- Common patterns (static sites, APIs, heavy apps)
- Traps to avoid (port mismatch, OOM, autostop, env vars)
- Post-deploy management (logs, exec, stop, destroy)

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
