"""Privacy guarantees: a stored secret must not escape through any channel.

Channels checked: vault file, audit log, H-task views/queue JSON, daemon
journal, bridge tiles, status feed, error messages. Sim-game credentials
(admin/admin) are puzzle fixtures, not secrets, and are out of scope.
"""
import json
import os
import tempfile

from agentcom.vault.store import Vault
from agentcom.htasks.queue import HQueue, HTask
from agentcom.services.daemon import Daemon
from agentcom.interfaces.agentdeck_bridge import tiles_for_status

MARKER = "SECRET-VALUE-9f8e7d6c5b4a"


def _vault():
    d = tempfile.mkdtemp()
    return Vault(os.path.join(d, "vault.json"), os.path.join(d, "vault.key"))


def test_secret_in_no_persisted_artifact():
    v = _vault()
    v.store("DEPOT", MARKER, ["tool-x"], ["worker-1"], scope="s", ttl_s=600)
    cap = v.secrets["DEPOT"]["capability"]
    v.resolve("DEPOT", "tool-x", "worker-1", cap, scope="s")
    blob = open(v.store_path).read()
    assert MARKER not in blob
    assert MARKER not in json.dumps(v.audit)


def test_secret_in_no_task_or_tile_surface():
    q = HQueue()
    t = q.emit(HTask("s1", "secret", "Paste API key for service X"))
    t.display()
    assert MARKER not in q.to_json()
    assert MARKER not in json.dumps(t.view())
    tiles = tiles_for_status({"programs": []}, hqueue=q)
    assert MARKER not in json.dumps(tiles)


def test_secret_in_no_daemon_or_status_surface():
    from core import module_adapter
    d = Daemon()
    d.submit({"kind": "lane", "pack": "demo", "note": "no secrets here"})
    d.tick(lambda job: {"ok": True})
    assert MARKER not in json.dumps(d.journal)
    assert MARKER not in json.dumps(module_adapter.status("demo"))


def test_error_paths_echo_nothing():
    v = _vault()
    v.store("E", MARKER, ["t"], ["w"], ttl_s=600)
    for args in [("E", "nope", "w", "bad"), ("E", "t", "w", "bad"),
                 ("missing", "t", "w", "bad")]:
        try:
            v.resolve(*args)
            assert False, "must raise"
        except ValueError as e:
            assert MARKER not in str(e)
