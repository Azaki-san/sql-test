import time

_viewers = {}

def viewer_ping(viewer_id=None):
    now = time.time()
    viewer_id = viewer_id or str(now)
    _viewers[viewer_id] = now

def get_viewer_count():
    now = time.time()
    stale = [k for k, t in _viewers.items() if now - t > 15]
    for k in stale:
        del _viewers[k]
    return len(_viewers)