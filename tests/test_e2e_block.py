"""End-to-end screen-time scenario.

The core use case of the whole setup: block a domain via the MCP tool,
observe the DNS effect, remove the rule, observe the effect gone.
Uses a unique .invalid domain per run (RFC 6761 reserved — never real traffic).

Test order within the class matters; pytest executes methods in definition
order. The unique domain comes from a class-scoped fixture.
"""
from __future__ import annotations

import dns.resolver
import pytest

from conftest import resolve_with_retry


@pytest.fixture(scope="class")
def cls_domain(unique_domain):
    return unique_domain


class TestScreenTimeBlockScenario:
    """Scenario: parent blocks a domain (e.g. youtube.com for the kids),
    DNS enforces it immediately, rule is removed afterwards."""

    def test_01_block_domain_via_mcp(self, mcp, cls_domain):
        out = mcp.call(
            "block_domain",
            {"domain": cls_domain, "kind": "exact",
             "comment": "pytest e2e screen-time scenario"},
        )
        # response shape: {"domains": [rule], "processed": {...}}
        rule = out["domains"][0]
        assert rule["domain"] == cls_domain, out
        assert rule["type"] in ("deny", "block"), out

    def test_02_dns_returns_null_while_blocked(self, resolver, cls_domain):
        ans = resolve_with_retry(resolver, cls_domain, "A")
        assert any(r.address == "0.0.0.0" for r in ans), \
            f"{cls_domain} not blocked after block_domain"

    def test_03_rule_visible_in_domain_rules(self, mcp, cls_domain):
        out = mcp.call("list_domain_rules", {"type": "deny", "kind": "exact"})
        entries = out.get("domains", out) if isinstance(out, dict) else out
        assert any(
            (e.get("domain") == cls_domain) for e in entries
        ), f"{cls_domain} not in deny rules"

    def test_04_find_why_blocked_names_comment(self, mcp, cls_domain):
        out = mcp.call("find_why_blocked", {"domain": cls_domain})
        assert cls_domain in str(out)

    def test_05_remove_rule_via_mcp(self, mcp, cls_domain):
        mcp.call(
            "remove_domain_rule",
            {"type": "deny", "kind": "exact", "domain": cls_domain,
             "confirm": True},
        )

    def test_06_dns_nxdomain_after_unblock(self, resolver, cls_domain):
        resolve_with_retry(resolver, cls_domain, "A", expect_nxdomain=True)

    def test_07_rule_gone_from_api(self, api, cls_domain):
        listing = api.get("/api/domains", params={"type": "deny"})
        matches = [d for d in listing["domains"] if d["domain"] == cls_domain]
        assert matches == []

    def test_08_no_leftover_rules(self, api):
        """No pytest rules may survive the run (hygiene check + best-effort
        cleanup so a failed assertion does not poison the next run)."""
        listing = api.get("/api/domains", params={"type": "deny"})
        leftovers = [d for d in listing["domains"]
                     if d["domain"].startswith(("pytest-e2e-", "api-crud-"))]
        if leftovers:
            for rule in leftovers:
                api.remove_deny_exact(rule["domain"])
        assert leftovers == [], f"leftover test rules (cleaned up now): {leftovers}"
