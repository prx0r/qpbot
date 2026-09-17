# qpbot — QP Proof Reference

## What is a QP proof

A QP proof is not a mathematical deduction. It's an **empirical verification procedure**:

```
claim + evidence + gates → verdict → receipt
```

You define what you want to know (claim), what evidence you need, and what
checks must pass (gates) — **before** running. The run executes the checks
and produces a verifiable receipt.

## The one equation

$$
S_{t+1} = T(S_t, P) \iff \bigwedge_i G_i(S_t, P, E, A) = PASS
$$

State only changes when all gates pass. Not because someone says it succeeded.

## Creating a QP proof

```python
from acom.objects import make_claim, make_evidence
from acom.gates import execute
from acom.receipts import transition, verify_receipt

# 1. Define claim
claim = make_claim(
    statement="Large BTC transactions exist",
    domain="blockchain.bitcoin",
    result="UNKNOWN"
)

# 2. Collect evidence
ev = make_evidence(
    metric="btc_transaction",
    value=1000000,
    unit="usd",
    as_of="2026-09-17",
    source={"class": "blockchain", "source_id": "whale_feed",
            "artifact_hash": "sha256:abc123"}
)

# 3. Execute gates
gate = execute("evidence-fresh-v1", {"evidence": [ev]})
assert gate["result"] == "PASS"

# 4. Create receipt
claim["result"] = "TRUE"
receipt = transition(
    state_before={"cursor": 0},
    proposal=claim,
    evidence=[ev],
    gate_ids=["evidence-fresh-v1"],
    run={"worker": "test", "tokens": 0},
    proof_level=4
)

# 5. Verify receipt
v = verify_receipt(receipt)
assert v["ok"] is True
```

## Built-in gates

| Gate | What it checks |
|------|---------------|
| two-sources-v1 | ≥2 distinct source classes in evidence |
| claim-resolved-v1 | Claim result is TRUE or FALSE (not UNKNOWN) |
| evidence-fresh-v1 | Every evidence item has metric, as_of, value |
| no-duplicate-v1 | No two evidence items share an id |

## Receipt format

```json
{
  "protocol": "acom/0.1",
  "transition_type": "RESOLVE",
  "subject": "claim:abc123",
  "proposal": {...},
  "evidence_root": "merkle_root",
  "gates": [
    {"id": "evidence-fresh-v1", "result": "PASS", "proof": "2 items complete"}
  ],
  "passed": true,
  "id": "receipt:def456",
  "signature": ""
}
```

## Formal spec

Full mathematical formalization at: `/home/ubuntu/qprivately/`

Key files:
- `SPEC.md` — mathematical definitions
- `docs/RECIPES.md` — how to use the system
- `docs/FLOW.md` — step-by-step flow
- `wire/` — integration adapters

## Example: whale feed proof

```python
# From frameworks/test_qp_proof_reality.py
from wire.seesaw_to_discovery import ConstraintNode

# Real API call
api_result = call_tool("whale_feed", ["10000"])
txs = api_result.get("txs", [])

# Create evidence from real data
evidence = [make_evidence(
    metric="btc_transaction",
    value=tx.get("usd_approx", 0),
    unit="usd",
    as_of=time.strftime("%Y-%m-%d"),
    source={"class": "blockchain", "source_id": "btc",
            "artifact_hash": f"sha256:{tx.get('tx_hash', '')[:16]}"}
) for tx in txs[:3]]

# Execute gates
gate = execute("evidence-fresh-v1", {"evidence": evidence})
assert gate["result"] == "PASS"

# Create and verify receipt
receipt = transition(state_before, claim, evidence, ["evidence-fresh-v1"], run={...})
v = verify_receipt(receipt)
assert v["ok"] is True
```
