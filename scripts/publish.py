#!/usr/bin/env python3
"""Publish only the audited cask for an existing immutable PR Sniper release."""

import base64
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

SOURCE = "jdylanmc/pr-sniper"
TAP = "jdylanmc/homebrew-pr-sniper"
BUNDLE = "com.jdylanmc.pr-sniper"
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
SHA = re.compile(r"[0-9a-f]{40}")
HASH = re.compile(r"[0-9a-f]{64}")
ROOT = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "pr-sniper-publisher"
CASK = Path("Casks/pr-sniper.rb")


class Failure(Exception):
    pass


def require(ok, message):
    if not ok:
        raise Failure(message)


def release_version(tag):
    require(isinstance(tag, str) and tag.startswith("v") and VERSION.fullmatch(tag[1:]),
            "Expected a stable vMAJOR.MINOR.PATCH tag.")
    return tag[1:]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api(path, method="GET", body=None, missing=False):
    require(path.startswith(f"/repos/{SOURCE}/") or path.startswith(f"/repos/{TAP}/"),
            "Unexpected GitHub repository.")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "pr-sniper-tap",
               "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"}
    if method != "GET":
        require(path == f"/repos/{TAP}/contents/Casks/pr-sniper.rb" and method == "PUT",
                "Only the owned cask can be updated.")
        token = os.environ.get("GITHUB_TOKEN")
        require(token, "Missing repository-scoped publisher token.")
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request("https://api.github.com" + path, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if missing and error.code == 404:
            return None
        raise Failure(f"GitHub {method} returned HTTP {error.code}; no mutation retry.") from None
    except (OSError, ValueError):
        raise Failure(f"GitHub {method} outcome unavailable; inspect state before retrying.") from None


def download(url, destination, limit):
    require(url.startswith(f"https://github.com/{SOURCE}/releases/download/"),
            "Download must belong to the source repository.")
    total = 0
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=90) as response, destination.open("xb") as output:
            final = urllib.parse.urlparse(response.url)
            require(final.scheme == "https" and final.hostname in {
                "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com",
            }, "Unexpected download redirect.")
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                require(total <= limit, "Release asset exceeds its expected size.")
                digest.update(chunk)
                output.write(chunk)
    except OSError:
        raise Failure("Public release download failed.") from None
    return digest.hexdigest(), total


def tag_commit(tag):
    release_version(tag)
    obj = api(f"/repos/{SOURCE}/git/ref/tags/{tag}")["object"]
    for _ in range(5):
        if obj["type"] == "commit":
            require(SHA.fullmatch(obj["sha"]), "Invalid source commit.")
            return obj["sha"]
        require(obj["type"] == "tag", "Unexpected tag object type.")
        obj = api(f"/repos/{SOURCE}/git/tags/{obj['sha']}")["object"]
    raise Failure("Too many nested tags.")


def manifest_check(manifest, tag, commit, team):
    version = release_version(tag)
    require(set(manifest) == {"version", "tag", "source_sha", "filename", "sha256", "architecture",
                              "bundle_id", "team_id", "notarization_id"}, "Unexpected release manifest.")
    require(manifest["version"] == version and manifest["tag"] == tag
            and manifest["source_sha"] == commit
            and manifest["filename"] == f"pr-sniper-{version}-aarch64-apple-darwin.zip"
            and manifest["architecture"] == "arm64" and manifest["bundle_id"] == BUNDLE
            and re.fullmatch(r"[A-Z0-9]{10}", team or "") and manifest["team_id"] == team
            and HASH.fullmatch(manifest["sha256"]), "Release provenance or platform mismatch.")
    try:
        uuid.UUID(manifest["notarization_id"])
    except (ValueError, TypeError, AttributeError):
        raise Failure("Invalid notarization receipt.") from None


