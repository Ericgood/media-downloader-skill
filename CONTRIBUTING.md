# Contributing

感谢一起维护媒体下载能力。平台页面和签名机制变化很快，因此每个修复必须同时包含可重复的自动化证据和当日真实下载证据。

## 开发流程

1. 先在 `docs/` 新建或更新带 CST 时间戳的产品/技术文档与验证计划。
2. 为解析器、路由或安全策略写一个会失败的本地 fixture 测试。
3. 用最小改动修复，并运行全部单元测试。
4. 为每个受影响的平台找一条独立公开 URL，实际下载并用 `ffprobe` 验证。
5. 把 URL、时间、实际后端、失败链、字节数、SHA-256、时长和编码写回同一份验证文档。
6. 更新 `CHANGELOG.md` 的精确 CST 时间戳后再提交。

具体规则以 [AGENTS.md](AGENTS.md) 为准。

## 本地检查

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q skill/media-downloader/scripts tests
ruff check skill/media-downloader/scripts tests
python3 skill/media-downloader/scripts/download.py doctor --json
```

Skill 结构还需用 Codex `skill-creator` 自带的 `quick_validate.py` 检查。

## 提交边界

不要提交下载成品、`.tools/`、`.local/`、Cookie、Token、API Key、带时效签名的 CDN URL 或用户私密链接。测试 fixture 必须脱敏且体积足够小。涉及登录态的验证只能在用户明确授权后进行，并且证据中不得出现凭据。
