import html as html_module
import json
import re
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urljoin, urlparse

from .models import MediaAsset, MediaKind, Resolution


class ParseError(ValueError):
    pass


def _normalized_flight_text(page: str) -> str:
    text = html_module.unescape(page)
    text = text.replace('\\"', '"').replace("\\/", "/")
    text = re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda match: chr(int(match.group(1), 16)),
        text,
    )
    return text


def _object_with_field(text: str, object_name: str, required_field: str) -> str:
    marker = re.compile(r'"{}"\s*:\s*\{{'.format(re.escape(object_name)))
    for match in marker.finditer(text):
        start = text.find("{", match.start())
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            character = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
                continue
            if character == '"':
                in_string = True
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : index + 1]
                    if '"{}"'.format(required_field) in candidate:
                        return candidate
                    break
    raise ParseError("page did not contain a {} object with {}".format(object_name, required_field))


def _extension_from_url(url: str, fallback: str = "") -> str:
    path = urlparse(url).path
    if "." not in path.rsplit("/", 1)[-1]:
        return fallback
    return path.rsplit(".", 1)[-1].lower()


def _asset(url: str, kind: MediaKind, fallback_ext: str = "") -> Optional[MediaAsset]:
    if not url:
        return None
    return MediaAsset(url=url, kind=kind, extension=_extension_from_url(url, fallback_ext))


def parse_suno_page(page: str, source_url: str = "") -> Resolution:
    text = _normalized_flight_text(page)
    clip = _object_with_field(text, "clip", "audio_url")
    try:
        clip_data = json.loads(clip)
    except json.JSONDecodeError as exc:
        raise ParseError("Suno clip object was invalid JSON") from exc
    metadata = clip_data.get("metadata") if isinstance(clip_data.get("metadata"), dict) else {}
    title = str(clip_data.get("title") or "")
    audio_url = str(clip_data.get("audio_url") or "")
    if not audio_url:
        raise ParseError("Suno page did not contain an audio URL")
    assets = [
        item
        for item in (
            _asset(audio_url, MediaKind.AUDIO, "mp3"),
            _asset(str(clip_data.get("video_url") or ""), MediaKind.VIDEO, "mp4"),
            _asset(
                str(clip_data.get("image_large_url") or clip_data.get("image_url") or ""),
                MediaKind.IMAGE,
                "jpeg",
            ),
        )
        if item
    ]
    return Resolution(
        title=title or "Suno song",
        artist=str(clip_data.get("display_name") or ""),
        source_id=str(clip_data.get("id") or ""),
        source_url=source_url,
        backend="suno",
        assets=assets,
        duration=float(metadata.get("duration", 0) or 0),
        prompt=str(metadata.get("prompt") or ""),
        metadata={"default_kind": MediaKind.AUDIO.value},
    )


def parse_udio_page(page: str, source_url: str = "") -> Resolution:
    text = _normalized_flight_text(page)
    track = _object_with_field(text, "track", "song_path")
    try:
        track_data = json.loads(track)
    except json.JSONDecodeError as exc:
        raise ParseError("Udio track object was invalid JSON") from exc
    audio_url = str(track_data.get("song_path") or "")
    if not audio_url:
        raise ParseError("Udio page did not contain a song path")
    assets = [
        item
        for item in (
            _asset(audio_url, MediaKind.AUDIO, "mp3"),
            _asset(str(track_data.get("video_path") or ""), MediaKind.VIDEO, "mp4"),
            _asset(str(track_data.get("image_path") or ""), MediaKind.IMAGE, "jpg"),
        )
        if item
    ]
    return Resolution(
        title=str(track_data.get("title") or "Udio song"),
        artist=str(track_data.get("artist") or ""),
        source_id=str(track_data.get("id") or ""),
        source_url=source_url,
        backend="udio",
        assets=assets,
        duration=float(track_data.get("duration", 0) or 0),
        lyrics=str(track_data.get("lyrics") or "").replace("\\n", "\n"),
        prompt=str(track_data.get("prompt") or ""),
        metadata={"default_kind": MediaKind.AUDIO.value},
    )


def parse_tikwm_response(
    data: Dict[str, Any], media: MediaKind = MediaKind.VIDEO, source_url: str = ""
) -> Resolution:
    if data.get("code") != 0 or not isinstance(data.get("data"), dict):
        raise ParseError("TikWM returned an error: {}".format(data.get("msg", "unknown error")))
    item = data["data"]
    if media == MediaKind.AUDIO:
        selected_url = item.get("music", "")
        kind = MediaKind.AUDIO
        fallback_ext = "mp3"
    else:
        selected_url = item.get("hdplay") or item.get("play") or item.get("wmplay", "")
        kind = MediaKind.VIDEO
        fallback_ext = "mp4"
    if selected_url.startswith("/"):
        selected_url = urljoin("https://www.tikwm.com", selected_url)
    if not selected_url:
        raise ParseError("TikWM response did not contain the requested media")
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    return Resolution(
        title=item.get("title") or "TikTok video",
        artist=author.get("nickname", ""),
        source_id=str(item.get("id", "")),
        source_url=source_url,
        backend="tikwm",
        assets=[MediaAsset(selected_url, kind, _extension_from_url(selected_url, fallback_ext))],
    )


