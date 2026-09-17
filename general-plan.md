# General plan (frame, not gospel)

Make **AgentCom v2 the actual control plane**, while Argos and AgentDeck are
just two different views/controllers over it. Don't make Argos, AgentDeck, or
Pi authoritative. The v2 ownership split stands: workers propose, probes
observe, QP settles/commits. Pi simply replaces the earlier assumed worker
runtime.

```text
                       YOU
                        │
            ┌───────────┴────────────┐
            │                        │
        ARGOS                    AGENTDECK
   rich desktop/chat          phone / deck / TUI
            │                        │
            │ ACP              status + 0–9
            │                        │
            └───────────┬────────────┘
                        ▼
                 ┌─────────────┐
                 │ AGENTCOM v2 │
                 │ control     │
                 │ plane       │
                 └──────┬──────┘
                        │
              ContractRoot / ATask
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
       PI #1           PI #2           PI #3
      worker          worker          worker
         │              │              │
         └──────────────┼──────────────┘
                        ▼
                       QP
          proof / authority / settlement
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
          COMMIT                H-TASK
                                  │
                                  ▼
                          AgentDeck 0–9
```

## 1. Pi becomes the worker runtime

AgentCom generates an `ATask` containing objective, budget, time limit,
permissions, proof requirements, working directory, and expected artifact.
Then AgentCom spawns Pi for that bounded job.

Current `pi-acp` implementations already expose Pi as a standard ACP agent
without modifying Pi; one ACP session maps to a dedicated Pi
session/process. So instead of AgentCom containing model loops:

```text
AgentCom → ACP → pi-acp → Pi → manually chosen model
```

Pi already supports arbitrary configured providers/models (Phala, Venice,
NanoGPT, Chutes live here). AgentCom doesn't care which model Pi uses.

## 2. Argos becomes the main desktop UI

Expose two things to Argos: Stealth RAW Pi (direct Pi ACP, minimal harness,
no QP) and AgentCom (AgentCom ACP server: Argos → AgentCom → ATask →
Pi workers → QP). Raw mode is for talking to a model directly; AgentCom
mode is for running the whole v2 machine. Don't force everything through
AgentCom.

## 3. AgentDeck feeds off AgentCom state, not Pi directly

Tiles represent Campaigns, ATasks, or HTasks — not shell processes:

```text
PROJECT         STATE
QP              ● RUNNING
Stealth         ● RUNNING
AgentCom        ! HUMAN
Seed0           ○ WAITING
security        ✓ VERIFIED
```

## 4. The 0–9 system goes onto AgentDeck

When AgentCom produces an H_TASK (class, question, prediction, confidence),
the phone/deck shows the choice plus a 0–9 pad. The press returns a
HumanDecision with task id, prediction-before-display, actual, timestamp,
and context hash back into HLoop. Calibration improves over time, while QP
remains the authority gate.

## 5. QP stays underneath consequences

Never Pi-says-DONE → AgentCom-marks-DONE. The chain stays: Pi finishes →
AgentCom holds a candidate → probe observes → QP Processor attempts → QP
verifies → AgentCom transitions state. Pi never needs to understand QP.

## 6. Don't put QP around every keystroke

Let Pi freely read, write, test, branch, reason, and explore inside its
bounded environment as speculative work. Protect boundaries only: git
candidate → QP validation → merge; deployment, payment, and send proposals
→ QP authority (+ money grant for pay) → execute. Git branches/worktrees
are speculative lanes; only validated candidates promote.

## 7. Seed0 becomes multiple Pi lanes

AgentCom freezes the problem (ContractRoot, ProofRoot) and launches lanes
— Pi plus model/strategy variants plus QP processor and experimental lanes
— all sharing objective, proof requirements, and budget envelope. Outputs go
through external validation; QP-valid candidates only; Seed0 compares;
winner takes it. Same v2 tournament, minus owning the harness.

## 8. AgentDeck displays work items, not agents

Tiles show status, cost, lane progress, proof share; tap drills into the
Argos conversation or the H-task; 0–9 decides; long press stops. Argos
keeps conversation, reasoning stream, artifacts, diffs, and history.
AgentCom keeps truthful project state. QP keeps truth and authority.

## 9. Minimal integration to write

```text
agentcom/
├─ runtime/pi_acp.py
├─ interfaces/acp_server.py        # Argos → AgentCom
├─ interfaces/agentdeck_bridge.py  # AgentCom → Deck
├─ events (task_state, human_task, human_decision, qp_verdict)
└─ existing v2 (atask, qp, actuality, seed0, hloop)
```

No Pi modifications. No Argos fork initially. Ideally one AgentCom adapter
for AgentDeck. Stop building the dashboard portion of AgentCom: the UI is
Argos + AgentDeck, and AgentCom v2 becomes a headless control-plane service
that compiles work, runs Pi lanes, tracks evidence, invokes QP, and emits
human tasks.
