"""Workflows — decompose high-level goals into concrete tool chains.

Each workflow is a sequence of steps. Each step has:
- A tool to call (or a sub-workflow)
- Input mapping from previous step outputs
- Validation criteria (QP proof)
- Output shape for the next step

The LLM follows the workflow like a playbook. Each step produces
evidence that gets validated and stored as a prize.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class StepResult:
    step: str
    tool: str
    args: list[str]
    output: dict
    valid: bool = False
    evidence: str = ""
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowResult:
    workflow: str
    goal: str
    steps: list[StepResult] = field(default_factory=list)
    status: str = "running"  # running -> completed -> failed
    prize: dict = field(default_factory=dict)
    started: float = 0.0
    finished: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "workflow": self.workflow,
            "goal": self.goal,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "prize": self.prize,
            "duration_s": round(self.finished - self.started, 1) if self.finished else 0,
            "error": self.error,
        }


# ── Step definitions ───────────────────────────────────────────────────

@dataclass
class Step:
    name: str
    tool: str
    args_from: dict[str, str] = field(default_factory=dict)
    # args_from maps: arg_position -> "previous_step.field" or "constant"
    validate: str = ""  # JSONPath-like check: "data.total_usd > 0"
    description: str = ""

    def build_args(self, context: dict) -> list[str]:
        """Build tool args from the context of previous step outputs."""
        args = []
        for i in range(10):  # max 10 positional args
            key = str(i)
            if key not in self.args_from:
                break
            ref = self.args_from[key]
            if ref.startswith("$"):
                # Reference to previous step output: "$step_name.field"
                parts = ref[1:].split(".", 1)
                step_name = parts[0]
                field_path = parts[1] if len(parts) > 1 else ""
                val = context.get(step_name, {})
                if field_path:
                    for f in field_path.split("."):
                        if isinstance(val, list) and f.isdigit():
                            idx = int(f)
                            val = val[idx] if idx < len(val) else ""
                        elif isinstance(val, dict):
                            val = val.get(f, "")
                        else:
                            val = ""
                            break
                args.append(str(val) if val else "")
            else:
                # Constant value
                args.append(ref)
        return args

    def validate_output(self, output: dict) -> tuple[bool, str]:
        """Validate step output against criteria. Returns (valid, evidence)."""
        if not self.validate:
            return True, "no validation criteria"

        try:
            checks = [c.strip() for c in self.validate.split(" and ")]
            for check in checks:
                if ">" in check:
                    parts = check.split(">")
                    path = parts[0].strip()
                    threshold = float(parts[1].strip())
                    val = self._resolve_path(output, path)
                    if val is None:
                        return False, f"{path}=None <= {threshold}"
                    if float(val) <= threshold:
                        return False, f"{path}={val} <= {threshold}"
                elif "==" in check:
                    parts = check.split("==")
                    path = parts[0].strip()
                    expected = parts[1].strip().strip("'\"")
                    val = str(self._resolve_path(output, path))
                    if val != expected:
                        return False, f"{path}={val} != {expected}"
                elif "exists" in check:
                    path = check.replace("exists", "").strip()
                    val = self._resolve_path(output, path)
                    if not val:
                        return False, f"{path} does not exist"
            return True, "validated"
        except Exception as e:
            return False, f"validation error: {e}"

    def _resolve_path(self, data: dict, path: str) -> Any:
        """Resolve a dot-path against a nested dict/list."""
        parts = path.split(".")
        node = data
        for p in parts:
            if isinstance(node, list) and p.isdigit():
                idx = int(p)
                node = node[idx] if idx < len(node) else None
            elif isinstance(node, dict) and p in node:
                node = node[p]
            else:
                return None
        return node


# ── Workflow definitions ───────────────────────────────────────────────

WORKFLOWS: dict[str, dict] = {}


def define_workflow(name: str, goal: str, steps: list[Step],
                    description: str = ""):
    WORKFLOWS[name] = {
        "name": name,
        "goal": goal,
        "steps": steps,
        "description": description,
    }


# Workflow 1: Find a funded wallet
define_workflow(
    name="find_funded_wallet",
    goal="Discover a cryptocurrency wallet with funds, verify the balance, and classify the key type.",
    description="Scans whale transactions, checks balances, classifies the key.",
    steps=[
        Step(
            name="discover_wallets",
            tool="whale_feed",
            args_from={"0": "100000"},  # min_usd filter
            validate="count > 0",
            description="Find recent large transactions",
        ),
        Step(
            name="check_balance",
            tool="eth_check",
            args_from={"0": "$discover_wallets.txs.0.from.0"},
            validate="total_usd > 0",
            description="Check if the wallet has funds",
        ),
        Step(
            name="classify",
            tool="drain_classify",
            args_from={"0": "$discover_wallets.txs.0.from.0"},
            description="Classify the wallet key type and drain authority",
        ),
    ],
)

# Workflow 2: Find GitHub connected to a wallet (full investigation chain)
define_workflow(
    name="find_github_for_wallet",
    goal="Full OSINT investigation: resolve wallet to identity through multiple signal chains.",
    description="""Investigation pipeline:
  Phase 1 - On-chain resolution (fast, free):
    ENS reverse → name.eth → extract username
    ENS com.github text record → GitHub username directly
    Farcaster → @username
    Lens Protocol → @username
    FOMO → @trader_handle
    Etherscan → contract name / entity label
    OpenSea → @username

  Phase 2 - GitHub search (network):
    Search GitHub code for wallet address
    Check if address is in README (donation address = high confidence)
    Extract repo owners as candidate handles

  Phase 3 - Cross-platform correlation:
    For each handle found, check GitHub profile + social platforms
    Score confidence based on signal overlap
    2+ high-confidence signals = strong match""",
    steps=[
        Step(
            name="investigate",
            tool="wallet_investigate",
            args_from={"0": "$WALLET_ADDRESS"},
            validate="summary.signals_count > 0",
            description="Full OSINT chain: ENS → Farcaster → Lens → FOMO → GitHub → social",
        ),
        Step(
            name="search_repos",
            tool="wallet_github",
            args_from={"0": "address", "1": "$WALLET_ADDRESS"},
            description="Deep GitHub search for repos containing the wallet address",
        ),
        Step(
            name="scan_best_repo",
            tool="clone_scan",
            args_from={"0": "$search_repos.results.0.repo"},
            description="Clone and scan the most relevant repo for secrets",
        ),
    ],
)

# Workflow 3: Full prize pipeline (wallet + key + repo)
define_workflow(
    name="capture_prize",
    goal="Full prize capture: find wallet, investigate identity, extract key, classify, validate, store.",
    description="""End-to-end prize capture:
  1. Find a high-value wallet via whale feed
  2. Verify it's funded (QP proof: balance > $1000)
  3. Full OSINT investigation (ENS, Farcaster, Lens, FOMO, GitHub)
  4. Classify the key type and drain authority
  5. Store as prize with full context""",
    steps=[
        Step(
            name="find_wallet",
            tool="whale_feed",
            args_from={"0": "500000"},
            validate="count > 0",
            description="Find a high-value wallet from whale transactions",
        ),
        Step(
            name="verify_funded",
            tool="eth_check",
            args_from={"0": "$find_wallet.txs.0.from.0"},
            validate="total_usd > 1000",
            description="Verify the wallet is funded (QP proof: balance > $1000)",
        ),
        Step(
            name="investigate",
            tool="wallet_investigate",
            args_from={"0": "$find_wallet.txs.0.from.0"},
            validate="summary.signals_count > 0",
            description="Full OSINT investigation to find GitHub/social identity",
        ),
        Step(
            name="classify_key",
            tool="drain_classify",
            args_from={"0": "$find_wallet.txs.0.from.0"},
            description="Classify the key type and drain authority",
        ),
    ],
)

# Workflow 4: Scan a specific repo for secrets
define_workflow(
    name="scan_repo_secrets",
    goal="Clone a repository and extract all secrets, classify them, check balances.",
    description="Deep repo scan with full classification pipeline.",
    steps=[
        Step(
            name="clone_and_scan",
            tool="clone_scan",
            args_from={"0": "$REPO_URL"},
            validate="total_secrets >= 0",
            description="Clone repo and scan for secrets",
        ),
        Step(
            name="classify",
            tool="drain_classify",
            args_from={"0": "$clone_and_scan.findings.git_history.0.data.secrets.0"},
            description="Classify each found secret",
        ),
    ],
)


# ── Workflow runner ────────────────────────────────────────────────────

class WorkflowRunner:
    """Execute a workflow step by step, collecting evidence."""

    def __init__(self, tool_executor):
        """
        Args:
            tool_executor: callable(tool_name, args) -> dict
                          e.g., scanners.registry.fire or harness.execute_tool
        """
        self.execute = tool_executor

    def run(self, workflow_name: str, initial_context: dict | None = None,
            max_steps: int = 10, force: bool = False) -> WorkflowResult:
        """Run a workflow from start to finish with RSI logging."""
        from agentcom.invlog import InvestigationLog
        from agentcom.seen import SeenTracker

        wf = WORKFLOWS.get(workflow_name)
        if not wf:
            return WorkflowResult(workflow=workflow_name, goal="",
                                  status="failed", error=f"unknown workflow: {workflow_name}")

        result = WorkflowResult(
            workflow=workflow_name,
            goal=wf["goal"],
            status="running",
            started=time.time(),
        )
        context = dict(initial_context or {})

        # RSI: log investigation start
        invlog = InvestigationLog()
        address = context.get("WALLET_ADDRESS", context.get("0", ""))
        run_id = invlog.log_start(address, workflow=workflow_name)

        # Dedup: skip if wallet already investigated
        seen = SeenTracker()
        if address and not force:
            if seen.is_seen(address):
                result.status = "skipped"
                result.error = f"wallet {address} already investigated recently"
                result.finished = time.time()
                return result

        for step in wf["steps"][:max_steps]:
            t0 = time.time()

            # Build args
            args = step.build_args(context)
            if not args and step.tool != "whale_feed":
                result.status = "failed"
                result.error = f"step '{step.name}': could not resolve args"
                result.finished = time.time()
                invlog.log_end(run_id, "failed", len(result.steps), 0, False)
                return result

            # Execute tool
            try:
                output = self.execute(step.tool, args)
                if isinstance(output, str):
                    try:
                        output = json.loads(output)
                    except json.JSONDecodeError:
                        output = {"raw": output}
            except Exception as e:
                output = {"error": str(e)}

            # RSI: log investigation step
            duration_ms = int((time.time() - t0) * 1000)
            invlog.log_step(run_id, step.tool, args, output, duration_ms)

            # Validate
            valid, evidence = step.validate_output(output)

            step_result = StepResult(
                step=step.name,
                tool=step.tool,
                args=args,
                output=output,
                valid=valid,
                evidence=evidence,
                duration_s=round(time.time() - t0, 2),
            )
            result.steps.append(step_result)

            # Store output in context for next step
            context[step.name] = output

        # Check if all validations passed
        all_valid = all(s.valid for s in result.steps if s.evidence != "no validation criteria")
        result.status = "completed" if all_valid else "completed_with_warnings"
        result.finished = time.time()

        # RSI: log investigation end
        total_signals = sum(1 for s in result.steps if s.valid)
        invlog.log_end(run_id, result.status, len(result.steps),
                       total_signals, all_valid)

        # Dedup: mark address as investigated
        if address:
            has_github = any("github" in s.tool.lower() or "investigate" in s.tool.lower()
                            for s in result.steps)
            chain = "ethereum" if address.startswith("0x") else "unknown"
            seen.mark(address, workflow=workflow_name, run_id=run_id,
                      signals_found=total_signals, prize_stored=all_valid,
                      github_found=has_github, chain=chain)

        return result


# ── Helper: extract wallet info from workflow result ───────────────────

def extract_wallet_info(result: WorkflowResult) -> dict:
    """Extract structured wallet info from a workflow result for prize storage."""
    info = {
        "address": "",
        "chain": "",
        "wallet_kind": "",
        "balance_usd": 0,
        "key_type": "",
        "drain_class": "",
        "github_repos": [],
        "github_handles": [],
        "fomo_handle": "",
        "signals": [],
    }

    for step in result.steps:
        output = step.output

        if step.step in ("check_balance", "verify_funded"):
            info["balance_usd"] = output.get("total_usd", 0) or output.get("sol_usd", 0)
            if output.get("ETH", 0) > 0:
                info["chain"] = "ethereum"
                info["wallet_kind"] = "evm"
            elif output.get("SOL", 0) > 0:
                info["chain"] = "solana"
                info["wallet_kind"] = "solana"

        elif step.step == "classify" or step.step == "classify_key":
            info["key_type"] = output.get("kind", output.get("type", ""))
            info["drain_class"] = output.get("authority", output.get("class", ""))

        elif step.step == "resolve_identity" or step.step == "find_github":
            info["github_repos"] = [r.get("repo", "") for r in output.get("github_repos", [])]
            info["github_handles"] = [h.get("handle", "") for h in output.get("handles", [])]
            info["signals"] = output.get("signals", [])
            for h in output.get("handles", []):
                if h.get("source") == "fomo":
                    info["fomo_handle"] = h.get("handle", "")

        elif step.step == "discover_wallets" or step.step == "find_wallet":
            txs = output.get("txs", [])
            if txs:
                info["address"] = txs[0].get("from", [""])[0] if isinstance(txs[0].get("from"), list) else txs[0].get("from", "")
                chain = txs[0].get("chain", "")
                if chain == "bitcoin":
                    info["chain"] = "bitcoin"
                    info["wallet_kind"] = "btc"
                elif chain == "ethereum":
                    info["chain"] = "ethereum"
                    info["wallet_kind"] = "evm"

    return info
