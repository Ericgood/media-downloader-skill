import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional, Sequence
from urllib.parse import quote, urlencode

from .dispatcher import BackendFailure, Dispatcher
from .models import DownloadRequest, MediaAsset, MediaKind, Resolution
from .network import NetworkClient, NetworkError
from .parsers import (
    ParseError,
    parse_cobalt_response,
    parse_douyin_page,
    parse_fxtwitter_response,
    parse_suno_page,
    parse_tikwm_response,
    parse_udio_page,
)
from .platforms import Platform


def _clean_error(value: str, limit: int = 1200) -> str:
    value = re.sub(
        r"([?&][^=&\s]*(?:token|key|signature|sig|auth|policy|expires|jwt)[^=&\s]*=)[^&\s]+",
        r"\1[redacted]",
        value,
        flags=re.I,
    )
    return value.strip()[-limit:]


def find_ytdlp_command() -> Optional[List[str]]:
    configured = os.environ.get("MEDIA_DOWNLOADER_YTDLP", "").strip()
    if configured:
        return shlex.split(configured)
    skill_root = Path(__file__).resolve().parents[2]
    candidates = [
        skill_root / ".tools" / "yt-dlp",
        skill_root / ".tools" / "yt-dlp.exe",
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(str(candidate), os.X_OK):
            return [str(candidate)]
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    if importlib.util.find_spec("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    return None


class YtDlpBackend:
    name = "yt-dlp"

    def __init__(self, *, command: Optional[Sequence[str]] = None, runner: Callable = subprocess.run):
        self.command = list(command) if command else find_ytdlp_command()
        self.runner = runner

    def _base_command(self, request: DownloadRequest) -> List[str]:
        if not self.command:
            raise BackendFailure("yt-dlp is not installed; run scripts/bootstrap.py")
        command = list(self.command)
        if request.proxy:
            command.extend(["--proxy", request.proxy])
        if request.cookies_from_browser:
            command.extend(["--cookies-from-browser", request.cookies_from_browser])
        command.append("--yes-playlist" if request.playlist else "--no-playlist")
        return command

    def resolve(self, request: DownloadRequest) -> Resolution:
        command = self._base_command(request)
        command.extend(["--dump-single-json", "--skip-download", "--no-warnings", "--", request.url])
        completed = self._run(command, timeout=120)
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise BackendFailure("yt-dlp returned invalid metadata") from exc
        media_kind = request.media
        if media_kind in (MediaKind.AUTO, MediaKind.SUBTITLE):
            media_kind = MediaKind.VIDEO
        return Resolution(
            title=payload.get("title") or payload.get("id") or "download",
            artist=payload.get("uploader") or payload.get("creator") or "",
            source_id=str(payload.get("id", "")),
            source_url=request.url,
            backend=self.name,
            assets=[
                MediaAsset(
                    request.url,
                    media_kind,
                    payload.get("ext", ""),
                    metadata={"backend_managed": True},
                )
            ],
            duration=float(payload.get("duration", 0) or 0),
            width=int(payload.get("width", 0) or 0),
            height=int(payload.get("height", 0) or 0),
            metadata={"backend_managed": True},
        )

    def download(self, request: DownloadRequest, resolution: Resolution) -> List[Path]:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        before = {path.resolve() for path in request.output_dir.rglob("*") if path.is_file()}
        command = self._base_command(request)
        command.extend(
            [
                "--no-progress",
                "--newline",
                "--windows-filenames",
                "--paths",
                str(request.output_dir),
                "--output",
                "%(title).180B [%(id)s].%(ext)s",
                "--print",
                "after_move:filepath",
            ]
        )
        if request.media == MediaKind.SUBTITLE:
            command.extend(
                [
                    "--skip-download",
                    "--write-subs",
                    "--write-auto-subs",
                    "--sub-langs",
                    request.subtitle_langs,
                    "--sub-format",
                    request.subtitle_format,
                    "--convert-subs",
                    request.subtitle_format,
                ]
            )
        elif request.media == MediaKind.AUDIO:
            command.extend(["--extract-audio", "--audio-format", request.audio_format])
        else:
            if request.resolution == "best":
                format_selector = "bestvideo*+bestaudio/best"
            else:
                format_selector = ("bestvideo*[height<={0}]+bestaudio/best[height<={0}]/best").format(
                    request.resolution
                )
            command.extend(["--format", format_selector, "--merge-output-format", "mp4"])
        command.extend(["--", request.url])
        completed = self._run(command, timeout=1800)
        reported = []
        for line in completed.stdout.splitlines():
            candidate = Path(line.strip()).expanduser()
            if candidate.is_file():
                reported.append(candidate.resolve())
        after = {path.resolve() for path in request.output_dir.rglob("*") if path.is_file()}
        paths = sorted(set(reported) | (after - before), key=lambda path: str(path))
        if not paths:
            raise BackendFailure("yt-dlp exited successfully but produced no files")
        return paths

    def version(self) -> str:
        if not self.command:
            return "not installed"
        try:
            return self._run(list(self.command) + ["--version"], timeout=30).stdout.strip()
        except BackendFailure as exc:
            return "error: {}".format(exc)

    def _run(self, command: List[str], *, timeout: int):
        try:
            completed = self.runner(command, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BackendFailure(str(exc)) from exc
        if completed.returncode != 0:
            error = _clean_error(completed.stderr or completed.stdout or "unknown yt-dlp error")
            raise BackendFailure(error)
        return completed


class SunoBackend:
    name = "suno"

    def __init__(self, network: NetworkClient):
        self.network = network

    def resolve(self, request: DownloadRequest) -> Resolution:
        try:
            page = self.network.fetch_text(request.url)
            return parse_suno_page(page, request.url)
        except (NetworkError, ParseError) as exc:
            raise BackendFailure(str(exc)) from exc


class UdioBackend:
    name = "udio"

    def __init__(self, network: NetworkClient):
        self.network = network

    def resolve(self, request: DownloadRequest) -> Resolution:
        try:
            page = self.network.fetch_text(request.url)
            return parse_udio_page(page, request.url)
        except (NetworkError, ParseError) as exc:
            raise BackendFailure(str(exc)) from exc


class TikWMBackend:
    name = "tikwm"

    def __init__(self, network: NetworkClient, endpoint: str = None):
        self.network = network
        self.endpoint = endpoint or os.environ.get("TIKWM_API_URL", "https://www.tikwm.com/api/")

    def resolve(self, request: DownloadRequest) -> Resolution:
        media = MediaKind.AUDIO if request.media == MediaKind.AUDIO else MediaKind.VIDEO
        query = urlencode({"url": request.url, "hd": "1"})
        separator = "&" if "?" in self.endpoint else "?"
        try:
            payload = self.network.fetch_json(self.endpoint + separator + query)
            return parse_tikwm_response(payload, media, request.url)
        except (NetworkError, ParseError) as exc:
            raise BackendFailure(str(exc)) from exc


class DouyinBackend:
    name = "douyin"
    MOBILE_UA = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
    )

    def __init__(self, network: NetworkClient):
        self.network = network

    @staticmethod
    def _share_url(source_url: str) -> str:
        match = re.search(r"/(?:video|note)/(\d+)", source_url)
        if not match:
            return source_url
        return "https://www.iesdouyin.com/share/video/{}".format(match.group(1))

    def resolve(self, request: DownloadRequest) -> Resolution:
        try:
            page = self.network.fetch_text(
                self._share_url(request.url),
                headers={"User-Agent": self.MOBILE_UA, "Referer": "https://www.douyin.com/"},
            )
            return parse_douyin_page(page, request.url)
        except (NetworkError, ParseError) as exc:
            raise BackendFailure(str(exc)) from exc


class DouyinAPIBackend:
    name = "douyin-api"

    def __init__(self, endpoint: str = None):
        self.endpoint = (endpoint or os.environ.get("DOUYIN_API_URL", "")).rstrip("/")

    def resolve(self, request: DownloadRequest) -> Resolution:
        if not self.endpoint:
            raise BackendFailure("DOUYIN_API_URL is not configured")
        download_url = "{}/api/download?{}".format(
            self.endpoint,
            urlencode({"url": request.url, "prefix": "true", "with_watermark": "false"}),
        )
        return Resolution(
            title="Douyin video",
            source_url=request.url,
            backend=self.name,
            assets=[MediaAsset(download_url, MediaKind.VIDEO, "mp4")],
        )


class FxTwitterBackend:
    name = "fxtwitter"

    def __init__(self, network: NetworkClient, endpoint: str = None):
        self.network = network
        self.endpoint = (endpoint or os.environ.get("FXTWITTER_API_URL", "https://api.fxtwitter.com")).rstrip(
            "/"
        )

    def resolve(self, request: DownloadRequest) -> Resolution:
        match = re.search(r"(?:x\.com|twitter\.com)/([^/]+)/status/(\d+)", request.url)
        if not match:
            raise BackendFailure("X URL did not contain a status ID")
        username, status_id = match.groups()
        api_url = "{}/{}/status/{}".format(self.endpoint, quote(username), status_id)
        try:
            payload = self.network.fetch_json(api_url)
            result = parse_fxtwitter_response(payload, request.url)
            if request.media == MediaKind.AUDIO:
                raise BackendFailure("FxTwitter does not expose a standalone audio asset")
            return result
        except (NetworkError, ParseError) as exc:
            raise BackendFailure(str(exc)) from exc


class CobaltBackend:
    name = "cobalt"

    def __init__(self, network: NetworkClient, endpoint: str = None, api_key: str = None):
        self.network = network
        self.endpoint = (endpoint or os.environ.get("COBALT_API_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("COBALT_API_KEY", "")

    def resolve(self, request: DownloadRequest) -> Resolution:
        if not self.endpoint:
            raise BackendFailure("COBALT_API_URL is not configured")
        mode = "audio" if request.media == MediaKind.AUDIO else "auto"
        payload = {
            "url": request.url,
            "downloadMode": mode,
            "audioFormat": request.audio_format,
            "videoQuality": request.resolution if request.resolution != "best" else "max",
            "filenameStyle": "pretty",
        }
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Api-Key {}".format(self.api_key)
        try:
            response = self.network.post_json(self.endpoint + "/", payload, headers=headers)
            result = parse_cobalt_response(response, request.url)
            if request.media == MediaKind.AUDIO:
                for asset in result.assets:
                    if asset.kind == MediaKind.VIDEO:
                        asset.kind = MediaKind.AUDIO
            return result
        except (NetworkError, ParseError) as exc:
            raise BackendFailure(str(exc)) from exc


def build_default_dispatcher(*, network: NetworkClient = None, ytdlp: YtDlpBackend = None) -> Dispatcher:
    network = network or NetworkClient()
    ytdlp = ytdlp or YtDlpBackend()
    tikwm = TikWMBackend(network)
    douyin = DouyinBackend(network)
    douyin_api = DouyinAPIBackend()
    fxtwitter = FxTwitterBackend(network)
    cobalt = CobaltBackend(network)
    suno = SunoBackend(network)
    udio = UdioBackend(network)
    routes = {
        Platform.TIKTOK: [ytdlp, tikwm, cobalt],
        Platform.DOUYIN: [ytdlp, douyin, douyin_api],
        Platform.TWITTER: [ytdlp, fxtwitter, cobalt],
        Platform.BILIBILI: [ytdlp, cobalt],
        Platform.SUNO: [suno],
        Platform.UDIO: [udio],
        Platform.YOUTUBE: [ytdlp],
        Platform.GENERIC: [ytdlp],
    }
    return Dispatcher(routes, generic=[ytdlp])
