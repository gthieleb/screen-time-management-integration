# Deployment-Runbook (Pi-hole auf K3s)

Schritt-für-Schritt-Anleitung zum Ausrollen von Pi-hole v6 auf dem QNAP-K3s-Cluster.

**Voraussetzungen:**
- `kubectl` konfiguriert für das K3s-Cluster
- SSH-Zugriff auf den K3s-Host (`gun@k3s` via Tailscale)
- Pre-Flight-Checks bestanden — siehe [pre-flight-checks.md](pre-flight-checks.md)

---

## 0. Vor Apply: Port 53 Host-Check

Bevor der Pi-hole-Pod startet, muss Port 53 auf dem Host-Interface frei sein.

```bash
ssh gun@k3s 'sudo ss -tulnp | grep :53'
```

- **Kein Output** → Port frei, weiter mit Schritt 1.
- **Output mit `systemd-resolved`** → siehe [troubleshooting.md](troubleshooting.md) (Abschnitt *Port 53 belegt durch systemd-resolved*).

---

## 1. Secret anpassen

Das im Repo abgelegte `secret.yaml` enthält nur einen Platzhalter. Vor dem Apply das echte Passwort setzen — am besten direkt via `kubectl create secret`, damit das Passwort nicht im Git landet:

```bash
kubectl create secret generic pihole-webpassword -n pihole \
  --from-literal=PIHOLE_WEBPASSWORD='<strong-pw>' \
  --dry-run=client -o yaml | kubectl apply -f -
```

Alternativ: in `deployment/pihole/secret.yaml` den Base64-Wert ersetzen:

```bash
echo -n 'strong-pw' | base64
# -> <base64-wert> in secret.yaml eintragen, dann kubectl apply -k
```

> **Empfohlen:** Variante mit `kubectl create secret` nutzen, dann `secret.yaml` aus `kustomization.yaml` entfernen, damit das Passwort nicht ins Repo committet wird.

## 2. Manifeste anwenden

```bash
kubectl apply -k deployment/pihole/
```

Erwartete Output-Zeilen:
```
namespace/pihole created
secret/pihole-webpassword created
configmap/pihole-config created
persistentvolumeclaim/pihole-config created
deployment.apps/pihole created
service/pihole created
```

## 3. Warten bis Pod Ready

```bash
kubectl get pods -n pihole -w
```

Erwartet: `pihole-<hash>` geht nach kurzer Zeit auf `1/1 Running`. Die `readinessProbe` (tcpSocket :53) wartet initial 10 s.

Abbruch mit `Ctrl+C`, sobald Ready.

Falls `CrashLoopBackOff` oder `Pending`: siehe [troubleshooting.md](troubleshooting.md).

## 4. Service prüfen

```bash
kubectl get svc -n pihole
```

Erwartet:
```
NAME     TYPE           CLUSTER-IP     EXTERNAL-IP      PORT(S)                                    AGE
pihole   LoadBalancer   10.43.x.y      192.168.50.80    53:300xx/UDP,53:300xx/TCP,80:300xx/TCP     1m
```

- `EXTERNAL-IP` muss `192.168.50.80` sein (ServiceLB vergibt Node-IP).
- Falls `EXTERNAL-IP` auf `<pending>` bleibt: siehe [troubleshooting.md](troubleshooting.md) (Abschnitt *ServiceLB vergibt keine External-IP*).

## 5. Smoke-Test DNS

```bash
# Von einem Gerät im LAN (nicht vom K3s-Host selbst):
nslookup heise.de 192.168.50.80
```

Erwartet: Antwort mit einer öffentlichen IP von `heise.de`. Antwortzeit < 100 ms typisch.

```bash
# Reverse-Check Pi-hole selbst
nslookup pi.hole 192.168.50.80
```

## 6. Pi-hole Web-UI öffnen

```
http://192.168.50.80/admin/
```

Login mit dem in Schritt 1 gesetzten `PIHOLE_WEBPASSWORD`.

## 7. Blocklists aktivieren

In der Web-UI unter **Adlists** (früher *Group Management → Adlists*) folgende URLs hinzufügen, dann *Save*:

| Name | URL |
|------|-----|
| StevenBlack Unified | https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts |
| AdGuard DNS filter | https://adguardteam.github.io/AdGuardDNSFilter/Filters/filter.txt |
| OISD Big | https://big.oisd.nl/domainswild |

Anschließend unter **Tools → Update Gravity** (oder Sidebar *Update Gravity*) ausführen — das lädt die Listen herunter und baut die internen Lookup-Tables. Dauert 1–3 min.

## 8. Client-Gruppen anlegen

In der Web-UI unter **Groups**:

- Gruppe **children** anlegen
- Gruppe **adults** anlegen
- Unter **Clients** die Geräte zuordnen (per MAC, IP oder Hostname). Da der Service `externalTrafficPolicy: Local` nutzt, bleiben die echten Client-IPs erhalten — Pi-hole erkennt die Kindergeräte zuverlässig.
- Pro Gruppe passende Adlist-/Allow-/Deny-Regeln konfigurieren.

## 9. Test — Blockierung verifizieren

```bash
# Wird von einer Standard-Blocklist erfasst (keine eigene Regel nötig):
nslookup youtube.com 192.168.50.80

# Explizit blockte Domain prüfen (Beispiel aus StevenBlack):
nslookup ads.google.com 192.168.50.80
```

Erwartet nach erfolgreicher Gravity-Aktualisierung:
- Antwort zeigt `0.0.0.0` bzw. die Pi-hole-Block-IP.
- In der Web-UI unter **Query Log** taucht die Anfrage als *blocked (gravity)* auf.

## 10. FRITZ!Box DNS umstellen

Erst nach erfolgreichem Smoke-Test und funktionierender Blocklist die FRITZ!Box auf Pi-hole umstellen — siehe [fritzbox-dns-setup.md](fritzbox-dns-setup.md).

Empfohlen: zunächst Variante B (pro Gerät), 24 h beobachten, dann Variante A (global).

## Rollback

Falls etwas schiefgeht und Pi-hole sofort aus dem DNS-Pfad genommen werden muss:

```bash
# FRITZ!Box: DNS1 zurück auf 192.168.50.1 (FRITZ!Box selbst), DNS2 leer/gleich
# Dann Pi-hole im Cluster parken (nicht löschen — behält Config):
kubectl scale deploy -n pihole pihole --replicas=0

# Komplett entfernen:
kubectl delete -k deployment/pihole/
# PVC behalten: nicht löschen, falls Config erhalten bleiben soll
```