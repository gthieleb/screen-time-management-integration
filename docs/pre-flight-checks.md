# Pre-Flight-Checks (Wave 1)

Ergebnisse der Pre-Flight-Checks vor dem Pi-hole-K3s-Deployment.
Datum: 2026-08-17

## Zusammenfassung

**Go/No-Go: GO**

Alle relevanten Checks bestanden. Ein offener Punkt (Port 53 auf dem Host-Interface) muss vor dem endgültigen `kubectl apply` via SSH auf dem K3s-Host geprüft werden — betrifft nur den K3s-Host, nicht den Cluster selbst.

## Check-Ergebnisse

| # | Check | Soll | Ist | Status |
|---|-------|------|-----|--------|
| 1 | K3s-Node Ready | Ready | Ready | PASS |
| 2 | g14-Node Ready (Worker, optional) | Ready/NotReady | n/a (nur k3s relevant) | INFO |
| 3 | CPU Cores auf k3s | >= 2 | 2 Cores | PASS |
| 4 | freie CPU auf k3s | > 500m | 816m frei | PASS |
| 5 | RAM auf k3s | >= 8 GB | 15.8 GB | PASS |
| 6 | freier RAM auf k3s | > 8 GB | 12.6 GB frei | PASS |
| 7 | CoreDNS im Cluster | ClusterIP, kein Host-Port 53 | ClusterIP 10.43.0.10 | PASS |
| 8 | ServiceLB vergibt Node-IP | 192.168.50.80 | 192.168.50.80 (Traefik: 192.168.50.30, 192.168.50.80) | PASS |
| 9 | Port 53 auf Host-Interface frei | kein Listener auf :53 | via `kubectl` nicht prüfbar | OFFEN |

## Offener Punkt: Port 53 Host-Check

Pi-hole benötigt Port 53 (UDP/TCP) auf dem Host-Interface. Die Prüfung via `kubectl` ist nicht möglich — sie muss direkt auf dem K3s-Host ausgeführt werden.

**Voraussetzung:** Tailscale-Auth auf dem K3s-Host, SSH-Zugriff auf `gun@k3s`.

**Befehl:**
```bash
ssh gun@k3s 'sudo ss -tulnp | grep :53'
```

**Erwartetes Ergebnis:** Kein Output (= Port 53 frei) oder nur Pi-hole selbst nach dem Deployment.

**Falls `systemd-resolved` blockt:** Siehe [troubleshooting.md](troubleshooting.md).

## Befehle zum Wiederholen der Checks

```bash
# Nodes + Rollen
kubectl get nodes -o wide

# Node-Ressourcen (metrics-server vorausgesetzt)
kubectl top node k3s

# CoreDNS Service
kubectl get svc -n kube-system -l k8s-app=kube-dns

# Alle Services mit External-IP (ServiceLB-Verhalten prüfen)
kubectl get svc --all-namespaces -o wide

# Pods auf dem k3s-Node
kubectl get pods --all-namespaces -o wide --field-selector spec.nodeName=k3s

# Host-Port 53 (auf dem K3s-Host direkt)
ssh gun@k3s 'sudo ss -tulnp | grep :53'
```

## Nächste Schritte

1. Offenen Port-53-Check via SSH klären.
2. Manifeste anwenden: siehe [deployment-runbook.md](deployment-runbook.md).
3. FRITZ!Box DNS umstellen: siehe [fritzbox-dns-setup.md](fritzbox-dns-setup.md).