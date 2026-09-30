#!/usr/bin/env bash
set -euo pipefail

test "${RUNNER_ENVIRONMENT:-}" = github-hosted
test "$(uname -m)" = arm64
test ! -e "$RUNNER_TEMP/pr-sniper-install"
installed_casks="$(brew list --cask)"
if printf '%s\n' "$installed_casks" | grep -Fxq pr-sniper; then
  echo "Refusing to replace an existing PR Sniper installation." >&2
  exit 1
fi

mkdir "$RUNNER_TEMP/pr-sniper-install"
installed=no
cleanup() {
  if [ "$installed" = yes ]; then
    brew uninstall --cask pr-sniper
    test ! -e "$RUNNER_TEMP/pr-sniper-install/PR Sniper.app"
  fi
}
trap cleanup EXIT

brew tap jdylanmc/pr-sniper https://github.com/jdylanmc/homebrew-pr-sniper
tap="$(brew --repository jdylanmc/pr-sniper)"
cp Casks/pr-sniper.rb "$tap/Casks/pr-sniper.rb"
brew style --cask jdylanmc/pr-sniper/pr-sniper
brew audit --cask --online jdylanmc/pr-sniper/pr-sniper
brew install --cask --appdir="$RUNNER_TEMP/pr-sniper-install" jdylanmc/pr-sniper/pr-sniper
installed=yes
python3 -B scripts/publish.py verify-install
