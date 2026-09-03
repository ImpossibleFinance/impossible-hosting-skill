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
                "curl --fail https://host.impossibuild.ai/install \\\n"
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

    def test_public_bootstrap_drift_is_rejected(self) -> None:
        self.replace(
            "RUNBOOK.md",
            "inspect the authenticated metadata",
            "review the authenticated metadata",
        )
        self.assert_rejected(verify.verify_docs)


if __name__ == "__main__":
    unittest.main()