def cask(manifest):
    version = release_version(manifest["tag"])
    require(HASH.fullmatch(manifest["sha256"]), "Invalid checksum.")
    return f'''# frozen_string_literal: true

cask "pr-sniper" do
  version "{version}"
  sha256 "{manifest["sha256"]}"

  url "https://github.com/{SOURCE}/releases/download/v#{{version}}/pr-sniper-#{{version}}-aarch64-apple-darwin.zip"
  name "PR Sniper"
  desc "Human-owned pull request review from your menu bar"
  homepage "https://github.com/{SOURCE}"

  depends_on arch: :arm64
  depends_on macos: :ventura

  app "PR Sniper.app"

  caveats "Requires macOS 13.5 or later. Quit PR Sniper before upgrading; settings and credentials are preserved."
end
'''


def replacement(existing, content):
    if existing == content:
        return False
    if existing is not None:
        old = re.findall(r'^  version "([^"]+)"$', existing, re.M)
        new = re.findall(r'^  version "([^"]+)"$', content, re.M)
        require(len(old) == len(new) == 1 and VERSION.fullmatch(old[0]) and VERSION.fullmatch(new[0]),
                "Cannot compare cask versions.")
        require(tuple(map(int, new[0].split("."))) > tuple(map(int, old[0].split("."))),
                "Refusing cask downgrade or same-version byte replacement.")
    return True


def remote_cask():
    record = api(f"/repos/{TAP}/contents/Casks/pr-sniper.rb?ref=main", missing=True)
    if record is None:
        return None, None
    require(record.get("type") == "file" and record.get("encoding") == "base64", "Invalid cask response.")
    return base64.b64decode(record["content"]).decode(), record["sha"]


def prepare(candidate=False):
    existing_candidate = CASK.read_text() if candidate else None
    tag = os.environ.get("RELEASE_TAG", "")
    version = release_version(tag)
    commit = tag_commit(tag)
    release = api(f"/repos/{SOURCE}/releases/tags/{tag}")
    require(not release["draft"] and not release["prerelease"] and release["tag_name"] == tag
            and release["target_commitish"] == commit, "Release is not public at the expected source.")
    rows = api(f"/repos/{SOURCE}/releases/{release['id']}/assets?per_page=100")
    names = {"manifest.json", "SHA256SUMS", f"pr-sniper-{version}-aarch64-apple-darwin.zip"}
    require(len(rows) == 3 and {row["name"] for row in rows} == names, "Unexpected release assets.")
    require(not ROOT.exists(), "Publisher staging already exists.")
    ROOT.mkdir(mode=0o700)
    for row in rows:
        url = f"https://github.com/{SOURCE}/releases/download/{tag}/{row['name']}"
        require(row["browser_download_url"] == url and row["state"] == "uploaded"
                and 0 < row["size"] <= 1024 * 1024 * 1024, "Invalid release asset.")
        digest, size = download(url, ROOT / row["name"], row["size"])
        require(size == row["size"] and row.get("digest") == "sha256:" + digest, "GitHub asset digest mismatch.")
    manifest = json.loads((ROOT / "manifest.json").read_text())
    manifest_check(manifest, tag, commit, os.environ.get("APPLE_TEAM_ID"))
    require(hashlib.sha256((ROOT / manifest["filename"]).read_bytes()).hexdigest() == manifest["sha256"],
            "Archive checksum mismatch.")
    require((ROOT / "SHA256SUMS").read_text() == f"{manifest['sha256']}  {manifest['filename']}\n",
            "Checksum file mismatch.")
    require(tag_commit(tag) == commit, "Source tag moved during download.")
    content = cask(manifest)
    if candidate:
        require(existing_candidate == content, "Candidate cask differs from the verified release definition.")
    old, old_sha = remote_cask()
    replacement(old, content)
    CASK.parent.mkdir(exist_ok=True)
    CASK.write_text(content)
    (ROOT / "prepared.json").write_text(json.dumps({
        "manifest": manifest, "previous_cask_sha": old_sha, "cask_sha256": hashlib.sha256(content.encode()).hexdigest(),
    }))


def native(args):
    result = subprocess.run(args, capture_output=True, timeout=120, check=False)
    require(result.returncode == 0, "Native installed-app verification failed: " + args[0])
    return result.stdout or result.stderr


