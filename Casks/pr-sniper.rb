# frozen_string_literal: true

cask "pr-sniper" do
  version "0.5.4"
  sha256 "0fd7088b9de6c21532297d185b54f2f57866b75bb6975ff1ec42f804f4105530"

  url "https://github.com/jdylanmc/pr-sniper/releases/download/v#{version}/pr-sniper-#{version}-aarch64-apple-darwin.zip"
  name "PR Sniper"
  desc "Human-owned pull request review from your menu bar"
  homepage "https://github.com/jdylanmc/pr-sniper"

  depends_on arch: :arm64
  depends_on macos: :ventura

  app "PR Sniper.app"

  caveats "Requires macOS 13.5 or later. Quit PR Sniper before upgrading; settings and credentials are preserved."
end
