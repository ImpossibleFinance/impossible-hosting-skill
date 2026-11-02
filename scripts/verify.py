#!/usr/bin/env python3
"""Fail closed when the ifhost skill drifts into unsafe or stale guidance."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ("README.md", "RUNBOOK.md", "SECURITY.md", "SKILL.md")
BOOTSTRAP_DOCS = ("README.md", "RUNBOOK.md", "SKILL.md")
BOOTSTRAP_BEGIN = "<!-- BEGIN VERIFIED CLI BOOTSTRAP -->"
BOOTSTRAP_END = "<!-- END VERIFIED CLI BOOTSTRAP -->"
RELEASE_ORIGIN = "https://innstance.impossibuild.ai"
# The MCP server lives on the control plane, a different registrable domain
# from the tenant suffix, so no customer app can stand in for it. The public
# guides lead with it and with npx; the CLI bootstrap comes after both.
MCP_ENDPOINT = RELEASE_ORIGIN + "/mcp"
# Any address whose path starts with /mcp names an MCP endpoint, with or
# without a scheme. A trailing slash, a subpath, plain http or a tenant host is
# exactly how a lookalike would slip in, so only the endpoint spelled as
# MCP_ENDPOINT may appear.
MCP_ADDRESS = re.compile(
    r"(?:\b[A-Za-z][A-Za-z0-9+.-]*://)?"
    r"\b(?:localhost|[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?::[0-9]+)?"
    r"/mcp[^\s`'\"()<>\[\]{}]*",
    re.I,
)
NPX_COMMAND = "npx innstance"
# What npx may run: the innstance package, optionally at a version the agent
# has just checked. Every package runner counts, not only npx, and the only
# flag allowed is --yes: --package, --registry and --userconfig each change
# what actually runs.
NPX_PACKAGE = re.compile(r"innstance(?:@(?:[0-9A-Za-z.+-]+|<version>))?")
PACKAGE_RUNNER = re.compile(
    r"(?<![\w-])(?:npx|pnpx|bunx|(?:pnpm|yarn|bun)\s+dlx|npm\s+(?:exec|x)|bun\s+x)\b"
    r"((?:[ \t]+[^\s`]+)*)",
    re.I,
)
NPX_ALLOWED_FLAGS = frozenset({"--yes", "-y"})
# The platform's API tokens start with imp_. None belongs in a guide, and an
# Innstance token variable is only ever assigned from another expansion.
TOKEN_LITERAL = re.compile(r"\bimp_[0-9A-Za-z]{8,}")
TOKEN_ASSIGNMENT = re.compile(
    r"\b(?:INNSTANCE|IFHOST|IMPOSSIBLE_API)_TOKEN\b[\"']?\s*[:=]\s*[\"']?([^\s\"'`,}]*)"
)
BEARER_VALUE = re.compile(r"\bBearer\s+([^\s\"'`]+)", re.I)
TRUST_ANCHOR = (
    "ifhost ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIEv+FR+Wibo0JJPEmmJfqQz2wsoBkrCLatDZ8XwZq2zJ"
)
# Spellings the skill once taught that the CLI never accepted. Each one sent
# agents into an "unknown flag" loop; the reason names what the CLI does
# instead, so the failure message is the fix.
NONEXISTENT_SPELLINGS = (
    (
        re.compile(r"--reset-password\b"),
        "agents panel has no --reset-password; the owner reveals the password once "
        "(--show-password or the dashboard) and changes it in the panel",
    ),
    (
        re.compile(r"machines\s+logs\b[^\n`]*--follow\b"),
        "machines logs has no --follow; it streams by default until stopped",
    ),
)
# Apps are always-on unless the user opts into autostop, and a runner app does
# not survive an idle stop. Scaling to zero or sleeping when idle may appear
# only where the sentence itself denies it: a negation directly before the
# phrase ("do not scale to zero"), or the phrase directly followed by "is not
# the default" or "is opt-in". A "no" or "not" elsewhere in the sentence does
# not count; "scale to zero by default, no setup" is still a promise.
#
# Delete this rule when a sleeping default ships (the supervisor and idle
# sleep, P2/P3 in the plan); the docs will then have to say it.
IDLE_PROMISE = re.compile(
    r"\bscal(?:e|es|ed|ing)(?:[-\s]+(?:down|back))?[-\s]+to[-\s]+(?:zero|0)\b"
    r"|\b(?:sleeps?|sleeping|spins?[-\s]+down|suspends?)\s+(?:when|while|if)\s+"
    r"(?:it\s+is\s+|it's\s+)?idle\b",
    re.I,
)
IDLE_DENIED_BEFORE = re.compile(r"(?:\bnot|\bnever|n't|\bno\s+longer)\s+(?:\w+\s+)?$", re.I)
IDLE_DENIED_AFTER = re.compile(
    r"^\s+(?:is|are)\s+(?:not\s+(?:the\s+)?default|opt-in|off\s+by\s+default)\b", re.I
)


def fail(message: str) -> None:
    print(f"verify: {message}", file=sys.stderr)
    raise SystemExit(1)


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def logical_lines(text: str) -> list[tuple[int, str]]:
    """Each line, with backslash-continued lines joined onto the first."""
    joined: list[tuple[int, str]] = []
    pending: tuple[int, str] | None = None
    for number, line in enumerate(text.splitlines(), 1):
        if pending is not None:
            number, line = pending[0], pending[1] + " " + line.lstrip()
            pending = None
        if line.endswith("\\"):
            pending = (number, line[:-1].rstrip())
            continue
        joined.append((number, line))
    if pending is not None:
        joined.append(pending)
    return joined


def package_runner_problem(arguments: str) -> str | None:
    """Why a package-runner invocation is not exactly the innstance package."""
    for word in arguments.split():
        word = word.strip("\"'")
        if word.startswith("-"):
            if word not in NPX_ALLOWED_FLAGS:
                return f"never with {word!r}, which can change what runs"
            continue
        package = word.rstrip(".,;:!?)")
        if NPX_PACKAGE.fullmatch(package):
            return None
        return f"never {package!r}"
    return None


def verify_metadata(root: Path = ROOT) -> None:
    root = root.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest) != {"version"}:
        fail("manifest.json must contain only version")
    if not re.fullmatch(r"[0-9]{8}-[1-9][0-9]*", manifest["version"]):
        fail("manifest version must be YYYYMMDD-N")

    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    if not skill.startswith("---\n") or "\nname: innstance\n" not in skill[:500]:
        fail("SKILL.md must carry innstance front matter")
    # Rule 0 compares this copy with what `innstance skill sync` installs, so
    # an agent that read a newer guide is not walked back to the CLI's older
    # pin. That only works while the file states the manifest's version.
    if f"This copy is version `{manifest['version']}`." not in skill:
        fail(f"SKILL.md must say \"This copy is version `{manifest['version']}`.\" "
             "to match manifest.json")

    anchor_path = root / "release-signers"
    if not anchor_path.is_file() or anchor_path.is_symlink():
        fail("release-signers must be a regular file")
    if anchor_path.read_text(encoding="ascii") != TRUST_ANCHOR + "\n":
        fail("release-signers must contain exactly the reviewed ifhost trust anchor")


def verify_docs(root: Path = ROOT) -> None:
    root = root.resolve()
    secret_command = re.compile(
        r"(?:--secret|machines\s+secrets\s+set)\s+"
        r"[A-Z][A-Z0-9_]*=([^\s`|\\]+)"
    )
    safe_secret = re.compile(r"@(?:env:[A-Za-z_][A-Za-z0-9_]*|file:.+|stdin)$")
    relative_link = re.compile(r"\]\((?!https?://|#|mailto:)([^)#]+)(?:#[^)]+)?\)")
    pricing = (
        re.compile(r"\$[0-9]+(?:\.[0-9]+)?\s*/\s*(?:mo|month|GB)"),
        re.compile(r"[0-9]+\s*(?:MB|GB|TB)\s+(?:RAM|volume)\s+pool", re.I),
        re.compile(r"[0-9]+\s*GB\s+(?:on|for)\s+(?:free|hobby|pro|team)", re.I),
    )
    remote_pipe = re.compile(
        r"\b(?:curl|wget)\b[^\n]*(?:\\\n[^\n]*)*\|\s*(?:sh|bash|tar|unzip)\b",
        re.I,
    )
    installer_url = re.compile(
        r"https://[^\s`'\"()]+/install(?:\.sh|\.ps1)?"
        r"(?:[/?#.,;:\s`'\"()]|$)",
        re.I,
    )
    installer_execution = re.compile(
        r"(?im)^\s*(?:(?:sh|bash|powershell|pwsh)(?:\s+-File)?\s+[\"']?"
        r"\$(?:installer|download(?:ed)?)\b|[&.]\s*[\"']?"
        r"\$(?:installer|download(?:ed)?)\b|Start-Process(?:\s+-FilePath)?\s+"
        r"[\"']?\$(?:installer|download(?:ed)?)\b)"
    )
    release_resource = re.compile(
        r"https://[^\s`'\"()]+/(?:release\.txt(?:\.sshsig)?|(?:innstance|ifhost)_[^\s`'\"()]+)",
        re.I,
    )
    required_bootstrap = (
        RELEASE_ORIGIN,
        "$release_origin/dl/release.txt",
        "$release_origin/dl/release.txt.sshsig",
        "$release_origin/dl/$archive",
        "$ReleaseOrigin/dl/release.txt",
        "$ReleaseOrigin/dl/release.txt.sshsig",
        "$ReleaseOrigin/dl/$Archive",
        "ssh-keygen -Y verify",
        "Get-Command ssh-keygen",
        "sha256sum",
        "Get-FileHash",
    )
    ordered_bootstrap = {
        "bash": (
            f"release_origin={RELEASE_ORIGIN}",
            '"$release_origin/dl/release.txt"',
            '"$release_origin/dl/release.txt.sshsig"',
            "ssh-keygen -Y verify",
            'cat "$tmp/release.txt"',
            'expected=$(signed_value "artifact.$archive")',
            '"$release_origin/dl/$archive"',
            '[ "$actual" = "$expected" ] ||',
            'contents=$(tar -tzf "$tmp/$archive")',
            'tar -xzf "$tmp/$archive"',
            'install -m 0755 "$tmp/innstance"',
            "innstance version",
        ),
        "powershell": (
            f"$ReleaseOrigin = '{RELEASE_ORIGIN}'",
            '"$ReleaseOrigin/dl/release.txt"',
            '"$ReleaseOrigin/dl/release.txt.sshsig"',
            "[void]$Process.Start()",
            "if ($Process.ExitCode -ne 0) { throw",
            "Get-Content -LiteralPath $ReleasePath",
            'Get-SignedValue $Lines "artifact.$Archive"',
            '"$ReleaseOrigin/dl/$Archive"',
            "Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256",
            "if ($Actual -cne $Expected) { throw",
            "[IO.Compression.ZipFile]::OpenRead($ZipPath)",
            "Expand-Archive -LiteralPath $ZipPath",
            "Move-Item -LiteralPath",
            "innstance version",
        ),
    }

    canonical_bootstrap: str | None = None


    for name in DOCS:
        path = root / name
        text = path.read_text(encoding="utf-8")
        if remote_pipe.search(text):
            fail(f"{name}: remote downloads must never pipe into an interpreter or extractor")
        if installer_url.search(text):
            fail(f"{name}: release-origin installers are not an authenticated bootstrap")
        if installer_execution.search(text) or re.search(r"\b(?:Invoke-Expression|iex)\b", text, re.I):
            fail(f"{name}: downloaded installer execution is forbidden")
        for match in release_resource.finditer(text):
            if not match.group(0).startswith(RELEASE_ORIGIN + "/dl/"):
                fail(f"{name}: release resources must use the active {RELEASE_ORIGIN}/dl channel")
        for match in MCP_ADDRESS.finditer(text):
            address = match.group(0).rstrip(".,;:!?")
            if address != MCP_ENDPOINT:
                fail(f"{name}:{line_of(text, match.start())}: the MCP server is "
                     f"{MCP_ENDPOINT} on the control plane, never {address}")
        for match in TOKEN_LITERAL.finditer(text):
            fail(f"{name}:{line_of(text, match.start())}: an API token value never "
                 "appears in the guides")
        for match in IDLE_PROMISE.finditer(text):
            if not (IDLE_DENIED_BEFORE.search(text[max(0, match.start() - 40):match.start()])
                    or IDLE_DENIED_AFTER.match(text[match.end():match.end() + 40])):
                fail(f"{name}:{line_of(text, match.start())}: apps are always-on by default; "
                     "never promise scale-to-zero or sleeping when idle")
        # A command continued with a trailing backslash is one command, so a
        # flag on the next line still belongs to it.
        for number, logical in logical_lines(text):
            for pattern, reason in NONEXISTENT_SPELLINGS:
                if pattern.search(logical):
                    fail(f"{name}:{number}: {reason}")
            token_login = re.search(
                r"(?:innstance|ifhost)\s+login\s+--token(?:=|\s+)([^\s`|]+)", logical
            )
            if token_login and token_login.group(1) != "-":
                fail(f"{name}:{number}: token must come from stdin or --from-file")
            for match in PACKAGE_RUNNER.finditer(logical):
                problem = package_runner_problem(match.group(1))
                if problem:
                    fail(f"{name}:{number}: npx runs only the innstance package; {problem}")

        if name in BOOTSTRAP_DOCS:
            if text.count(BOOTSTRAP_BEGIN) != 1 or text.count(BOOTSTRAP_END) != 1:
                fail(f"{name}: expected exactly one verified CLI bootstrap")
            for way_in in (MCP_ENDPOINT, NPX_COMMAND):
                position = text.find(way_in)
                if position < 0 or position > text.index(BOOTSTRAP_BEGIN):
                    fail(f"{name}: lead with {way_in} before the CLI bootstrap; "
                         "the CLI is the power-user path")
            bootstrap = text.split(BOOTSTRAP_BEGIN, 1)[1].split(BOOTSTRAP_END, 1)[0]
            for required in required_bootstrap:
                if required not in bootstrap:
                    fail(f"{name}: verified CLI bootstrap is missing {required!r}")
            if bootstrap.count(TRUST_ANCHOR) != 2:
                fail(f"{name}: both platform bootstraps must pin the repository trust anchor")
            for language, sequence in ordered_bootstrap.items():
                match = re.search(
                    rf"```{language}\n(.*?)\n```",
                    bootstrap,
                    re.S,
                )
                if match is None:
                    fail(f"{name}: verified CLI bootstrap is missing its {language} flow")
                position = -1
                for required in sequence:
                    position = match.group(1).find(required, position + 1)
                    if position < 0:
                        fail(
                            f"{name}: {language} bootstrap must verify before "
                            f"extracting or executing; missing ordered step {required!r}"
                        )
            if re.search(r"ssh-keygen -Y verify[\s\S]{0,200}\|\|\s*true", bootstrap):
                fail(f"{name}: SSHSIG verification must not be bypassed")
            # The native Windows binary is optional: Windows readers meet WSL
            # before the PowerShell flow, never the executable as the only way.
            wsl = bootstrap.find("inside WSL")
            if wsl < 0 or wsl > bootstrap.find("```powershell"):
                fail(f"{name}: offer the CLI inside WSL before the optional native Windows binary")
            if canonical_bootstrap is None:
                canonical_bootstrap = bootstrap
            elif bootstrap != canonical_bootstrap:
                fail(f"{name}: verified CLI bootstrap drifted from the other public guides")

        fence_language: str | None = None
        for number, line in enumerate(text.splitlines(), 1):
            if line.rstrip() != line:
                fail(f"{name}:{number}: trailing whitespace")
            if line.startswith("```"):
                if fence_language is None:
                    fence_language = line[3:].strip()
                else:
                    fence_language = None
                continue
            if fence_language in {"bash", "powershell", "toml", "dockerfile"} and line.startswith("**"):
                fail(f"{name}:{number}: markdown prose is trapped inside a {fence_language} code fence")
            for match in secret_command.finditer(line):
                if not safe_secret.fullmatch(match.group(1)):
                    fail(f"{name}:{number}: literal secret example is forbidden")
            for match in BEARER_VALUE.finditer(line):
                value = match.group(1)
                # "a bearer token" is the phrase, not a value.
                if value.lower().rstrip(".,;:)") in {"token", "tokens"}:
                    continue
                if not value.startswith("${"):
                    fail(f"{name}:{number}: an MCP bearer token comes from an environment "
                         "variable the client expands, never a value in the file")
            for match in TOKEN_ASSIGNMENT.finditer(line):
                if not match.group(1).startswith("$"):
                    fail(f"{name}:{number}: an Innstance token variable is set from another "
                         "expansion or by the user, never to a value written here")
            if re.search(r"machines\s+secrets\s+set.*--from-file", line):
                fail(f"{name}:{number}: secrets set uses KEY=@file:PATH, not --from-file")
            if re.search(r"https://<?[A-Za-z0-9_-]+>?\.host\.(impossi\.build|impossibuild\.ai)", line) and not re.search(r"alias|legacy|pre-move|formerly|retired", line, re.I):
                fail(f"{name}:{number}: published guidance hands out tenant addresses on innstance.app; "
                     "host.impossibuild.ai and host.impossi.build are retired suffixes that only redirect old "
                     "URLs, never a name we publish - mark the line as legacy if it must appear")
            if re.search(r"\bcurl\b.*https://", line) and "--max-time" not in line and not line.endswith("\\"):
                fail(f"{name}:{number}: one-line HTTP examples need a hard deadline")
            if any(pattern.search(line) for pattern in pricing):
                fail(f"{name}:{number}: plan price or allowance must come from the live API")

        if fence_language is not None:
            fail(f"{name}: unclosed {fence_language or 'plain'} code fence")

        for match in relative_link.finditer(text):
            target = (path.parent / match.group(1)).resolve()
            if root not in target.parents and target != root:
                fail(f"{name}: relative link escapes the repository: {match.group(1)}")
            if not target.exists():
                fail(f"{name}: broken relative link: {match.group(1)}")


def main() -> None:
    verify_metadata()
    verify_docs()
    print("verified skill metadata, links, and security guidance")


if __name__ == "__main__":
    main()
