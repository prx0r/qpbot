# DEV PLAN — AgentCom v2 control plane with Pi workers, Argos + AgentDeck views

Frame: `general-plan.md`. Authority: AgentCom v2 controls, Pi works, Argos
and AgentDeck view, QP settles. Nothing below makes a viewer authoritative.

## Where we stand (verified 2026-09-17)

- `/agentcomfinal`: 70 tests green. Real skeleton: `core/` (ids, lineage,
  scheduler, portfolio), `contracts/` (5 schemas + checker), `adapters/`
  (qp pure-delegates to `/home/ubuntu/qp`; atask sandbox; seed0; gitgoblin;
  seesaw; cg real runner), `agentcom/` one-shot CLI, `autobuild/` compiler,
  `trajectory/` evidence store, `experiments/policies/` lanes. Missing: ACP,
  headless service, AgentDeck/Argos bridges, H-task queue, Pi runner. HLoop
  absent (only Seed0 `learn.propose` + trajectory ladder).
- `qpbot/core/`: fully runnable arena game, 10 tests green, in sync with
  `xmrecon/`. Tournament 3/3 all lanes, autopilot promotes.
- `qpbot/connectors/pi-xmrecon/`: scaffold, not runnable. No node_modules,
  no pi binary, no key, plus 2 live bugs (`arena_probe` never probes,
  `arena_submit` unquoted interpolation).
- `/home/ubuntu/pi-acp`: unbuilt, needs `npm ci && npm run build`, pi binary.
- `qpfinal/`: parts library + byte archive, 4 smoke tests green. Source for
  every port below.

## Phase 0 — baselines (no behavior change)

- Record pins: `agentcomfinal` HEAD, `qpbot/{pi,argos,agentdeck}` vendor
  HEADs (`e4c75a7`, `2db3aebc`, `fde84b95`), pi-acp HEAD `3f46f29` into
  `qpbot/docs/VENDOR_PINS.md`.
- Provenance: read-only. No code moves yet.

## Phase 1 — Pi red-team thin slice (first live proof)

Goal: a Pi session captures all 3 demo targets through arena tools with
chained receipts.

- Fix `qpbot/connectors/pi-xmrecon/redteam.ts`: real per-target probe call;
  quote `arena.submit_flag` args (parametrized argv, never interpolation).
- `npm install` in connector dir; install pi binary (>= 0.80.4); supply key
  via env at runtime, never in repo.
- Provenance: Pi SDK patterns from `qpbot/pi/packages/coding-agent/
  examples/sdk/05-tools.ts`; arena backend stays `qpbot/core/`.
- Done when: 3/3 CAPTURED receipts verify against `core` ledger.

## Phase 2 — AgentCom v2 service in qpbot (the control plane)

New `qpbot/agentcom/` (headless service; existing `agentcom/cli.py` stays
one-shot). Port canonical code, do not rewrite:

- `agentcom/core/` ← `/agentcomfinal/core/` (ids, lineage, scheduler,
  portfolio) as-is.
- `agentcom/contracts/` ← `/agentcomfinal/contracts/` (5 schemas + check.py).
- `agentcom/adapters/qp.py` ← `/agentcomfinal/adapters/qp.py` (pure
  delegation to `/home/ubuntu/qp`; R13 no-settle invariant kept).
- `agentcom/adapters/{atask,seed0,gitgoblin,seesaw,cg}.py` ← agentcomfinal
  counterparts; atask keeps sandbox-dir rule.
- `agentcom/compiler/` ← `/agentcomfinal/autobuild/compiler/` (frozen
  ContractRoot/PlanRoot, unprovable-leaf refusal).
- `agentcom/trajectory/` ← `/agentcomfinal/trajectory/` (evidence tiers).
- NEW `agentcom/services/daemon.py`: persistent job queue + scheduler loop
  (one-shot CLI becomes a client of this).
- NEW `agentcom/runtime/pi_acp.py`: spawn Pi per ATask over ACP
  (pattern from `/home/ubuntu/pi-acp` README; build pi-acp first).
- NEW `agentcom/interfaces/acp_server.py`: Argos → AgentCom ACP endpoint
  (RAW Pi passthrough + AgentCom mode).
