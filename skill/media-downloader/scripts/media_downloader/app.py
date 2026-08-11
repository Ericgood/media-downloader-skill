import dataclasses
import json
import os
import shutil
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .backends import YtDlpBackend, build_default_dispatcher
from .cli import build_parser, request_from_args
from .dispatcher import BackendFailure
from .models import DownloadReport, Resolution
from .service import DownloaderService


def _redact_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.query:
        return value
    sensitive_markers = ("token", "key", "signature", "sig", "auth", "policy", "expires", "jwt")
    query = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        normalized_key = key.lower().replace("-", "").replace("_", "")
        if any(marker in normalized_key for marker in sensitive_markers):
            item = "[redacted]"
        query.append((key, item))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _serializable(value: Any):
    if dataclasses.is_dataclass(value):
        return {key: _serializable(item) for key, item in dataclasses.asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            key: _redact_url(item)
            if key in ("url", "source_url") and isinstance(item, str)
            else _serializable(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    return value


def collect_doctor() -> Dict[str, Any]:
    ytdlp = YtDlpBackend()
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    return {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "yt_dlp": ytdlp.version(),
        "yt_dlp_command": ytdlp.command or [],
        "ffmpeg": ffmpeg or "not installed",
        "ffprobe": ffprobe or "not installed",
        "optional_backends": {
            "tikwm": os.environ.get("TIKWM_API_URL", "https://www.tikwm.com/api/"),
            "fxtwitter": os.environ.get("FXTWITTER_API_URL", "https://api.fxtwitter.com"),
            "cobalt": "configured" if os.environ.get("COBALT_API_URL") else "not configured",
            "douyin_api": "configured" if os.environ.get("DOUYIN_API_URL") else "not configured",
        },
    }


def _print_resolution(result: Resolution) -> None:
    print("Title: {}".format(result.title))
    if result.artist:
        print("Artist: {}".format(result.artist))
    print("Backend: {}".format(result.backend))
    for asset in result.assets:
        print("- {}: {}".format(asset.kind.value, _redact_url(asset.url)))
    for failure in result.failures:
        print("Fallback: {}".format(failure))


def _print_report(report: DownloadReport) -> None:
    print("Downloaded: {}".format(report.title))
    print("Backend: {}".format(report.backend))
    for path in report.files:
        print("- {}".format(path))
    for probe in report.probes:
        details = ["{:.2f}s".format(probe.duration), probe.format_name]
        if probe.video_codec:
            details.append("{} {}x{}".format(probe.video_codec, probe.width, probe.height))
        if probe.audio_codec:
            details.append("{} {}Hz {}ch".format(probe.audio_codec, probe.sample_rate, probe.channels))
        print("  verified: {} ({})".format(probe.path, ", ".join(details)))
    for failure in report.failures:
        print("Fallback: {}".format(failure))


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        result = collect_doctor()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for key, value in result.items():
                print("{}: {}".format(key, value))
        return 0

    service = DownloaderService(build_default_dispatcher())
    urls = list(args.urls)
    results = []
    failed = False
    try:
        for url in urls:
            request = request_from_args(args, url)
            try:
                result = service.info(request) if args.command == "info" else service.download(request)
            except BackendFailure as exc:
                failed = True
                error = {"url": url, "error": str(exc)}
                if args.json:
                    results.append(error)
                else:
                    print("ERROR [{}]: {}".format(url, exc), file=sys.stderr)
                continue

            if args.json:
                results.append(_serializable(result))
            else:
                if len(urls) > 1:
                    print("URL: {}".format(url))
                if args.command == "info":
                    _print_resolution(result)
                else:
                    _print_report(result)
        if args.json:
            payload = results[0] if len(urls) == 1 else results
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if failed else 0
    except KeyboardInterrupt:
        print("Download cancelled", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