def _find_video_info(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get("videoInfoRes"), dict):
            return value["videoInfoRes"]
        for child in value.values():
            found = _find_video_info(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_video_info(child)
            if found:
                return found
    return None


def parse_douyin_page(page: str, source_url: str = "") -> Resolution:
    match = re.search(
        r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*;?\s*</script>",
        page,
        re.DOTALL,
    )
    if not match:
        raise ParseError("Douyin page did not contain _ROUTER_DATA")
    try:
        router_data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ParseError("Douyin _ROUTER_DATA was invalid JSON") from exc
    video_info = _find_video_info(router_data)
    item_list = video_info.get("item_list", []) if video_info else []
    if not item_list:
        raise ParseError("Douyin page did not contain video data")
    item = item_list[0]
    video = item.get("video", {})
    play_addr = video.get("play_addr", {})
    video_id = play_addr.get("uri", "")
    play_urls = play_addr.get("url_list", []) or []
    if video_id:
        media_url = "https://aweme.snssdk.com/aweme/v1/play/?video_id={}&ratio=1080p&line=0".format(video_id)
    elif play_urls:
        media_url = play_urls[0].replace("/playwm/", "/play/").replace("playwm", "play")
    else:
        raise ParseError("Douyin video had no playable URL")
    cover_urls = video.get("cover", {}).get("url_list", []) or []
    assets = [MediaAsset(media_url, MediaKind.VIDEO, "mp4")]
    if cover_urls:
        assets.append(MediaAsset(cover_urls[0], MediaKind.IMAGE, _extension_from_url(cover_urls[0], "jpeg")))
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    return Resolution(
        title=item.get("desc") or "Douyin video",
        artist=author.get("nickname", ""),
        source_id=str(item.get("aweme_id", "")),
        source_url=source_url,
        backend="douyin",
        assets=assets,
        duration=float(video.get("duration", 0)) / 1000,
        width=int(video.get("width", 0) or 0),
        height=int(video.get("height", 0) or 0),
    )


def _best_mp4(variants: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    mp4s = [item for item in variants if item.get("content_type") == "video/mp4" and item.get("url")]
    return max(mp4s, key=lambda item: int(item.get("bit_rate", 0) or 0), default=None)


def parse_fxtwitter_response(data: Dict[str, Any], source_url: str = "") -> Resolution:
    if data.get("code") != 200 or not isinstance(data.get("tweet"), dict):
        raise ParseError("FxTwitter returned an error")
    tweet = data["tweet"]
    article = tweet.get("article") if isinstance(tweet.get("article"), dict) else {}
    assets = []
    for entity in article.get("media_entities", []) or []:
        media_info = entity.get("media_info") if isinstance(entity, dict) else {}
        if media_info.get("__typename") != "ApiVideo":
            continue
        best = _best_mp4(media_info.get("variants", []) or [])
        if best:
            assets.append(
                MediaAsset(
                    best["url"],
                    MediaKind.VIDEO,
                    "mp4",
                    bitrate=int(best.get("bit_rate", 0) or 0),
                )
            )
    if not assets:
        media = tweet.get("media") if isinstance(tweet.get("media"), dict) else {}
        for item in media.get("all", []) or []:
            if item.get("type") in ("video", "gif") and item.get("url"):
                assets.append(MediaAsset(item["url"], MediaKind.VIDEO, "mp4"))
    if not assets:
        raise ParseError("FxTwitter response contained no videos")
    author = tweet.get("author") if isinstance(tweet.get("author"), dict) else {}
    return Resolution(
        title=article.get("title") or tweet.get("text") or "X video",
        artist=author.get("name", ""),
        source_url=source_url,
        backend="fxtwitter",
        assets=assets,
    )


def parse_cobalt_response(data: Dict[str, Any], source_url: str = "") -> Resolution:
    status = data.get("status", "")
    assets = []
    if status in ("redirect", "tunnel", "stream") and data.get("url"):
        kind = MediaKind.AUDIO if data.get("audio") else MediaKind.VIDEO
        assets.append(MediaAsset(data["url"], kind, _extension_from_url(data["url"])))
    elif status == "picker":
        for item in data.get("picker", []) or []:
            url = item.get("url", "")
            item_type = item.get("type", "")
            if not url:
                continue
            kind = {
                "video": MediaKind.VIDEO,
                "gif": MediaKind.VIDEO,
                "photo": MediaKind.IMAGE,
                "image": MediaKind.IMAGE,
                "audio": MediaKind.AUDIO,
            }.get(item_type, MediaKind.VIDEO)
            assets.append(MediaAsset(url, kind, _extension_from_url(url)))
    if not assets:
        raise ParseError(
            "Cobalt returned no downloadable assets: {}".format(data.get("error", data.get("text", status)))
        )
    return Resolution(
        title=data.get("filename") or "download",
        source_url=source_url,
        backend="cobalt",
        assets=assets,
    )
