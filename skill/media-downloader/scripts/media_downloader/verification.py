import json
import subprocess
from pathlib import Path
from typing import Callable

from .models import MediaProbe


class ProbeError(RuntimeError):
    pass


def probe_media(path: Path, *, runner: Callable = subprocess.run) -> MediaProbe:
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise ProbeError("media file is missing or empty")
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=format_name,duration,size:stream=codec_type,codec_name,width,height,sample_rate,channels",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = runner(command, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError("ffprobe could not run: {}".format(exc)) from exc
    if completed.returncode != 0:
        raise ProbeError("ffprobe rejected the file: {}".format(completed.stderr.strip()))
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError("ffprobe returned invalid JSON") from exc
    streams = payload.get("streams", []) or []
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
    if not video and not audio:
        raise ProbeError("file contains no audio or video stream")
    media_format = payload.get("format", {}) or {}
    return MediaProbe(
        path=str(path.resolve()),
        size=path.stat().st_size,
        format_name=media_format.get("format_name", ""),
        duration=float(media_format.get("duration", 0) or 0),
        video_codec=video.get("codec_name", ""),
        width=int(video.get("width", 0) or 0),
        height=int(video.get("height", 0) or 0),
        audio_codec=audio.get("codec_name", ""),
        sample_rate=int(audio.get("sample_rate", 0) or 0),
        channels=int(audio.get("channels", 0) or 0),
    )
