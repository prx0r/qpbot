import time
import tempfile, os, json, queue

from agentcom.vault.ratelimit import RateLimiter, RateLimit
from agentcom.vault.circuitbreaker import CircuitBreaker
from agentcom.vault.asynclog import UsageLogger
from agentcom.vault.store import Vault


def test_rate_limiter_allows_under_limit():
    rl = RateLimiter()
    r = rl.check([("key-1", RateLimit(per_minute=3))])
    assert r["ok"] is True
    assert r["remaining_minute"] == 2


def test_rate_limiter_blocks_over_limit():
    rl = RateLimiter()
    for _ in range(3):
        rl.check([("k", RateLimit(per_minute=3))])
    r = rl.check([("k", RateLimit(per_minute=3))])
    assert r["ok"] is False
    assert "per_minute" in r["reason"]


def test_rate_limiter_three_tier():
    rl = RateLimiter()
    # key allows 10, team allows 2 → team blocks first
    for _ in range(2):
        rl.check([("key-1", RateLimit(per_minute=10)),
                  ("team-1", RateLimit(per_minute=2))])
    r = rl.check([("key-1", RateLimit(per_minute=10)),
                  ("team-1", RateLimit(per_minute=2))])
    assert r["ok"] is False
    assert r["blocked_scope"] == "team-1"


def test_circuit_breaker_trip_and_recovery():
    cb = CircuitBreaker(threshold=3, timeout_s=0.1)
    assert cb.allow() is True
    for _ in range(3):
        cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN
    assert cb.allow() is False
    time.sleep(0.15)
    assert cb.allow() is True
    assert cb.state == CircuitBreaker.HALF_OPEN
    for _ in range(3):
        cb.record_success()
    assert cb.state == CircuitBreaker.CLOSED


def test_circuit_breaker_neutral_preserves_state():
    cb = CircuitBreaker(threshold=3)
    cb.record_failure()
    cb.record_failure()
    cb.record_neutral()  # 429
    assert cb.state == CircuitBreaker.CLOSED
    assert cb._failures == 2


def test_async_logger_flushes_to_vault():
    d = tempfile.mkdtemp()
    v = Vault(os.path.join(d, "v.json"), os.path.join(d, "k"))
    v.store("L1", "k", ["t"], ["w"], ttl_s=600, kind="llm-inference",
            model="mimo-v2.5")
    log = UsageLogger(vault=v, buffer_size=10, flush_interval_s=0.05)
    log.log("L1", "mimo-v2.5", tokens_in=100, tokens_out=50, cost_minor=2)
    log.log("L1", "mimo-v2.5", tokens_in=200, tokens_out=80, cost_minor=3)
    time.sleep(0.15)
    log.shutdown()
    u = v.secrets["L1"]["usage"]
    assert u["calls"] == 2
    assert u["tokens_in"] == 300


def test_async_logger_drops_on_full():
    log = UsageLogger(buffer_size=2, flush_interval_s=999)
    for _ in range(5):
        log.log("x", "m")
    assert log.buffer.qsize() == 2  # only 2 fit
    log.shutdown()


def test_vault_find_and_usage_summary():
    d = tempfile.mkdtemp()
    v = Vault(os.path.join(d, "v.json"), os.path.join(d, "k"))
    v.store("A", "k1", ["t"], ["w"], ttl_s=600, kind="llm-inference",
            tier="paid", provider="opencode-go", model="mimo-v2.5")
    v.store("B", "k2", ["t"], ["w"], ttl_s=600, kind="cloudflare",
            tier="paid", provider="cloudflare")
    llm = v.find(kind="llm-inference")
    assert len(llm) == 1 and llm[0]["name"] == "A"
    cf = v.find(kind="cloudflare")
    assert len(cf) == 1
    v.record_usage("A", tokens_in=500, tokens_out=200, cost_minor=5)
    s = v.usage_summary()
    assert s["totals"]["calls"] == 1
    assert s["by_model"]["mimo-v2.5"]["tokens_in"] == 500
