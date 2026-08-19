"""DNS-level tests against Pi-hole (dig/host equivalent, via dnspython).

Run from LAN with PIHOLE_HOST=192.168.50.80, or from Tailnet with the
default 100.109.202.81.
"""
from __future__ import annotations

import time

import dns.resolver
import pytest

from conftest import BLOCKED_DOMAIN, NORMAL_DOMAIN, resolve_with_retry


def test_normal_domain_resolves_to_real_ip(resolver):
    """Allowed domains must resolve to a routable answer (not 0.0.0.0)."""
    ans = resolve_with_retry(resolver, NORMAL_DOMAIN, "A")
    ips = [r.address for r in ans]
    assert ips, "no A record returned"
    assert "0.0.0.0" not in ips, f"{NORMAL_DOMAIN} unexpectedly blocked: {ips}"


def test_blocked_domain_resolves_to_null(resolver):
    """List-blocked domains must return 0.0.0.0 (Pi-hole NULL blocking mode)."""
    ans = resolve_with_retry(resolver, BLOCKED_DOMAIN, "A")
    assert any(r.address == "0.0.0.0" for r in ans), \
        f"{BLOCKED_DOMAIN} not blocked: {[r.address for r in ans]}"


def test_blocked_domain_ipv6_null(resolver):
    ans = resolve_with_retry(resolver, BLOCKED_DOMAIN, "AAAA")
    assert any(r.address == "::" for r in ans), \
        f"{BLOCKED_DOMAIN} AAAA not nulled: {[r.address for r in ans]}"


def test_query_over_tcp(resolver):
    """DNS over TCP (fallback path) must work identically."""
    import dns.message
    import dns.query
    import dns.rdatatype

    q = dns.message.make_query(NORMAL_DOMAIN, "A")
    resp = dns.query.tcp(q, resolver.nameservers[0], timeout=5)
    answer_ips = [
        rdata.address
        for rr in resp.answer
        if rr.rdtype == dns.rdatatype.A
        for rdata in rr
    ]
    assert answer_ips, "no A record over TCP"
    assert "0.0.0.0" not in answer_ips, f"{NORMAL_DOMAIN} blocked over TCP"


def test_unknown_domain_nxdomain(resolver):
    """Nonexistent domains must yield NXDOMAIN (not a blocked answer)."""
    resolve_with_retry(resolver, "does-not-exist-xyz.invalid", "A", expect_nxdomain=True)


def test_cached_response_is_fast(resolver):
    """Warm-cache answers should return well under 1.5s (LAN/Tailnet RTT)."""
    resolve_with_retry(resolver, NORMAL_DOMAIN, "A")  # warm the cache
    t0 = time.monotonic()
    resolver.resolve(NORMAL_DOMAIN, "A")
    elapsed = time.monotonic() - t0
    assert elapsed < 1.5, f"cached lookup took {elapsed:.2f}s"


def test_upstream_chain_works(resolver):
    """A less common but real domain must resolve (proves upstream forwarding
    through 192.168.50.3 works, not just cached popular domains)."""
    ans = resolve_with_retry(resolver, "denic.de", "A")
    assert any(r.address != "0.0.0.0" for r in ans)
