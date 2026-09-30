import base64
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish


def manifest():
    return {"version": "0.1.1", "tag": "v0.1.1", "source_sha": "a" * 40,
            "filename": "pr-sniper-0.1.1-aarch64-apple-darwin.zip", "sha256": "b" * 64,
            "architecture": "arm64", "bundle_id": publish.BUNDLE, "team_id": "ABCDEFGHIJ",
            "notarization_id": "00000000-0000-0000-0000-000000000001"}


class PublisherTests(unittest.TestCase):
    def test_workflows_authenticate_both_metadata_and_homebrew_requests(self):
        root = Path(__file__).resolve().parents[1]
        for workflow in ("cask.yml", "publish.yml"):
            content = (root / ".github/workflows" / workflow).read_text()
            self.assertIn("GITHUB_TOKEN: ${{ github.token }}", content)
            self.assertIn("HOMEBREW_GITHUB_API_TOKEN: ${{ github.token }}", content)

    def test_native_verification_does_not_inherit_api_tokens(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-one", "HOMEBREW_GITHUB_API_TOKEN": "synthetic-two"}), \
                patch.object(publish.subprocess, "run") as native:
            native.return_value.returncode = 0
            native.return_value.stdout = b"ok"
            publish.native(["codesign", "--verify", "fixture"])
            self.assertNotIn("GITHUB_TOKEN", native.call_args.kwargs["env"])
            self.assertNotIn("HOMEBREW_GITHUB_API_TOKEN", native.call_args.kwargs["env"])

    def test_github_metadata_reads_use_scoped_token_but_downloads_do_not(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-api-token"}), \
                patch.object(publish.urllib.request, "build_opener") as opener, \
                patch.object(publish.json, "load", return_value={}):
            publish.api(f"/repos/{publish.SOURCE}/releases/tags/v0.1.1")
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-api-token")
            self.assertEqual(request.full_url, f"https://api.github.com/repos/{publish.SOURCE}/releases/tags/v0.1.1")
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-api-token"}), \
                patch.object(publish.urllib.request, "urlopen") as download:
            response = download.return_value.__enter__.return_value
            response.url = "https://release-assets.githubusercontent.com/fixture"
            response.read.side_effect = [b"fixture", b""]
            url = f"https://github.com/{publish.SOURCE}/releases/download/v0.1.1/file.zip"
            publish.download(url, Path(root) / "file.zip", 7)
            self.assertEqual(download.call_args.args, (url,))
            self.assertNotIn("headers", download.call_args.kwargs)

    def test_forbidden_api_response_is_classified_without_leaking_body_or_token(self):
        for headers, category in [({"X-RateLimit-Remaining": "0"}, "rate-limited"), ({}, "forbidden")]:
            error = urllib.error.HTTPError("https://api.github.com", 403, "private body", headers, None)
            with patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-api-token"}), \
                    patch.object(publish.urllib.request, "build_opener") as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(publish.Failure) as result:
                    publish.api(f"/repos/{publish.SOURCE}/releases/tags/v0.1.1")
                self.assertIn(category, str(result.exception))
                self.assertNotIn("private body", str(result.exception))
                self.assertNotIn("synthetic-api-token", str(result.exception))

    def test_existing_cask_matches_the_publisher_format(self):
        content = (Path(__file__).resolve().parents[1] / "Casks/pr-sniper.rb").read_text()
        tag = "v" + re.search(r'^  version "([^"]+)"$', content, re.M)[1]
        digest = re.search(r'^  sha256 "([^"]+)"$', content, re.M)[1]
        self.assertEqual(content, publish.cask({"tag": tag, "sha256": digest}))

    def test_manifest_requires_exact_release_commit_architecture_and_team(self):
        value = manifest()
        publish.manifest_check(value, "v0.1.1", "a" * 40, "ABCDEFGHIJ")
        for key, bad in [("source_sha", "c" * 40), ("version", "0.1.2"), ("architecture", "x86_64"),
                         ("team_id", "OTHERTEAM0"), ("bundle_id", "other"), ("filename", "../escape"),
                         ("sha256", ""), ("notarization_id", "unknown")]:
            with self.subTest(key=key), self.assertRaises(publish.Failure):
                publish.manifest_check({**value, key: bad}, "v0.1.1", "a" * 40, "ABCDEFGHIJ")

    def test_cask_data_cannot_inject_ruby_and_preserves_update_ownership(self):
        value = manifest()
        cask = publish.cask(value)
        self.assertIn("depends_on arch: :arm64", cask)
        self.assertNotIn("auto_updates", cask)
        self.assertNotIn("zap", cask)
        for tag in ["v1.2.3;puts 1", "v1.2.3-beta", "v01.2.3"]:
            with self.assertRaises(publish.Failure):
                publish.cask({**value, "tag": tag})
        with self.assertRaises(publish.Failure):
            publish.cask({**value, "sha256": '";system("bad")'})

    def test_existing_version_is_noop_but_downgrade_or_same_version_replacement_fails(self):
        current = publish.cask(manifest())
        self.assertFalse(publish.replacement(current, current))
        self.assertTrue(publish.replacement(None, current))
        self.assertTrue(publish.replacement(current.replace('"0.1.1"', '"0.1.0"'), current))
        for old in [current.replace('"0.1.1"', '"0.1.2"'), current.replace("b" * 64, "c" * 64)]:
            with self.assertRaises(publish.Failure):
                publish.replacement(old, current)

    def test_commit_requires_verified_receipt_and_cas_without_replacing_a_concurrent_edit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cask_file = root / "cask.rb"
            value = manifest()
            content = publish.cask(value)
            cask_file.write_text(content)
            verified = {"manifest": value, "previous_cask_sha": "old",
                        "cask_sha256": hashlib.sha256(content.encode()).hexdigest()}
            (root / "verified.json").write_text(json.dumps(verified))
            previous = content.replace('"0.1.1"', '"0.1.0"')
            with patch.object(publish, "ROOT", root), patch.object(publish, "CASK", cask_file), \
                    patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "repository_dispatch"}), \
                    patch.object(publish, "tag_commit", return_value=value["source_sha"]), \
                    patch.object(publish, "remote_cask", side_effect=[(previous, "old"), (content, "new")]), \
                    patch.object(publish, "api") as api:
                publish.commit()
                request = api.call_args.args
                self.assertEqual(request[:2], (f"/repos/{publish.TAP}/contents/Casks/pr-sniper.rb", "PUT"))
                self.assertEqual(request[2]["sha"], "old")
                self.assertEqual(base64.b64decode(request[2]["content"]).decode(), content)
            with patch.object(publish, "ROOT", root), patch.object(publish, "CASK", cask_file), \
                    patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "repository_dispatch"}), \
                    patch.object(publish, "tag_commit", return_value=value["source_sha"]), \
                    patch.object(publish, "remote_cask", return_value=(previous, "concurrent")), \
                    patch.object(publish, "api") as api, self.assertRaises(publish.Failure):
                publish.commit()
            api.assert_not_called()

    def test_commit_cannot_run_on_a_pr_or_other_ref(self):
        for event, ref in [("pull_request", "refs/pull/1/merge"), ("workflow_dispatch", "refs/heads/feature")]:
            with patch.dict(os.environ, {"GITHUB_REF": ref, "GITHUB_EVENT_NAME": event}), \
                    self.assertRaises(publish.Failure):
                publish.commit()


if __name__ == "__main__":
    unittest.main()
