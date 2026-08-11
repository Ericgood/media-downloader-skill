import argparse
from pathlib import Path
from typing import Optional

from .models import DownloadRequest, MediaKind

BROWSERS = ("safari", "chrome", "firefox", "edge", "brave", "opera")


def _add_network_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--proxy")
    parser.add_argument("--cookies-from-browser", choices=BROWSERS)
    parser.add_argument("--backend", default="auto")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="media-downloader",
        description="Download and verify public video, audio, subtitles, and AI music.",
    )
    parser.add_argument("--version", action="version", version="media-downloader 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="check runtime dependencies and optional backends")
    doctor.add_argument("--json", action="store_true")

    info = commands.add_parser("info", help="inspect a public media URL")
    info.add_argument("urls", nargs="+")
    info.add_argument(
        "--media", choices=[item.value for item in MediaKind if item != MediaKind.SUBTITLE], default="auto"
    )
    info.add_argument("--json", action="store_true")
    _add_network_options(info)

    download = commands.add_parser("download", help="download video, audio, or AI music")
    download.add_argument("urls", nargs="+")
    download.add_argument("--output-dir", default="~/Downloads/media")
    download.add_argument("--media", choices=("auto", "video", "audio"), default="auto")
    download.add_argument("--audio-only", action="store_true", help="legacy alias for --media audio")
    download.add_argument(
        "--audio-format", choices=("best", "mp3", "m4a", "wav", "flac", "opus"), default="mp3"
    )
    download.add_argument("--resolution", default="best")
    download.add_argument("--playlist", action="store_true")
    download.add_argument("--with-cover", action="store_true")
    download.add_argument("--with-lyrics", action="store_true")
    download.add_argument("--with-metadata", action="store_true")
    download.add_argument("--all-assets", action="store_true")
    download.add_argument("--max-bytes", type=int, default=2 * 1024 * 1024 * 1024)
    download.add_argument("--json", action="store_true")
    _add_network_options(download)

    subtitles = commands.add_parser("subtitles", help="download subtitles through yt-dlp")
    subtitles.add_argument("urls", nargs="+")
    subtitles.add_argument("--output-dir", default="~/Downloads/media")
    subtitles.add_argument("--subtitle-langs", default="en")
    subtitles.add_argument("--format", dest="subtitle_format", choices=("srt", "vtt", "ass"), default="srt")
    subtitles.add_argument("--playlist", action="store_true")
    subtitles.add_argument("--json", action="store_true")
    _add_network_options(subtitles)
    return parser


def request_from_args(args: argparse.Namespace, url: Optional[str] = None) -> DownloadRequest:
    media_value = getattr(args, "media", "auto")
    if getattr(args, "audio_only", False):
        media_value = "audio"
    if getattr(args, "command", "") == "subtitles":
        media_value = "subtitle"
    source_url = url or args.urls[0]
    return DownloadRequest(
        url=source_url,
        media=MediaKind(media_value),
        output_dir=Path(getattr(args, "output_dir", "~/Downloads/media")).expanduser().resolve(),
        resolution=getattr(args, "resolution", "best"),
        audio_format=getattr(args, "audio_format", "mp3"),
        subtitle_langs=getattr(args, "subtitle_langs", "en"),
        subtitle_format=getattr(args, "subtitle_format", "srt"),
        playlist=getattr(args, "playlist", False),
        proxy=getattr(args, "proxy", None),
        cookies_from_browser=getattr(args, "cookies_from_browser", None),
        backend=getattr(args, "backend", "auto"),
        with_cover=getattr(args, "with_cover", False),
        with_lyrics=getattr(args, "with_lyrics", False),
        with_metadata=getattr(args, "with_metadata", False),
        all_assets=getattr(args, "all_assets", False),
        max_bytes=getattr(args, "max_bytes", 2 * 1024 * 1024 * 1024),
    )
