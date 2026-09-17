# PLAY — every runnable thing, in the order you'd try it

All from `/home/ubuntu/qpbot`. Python side needs nothing but python3.
TypeScript side needs `npm install` (done) plus your own model key.

## The game (key-free, always works)

```bash
python3 -m pytest tests/ -q                       # whole suite, 24 tests
python3 -m core.cli list-targets                  # see the 3 targets
python3 -m core.cli probe weak-creds-01           # recon one target
python3 -m core.cli submit weak-creds-01 XMCTF{weak_creds_demo_01}  # verdict
python3 -m core.cli run --agent red-01 --pack demo # full campaign, 3/3
python3 -m core.cli chain runs/demo/events.jsonl  # verify the ledger
python3 -m core.cli tournament                    # 3 lanes compete, winner ranked
python3 -m core.cli autopilot --rounds 3          # continuous loop with caps
python3 -m core.cli status --pack demo            # controller status feed
```

## The control plane (key-free, in-process)

```python
from agentcom.htasks.queue import HQueue, HTask
q = HQueue()
t = q.emit(HTask("t1", "digit", "Pick direction?", prediction="7",
                 confidence=0.72, lease_s=300))
t.display(); t.acknowledge(); t.answer_task("8", "7")
q.sweep()  # expire past-due tasks to safe defaults

from agentcom.lanes.seed0 import LaneSpec, contract_root, run_seed0
root = contract_root("capture demo", ["CAPTURED"], {})
run_seed0("capture demo", ["CAPTURED"], {},
          [LaneSpec("a", strategy="creds-first", contract_root=root)])

from agentcom.services.daemon import Daemon
d = Daemon()
d.submit({"kind": "lane", "pack": "demo"})
d.tick(lambda job: {"ok": True})  # crash inside runner → UNKNOWN, never raises

from agentcom.interfaces.agentdeck_bridge import tiles_for_status
tiles_for_status(status_dict, hqueue=q, spend={"usd_minor": 14})
```

## Pi modes (needs your key in env at runtime, never in repo)

```bash
cd connectors/pi-xmrecon
npm run raw -- --model anthropic/claude-opus-4-5 -- "Say hello."
npm run redteam -- --model anthropic/claude-opus-4-5 --pack demo
```

Raw mode: no tools, minimal prompt, manual model. Red-team: explicit arena
tools only, claims settle server-side.

## Views (vendors, unmodified)

- Argos (`argos/`): desktop control plane; point an ACP entry at pi-acp's
  built `dist/index.js` for Pi, another at the future AgentCom server.
- AgentDeck (`agentdeck/`): phone/deck controller; tiles come from
  `agentdeck_bridge.tiles_for_status`.
- pi-acp (`/home/ubuntu/pi-acp`, built): ACP ↔ Pi subprocess bridge.

## What is still scaffold

Pi live runs (key), Argos ACP entries (config), AgentDeck adapter (bridge
functions exist, transport push next), QP crypto seam (qpfinal reference),
HLoop scoring (qpfinal reference). Everything else above runs today.
