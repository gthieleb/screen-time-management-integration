"""Pi-hole v6 REST API tests (direct HTTP, the layer below the MCP tools)."""
from __future__ import annotations

import uuid

import requests

from conftest import PIHOLE_WEB


def test_auth_returns_valid_session():
    from conftest import PIHOLE_PASSWORD
    if not PIHOLE_PASSWORD:
        import pytest
        pytest.skip("PIHOLE_PASSWORD not set")
    r = requests.post(f"{PIHOLE_WEB}/api/auth", json={"password": PIHOLE_PASSWORD}, timeout=10)
    r.raise_for_status()
    session = r.json()["session"]
    assert session["valid"] is True
    assert session["sid"]


def test_auth_rejects_wrong_password():
    r = requests.post(f"{PIHOLE_WEB}/api/auth", json={"password": "wrong"}, timeout=10)
    assert r.status_code in (401, 403)
    assert not r.json().get("session", {}).get("valid", False)


def test_requires_session(api):
    """Unauthenticated API access must be rejected."""
    r = requests.get(f"{PIHOLE_WEB}/api/stats/summary", timeout=10)
    assert r.status_code in (401, 403)


def test_version(api):
    # FTL v6.4.x exposes version info under /api/info/version
    data = api.get("/api/info/version")
    assert data["version"]["core"]["local"]["version"].startswith("v6")


def test_blocking_enabled(api):
    data = api.get("/api/dns/blocking")
    assert data["blocking"] == "enabled"


def test_stats_summary(api):
    data = api.get("/api/stats/summary")
    assert "clients" in data
    assert "queries" in data


def test_blocklists_installed(api):
    """The two shipped lists (StevenBlack + AdGuard) must be configured."""
    data = api.get("/api/lists")
    addresses = [lst["address"] for lst in data["lists"]]
    assert any("StevenBlack" in a for a in addresses), addresses
    assert any("AdGuardDNS" in a for a in addresses), addresses


def test_gravity_loaded(api):
    """Gravity must actually contain blocked domains from the lists."""
    data = api.get("/api/stats/summary")
    gravity = data["gravity"]["domains_being_blocked"]
    assert gravity > 50_000, f"gravity={gravity} — lists not loaded?"


def test_domain_rule_crud(api):
    """Add an exact deny rule, verify it, delete it, verify it's gone."""
    domain = f"api-crud-{uuid.uuid4().hex[:8]}.invalid"

    try:
        created = api.add_deny_exact(domain, comment="pytest api crud")
        assert created["domain"] == domain
        assert created["type"] == "deny"
        assert created["enabled"] is True

        # single-domain GET returns {"domains": [ ... ]} (plural key)
        found = api.get(f"/api/domains/deny/exact/{domain}")
        assert found["domains"][0]["domain"] == domain
    finally:
        api.remove_deny_exact(domain)

    # list endpoint does not server-side filter by domain param — filter client-side
    listing = api.get("/api/domains", params={"type": "deny"})
    matches = [d for d in listing["domains"] if d["domain"] == domain]
    assert matches == []
