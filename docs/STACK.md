# Stack — how qpbot pieces connect

```text
AGENTDECK (phone + desk controller)
  sessions: working / waiting / idle, approvals, jump-in
        │
ARGOS (desktop control plane)
  multi-agent chats over ACP (Pi, Goose, Codex, raw models)
        │ ACP via pi-acp
PI (agent runtime)
  raw chat mode: noTools all, minimal prompt, manual model
  red-team mode: explicit tools + custom arena tools
        │ subprocess: python3 -m core.cli
CORE (this repo: arena + verifier + ledger + tournament + autopilot)
  game truth, receipts, promotion gate, spend caps
```

## AgentDeck session mapping

| AgentDeck state | qpbot meaning |
|---|---|
| working | autopilot round or tournament lane running |
| waiting on you | high-risk tool or promotion gate needs approval |
| idle | pack fully captured, receipts chained, nothing queued |
| approval | submit claim pending verifier verdict |

## Status feed

`python3 -m core.cli status --pack demo` emits the module-status shape
(qdw-workbench compatible) that any controller can poll. AgentDeck and
Argos read it; neither reaches into the arena.
