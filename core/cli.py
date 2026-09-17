"""xmrecon CLI. Thin shell, no semantics. JSON on stdout, exit = verdict."""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    ap = argparse.ArgumentParser(prog="qpbot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list-targets").add_argument("--pack", default="demo")
    p = sub.add_parser("probe")
    p.add_argument("target")
    p = sub.add_parser("run")
    p.add_argument("--pack", default="demo")
    p.add_argument("--agent", default="red-01")
    p.add_argument("--runs-dir", default="runs")
    p = sub.add_parser("submit")
    p.add_argument("target")
    p.add_argument("flag")
    p = sub.add_parser("try-creds")
    p.add_argument("target")
    p.add_argument("user")
    p.add_argument("pw")
    p = sub.add_parser("read-file")
    p.add_argument("target")
    p.add_argument("path")
    p = sub.add_parser("sqli")
    p.add_argument("target")
    p.add_argument("payload")
    p = sub.add_parser("vault-store")
    p.add_argument("name")
    p.add_argument("--tools", default="")
    p.add_argument("--workers", default="")
    p.add_argument("--scope", default="")
    p.add_argument("--ttl", type=int, default=3600)
    p.add_argument("--max-uses", type=int, default=0)
    p.add_argument("--store", default="~/.qpbot/vault.json")
    p = sub.add_parser("vault-available")
    p.add_argument("name")
    p.add_argument("--store", default="~/.qpbot/vault.json")
    p = sub.add_parser("vault-resolve")
    p.add_argument("name")
    p.add_argument("--tool", required=True)
    p.add_argument("--worker", required=True)
    p.add_argument("--cap", required=True)
    p.add_argument("--scope", default="")
    p.add_argument("--store", default="~/.qpbot/vault.json")
    p = sub.add_parser("vault-find")
    p.add_argument("--kind", default="")
    p.add_argument("--tier", default="")
    p.add_argument("--provider", default="")
    p.add_argument("--store", default="~/.qpbot/vault.json")
    p = sub.add_parser("vault-usage")
    p.add_argument("--store", default="~/.qpbot/vault.json")
    p = sub.add_parser("prize")
    p.add_argument("--target", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--store", default="~/.qpbot/vault.json")
    p = sub.add_parser("prize-stats")
    p.add_argument("--store", default="~/.qpbot/vault.json")
    p = sub.add_parser("prize-record")
    p.add_argument("target")
    p.add_argument("--agent", default="")
    p.add_argument("--flag-sha256", default="")
    p.add_argument("--receipt", default="")
    p.add_argument("--model", default="")
    p.add_argument("--turns", type=int, default=0)
    p.add_argument("--tokens-in", type=int, default=0)
    p.add_argument("--tokens-out", type=int, default=0)
    p.add_argument("--tools", default="")
    p.add_argument("--store", default="~/.qpbot/vault.json")
    p = sub.add_parser("chain")
    p.add_argument("store")
    p = sub.add_parser("status")
    p.add_argument("--pack", default="demo")
    p.add_argument("--agent", default="red-01")
    sub.add_parser("tournament").add_argument("--pack", default="demo")
    p = sub.add_parser("autopilot")
    p.add_argument("--pack", default="demo")
    p.add_argument("--agent", default="red-01")
    p.add_argument("--rounds", type=int, default=5)
    a = ap.parse_args()

    if a.cmd == "list-targets":
        from . import arena
        print(json.dumps(arena.list_targets(a.pack), indent=1))
        return 0
    if a.cmd == "run":
        from . import campaign
        s = campaign.run_campaign(a.pack, a.agent, a.runs_dir)
        print(json.dumps({k: v for k, v in s.items() if k != "results"}, indent=1))
        return 0 if s["captured"] == s["targets"] else 1
    if a.cmd == "probe":
        from . import arena
        print(json.dumps(arena.probe(a.target), indent=1))
        return 0 if arena.probe(a.target).get("ok") else 1
    if a.cmd == "submit":
        from . import arena
        r = arena.submit_flag(a.target, a.flag)
        print(json.dumps(r, indent=1))
        return 0 if r.get("ok") else 1
    if a.cmd == "try-creds":
        from . import arena
        r = arena.try_creds(a.target, a.user, a.pw)
        print(json.dumps(r, indent=1))
        return 0
    if a.cmd == "read-file":
        from . import arena
        r = arena.read_file(a.target, a.path)
        print(json.dumps(r, indent=1))
        return 0
    if a.cmd == "sqli":
        from . import arena
        r = arena.exploit_sqli_sim(a.target, a.payload)
        print(json.dumps(r, indent=1))
        return 0
    if a.cmd == "vault-store":
        import os as _os
        import sys as _sys
        from agentcom.vault.store import Vault
        store = _os.path.expanduser(a.store)
        v = Vault(store)
        value = _sys.stdin.read().strip()
        if not value:
            print(json.dumps({"ok": False, "error": "empty value"}))
            return 1
        out = v.store(a.name, value,
                      [t for t in a.tools.split(",") if t],
                      [w for w in a.workers.split(",") if w],
                      scope=a.scope, ttl_s=a.ttl, max_uses=a.max_uses)
        cap = v.secrets[a.name]["capability"]
        print(json.dumps({"ok": True, **out, "capability": cap}))
        return 0
    if a.cmd == "vault-available":
        import os as _os
        from agentcom.vault.store import Vault
        v = Vault(_os.path.expanduser(a.store))
        print(json.dumps({"available": v.credential_available(a.name)}))
        return 0
    if a.cmd == "vault-resolve":
        import os as _os
        from agentcom.vault.store import Vault
        v = Vault(_os.path.expanduser(a.store))
        try:
            print(v.resolve(a.name, a.tool, a.worker, a.cap,
                            scope=a.scope), end="")
            return 0
        except ValueError as e:
            print(json.dumps({"ok": False, "error": str(e)}))
            return 1
    if a.cmd == "vault-find":
        import os as _os
        from agentcom.vault.store import Vault
        v = Vault(_os.path.expanduser(a.store))
        results = v.find(kind=a.kind, tier=a.tier, provider=a.provider)
        print(json.dumps(results, indent=1))
        return 0
    if a.cmd == "vault-usage":
        import os as _os
        from agentcom.vault.store import Vault
        v = Vault(_os.path.expanduser(a.store))
        print(json.dumps(v.usage_summary(), indent=1))
        return 0
    if a.cmd == "prize":
        import os as _os
        from agentcom.vault.store import Vault
        v = Vault(_os.path.expanduser(a.store))
        prizes = v.prizes_list(agent_id=a.agent, target_id=a.target)
        print(json.dumps(prizes, indent=1))
        return 0
    if a.cmd == "prize-stats":
        import os as _os
        from agentcom.vault.store import Vault
        v = Vault(_os.path.expanduser(a.store))
        print(json.dumps(v.prize_stats(), indent=1))
        return 0
    if a.cmd == "prize-record":
        import os as _os
        from agentcom.vault.store import Vault
        v = Vault(_os.path.expanduser(a.store))
        prize = v.capture(a.target, a.agent, a.flag_sha256, a.receipt,
                          model=a.model, turns=a.turns,
                          tokens_in=a.tokens_in, tokens_out=a.tokens_out,
                          tools_used=[t for t in a.tools.split(",") if t])
        print(json.dumps({"ok": True, "prize": prize}, indent=1))
        return 0
    if a.cmd == "chain":
        from .ledger import Ledger
        ok = Ledger(a.store).verify_chain()
        print(json.dumps({"ok": ok}))
        return 0 if ok else 1
    if a.cmd == "status":
        from . import module_adapter
        print(json.dumps(module_adapter.status(a.pack, a.agent), indent=1))
        return 0
    if a.cmd == "tournament":
        from . import tournament
        t = tournament.run_tournament(a.pack)
        print(json.dumps({k: v for k, v in t.items()}, indent=1))
        return 0
    if a.cmd == "autopilot":
        from . import autopilot
        s = autopilot.run_autopilot(a.pack, a.agent, a.rounds)
        print(json.dumps({k: v for k, v in s.items() if k != "history"},
                         indent=1))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
