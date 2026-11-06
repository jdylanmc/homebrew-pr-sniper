# frozen_string_literal: true

cask "pr-sniper" do
  version "0.6.1"
  sha256 "a5b1efefee82ab7000cad3547431a7dd86ce0aaa6307b8cb022ad4a4232885ba"

  url "https://github.com/jdylanmc/pr-sniper/releases/download/v#{version}/pr-sniper-#{version}-aarch64-apple-darwin.zip"
  name "PR Sniper"
  desc "Human-owned pull request review from your menu bar"
  homepage "https://github.com/jdylanmc/pr-sniper"

  depends_on arch: :arm64
  depends_on macos: :ventura

  app "PR Sniper.app"

  caveats "Requires macOS 13.5 or later. Quit PR Sniper before upgrading; settings and credentials are preserved."
end
