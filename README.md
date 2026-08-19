# screen-time-management-integration

Design-Dokumente und Architekturvergleich für Screen-Time-/Credit-Management-Integrationen.

## Pi-hole Deployment auf qnap-k3s

Pi-hole v6 als DNS-Filter auf dem K3s-Cluster (QNAP-VM, 24/7). FRITZ!Box bleibt DHCP-Server und dient als DNS-Fallback.

- Architektur und Plan: [docs/plans/2026-08-17-pihole-k3s-deployment.md](docs/plans/2026-08-17-pihole-k3s-deployment.md)
- Pre-Flight-Checks: [docs/pre-flight-checks.md](docs/pre-flight-checks.md)
- Deployment-Runbook: [docs/deployment-runbook.md](docs/deployment-runbook.md)
- FritzBox DNS-Setup: [docs/fritzbox-dns-setup.md](docs/fritzbox-dns-setup.md)
- Troubleshooting: [docs/troubleshooting.md](docs/troubleshooting.md)
- Manifeste: [deployment/pihole/](deployment/pihole/)

Status: **Design-Phase / Deployment bereit** — Pre-Flight-Checks Passed, Manifeste geschrieben, wartet auf manuelles `kubectl apply`.