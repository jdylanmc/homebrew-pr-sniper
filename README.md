# PR Sniper Homebrew tap

Homebrew distribution for [PR Sniper](https://github.com/jdylanmc/pr-sniper).
Apple Silicon, macOS 13.5 or later.

The cask references the immutable, Developer ID-signed and Apple-notarized
[v0.1.1 release](https://github.com/jdylanmc/pr-sniper/releases/tag/v0.1.1).
Its checksum is verified against the published release manifest and archive.

```sh
brew install --cask jdylanmc/pr-sniper/pr-sniper
```

Quit PR Sniper before upgrading, then:

```sh
brew update
brew upgrade --cask pr-sniper
```

Homebrew owns upgrades for this installation; there is no competing in-app
updater. Installation does not launch the app, enable login items or opt into
review execution/notifications. Ordinary uninstall preserves application data
and credentials; this tap has no destructive `zap` stanza.

## Release ownership

The PR Sniper repository's stable `vMAJOR.MINOR.PATCH` release workflow requires
the exact tagged commit on main and green main CI, then signs with Developer ID,
notarizes/staples and verifies the archive. Only afterward does it publish the
versioned ZIP and checksum/provenance files and update this cask's URL/checksum.
Same-version checksum replacement and downgrade are rejected.

The application's fine-grained token only dispatches this tap's publisher.
The publisher runs from this repository's `main`, independently downloads and
checks the public release/tag/manifest/checksum, and verifies the expected
Developer ID team from the public `APPLE_TEAM_ID` repository variable. Apple
private keys and signing credentials never enter this repository.
GitHub metadata requests use the job's scoped API token, including public
source-repository reads; they do not rely on the shared runner's unauthenticated
API quota. Archive/CDN downloads remain credential-free. API errors distinguish
an exhausted quota from other forbidden responses without exposing response
bodies or token values.

`Publish verified cask` handles `repository_dispatch` type `pr-sniper-release`
with `client_payload.tag`, or manual workflow dispatch with an existing stable
tag. The payload is a selector, not trusted provenance: only the fixed PR Sniper
repository supplies assets. PR and push CI exercise the same online audit and
Homebrew install/verify/uninstall flow in a disposable runner-only app directory.
They never launch the application or publish a cask.

Only after those checks pass does the main publisher use its own
repository-scoped `GITHUB_TOKEN` to update the exact cask file. It checks the
original file SHA again, refuses downgrade/same-version replacement, and treats
an already-matching cask as a no-op. Run the publisher manually for an existing
version to recover the tap without re-signing or retagging the app. Errors retain
their direct Homebrew logs. A failed publisher does not replace the prior cask.

The application release dispatches once and waits for matching published cask
bytes. A timeout is unconfirmed, not success or permission to blindly redispatch.
The first v0.1.1 cask was recovered through a separately reviewed/authorized PR
after the original app-context tap audit failed; the new publisher does not
claim the old failure's cause was proven.

Do not manually point the cask at CI artifacts, mutable `latest` downloads,
unnotarized builds, or `sha256 :no_check`. See
[release operations](https://github.com/jdylanmc/pr-sniper/blob/main/docs/releases.md).
