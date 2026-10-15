# frozen_string_literal: true

cask "pr-sniper" do
  version "0.4.0"
  sha256 "cfdd62ca161bdccf633cc3f435a14a7fefe1ce88763e764c00a3dcfb0305eb60"

  url "https://github.com/jdylanmc/pr-sniper/releases/download/v#{version}/pr-sniper-#{version}-aarch64-apple-darwin.zip"
  name "PR Sniper"
  desc "Human-owned pull request review from your menu bar"
  homepage "https://github.com/jdylanmc/pr-sniper"

  depends_on arch: :arm64
  depends_on macos: :ventura

  app "PR Sniper.app"

  caveats "Requires macOS 13.5 or later. Quit PR Sniper before upgrading; settings and credentials are preserved."
end
