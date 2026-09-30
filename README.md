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

The publishing token has Contents write access only to this repository. It
cannot change Apple credentials in the application repository. Push and PR
validation checks cask style, syntax and online metadata; the release job also
checks the generated cask before updating it.

Do not manually point the cask at CI artifacts, mutable `latest` downloads,
unnotarized builds, or `sha256 :no_check`. See
[release operations](https://github.com/jdylanmc/pr-sniper/blob/main/docs/releases.md).
