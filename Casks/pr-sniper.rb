# frozen_string_literal: true

cask "pr-sniper" do
  version "0.1.2"
  sha256 "574872dd84e1d76a2d3e80008247a5966d98adfdde3ff17e53163a47c7a6b606"

  url "https://github.com/jdylanmc/pr-sniper/releases/download/v#{version}/pr-sniper-#{version}-aarch64-apple-darwin.zip"
  name "PR Sniper"
  desc "Human-owned pull request review from your menu bar"
  homepage "https://github.com/jdylanmc/pr-sniper"

  depends_on arch: :arm64
  depends_on macos: :ventura

  app "PR Sniper.app"

  caveats "Requires macOS 13.5 or later. Quit PR Sniper before upgrading; settings and credentials are preserved."
end
