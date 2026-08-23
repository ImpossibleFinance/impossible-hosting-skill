#!/usr/bin/env python3
"""Fail closed when the ifhost skill drifts into unsafe or stale guidance."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ("README.md", "RUNBOOK.md", "SKILL.md")


def fail(message: str) -> None:
    print(f"verify: {message}", file=sys.stderr)
    raise SystemExit(1)


def verify_metadata() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest) != {"version"}:
        fail("manifest.json must contain only version")
    if not re.fullmatch(r"[0-9]{8}-[1-9][0-9]*", manifest["version"]):
        fail("manifest version must be YYYYMMDD-N")

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not skill.startswith("---\n") or "\nname: ifhost\n" not in skill[:500]:
        fail("SKILL.md must carry ifhost front matter")


def verify_docs() -> None:
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
    tenant_on_control_domain = re.compile(
        r"(?:<[^>\s]+>|[A-Za-z0-9_-]+)\.host\.impossibuild\.ai",
        re.I,
    )

    for name in DOCS:
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if line.rstrip() != line:
                fail(f"{name}:{number}: trailing whitespace")
            for match in secret_command.finditer(line):
                if not safe_secret.fullmatch(match.group(1)):
                    fail(f"{name}:{number}: literal secret example is forbidden")
            token_login = re.search(r"ifhost\s+login\s+--token(?:=|\s+)([^\s`|]+)", line)
            if token_login and token_login.group(1) != "-":
                fail(f"{name}:{number}: token must come from stdin or --from-file")
            if re.search(r"machines\s+secrets\s+set.*--from-file", line):
                fail(f"{name}:{number}: secrets set uses KEY=@file:PATH, not --from-file")
            if re.search(r"/dl/ifhost_[^|\s]+\s*\|\s*(?:tar|unzip)", line):
                fail(f"{name}:{number}: direct unsigned archive pipe is forbidden")
            if re.search(r"https://host\.(?:impossi\.build|impossibuild\.ai)/install(?:\.ps1)?\s*\|\s*(?:sh|bash|iex)", line, re.I):
                fail(f"{name}:{number}: download the installer completely and inspect it before execution")
            if "https://host.impossi.build/install" in line:
                fail(f"{name}:{number}: installer must use the separated control-plane domain")
            if tenant_on_control_domain.search(line):
                fail(f"{name}:{number}: tenant URL must not reuse the control-plane registrable domain")
            if re.search(r"\bcurl\b.*https://", line) and "--max-time" not in line and not line.endswith("\\"):
                fail(f"{name}:{number}: one-line HTTP examples need a hard deadline")
            if any(pattern.search(line) for pattern in pricing):
                fail(f"{name}:{number}: plan price or allowance must come from the live API")

        for match in relative_link.finditer(text):
            target = (path.parent / match.group(1)).resolve()
            if ROOT not in target.parents and target != ROOT:
                fail(f"{name}: relative link escapes the repository: {match.group(1)}")
            if not target.exists():
                fail(f"{name}: broken relative link: {match.group(1)}")


def main() -> None:
    verify_metadata()
    verify_docs()
    print("verified skill metadata, links, and security guidance")


if __name__ == "__main__":
    main()
