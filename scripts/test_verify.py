#!/usr/bin/env python3
"""Regression tests for the public skill's release bootstrap policy."""

from __future__ import annotations

import contextlib
import io
import shutil
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

if __package__:
    from scripts import verify
else:
    import verify


class ReleaseBootstrapPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "skill"
        shutil.copytree(verify.ROOT, self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assert_rejected(self, check: Callable[[Path], None]) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            check(self.root)

    def replace(self, name: str, old: str, new: str) -> None:
        path = self.root / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def assert_rejected_when_appended(self, name: str, snippet: str) -> None:
        path = self.root / name
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(original + snippet, encoding="utf-8")
            self.assert_rejected(verify.verify_docs)
        finally:
            path.write_text(original, encoding="utf-8")

    def test_current_guidance_passes(self) -> None:
        verify.verify_metadata(self.root)
        verify.verify_docs(self.root)

    def test_substituted_trust_anchor_is_rejected(self) -> None:
        (self.root / "release-signers").write_text(
            verify.TRUST_ANCHOR[:-1] + "A\n", encoding="ascii"
        )
        self.assert_rejected(verify.verify_metadata)

    def test_multiline_curl_pipe_is_rejected(self) -> None:
        path = self.root / "README.md"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(
                "\n```bash\n"
                "curl --fail https://innstance.impossibuild.ai/install \\\n"
                "  | sh\n"
                "```\n"
            )
        self.assert_rejected(verify.verify_docs)

    def test_downloaded_installer_execution_is_rejected(self) -> None:
        path = self.root / "README.md"
        with path.open("a", encoding="utf-8") as stream:
            stream.write('\n```bash\nsh "$installer"\n```\n')
        self.assert_rejected(verify.verify_docs)

    def test_missing_signature_verification_is_rejected(self) -> None:
        self.replace("SKILL.md", "ssh-keygen -Y verify", "ssh-keygen -Y find-principals")
        self.assert_rejected(verify.verify_docs)

    def test_digest_gate_must_precede_extraction(self) -> None:
        self.replace(
            "SKILL.md",
            '[ "$actual" = "$expected" ] ||',
            '[ "$actual" != "$expected" ] ||',
        )
        self.assert_rejected(verify.verify_docs)


    def test_non_product_release_channel_is_rejected(self) -> None:
        path = self.root / "SECURITY.md"
        with path.open("a", encoding="utf-8") as stream:
            stream.write("\nFetch https://downloads.example/release.txt.\n")
        self.assert_rejected(verify.verify_docs)

    def test_spellings_the_cli_lacks_are_rejected(self) -> None:
        cases = (
            ("panel password reset", "SKILL.md",
             "\nRun `innstance agents panel my-agent --reset-password`.\n"),
            ("logs follow flag", "RUNBOOK.md",
             "\nWatch with `innstance machines logs --app my-app --follow`.\n"),
            ("literal login token", "README.md",
             "\n```bash\ninnstance login --token abc123\n```\n"),
        )
        for label, name, snippet in cases:
            with self.subTest(label):
                self.assert_rejected_when_appended(name, snippet)

    def test_unsafe_mcp_and_npx_guidance_is_rejected(self) -> None:
        cases = (
            ("MCP endpoint on a tenant address", "SKILL.md",
             "\nConnect to https://my-app.innstance.app/mcp instead.\n"),
            ("MCP endpoint on another origin", "SECURITY.md",
             "\nThe MCP server also answers at https://mcp.example/mcp.\n"),
            ("literal bearer token", "README.md",
             '\n```json\n{"headers": {"Authorization": "Bearer abc123"}}\n```\n'),
            ("a similarly named npm package", "RUNBOOK.md",
             "\n```bash\nnpx --yes innstance-cli\n```\n"),
            ("the old command name on npm", "SKILL.md",
             "\nOr run `npx ifhost` instead.\n"),
        )
        for label, name, snippet in cases:
            with self.subTest(label):
                self.assert_rejected_when_appended(name, snippet)

    def test_guides_lead_with_mcp_and_npx(self) -> None:
        for name in verify.BOOTSTRAP_DOCS:
            for way_in in (verify.MCP_ENDPOINT, verify.NPX_COMMAND):
                with self.subTest(name=name, way_in=way_in):
                    path = self.root / name
                    original = path.read_text(encoding="utf-8")
                    try:
                        # Mentioned only after the CLI bootstrap: the CLI leads.
                        moved = original.replace(way_in, "the other way in")
                        path.write_text(moved + f"\nSee {way_in}.\n", encoding="utf-8")
                        self.assert_rejected(verify.verify_docs)
                    finally:
                        path.write_text(original, encoding="utf-8")

    def test_idle_scaling_promises_are_rejected(self) -> None:
        cases = (
            ("scale-to-zero by default", "README.md",
             "\nApps scale to zero by default, so an idle app costs nothing.\n"),
            ("hyphenated scale-to-zero", "SKILL.md",
             "\n- Infra: lightweight VMs with scale-to-zero.\n"),
            ("sleeping when idle", "RUNBOOK.md",
             "\nA new app sleeps when idle and wakes on the next request.\n"),
        )
        for label, name, snippet in cases:
            with self.subTest(label):
                self.assert_rejected_when_appended(name, snippet)

    def test_windows_bootstrap_without_wsl_is_rejected(self) -> None:
        # Changed identically in every guide, so only the WSL rule can object.
        for name in verify.BOOTSTRAP_DOCS:
            self.replace(
                name,
                "run the macOS/Linux block above\ninside WSL.",
                "run the macOS/Linux block above\non another machine.",
            )
        self.assert_rejected(verify.verify_docs)

    def test_public_bootstrap_drift_is_rejected(self) -> None:
        self.replace(
            "RUNBOOK.md",
            "inspect the authenticated metadata",
            "review the authenticated metadata",
        )
        self.assert_rejected(verify.verify_docs)


if __name__ == "__main__":
    unittest.main()
