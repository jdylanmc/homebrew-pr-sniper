# frozen_string_literal: true

cask "pr-sniper" do
  version "0.6.0"
  sha256 "9c03fe4ef58683ca9f47a53fc6539f298140794c3b1e6851570bdd89edc2fccd"

  url "https://github.com/jdylanmc/pr-sniper/releases/download/v#{version}/pr-sniper-#{version}-aarch64-apple-darwin.zip"
  name "PR Sniper"
  desc "Human-owned pull request review from your menu bar"
  homepage "https://github.com/jdylanmc/pr-sniper"

  depends_on arch: :arm64
  depends_on macos: :ventura

  app "PR Sniper.app"

  caveats "Requires macOS 13.5 or later. Quit PR Sniper before upgrading; settings and credentials are preserved."
end
