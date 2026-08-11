# Media Downloader Skill

一个可维护、可验证的公开媒体下载 Skill。它不是“把 URL 交给单一下载器然后祈祷成功”，而是按平台使用多级后端，在真实文件落盘后用 `ffprobe` 验证音视频流，再报告成功。

当前一等支持 TikTok、抖音、X/Twitter、Bilibili、Suno 与 Udio；YouTube 和其他站点通过 `yt-dlp` 覆盖。支持视频、音频提取、AI 音乐原始音频、封面、歌词、元数据、字幕、播放列表与多 URL 批量下载。

## 2026-08-12 实测状态

| 平台 | 默认链路 | 真实下载 | 验证结果 |
|---|---|---:|---|
| TikTok | yt-dlp → TikWM → Cobalt | PASS | 2 条 MP4，均含视频和双声道音频 |
| 抖音 | yt-dlp → 官方移动分享页 → 可选 API | PASS | 816.87 秒 MP4，H.264 + AAC |
| X/Twitter | yt-dlp → FxTwitter → Cobalt | PASS | 12.93 秒 MP4，H.264 + AAC |
| Bilibili | yt-dlp → Cobalt | PASS | 80.38 秒 MP4，640×360，H.264 + AAC |
| Suno | 公开歌曲页 → 源站 CDN | PASS | 155.54 秒 MP3，48 kHz 双声道 |
| Udio | 公开歌曲页 → 源站 CDN | PASS | 32.86 秒 MP3，48 kHz 双声道 |

完整 URL、哈希、后端失败证据和媒体属性见 [v0.1.0 验证记录](docs/2026-08-12-v0.1.0-validation-plan.md)。平台页面随时可能变化，所以“支持”代表已有可复现证据和维护路径，不代表第三方服务永不变化。

## 快速开始

要求 Python 3.9+ 和 `ffprobe`。首次使用先安装校验过 SHA-256 的独立 `yt-dlp`：

```bash
git clone https://github.com/Ericgood/media-downloader-skill.git
cd media-downloader-skill/skill/media-downloader
python3 scripts/bootstrap.py
python3 scripts/download.py doctor
```

下载单条或多条公开视频：

```bash
python3 scripts/download.py download "PUBLIC_URL" --output-dir "$PWD/downloads"
python3 scripts/download.py download "URL_1" "URL_2" --output-dir "$PWD/downloads" --json
```

下载原始音乐和配套资源：

```bash
python3 scripts/download.py download "SUNO_OR_UDIO_URL" \
  --media audio --with-cover --with-lyrics --with-metadata
```

提取音频、限制视频清晰度或下载字幕：

```bash
python3 scripts/download.py download "VIDEO_URL" --media audio --audio-format mp3
python3 scripts/download.py download "VIDEO_URL" --media video --resolution 720
python3 scripts/download.py subtitles "VIDEO_URL" --subtitle-langs "en,zh-Hans"
```

## 作为 Codex Skill 使用

仓库中可直接安装的 Skill 位于 `skill/media-downloader/`。复制或软链接到个人 Skill 目录后，使用 `$media-downloader` 触发：

```bash
ln -s "$PWD/skill/media-downloader" "$HOME/.codex/skills/media-downloader"
```

重启或刷新 Codex 的 Skill 列表后即可使用。旧 `video-downloader` 可以保留；新 Skill 名称不同，不会覆盖旧目录。

## 后端配置

默认公开链路无需 Cookie。可选环境变量：

| 变量 | 用途 |
|---|---|
| `MEDIA_DOWNLOADER_YTDLP` | 自定义 yt-dlp 命令 |
| `TIKWM_API_URL` | TikWM 兼容解析端点 |
| `FXTWITTER_API_URL` | FxTwitter/FxEmbed API 根地址 |
| `COBALT_API_URL` | 自托管 Cobalt API 根地址 |
| `COBALT_API_KEY` | Cobalt 实例要求的 API Key |
| `DOUYIN_API_URL` | 自托管 Douyin/TikTok API 根地址 |

只有用户明确授权时才使用 `--cookies-from-browser safari|chrome|firefox|edge|brave|opera`。默认不会读取浏览器登录状态。

## 设计与维护

- [产品与技术设计](docs/2026-08-12-v0.1.0-product-technical-design.md)
- [验证计划与实测证据](docs/2026-08-12-v0.1.0-validation-plan.md)
- [开源项目评估](docs/2026-08-12-v0.1.0-open-source-evaluation.md)
- [平台与后端手册](skill/media-downloader/references/platforms.md)
- [参与维护](CONTRIBUTING.md)
- [更新日志](CHANGELOG.md)

## 安全与版权

仅下载公开内容或你有权访问、保存的内容。项目不绕过 DRM、付费墙、私密权限、地区限制或平台访问控制。解析器收到的媒体 URL 会再次进行协议与公网地址检查，下载采用 `.part` 临时文件和原子重命名。Cookie、Token、签名 URL、下载成品和本地工具二进制均不进入 Git。

本项目原创代码使用 [MIT License](LICENSE)。调用的第三方项目和服务保留各自许可证与条款，详见平台手册。
