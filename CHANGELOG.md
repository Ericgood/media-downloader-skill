# Changelog

All notable changes to this project are documented here. Each release entry uses China Standard Time (CST, UTC+08:00).

## [Unreleased]

## [0.1.0] - 2026-08-12 01:44:11 CST

### Added

- Created the standalone `media-downloader-skill` project and installable `$media-downloader` Codex Skill.
- Added platform detection and explicit fallback chains for TikTok, Douyin, X/Twitter, Bilibili, Suno, Udio, YouTube and generic yt-dlp-compatible sites.
- Added public-page/CDN parsers for Suno and Udio, including optional cover, lyrics, metadata and all-assets downloads.
- Added TikWM-compatible, official Douyin mobile share-page, FxTwitter/FxEmbed, Cobalt and optional Douyin API adapters.
- Added video, audio extraction, subtitles, playlists, resolution selection, legacy `--audio-only`, per-backend selection and multi-URL batch processing.
- Added `doctor` diagnostics and a checksum-verified yt-dlp bootstrap installer.
- Added 29 deterministic unit tests, fixture coverage and Python 3.9/3.12/3.13 GitHub Actions CI.
- Added timestamped product design, live-validation evidence, open-source evaluation, platform reference and contributor workflow.

### Changed

- Replaced the old single-engine assumption with a dispatcher that continues after extraction or download failure and preserves the attempted-backend evidence.
- Updated GitHub Actions to the current Node 24-based `checkout` and `setup-python` v7 releases.
- Scoped Suno and Udio parsing to the actual `clip`/`track` object after live pages exposed misleading app-shell metadata.
- Converted full Douyin video URLs to the official `iesdouyin.com/share/video/{id}` form before local parsing.
- Made signed query values redact automatically from `info` output and backend error logs.

### Security

- Restricted remote inputs and resolver outputs to public HTTP(S) URLs without embedded credentials, localhost or private addresses.
- Added pre-connection redirect validation, bounded response reads, content-type rejection, `.part` files and atomic rename.
- Kept browser Cookie access opt-in only; the v0.1.0 platform validations used no browser Cookies.
- Ignored runtime binaries, live downloads, credentials and local environment files from Git.

### Validation

- Live-downloaded and ffprobe-verified TikTok, Douyin, X/Twitter, Bilibili, Suno and Udio media on 2026-08-12 CST.
- Re-ran TikTok, X/Twitter and Udio downloads after the redirect-security change.
- Passed 29 unit tests, compileall, Ruff and the Codex Skill `quick_validate.py` check.

[Unreleased]: https://github.com/Ericgood/media-downloader-skill/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ericgood/media-downloader-skill/releases/tag/v0.1.0
