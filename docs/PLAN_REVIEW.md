# Plan review — gaps, verdict, and the ambient/chat UX the plan was missing

## Verdict: it will work, with additions below

No architectural blocker found. Every seam the plan depends on exists in a
verified form: Pi SDK sessions/tools/prompts, pi-acp one-process-per-session
mapping, AgentDeck daemon-to-surface prompt patterns, Argos ACP agent
entries, agentcomfinal compiler/evidence/QP paths, qpbot arena receipts.
Riskiest items are all tractable build tasks, ordered in the fix list.

## What the plan missed

### 1. The actual product loop: ambient chat with autonomous background + popups

The plan has RAW vs AgentCom modes but never describes the minute-to-minute
experience you asked for: you chat normally while CTF mode runs agents
autonomously, and H-tasks pop up mid-conversation. That loop needs stating:

- One conversational session (yours) plus one runtime per background worker.
  Never shared. Worker evidence never enters chat context; chat sees
  summaries only.
- H-tasks arrive as interrupts, not polls. Delivery has two paths: an
  approval-style card on AgentDeck surfaces (precedent in-tree:
  `agentdeck/bridge/src/pairing-knocks.ts` turns daemon refusals into
  operator prompts — same pattern) and an ACP permission-style prompt in
  Argos. Pi-side, `steer()` interrupts the current turn, `followUp()`
  queues behind it; H-tasks use steer, status updates use followUp.
- The chat session is plain Pi with tools and skills. Nothing custom. That
  is the whole point: normal chatbot is the default, autonomy is ambient.

### 2. H-task lifecycle with teeth

The plan has a queue but no state machine. Needed: emitted → displayed →
acknowledged → answered → expired, with lease timeouts, escalation on
no-answer (safe default wins, never auto-approve), and authenticity on the
answer path (device pairing covers it — same trust model as the knock
approval). A 0–9 press is authority, not proof: it routes the decision, it
never mints a receipt by itself.

### 3. One writer per session, enforced by the daemon

pi-acp documents the constraint plainly: parallel adapter processes are
fine for distinct sessions, but one persisted session must never have two
active writers or history diverges. The lane runner must spawn one Pi
subprocess per lane and the daemon must refuse to attach a second writer.
This is a daemon invariant with a test, not a convention.

### 4. Failure is UNKNOWN, not FAILED

Worker crash, Pi process death, ACP disconnect mid-lane: the lane goes
UNKNOWN with its evidence preserved, the campaign continues, retry policy
decides re-fire. Only a verifier verdict of false is FAILED. The plan's
verifier story covers judgments; it needs this crash story beside it.

### 5. Spend visibility per mode

Chat is cheap, lanes burn. Budget envelopes already exist per ATask; the
gap is display. The ledgers the insane hunt found are real — wire one of
them behind the router and show live spend on the dashboard next to each
tile. A human who can't see burn won't trust autonomy.

### 6. Model/key scoping per lane

Lane spec already allows model × strategy variants. Say it explicitly:
keys resolve per runtime (env or runtime override, never repo), chat model
and worker models are chosen independently, and a lane with no credential
for its model refuses to dispatch instead of falling back silently.

## Fix list, in build order

1. Pi connector bug fixes + live 3/3 capture (DEV_PLAN Phase 1, unchanged).
2. Daemon with one-writer enforcement + UNKNOWN-on-crash lane states.
3. H-task lifecycle + dual delivery (AgentDeck card, Argos prompt) with
   leases and safe-default expiry.
4. Spend readout from the real ledger on every tile.
5. Then Phases 3–7 as written (lanes, crypto seam, HLoop scoring, views,
   hardening).

## Insane-hunt items confirmed covered vs newly added

Covered already: test signers, auto-human fixture, unauth servers, lane
sandboxing, verifier freeze, crypto unification. Newly added by this
review: interrupt-vs-poll delivery, H-task expiry/escalation, writer
exclusivity, UNKNOWN crash semantics, spend display, per-lane credentials.
Fold all six into the build; none changes the architecture.
