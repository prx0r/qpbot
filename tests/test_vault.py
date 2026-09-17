import os
import tempfile

import pytest

from agentcom.vault.store import Vault


def _vault():
    d = tempfile.mkdtemp()
    return Vault(os.path.join(d, "vault.json"), os.path.join(d, "vault.key"))


def test_store_and_model_sees_only_availability():
    v = _vault()
    r = v.store("SERVICE_X_TOKEN", "sk-live-123", ["service-x"], ["worker-3"],
                scope="stealth", ttl_s=600, kind="llm-inference", tier="paid",
                model="mimo-v2.5", provider="opencode-go",
                rate_limit={"per_minute": 600, "monthly_cap": 150400})
    assert r["stored"] is True
    assert v.credential_available("SERVICE_X_TOKEN") is True
    assert "sk-live-123" not in open(v.store_path).read()


def test_resolve_enforces_full_grant():
    v = _vault()
    v.store("T", "val", ["good-tool"], ["w1"], scope="s", ttl_s=600)
    cap = v.secrets["T"]["capability"]
    assert v.resolve("T", "good-tool", "w1", cap, scope="s") == "val"
    with pytest.raises(ValueError):
        v.resolve("T", "evil-tool", "w1", cap, scope="s")
    with pytest.raises(ValueError):
        v.resolve("T", "good-tool", "w1", "wrong-cap", scope="s")


def test_expiry_and_usage_caps():
    v = _vault()
    v.store("E", "val", ["t"], ["w"], ttl_s=-1)
    assert v.credential_available("E") is False
    with pytest.raises(ValueError):
        v.resolve("E", "t", "w", v.secrets["E"]["capability"])
    v.store("U", "val", ["t"], ["w"], ttl_s=600, max_uses=1)
    cap = v.secrets["U"]["capability"]
    v.resolve("U", "t", "w", cap)
    with pytest.raises(ValueError):
        v.resolve("U", "t", "w", cap)


def test_revoke_and_audit():
    v = _vault()
    v.store("R", "val", ["t"], ["w"])
    v.revoke("R")
    assert v.credential_available("R") is False
    events = [e["event"] for e in v.audit]
    assert events == ["stored", "revoked"]


def test_active_flag():
    v = _vault()
    v.store("A", "val", ["t"], ["w"], ttl_s=600, active=True)
    assert v.credential_available("A") is True
    v.set_active("A", False)
    assert v.credential_available("A") is False
    with pytest.raises(ValueError, match="inactive"):
        v.resolve("A", "t", "w", v.secrets["A"]["capability"])


def test_find_by_kind_and_tier():
    v = _vault()
    v.store("LLM1", "k1", ["t"], ["w"], ttl_s=600, kind="llm-inference",
            tier="paid", provider="opencode-go", model="mimo-v2.5")
    v.store("LLM2", "k2", ["t"], ["w"], ttl_s=600, kind="llm-inference",
            tier="unpaid", provider="opencode-go", model="glm-5.3-flash",
            active=False)
    v.store("CF1", "k3", ["t"], ["w"], ttl_s=600, kind="cloudflare",
            tier="paid")
    paid = v.find(kind="llm-inference", tier="paid")
    assert len(paid) == 1 and paid[0]["name"] == "LLM1"
    all_llm = v.find(kind="llm-inference", active_only=False)
    assert len(all_llm) == 2
    assert len(v.find(kind="cloudflare")) == 1
    assert len(v.find(provider="opencode-go")) == 1


def test_usage_tracking():
    v = _vault()
    v.store("U1", "k", ["t"], ["w"], ttl_s=600, kind="llm-inference",
            model="mimo-v2.5")
    v.record_usage("U1", tokens_in=500, tokens_out=200, cost_minor=3)
    v.record_usage("U1", tokens_in=300, tokens_out=100, cost_minor=2)
    u = v.secrets["U1"]["usage"]
    assert u["calls"] == 2
    assert u["tokens_in"] == 800
    assert u["tokens_out"] == 300
    assert u["cost_minor"] == 5
    s = v.usage_summary()
    assert s["totals"]["calls"] == 2
    assert "llm-inference" in s["by_kind"]
    assert "mimo-v2.5" in s["by_model"]
