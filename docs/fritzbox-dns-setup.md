# FRITZ!Box DNS-Setup

Schritt-für-Schritt-Anleitung zur Umstellung der FRITZ!Box auf den Pi-hole als primären DNS-Server.

Pi-hole läuft unter `192.168.50.80` (K3s-Node, ServiceLB-External-IP). Die FRITZ!Box (`192.168.50.1`) bleibt DHCP-Server und dient als DNS-Fallback (DNS2).

## Übersicht der Varianten

| Variante | Scope | Einsatz | Risiko |
|----------|-------|---------|--------|
| A — Global | Alle Geräte im LAN | Finaler Zustand | Hoch — alle betroffen |
| B — Pro-Gerät | Einzelnes Gerät | Rollout-Phase, gezieltes Testing | Niedrig |

**Empfohlener Ablauf:** Erst Variante B für die Geräte der Kinder (Nepis Tablet, Switch), 24 h beobachten, dann schrittweise auf Variante A ausrollen.

---

## Variante A: Globaler DNS-Server in der FRITZ!Box

Setzt Pi-hole als primären DNS-Server für **alle** per DHCP verteilten Geräte.

1. FRITZ!Box-WebUI öffnen: `http://192.168.50.1`
2. **Heimnetz → Netzwerkeinstellungen** öffnen.
3. Reiter **IP-Adressen** wählen.
4. Im Bereich **DNS-Server**:
   - **Lokaler DNS-Server (primär):** `192.168.50.80` eintragen
   - **DNS-Server (sekundär):** `192.168.50.1` eintragen (FRITZ!Box als Fallback)
5. **Übernehmen** klicken.
6. Alle DHCP-Clients erneuern ihren Lease (neues DNS greift automatisch nach Lease-Erneuerung oder WLAN-Reconnect).

> **Hinweis:** Bestehende Verbindungen greifen erst nach DNS-Neuzuweisung. Bei Bedarf WLAN am Gerät einmal aus/einschalten.

### Screenshot-Platzhalter

```
[Screenshot: Heimnetz > Netzwerkeinstellungen > IP-Adressen > DNS-Server-Feld]
Speicherort: docs/img/fritzbox-dns-global.png
```

---

## Variante B: Pro-Gerät DNS zuweisen

Setzt Pi-hole nur für einzelne, ausgewählte Geräte — ideal für ein gezieltes Rollout an Nepis Tablet/Switch.

1. FRITZ!Box-WebUI öffnen: `http://192.168.50.1`
2. **Heimnetz → Geräteübersicht** öffnen.
3. Zielgerät (z.B. *Nepis Tablet*) suchen → **Bearbeiten** (Stift-Icon).
4. Reiter **Netzwerkeinstellungen** (bzw. *IP-Adressen*).
5. **DNS-Server zuweisen** aktivieren / auf manuell setzen:
   - **Primärer DNS-Server:** `192.168.50.80`
   - **Sekundärer DNS-Server:** `192.168.50.1` (FRITZ!Box)
6. **Übernehmen** klicken.
7. Gerät neu mit dem WLAN verbinden (WLAN aus/einschalten), damit das neue DNS greift.

### Screenshot-Platzhalter

```
[Screenshot: Heimnetz > Geräteübersicht > Gerät bearbeiten > DNS-Server zuweisen]
Speicherort: docs/img/fritzbox-dns-per-device.png
```

---

## Beobachtungsphase (24 h)

Unmittelbar nach der Umstellung auf Variante B oder A:

- [ ] Geräte kommen ins Internet (Standard-Seiten laden)
- [ ] Pi-hole Web-UI (`http://192.168.50.80/admin/`) zeigt Clients unter *Tools → Top Clients*
- [ ] Blockierte Domains tauchen unter *Tools → Top Blocked Domains* auf
- [ ] Keine auffälligen Latenzen beim Seitenaufbau
- [ ] Tablets/Switch der Kinder erreichen erlaubte Dienste, blockierte Dienste greifen nicht

Erst nach 24 h stabilem Betrieb auf alle Geräte ausrollen (Variante A).

---

## Wichtige Hinweise

### Mobiles Netz bypass

DNS-Filterung greift **nur im WLAN**. Mobilfunk (LTE/5G) und fremde WLANs umgehen Pi-hole vollständig. Für echte Screen-Time-Begrenzung ist zusätzlich nötig:

- **Android:** Google Family Link (Geräte-Ebene)
- **iOS / iPadOS:** Apple Screen Time (Geräte-Ebene)
- **Windows:** Microsoft Family Safety
- **Nintendo Switch:** Parental Controls der Nintendo-App

Siehe auch Hermes Skill `smart-home/screen-time-management`.

### Fallback verhält sich wie ohne Filter

Wenn Pi-hole ausfällt, verwendet das Gerät den DNS2 = `192.168.50.1` (FRITZ!Box). In dem Fall wird **ungefiltert** aufgelöst. Das ist erwünscht — Internet bleibt nutzbar, nur die Filterung pausiert. Bei dauerhaftem Pi-hole-Ausfall: FRITZ!Box DNS1 zurück auf `192.168.50.1` setzen.

### Bestehende manuelle DNS-Einträge prüfen

Einige Geräte haben evtl. fest codierte DNS-Server (z.B. `8.8.8.8`). Diese umgehen Pi-hole. In der FRITZ!Box unter *Heimnetz → Geräteübersicht → Bearbeiten* kontrollieren bzw. auf *automatisch* stellen.