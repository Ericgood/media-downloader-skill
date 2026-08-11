import json
import os
import re
from pathlib import Path
from typing import Callable, List
from urllib.parse import urlparse

from .dispatcher import BackendFailure, Dispatcher
from .models import (
    DownloadReport,
    DownloadRequest,
    MediaAsset,
    MediaKind,
    Resolution,
)
from .network import NetworkClient
from .verification import probe_media

MEDIA_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".aac"}


def sanitize_filename(value: str, limit: int = 160) -> str:
    value = re.sub(r"[\x00-\x1f<>:\"/\\|?*]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    if not value:
        value = "download"
    return value[:limit].rstrip(" .")


def _extension(asset: MediaAsset) -> str:
    if asset.extension:
        return asset.extension.lstrip(".")
    path = urlparse(asset.url).path
    suffix = Path(path).suffix.lstrip(".")
    if suffix:
        return suffix
    return {
        MediaKind.VIDEO: "mp4",
        MediaKind.AUDIO: "mp3",
        MediaKind.IMAGE: "jpg",
        MediaKind.SUBTITLE: "srt",
    }.get(asset.kind, "bin")


class DownloaderService:
    def __init__(
        self,
        dispatcher: Dispatcher,
        *,
        network: NetworkClient = None,
        prober: Callable = probe_media,
    ):
        self.dispatcher = dispatcher
        self.network = network or NetworkClient()
        self.prober = prober

    def info(self, request: DownloadRequest) -> Resolution:
        return self.dispatcher.resolve(request)

    def download(self, request: DownloadRequest) -> DownloadReport:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        failures = []
        backends = list(self.dispatcher.backends_for(request))
        if not backends:
            raise BackendFailure("no backend is configured for this URL")
        for backend in backends:
            created = []
            try:
                resolution = backend.resolve(request)
                if not resolution.assets:
                    raise BackendFailure("backend returned no media assets")
                if callable(getattr(backend, "download", None)):
                    paths = [Path(path) for path in backend.download(request, resolution)]
                else:
                    paths = self._download_resolution(request, resolution)
                created.extend(paths)
                probes = []
                for path in paths:
                    if path.suffix.lower() in MEDIA_EXTENSIONS:
                        probes.append(self.prober(path))
                if request.media != MediaKind.SUBTITLE and not probes:
                    raise BackendFailure("download produced no verifiable audio or video file")
                return DownloadReport(
                    source_url=request.url,
                    backend=backend.name,
                    title=resolution.title,
                    files=[str(path.resolve()) for path in paths],
                    probes=probes,
                    failures=failures + list(resolution.failures),
                )
            except Exception as exc:
                for path in created:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass
                failures.append("{}: {}".format(backend.name, exc))
        raise BackendFailure("all backends failed: {}".format("; ".join(failures)))

    def _download_resolution(self, request: DownloadRequest, resolution: Resolution) -> List[Path]:
        selected = self._select_assets(request, resolution)
        if not selected:
            raise BackendFailure("backend did not provide the requested media type")
        prefix = sanitize_filename(
            "{} - {}".format(resolution.artist, resolution.title) if resolution.artist else resolution.title
        )
        created = []
        try:
            for index, asset in enumerate(selected, 1):
                suffix = _extension(asset)
                label = "" if len(selected) == 1 else "-{:02d}".format(index)
                destination = request.output_dir / "{}{}.{}".format(prefix, label, suffix)
                destination = self._available_path(destination)
                headers = {"Referer": resolution.source_url} if resolution.source_url else None
                created.append(
                    self.network.download(
                        asset.url,
                        destination,
                        headers=headers,
                        max_bytes=request.max_bytes,
                    )
                )

            if (request.with_lyrics or request.all_assets) and resolution.lyrics:
                lyrics_path = self._available_path(request.output_dir / "{}.lyrics.txt".format(prefix))
                self._atomic_write_text(lyrics_path, resolution.lyrics)
                created.append(lyrics_path)
            if request.with_metadata or request.all_assets:
                metadata_path = self._available_path(request.output_dir / "{}.metadata.json".format(prefix))
                metadata = {
                    "title": resolution.title,
                    "artist": resolution.artist,
                    "source_id": resolution.source_id,
                    "source_url": resolution.source_url,
                    "backend": resolution.backend,
                    "duration": resolution.duration,
                    "width": resolution.width,
                    "height": resolution.height,
                    "prompt": resolution.prompt,
                }
                self._atomic_write_text(
                    metadata_path, json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
                )
                created.append(metadata_path)
            return created
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _select_assets(request: DownloadRequest, resolution: Resolution) -> List[MediaAsset]:
        if request.all_assets:
            return list(resolution.assets)
        requested_kind = request.media
        if requested_kind == MediaKind.AUTO:
            default_kind = resolution.metadata.get("default_kind", MediaKind.VIDEO.value)
            requested_kind = MediaKind(default_kind)
        selected = [asset for asset in resolution.assets if asset.kind == requested_kind]
        if request.with_cover:
            selected.extend(asset for asset in resolution.assets if asset.kind == MediaKind.IMAGE)
        return selected

    @staticmethod
    def _available_path(path: Path) -> Path:
        if not path.exists():
            return path
        for index in range(2, 10000):
            candidate = path.with_name("{} ({}){}".format(path.stem, index, path.suffix))
            if not candidate.exists():
                return candidate
        raise BackendFailure("could not allocate an output filename")

    @staticmethod
    def _atomic_write_text(path: Path, content: str) -> None:
        temporary = path.with_name(path.name + ".part")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary), str(path))
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
