# Changelog

## Unreleased

### Fixed

- Trust the PR Sniper cask before auditing and installing it, since Homebrew 7
  refuses to load casks from untrusted taps.

### Added

- Authenticate publisher metadata reads with the existing scoped Actions token;
  keep release downloads credential-free and classify API failures safely.

- Own cask publication in this tap, with direct online audit logs, immutable
  public-release verification and a disposable CI-only installation check.
  Support existing-release recovery without re-signing or replacing app assets.

- Add the first cask for the verified PR Sniper v0.1.1 Apple Silicon release.

- Dedicated PR Sniper tap with cask validation and release ownership guidance.
  The first cask will be created only after a real signed/notarized release.
