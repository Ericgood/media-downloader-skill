from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MediaKind(str, Enum):
    AUTO = "auto"
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    IMAGE = "image"


@dataclass
class MediaAsset:
    url: str
    kind: MediaKind
    extension: str = ""
    filename: str = ""
    bitrate: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Resolution:
    title: str
    backend: str
    assets: List[MediaAsset]
    artist: str = ""
    source_id: str = ""
    source_url: str = ""
    duration: float = 0.0
    width: int = 0
    height: int = 0
    lyrics: str = ""
    prompt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)

    @property
    def audio_url(self) -> str:
        return self._first_url(MediaKind.AUDIO)

    @property
    def video_url(self) -> str:
        return self._first_url(MediaKind.VIDEO)

    @property
    def cover_url(self) -> str:
        return self._first_url(MediaKind.IMAGE)

    def _first_url(self, kind: MediaKind) -> str:
        for asset in self.assets:
            if asset.kind == kind:
                return asset.url
        return ""


@dataclass
class DownloadRequest:
    url: str
    media: MediaKind = MediaKind.AUTO
    output_dir: Path = field(default_factory=lambda: Path("~/Downloads/media").expanduser())
    resolution: str = "best"
    audio_format: str = "mp3"
    subtitle_langs: str = "en"
    subtitle_format: str = "srt"
    playlist: bool = False
    proxy: Optional[str] = None
    cookies_from_browser: Optional[str] = None
    backend: str = "auto"
    with_cover: bool = False
    with_lyrics: bool = False
    with_metadata: bool = False
    all_assets: bool = False
    max_bytes: int = 2 * 1024 * 1024 * 1024


@dataclass
class MediaProbe:
    path: str
    size: int
    format_name: str
    duration: float
    video_codec: str = ""
    width: int = 0
    height: int = 0
    audio_codec: str = ""
    sample_rate: int = 0
    channels: int = 0


@dataclass
class DownloadReport:
    source_url: str
    backend: str
    title: str
    files: List[str]
    probes: List[MediaProbe]
    failures: List[str] = field(default_factory=list)
