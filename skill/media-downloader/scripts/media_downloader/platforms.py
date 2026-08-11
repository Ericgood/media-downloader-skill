from enum import Enum
from urllib.parse import urlparse


class Platform(str, Enum):
    TIKTOK = "tiktok"
    DOUYIN = "douyin"
    TWITTER = "twitter"
    BILIBILI = "bilibili"
    SUNO = "suno"
    UDIO = "udio"
    YOUTUBE = "youtube"
    GENERIC = "generic"


def _matches(host: str, domains):
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def detect_platform(url: str) -> Platform:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if _matches(host, ("tiktok.com", "vm.tiktok.com", "vt.tiktok.com")):
        return Platform.TIKTOK
    if _matches(host, ("douyin.com", "iesdouyin.com")):
        return Platform.DOUYIN
    if _matches(host, ("x.com", "twitter.com")):
        return Platform.TWITTER
    if _matches(host, ("bilibili.com", "b23.tv")):
        return Platform.BILIBILI
    if _matches(host, ("suno.com", "suno.ai")):
        return Platform.SUNO
    if _matches(host, ("udio.com",)):
        return Platform.UDIO
    if _matches(host, ("youtube.com", "youtu.be", "youtube-nocookie.com")):
        return Platform.YOUTUBE
    return Platform.GENERIC
