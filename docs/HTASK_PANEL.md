# H-task rail — docked right-third panel spec

Layout: terminal dashboard with chat on the left two-thirds, H-task rail
docked on the right third. The rail appears when a task needs the human and
collapses when the queue is empty. Chat never stops; the rail is a side
channel, not a modal. Precedent in vendor tree: AgentDeck's `ask-gate.ts`
and `awaiting-overlay.ts` already gate terminal attention this way.

## Rail contents, top to bottom

Task card first: which campaign and lane asked, the question in plain words,
the agent's prediction with confidence, cost so far, and time left on the
lease. Then the interaction area, which is one of three kinds. Then the
queue count beneath for waiting tasks.

## Three interaction kinds

**Digit decision.** The 0–9 pad plus the prediction shown against it. Single
keypress answers; the press records prediction-before-display, actual,
timestamp, and context hash into HLoop. No enter key, no second step.

**Typed confirmation.** For approvals with consequences — merge, deploy,
pay, send. The rail shows exactly what will happen and requires typing the
shown phrase (never a bare y/n). The phrase is generated per task so no
macro can pre-approve it. Answer routes the decision; QP still settles the
consequence behind its own grant.

**Secret deposit.** For API keys and credentials the agent needs. A masked
paste box whose contents go straight to the vault over the sealed channel —
never into chat, never into logs, never into the HLoop learning record
(the learning log rejects secret keys by design). The agent receives a
vault reference, not the value, and later retrieval resolves the reference
server-side. What the human pasted is never displayed back, only a receipt
that a secret of a given shape was stored.

## Behavior rules

- One active task at a time on the rail; the rest queue visibly. Answering
  advances the queue.
- Lease expiry collapses the card to an expired state and applies the safe
  default. Expiry is never approval.
- Focus stays in chat unless the human tabs over. Digit keys go to the rail
  only when it holds an active digit task; otherwise they type normally.
- Every answer is device-paired and timestamped. The rail shows receipt
  state (answered, stored, expired) so trust is visible.
- Collapse is manual or on empty queue. Nothing the agent does can force
  the rail open or closed — only tasks and the human control it.
