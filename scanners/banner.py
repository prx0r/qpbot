"""Banner scanner — probe every target, record banners + categories."""
from .common import cli, finding, targets

SCANNER = "banner"


def scan() -> list[dict]:
    out = []
    for tid in targets():
        r = cli("probe", tid)
        if r.get("ok"):
            out.append(finding(SCANNER, tid, "banner",
                               f"{r.get('banner', '')} [{r.get('category', '')}]"))
        else:
            out.append(finding(SCANNER, tid, "probe-failed",
                               str(r)[:120], confidence=0.0))
    return out
