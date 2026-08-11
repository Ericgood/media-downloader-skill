from typing import Dict, Iterable, List, Optional

from .models import DownloadRequest, Resolution
from .platforms import Platform, detect_platform


class BackendFailure(RuntimeError):
    pass


class Dispatcher:
    def __init__(self, routes: Dict[Platform, List[object]], generic: Optional[List[object]] = None):
        self.routes = routes
        self.generic = generic or []

    def backends_for(self, request: DownloadRequest) -> Iterable[object]:
        platform = detect_platform(request.url)
        backends = self.routes.get(platform, self.generic)
        if request.backend != "auto":
            backends = [backend for backend in backends if backend.name == request.backend]
        return backends

    def resolve(self, request: DownloadRequest) -> Resolution:
        failures = []
        backends = list(self.backends_for(request))
        if not backends:
            raise BackendFailure("no backend is configured for this URL")
        for backend in backends:
            try:
                result = backend.resolve(request)
                if not result.assets:
                    raise BackendFailure("backend returned no media assets")
                result.failures = failures + list(result.failures)
                return result
            except BackendFailure as exc:
                failures.append("{}: {}".format(backend.name, exc))
            except Exception as exc:
                failures.append("{}: {}".format(backend.name, exc))
        raise BackendFailure("all backends failed: {}".format("; ".join(failures)))
