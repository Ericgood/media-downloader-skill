---
name: media-downloader
description: Download and verify public video, audio, subtitles, and AI-generated music from TikTok, Douyin, X/Twitter, Bilibili, YouTube, Suno, Udio, and other yt-dlp-compatible sites. Use when Codex needs to save media from a public URL, extract audio, fetch subtitles or cover art, inspect media metadata, batch-download links, or diagnose why a media URL cannot be downloaded.
---

# Media Downloader

Download public media through a tested fallback chain and verify the saved artifact before reporting success.

Run the commands below from this Skill's `media-downloader/` directory so the bundled `scripts/` paths resolve correctly.

## Run the workflow

1. Confirm that the URL is public and that the requested use is authorized.
2. Bootstrap the checksum-verified yt-dlp binary once, then run the environment check:

   ```bash
   python3 scripts/bootstrap.py
   python3 scripts/download.py doctor
   ```

3. Inspect the URL when platform support or available assets are uncertain:

   ```bash
   python3 scripts/download.py info "URL" --json
   ```

4. Download the requested asset:

   ```bash
   python3 scripts/download.py download "URL" --output-dir "/absolute/output/path"
   ```

   Pass multiple URLs to the same command for a batch. Continue processing later URLs when one fails, and report per-URL results:

   ```bash
   python3 scripts/download.py download "URL_1" "URL_2" --output-dir "/absolute/output/path" --json
   ```

5. Verify the generated file with the script's built-in probe. Treat a non-empty file alone as insufficient proof.
6. Report the absolute paths, selected backend, file size, media type, duration, and resolution or audio properties.

## Select an asset

Use `--media video` for video, `--media audio` for extracted or original audio, and `--media auto` to preserve the source's primary media.

```bash
python3 scripts/download.py download "URL" --media audio --audio-format mp3
python3 scripts/download.py download "URL" --media video --resolution 1080
python3 scripts/download.py subtitles "URL" --subtitle-langs "en,zh-Hans"
```

For Suno and Udio, add `--with-cover`, `--with-lyrics`, `--with-metadata`, or `--all-assets` when the user wants companion files.

## Use authentication carefully

Do not read browser cookies unless the user explicitly authorizes using their signed-in browser session. Prefer public extraction first. When authorization is given, pass `--cookies-from-browser safari`, `chrome`, `firefox`, `edge`, or `brave`.

Never print cookie values, API keys, or authenticated media URLs containing secrets.

## Handle failures

Allow the dispatcher to try its platform-specific fallback chain. Do not repeat the same failed backend indefinitely.

- TikTok: yt-dlp, then the TikWM public resolver, then a configured Cobalt instance.
- Douyin: yt-dlp, then local public-page parsing, then a configured self-hosted Douyin/TikTok API.
- X/Twitter: yt-dlp, then FxTwitter, then a configured Cobalt instance.
- Bilibili: yt-dlp, then a configured Cobalt instance.
- Suno and Udio: parse the public song page and download from the source CDN.
- Other sites: use yt-dlp.

If all backends fail, return the attempted backends and actionable reason. Do not claim the content is unavailable solely because one extractor failed.

Read [references/platforms.md](references/platforms.md) when diagnosing a platform-specific failure or configuring optional backends.

## Respect boundaries

Download only public or user-authorized content. Do not bypass DRM, paywalls, private access controls, geographic restrictions, or platform security controls. Use proxies only when the user supplies or authorizes them.
