# Platform and backend reference

Last verified: 2026-08-12 01:36:16 CST

## Routing and current behavior

| Platform | Detection | Fallback chain | Authentication |
|---|---|---|---|
| TikTok | `tiktok.com`, `vm.tiktok.com`, `vt.tiktok.com` | yt-dlp → TikWM-compatible API → Cobalt | Not required for tested public posts |
| Douyin | `douyin.com`, `iesdouyin.com` | yt-dlp → official `iesdouyin` share page → configured API | Not required for tested public posts |
| X/Twitter | `x.com`, `twitter.com` | yt-dlp → FxTwitter/FxEmbed → Cobalt | Not required for tested public posts |
| Bilibili | `bilibili.com`, `b23.tv` | yt-dlp → Cobalt | Not required for tested public video |
| Suno | `suno.com`, `suno.ai` | public song page → source CDN | Not required for public songs |
| Udio | `udio.com` | public song page → source CDN | Not required for public songs |
| YouTube/other | known YouTube hosts or generic | yt-dlp | Depends on the source |

The downloader records every failed backend and reports the backend that actually produced the file. A resolved title or CDN URL is not considered success; the saved file must pass `ffprobe`.

## Runtime setup

Run from the `skill/media-downloader/` directory:

```bash
python3 scripts/bootstrap.py
python3 scripts/download.py doctor --json
```

`bootstrap.py` downloads the current platform-specific yt-dlp standalone asset and the official `SHA2-256SUMS`, verifies the exact SHA-256, and installs the binary in `.tools/`. The binary is runtime state and is ignored by Git.

`ffmpeg` and `ffprobe` must be installed separately. On macOS with Homebrew, use `brew install ffmpeg`.

## Optional self-hosted services

### Cobalt

Set `COBALT_API_URL` to a Cobalt API base URL, for example a trusted self-hosted instance. Set `COBALT_API_KEY` only if that instance requires it. The adapter sends the public source URL, requested download mode, audio format, video quality and filename style.

Official project: <https://github.com/imputnet/cobalt> (AGPL-3.0).

### Douyin API

Set `DOUYIN_API_URL` to a compatible self-hosted API. The adapter calls `/api/download` with the public URL and requests a non-watermarked response. Keep this disabled unless the instance is under your control or you trust its operator.

Evaluated projects include:

- <https://github.com/jiji262/douyin-downloader> (MIT)
- <https://github.com/yzfly/douyin-mcp-server> (Apache-2.0)

The default local adapter does not run or copy their code. It uses the official public mobile share page pattern confirmed by current open-source implementations.

### TikWM-compatible resolver

`TIKWM_API_URL` defaults to the public TikWM endpoint. This sends only the public TikTok URL; it never sends browser cookies. For stronger operational control, replace it with a trusted compatible endpoint or configure a self-hosted Cobalt instance.

### FxTwitter/FxEmbed

`FXTWITTER_API_URL` defaults to `https://api.fxtwitter.com`. The current open-source project is <https://github.com/FxEmbed/FxEmbed> (MIT). The adapter selects the highest-bitrate MP4 exposed for a public post or article.

## Platform troubleshooting

### TikTok

If yt-dlp reports an unexpected webpage response, allow automatic fallback. If TikWM also fails, verify the post is still public and configure Cobalt. Do not retry the same expired post ID indefinitely.

### Douyin

Full `/video/{id}` links are converted to `https://www.iesdouyin.com/share/video/{id}` before local parsing. Short links are followed normally. If the page no longer contains `_ROUTER_DATA`, look for a maintained public-page change before considering a user-authorized Cookie workflow.

### X/Twitter

Some posts expose media through the FxTwitter API even when yt-dlp says no video exists. The fallback preserves that first failure in its report. Article videos and standard post videos share the same route.

### Bilibili

Anonymous formats may be resolution-limited. Use `--resolution 360` or `720` for a public smoke test. Higher resolutions may legitimately require user-authorized authentication.

### Suno and Udio

Use `--media audio`; `--with-cover`, `--with-lyrics`, `--with-metadata`, or `--all-assets` select companion files when present. These parsers scope metadata to the actual `clip` or `track` object to avoid accidentally taking page-shell titles.

## Security notes

- Only HTTP(S) URLs are accepted.
- Embedded credentials, localhost, private IPs and local hostnames are rejected.
- Redirect targets and resolver-returned media URLs are validated again.
- HTML and JSON error responses are rejected as media.
- Downloads use bounded `.part` files followed by atomic rename.
- Browser Cookies are opt-in and must be explicitly authorized by the user.