- NEW `agentcom/interfaces/agentdeck_bridge.py`: AgentCom state projection
  (task_state/human_task/qp_verdict events; poll `core.cli status` until
  push lands).
- NEW `agentcom/htasks/queue.py`: canonical H-task emit/answer/route, QP
  grant-gated. Schemas from qpfinal `_source` scarce-state htask schemas;
  runtime from `qpfinal/human/` (v4 hloop controller present/decide).
- Provenance per file header: `agentcomfinal:<path>` or `qpfinal:<part>`.
- Done when: daemon compiles a spec → dispatches Pi lane → banks evidence
  → settles QP receipt → emits H-task, all headless.

## Phase 3 — Seed0 Pi lanes

- Promote `/agentcomfinal/experiments/policies/lanes.py` + `tournament_e4.py`
  to `agentcom/lanes/runner.py`: frozen ContractRoot/ProofRoot in, Pi lanes
  (model × strategy variants) out, external validation, QP-valid only,
  comparison, winner.
- QP processor lane from `qpfinal/processors/` (crowned SDK, 5 lanes).
- Done when: 5 lanes share one root and only QP-valid candidates compare.

## Phase 4 — settlement seam (unify crypto)

From `qpfinal/INSANE.md` seam 1: retire HMAC/demo signers, standardize on
the v4-harness Ed25519 grant-verify path + GrantBroker production signer.
Single `verify_grant` call path. Verifier freeze: builders never edit
verifiers (pin hashes like qpfinal's lab_v07 pin). qpbot `core` receipts
stay the arena-local form until this phase mints real QP receipts.

## Phase 5 — HLoop + 0–9 on AgentDeck

- Port learner: `qpfinal/human/` (v4 HLoopPolicyModel + sequence learner,
  prediction-before-human enforced) into `agentcom/hloop/`.
- Port money: integer-minor grant-gated ledger behind expected-verified-cost
  router; retire wallet variants.
- AgentDeck surface: H_TASK card (question + prediction + 0–9 pad) →
  HumanDecision (task id, prediction-before-display, actual, timestamp,
  context hash) → HLoop. Autonomy ladder with hard blocks on secret,
  identity, physical, authorization.
- Done when: phone press scores against banked prediction and calibration
  moves over repeated tasks.

## Phase 6 — Argos + AgentDeck views

- Argos: two ACP entries (Stealth RAW Pi direct; AgentCom server). No fork
  unless philosophy conflicts force it; Stealth fork later strips cloud,
  adds privacy badge + request inspector + RAW harness + session wipe.
- AgentDeck: one AgentCom adapter projecting work items (Campaign/ATask/
  HTask tiles with cost, lane progress, proof share). Tap → Argos session;
  0–9 → decision; long-press → stop.
- Done when: phone shows live AgentCom state; desktop chats drive both modes.

## Phase 7 — hardening (INSANE.md as checklist)

Test signers out of tree, auto-human fixture behind explicit flags, auth on
every server before any `0.0.0.0`, lane sandboxing for arbitrary-command
harnesses, remove dangerous fixtures from runnable paths, fix checksum and
nested-zip hygiene. Nothing in this phase changes architecture.

## UX loop (ambient chat + autonomous + popups — see docs/PLAN_REVIEW.md)

Default experience: one normal Pi chat session, autonomy ambient behind it,
H-tasks arriving as interrupts (steer) with status as queued follow-ups.
Chat and workers never share a session or runtime. H-task lifecycle:
emitted → displayed → acknowledged → answered → expired, lease timeouts,
safe-default on no-answer, device-paired authenticity. Lanes: one writer
per Pi session enforced by the daemon; crashes are UNKNOWN with evidence
preserved, never FAILED. Spend shown live per tile from the real ledger.
Per-lane models and credentials; no silent fallback.

## Explicitly out of scope

Rewriting Pi, Goose, Argos, or AgentDeck internals. Live money rails. Any
production deploy before Phase 4 crypto lands. QP around every keystroke —
speculative work stays free inside bounded environments; only boundary
consequences (merge, deploy, pay, send) go through QP.