def verify_install():
    prepared = json.loads((ROOT / "prepared.json").read_text())
    manifest = prepared["manifest"]
    app = Path(os.environ["RUNNER_TEMP"]) / "pr-sniper-install/PR Sniper.app"
    require(app.is_dir() and not app.is_symlink(), "Expected isolated Homebrew-installed app is missing.")
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    require(info.get("CFBundleIdentifier") == BUNDLE and info.get("CFBundleShortVersionString") == manifest["version"]
            and info.get("CFBundleVersion") == manifest["version"] and info.get("LSMinimumSystemVersion") == "13.5"
            and info.get("CFBundleExecutable") == "pr-sniper", "Installed app identity/version mismatch.")
    require(native(["lipo", "-archs", str(app / "Contents/MacOS/pr-sniper")]).decode().strip() == "arm64",
            "Installed architecture mismatch.")
    native(["codesign", "--verify", "--strict", str(app)])
    signature = native(["codesign", "-dv", "--verbose=4", str(app)]).decode()
    require(f"Identifier={BUNDLE}\n" in signature and f"TeamIdentifier={manifest['team_id']}\n" in signature
            and "Authority=Developer ID Application:" in signature and "Timestamp=" in signature
            and "runtime" in signature and "Signature=adhoc" not in signature, "Installed signing identity mismatch.")
    native(["xcrun", "stapler", "validate", str(app)])
    native(["spctl", "--assess", "--type", "execute", str(app)])
    require(hashlib.sha256(CASK.read_bytes()).hexdigest() == prepared["cask_sha256"], "Cask changed during validation.")
    (ROOT / "verified.json").write_text(json.dumps(prepared))


def commit():
    require(os.environ.get("GITHUB_REF") == "refs/heads/main"
            and os.environ.get("GITHUB_EVENT_NAME") in ("repository_dispatch", "workflow_dispatch"),
            "Only the trusted main publisher can update the cask.")
    verified = json.loads((ROOT / "verified.json").read_text())
    manifest = verified["manifest"]
    content = CASK.read_text()
    require(content == cask(manifest) and hashlib.sha256(content.encode()).hexdigest() == verified["cask_sha256"],
            "Cask no longer matches the installed/verified release.")
    require(tag_commit(manifest["tag"]) == manifest["source_sha"], "Source tag moved before publication.")
    old, old_sha = remote_cask()
    if not replacement(old, content):
        print("Cask already matches the verified release; no write required.")
        return
    require(old_sha == verified["previous_cask_sha"], "Cask changed while validation ran; no concurrent edit overwritten.")
    body = {"branch": "main", "message": "chore(cask): release PR Sniper " + manifest["version"],
            "content": base64.b64encode(content.encode()).decode()}
    if old_sha:
        body["sha"] = old_sha
    api(f"/repos/{TAP}/contents/Casks/pr-sniper.rb", "PUT", body)
    require(remote_cask()[0] == content, "Cask publication could not be confirmed.")
    print("Published verified cask for " + manifest["tag"])


if __name__ == "__main__":
    try:
        require(os.environ.get("GITHUB_REPOSITORY") == TAP
                and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
                "Publisher operations require this tap's disposable hosted runner.")
        action = sys.argv[1] if len(sys.argv) == 2 else ""
        require(action in ("prepare", "prepare-current", "verify-install", "commit"), "Unknown publisher stage.")
        if action == "prepare-current":
            matches = re.findall(r'^  version "([^"]+)"$', CASK.read_text(), re.M)
            require(len(matches) == 1, "Candidate has no unique version.")
            os.environ["RELEASE_TAG"] = "v" + matches[0]
            prepare(candidate=True)
        else:
            {"prepare": prepare, "verify-install": verify_install, "commit": commit}[action]()
    except (Failure, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print("Tap publication failed: " + (str(error) if isinstance(error, Failure) else "Invalid or unavailable publisher data."),
              file=sys.stderr)
        sys.exit(1)
