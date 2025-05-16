import sys
import threading


def get_third_party_profiler(config):
    profiler = sys.getprofile()
    if profiler:
        return profiler

    try:
        profiler = threading.getprofile()  # type: ignore[attr-defined]
    except AttributeError:
        profiler = threading._profile_hook
    if profiler:  # pragma: no branch
        return profiler

    return None
