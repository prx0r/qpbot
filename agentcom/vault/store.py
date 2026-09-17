"""Vault — local encrypted secret store with scoped capability grants.

Model sees credential_available(name) only. Tools resolve values through
grants bound to tool + worker + scope + expiry + usage cap. Every access
appends to the audit log. Master key: QPBOT_VAULT_KEY env or 0600 key file.

Categories organize secrets for agent retrieval:
  kind: llm-inference | cloudflare | service | other
  tier: paid | unpaid | trial
  active: bool — quick filter for "give me a working key"
  rate_limit: {per_minute, per_day, monthly_cap} — known limits
  usage: {calls, tokens_in, tokens_out, cost_minor} — deterministic counter
"""
from __future__ import annotations

import base64
import fcntl
import json
import os
import time
from contextlib import contextmanager

from cryptography.fernet import Fernet, InvalidToken


def _master_key(key_path: str) -> bytes:
    env = os.environ.get("QPBOT_VAULT_KEY", "")
    if env:
        return env.encode()
    if os.path.exists(key_path):
        return open(key_path, "rb").read().strip()
    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(key_path) or ".", exist_ok=True)
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key + b"\n")
    return key


class Vault:
    def __init__(self, store_path: str, key_path: str = ""):
        self.store_path = store_path
        self.fernet = Fernet(_master_key(
            key_path or os.path.join(os.path.dirname(store_path) or ".",
                                     "vault.key")))
        self._load()

    def _load_inner(self):
        self.secrets: dict[str, dict] = {}
        self.audit: list[dict] = []
        self.prizes: list[dict] = []
        if os.path.exists(self.store_path):
            raw = json.load(open(self.store_path))
            self.audit = raw.get("audit", [])
            self.prizes = raw.get("prizes", [])
            for name, s in raw.get("secrets", {}).items():
                self.secrets[name] = s

    def _load(self):
        with self._locked(False):
            self._load_inner()

    @contextmanager
    def _locked(self, exclusive: bool):
        """Cross-process guard: bg loop, harnesses, dashboard and
        prize-record subprocesses share one vault file."""
        os.makedirs(os.path.dirname(self.store_path) or ".", exist_ok=True)
        with open(self.store_path + ".lock", "a+") as lf:
            fcntl.flock(lf.fileno(),
                        fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                yield
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    def _save_inner(self):
        tmp = self.store_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"secrets": self.secrets, "audit": self.audit,
                       "prizes": self.prizes}, f, indent=1)
        os.replace(tmp, self.store_path)

    def _save(self):
        os.makedirs(os.path.dirname(self.store_path) or ".", exist_ok=True)
        # Atomic rename + exclusive lock: readers never see a torn file and
        # concurrent writers serialize (last wins, no interleave).
        with self._locked(True):
            self._save_inner()

    def _log(self, event: str, **fields):
        self.audit.append({"ts": int(time.time()), "event": event, **fields})

    def store(self, name: str, value: str, allowed_tools: list[str],
              allowed_workers: list[str], scope: str = "",
              ttl_s: int = 3600, max_uses: int = 0, *,
              kind: str = "other", tier: str = "unpaid",
              active: bool = True, rate_limit: dict | None = None,
              model: str = "", provider: str = "") -> dict:
        """Deposit from the H-task rail. Plaintext never leaves this call."""
        token = base64.urlsafe_b64encode(os.urandom(18)).decode()
        self.secrets[name] = {
            "cipher": self.fernet.encrypt(value.encode()).decode(),
            "allowed_tools": allowed_tools,
            "allowed_workers": allowed_workers,
            "scope": scope,
            "expires": int(time.time()) + ttl_s,
            "max_uses": max_uses,
            "uses": 0,
            "capability": token,
            "kind": kind,
            "tier": tier,
            "active": active,
            "model": model,
            "provider": provider,
            "rate_limit": rate_limit or {},
            "usage": {"calls": 0, "tokens_in": 0, "tokens_out": 0,
                      "cost_minor": 0},
        }
        self._log("stored", name=name, scope=scope, ttl_s=ttl_s,
                  kind=kind, tier=tier)
        self._save()
        return {"name": name, "stored": True, "expires_in_s": ttl_s}

    def credential_available(self, name: str) -> bool:
        """The only thing the model may see."""
        s = self.secrets.get(name)
        return bool(s) and s["expires"] > time.time() and s.get("active", True)

    def resolve(self, name: str, tool: str, worker: str,
                capability: str, scope: str = "") -> str:
        """Protected channel: value out only on full grant match."""
        s = self.secrets.get(name)
        if not s:
            raise ValueError("unknown secret")
        if not s.get("active", True):
            raise ValueError("key inactive")
        if s["capability"] != capability:
            raise ValueError("capability mismatch")
        if tool not in s["allowed_tools"]:
            raise ValueError(f"tool {tool} not granted")
        if worker not in s["allowed_workers"]:
            raise ValueError(f"worker {worker} not granted")
        if scope and s["scope"] and scope != s["scope"]:
            raise ValueError("scope mismatch")
        if s["expires"] <= time.time():
            raise ValueError("grant expired")
        if s["max_uses"] and s["uses"] >= s["max_uses"]:
            raise ValueError("usage cap reached")
        s["uses"] += 1
        self._log("resolved", name=name, tool=tool, worker=worker,
                  uses=s["uses"])
        self._save()
        try:
            return self.fernet.decrypt(s["cipher"].encode()).decode()
        except InvalidToken:
            raise ValueError("vault key mismatch")

    def record_usage(self, name: str, tokens_in: int = 0,
                       tokens_out: int = 0, cost_minor: int = 0):
        """Deterministic usage counter. Called after every API call.

        Holds the exclusive lock across reload → apply → save, so
        concurrent flushes serialize and no count is lost.
        """
        with self._locked(True):
            try:
                self._load_inner()
            except Exception:
                pass
            s = self.secrets.get(name)
            if not s:
                return
            u = s.setdefault("usage", {"calls": 0, "tokens_in": 0,
                                       "tokens_out": 0, "cost_minor": 0})
            u["calls"] += 1
            u["tokens_in"] += tokens_in
            u["tokens_out"] += tokens_out
            u["cost_minor"] += cost_minor
            self._log("usage", name=name, tokens_in=tokens_in,
                      tokens_out=tokens_out, cost_minor=cost_minor,
                      total_calls=u["calls"])
            self._save_inner()

    def set_active(self, name: str, active: bool):
        s = self.secrets.get(name)
        if s:
            s["active"] = active
            self._log("active_set", name=name, active=active)
            self._save()

    def find(self, kind: str = "", tier: str = "", active_only: bool = True,
             provider: str = "") -> list[dict]:
        """Agent query: find matching keys without resolving values."""
        out = []
        for name, s in self.secrets.items():
            if active_only and not s.get("active", True):
                continue
            if kind and s.get("kind") != kind:
                continue
            if tier and s.get("tier") != tier:
                continue
            if provider and s.get("provider") != provider:
                continue
            out.append({"name": name, "kind": s.get("kind", "other"),
                        "tier": s.get("tier", "unpaid"),
                        "provider": s.get("provider", ""),
                        "model": s.get("model", ""),
                        "usage": s.get("usage", {}),
                        "rate_limit": s.get("rate_limit", {}),
                        "capability": s.get("capability", "")})
        return out

    def usage_summary(self) -> dict:
        totals = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_minor": 0}
        by_kind: dict[str, dict] = {}
        by_model: dict[str, dict] = {}
        for name, s in self.secrets.items():
            u = s.get("usage", {})
            kind = s.get("kind", "other")
            model = s.get("model", "unknown")
            for k in ("calls", "tokens_in", "tokens_out", "cost_minor"):
                totals[k] += u.get(k, 0)
                by_kind.setdefault(kind, {}).setdefault(k, 0)
                by_kind[kind][k] += u.get(k, 0)
                by_model.setdefault(model, {}).setdefault(k, 0)
                by_model[model][k] += u.get(k, 0)
        return {"totals": totals, "by_kind": by_kind, "by_model": by_model}

    def revoke(self, name: str):
        if name in self.secrets:
            del self.secrets[name]
            self._log("revoked", name=name)
            self._save()

    def capture(self, target_id: str, agent_id: str, flag_sha256: str,
                receipt_id: str, model: str = "", turns: int = 0,
                tokens_in: int = 0, tokens_out: int = 0, cost_minor: int = 0,
                tools_used: list[str] | None = None, meta: dict | None = None,
                found_secret: str = "", found_name: str = "",
                found_kind: str = "other", found_tier: str = "unpaid",
                found_provider: str = "", found_model: str = ""):
        """Record a successful capture. If found_secret is provided, classify
        it, run tier-specific scripts, and store as a usable vault asset."""
        prize = {"ts": int(time.time()), "target_id": target_id,
                 "agent_id": agent_id, "flag_sha256": flag_sha256,
                 "receipt_id": receipt_id, "model": model, "turns": turns,
                 "tokens_in": tokens_in, "tokens_out": tokens_out,
                 "cost_minor": cost_minor,
                 "tools_used": tools_used or [], "meta": meta or {}}
        # Auto-classify and store found secrets
        asset_name = ""
        if found_secret and found_name:
            from .classifier import classify
            from .scripts import run_scripts
            profile = classify(found_secret)
            # Run tier-specific scripts
            script_results = run_scripts(found_secret, profile.scripts)
            # Store with classification metadata
            asset = self.store(
                found_name, found_secret,
                allowed_tools=["*"], allowed_workers=["*"],
                scope="captured", ttl_s=86400 * 30, max_uses=0,
                kind=profile.kind, tier=f"tier-{profile.tier}",
                active=True, provider=profile.chain, model=found_model)
            asset_name = found_name
            prize["asset_name"] = asset_name
            prize["asset_stored"] = True
            prize["key_type"] = profile.kind
            prize["key_tier"] = profile.tier
            prize["key_chain"] = profile.chain
            prize["key_confidence"] = profile.confidence
            prize["scripts_run"] = [r.get("script") for r in script_results]
            prize["script_results"] = script_results
        self.prizes.append(prize)
        self._log("prize", target_id=target_id, agent_id=agent_id,
                  receipt_id=receipt_id, model=model, turns=turns,
                  asset=asset_name)
        self._save()
        return prize

    def prizes_list(self, agent_id: str = "", target_id: str = "") -> list[dict]:
        out = self.prizes
        if agent_id:
            out = [p for p in out if p.get("agent_id") == agent_id]
        if target_id:
            out = [p for p in out if p.get("target_id") == target_id]
        return out

    def prize_stats(self) -> dict:
        total = len(self.prizes)
        if not total:
            return {"total": 0, "targets": 0, "agents": 0,
                    "total_cost_minor": 0, "total_tokens": 0}
        targets = len(set(p["target_id"] for p in self.prizes))
        agents = len(set(p["agent_id"] for p in self.prizes))
        cost = sum(p.get("cost_minor", 0) for p in self.prizes)
        tokens = sum(p.get("tokens_in", 0) + p.get("tokens_out", 0)
                     for p in self.prizes)
        return {"total": total, "targets": targets, "agents": agents,
                "total_cost_minor": cost, "total_tokens": tokens,
                "first_capture": self.prizes[0].get("ts", 0),
                "last_capture": self.prizes[-1].get("ts", 0)}
