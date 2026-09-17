# Advice — Stealth desktop product shape (frame, not gospel)

One conversational desktop workspace where chat is the primary interface,
while autonomous work stays visible and interruptible beside it.

```text
┌──────────────────────────────────────────────────────────────┬──────────────────────┐
│ STEALTH CHAT / CONTROL PLANE                                 │ HLOOP / HTASK         │
│                                                              │                      │
│ You: what's happening with the security audit?               │ CURRENT REQUEST      │
│                                                              │ Agent needs approval │
│ Agent: 3 workers are active. One found a probable issue...   │                      │
│                                                              │ [0][1][2][3][4]      │
│ You: have another agent verify it before we touch anything   │ [5][6][7][8][9]      │
│                                                              │                      │
│ Agent: started verification lane #4                          │ Provide required data│
│                                                              │ ┌──────────────────┐ │
│ > _                                                          │ │ paste here...    │ │
│                                                              │ └──────────────────┘ │
│                                                              │ [Send to Vault]      │
│                                                              │ [Approve] [Reject]   │
└──────────────────────────────────────────────────────────────┴──────────────────────┘
```

Conversation and autonomous system are the same interface. No separate
agent-administration dashboard most of the time. Natural language maps to
AgentCom operations: what's running, stop the weak lane, why is QP waiting,
have another agent check that, retry with another model, cap spend, open a
new loop, show everything needing me.

## Context-sensitive right panel

Collapsed or tiny status normally; opens to ~a third when something needs
you. Four H-task kinds: DECISION (0–9 pad), APPROVAL (approve/reject with
consequences), SECRET (secure input to vault), PHYSICAL/HUMAN (OTP, photo,
file, confirm-event). Always able to type instead: optional note rides with
the digit, decision trains HLoop, note becomes task context.

## Chat as the AgentCom shell

"Start two agents looking for a simpler implementation" → AgentCom spawns
lanes with budgets and proof requirements, replies conversationally, sidebar
shows live lanes. Unrelated chat continues freely mid-run; the assistant has
control-plane access without being synonymous with any worker.

## Three identities

YOU → STEALTH ASSISTANT (persistent conversational interface) → AGENTCOM
(orchestrates) → workers (disposable). The assistant never disappears into
a 40-minute loop; workers do, and it reports back.

## Left edge stays simple

New Chat; CONTROL (Overview, H-Tasks count, Agents count); CHATS;
PROJECTS. Overview converts chat into a richer control view. Agent status
appears inline as cards with inspect actions. No separate monitoring app.

## Right panel doubles as agent inspector

No H-task: agent card (task, harness, model, state, budget, tools, QP
standing, open transcript, pause, kill, fork). H-task arrives: same panel
becomes HLoop UI. Mental model: right side is whatever needs attention now.

## Vault as first-class subsystem

Safer than `.env` management. VaultSecret: name, encrypted value, allowed
tools, allowed workers, project scope, expiry, usage count,
never_expose_to_model. Tools receive credentials through a protected
execution channel. Flow: human → HLoop secure input → local encrypted vault
→ capability token → specific tool/process. The model only ever sees
`credential_available("service_x")`, never the value.

## Same H-task state on AgentDeck

Desktop right panel and phone show the same queue: approvals, OTP needs,
predictions with 0–9 pad. At the desk it feels like a ChatGPT/control-plane
hybrid; away, AgentDeck is the compressed human-control interface.

## Dynamic UI ratios

Chat 100% normal; 70/30 inspecting; 65/35 H-task; 40/60 deep control mode.
Dashboard never overwhelms conversation.

## Core shape

Stealth desktop over conversational assistant plus human loop, both over
AgentCom v2, over Pi workers, over QP verified state, with the vault beside
QP for permissions and secrets. ChatGPT-style conversation wrapped around a
live operating system for autonomous agents, with a secure human
intervention lane always beside it.
