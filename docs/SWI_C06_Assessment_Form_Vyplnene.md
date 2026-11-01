# C06 — Assessment Form (CZ)

## Projekt

```text
Hodnotící tým: EduGrid
Hodnocený tým: Office Reservation System team
Projekt: Office Reservation System
Assessed commit/tag: c06
Datum: 26. 10. 2026
```

---

# Stavy  
`YES / PARTLY / NO / N/A`  
Každý řádek obsahuje Evidence.

---

# Baseline

| ID | Odpověď | Evidence / komentář |
|---|---|---|
| **B1** Stejná identifikovaná baseline pro docs/code/tests | **YES** | `docs/intent-and-change.md` uvádí baseline v0.1 a v0.2; `docs/evidence-and-evolution.md` potvrzuje, že testy běží proti tagu `c06`; README obsahuje handover sekci s explicitním tagem. |
| **B2** Relevantní produkt nebo testy lze spustit | **YES** | `python manage.py test` → 66 testů OK na SQLite; PostgreSQL běh přes `TEST_DATABASE_URL` ověřen (`evidence-and-evolution.md`, C04). |

---

# C02 — Engineering Specification

Vybraná operace: **OP‑03 Confirm Reservation**  
Vybraný business rule / invariant: **BR‑02 — Invariant exkluzivity zdroje**

| ID | Odpověď | Evidence / komentář |
|---|---|---|
| **R1** Operation: input + precondition + postcondition/state | **YES** | OP‑03 v `intent-and-change.md` obsahuje spouštěcí událost, předpoklady, stav po provedení, změnu stavu. |
| **R2** Business rule/invariant je jednoznačný | **YES** | BR‑02 jasně definuje, že nesmí existovat dvě `CONFIRMED` rezervace stejného zdroje a dne; vynuceno kontrolou + DB indexem. |
| **R3** Operation/rule je konzistentní se state modelem | **YES** | Stavový diagram v `intent-and-change.md` (9b) odpovídá OP‑03 a BR‑02. |
| **R4** Implementace odpovídá specifikované semantics | **YES** | `services/lifecycle.py` (`confirm_reservation`, `ensure_can_allocate`, `allocate`) přesně implementují OP‑03 a BR‑02; potvrzeno testy C05. |
| **R5** Existuje vhodná verification evidence | **YES** | Testy: `test_create_and_confirm_desk_reservation`, `test_cannot_confirm_overlapping_resource`, `test_allocate_turns_a_lost_race_into_a_reservation_error`, měření C04. |

---

# C03 — Architecture

Vybraná responsibility: **Reservation Management owns all Reservation.status transitions**  
Vybraná interaction: **Confirm → allocate → notify_after_commit**  
Vybrané ADR/decision: **ADR‑01 — Approval workflow stays inside same deployable**

| ID | Odpověď | Evidence / komentář |
|---|---|---|
| **A1** Responsibility + owner jsou explicitní | **YES** | G2 v `c03-architecture.md` jasně definuje Reservation Management jako owner všech lifecycle změn. |
| **A2** Skutečný code ownership odpovídá architektuře | **YES** | `reservations/services/lifecycle.py` je jediné místo, kde se mění `Reservation.status`; ověřeno `test_architecture.py`. |
| **A3** Dynamic interaction odpovídá skutečnému call path | **YES** | Sekvenční diagram H1 odpovídá skutečnému toku v kódu (`confirm_reservation_view` → `confirm_reservation` → `allocate` → `notify_after_commit`). |
| **A4** ADR/decision odpovídá současné implementaci | **YES** | ADR‑01: žádný Approval Worker; expirace při čtení; notifikace oddělena v `integrations/notifications.py`. |

---

# C04 — Quality & Measurement

Quality concern: **Spolehlivost rezervace při souběhu (BR‑02)**  
Criterion: **20 souběžných pokusů → právě 1 CONFIRMED, ostatní ReservationError**

| ID | Odpověď | Evidence / komentář |
|---|---|---|
| **Q1** Criterion je skutečně evaluable | **YES** | Kritérium definováno přesně: počet vláken, počet kol, očekávané výsledky; viz C04 tabulka. |
| **Q2** Measurement měří criterion ve správném contextu | **YES** | Měření běží na PostgreSQL 15 přes `TEST_DATABASE_URL`; SQLite se správně přeskočí. |
| **Q3** Decision odpovídá výsledku měření | **YES** | Výsledné řešení M1 (explicitní zámek zdroje + DB index) splňuje kritérium ve všech 10 kolech; rozhodnutí popsáno v C04. |

---

# C05 — Detailed Design & Unit Verification

Vybraná software unit: **Confirm Reservation (services/lifecycle.py + rules.py)**

| ID | Odpověď | Evidence / komentář |
|---|---|---|
| **D1** Design intent je explicitní a pochopitelný | **YES** | DD sekce v `architecture-and-decisions.md` popisuje R1–R6, kontrakt `ensure_can_allocate`, algoritmus, pořadí kontrol. |
| **D2** DD odpovídá skutečné implementaci | **YES** | Kód odpovídá DD: explicitní zámek zdroje, čistá kontrola v `ensure_can_allocate`, notifikace po commitu. |
| **D3** Unit/component tests jsou odvoditelné z DD | **YES** | Testy v `test_confirmation_dd.py` přesně pokrývají DD‑1 až DD‑7. |
| **D4** Relevantní branches/boundaries/states/failures jsou ověřeny | **YES** | Testy pokrývají: neaktivní zdroj, konflikt, parkovací pravidlo, souběh, rollback, notifikace, nepovolené stavy. |
| **D5** Vybraný test má smysluplný oracle/expected result | **YES** | Např. `test_allocate_turns_a_lost_race_into_a_reservation_error` má jasný oracle: jedna CONFIRMED, ostatní ReservationError. |

---

# Candidate findings

### F1

```text
Source: C03 evidence (Part A)
Engineering claim: UI odpovídá statechartu v0.2
Expected: OP-01 a OP-03 jsou oddělené kroky
Observed: UI provádí create+confirm jako jednu akci (v0.3)
Evidence: intent-and-change.md — Baseline v0.3; views/create_reservation_view
Verification performed: kontrola kódu + testů
Result: VERIFIED FINDING
```

### F2

```text
Source: C05 evidence
Engineering claim: Notifikace je volána po commitu
Expected: notify_after_commit používá transaction.on_commit
Observed: Původní implementace volala notifikaci uvnitř transakce
Evidence: evidence-and-evolution.md — nález 2; test_notification_waits_for_the_commit
Verification performed: testy před/po opravě
Result: VERIFIED FINDING
```

### F3

```text
Source: C04 measurement
Engineering claim: Souběh drží DB index
Expected: index zachytí konflikty
Observed: na PostgreSQL rozhoduje zámek zdroje, index je až pojistka
Evidence: C04 — běhy M0, A, B, M1
Verification performed: měření na PostgreSQL
Result: VERIFIED FINDING
```

---

# Owner disposition

| Finding | ACCEPTED / REJECTED / DEFERRED | Reason/evidence | Action / no-change |
|---|---|---|---|
| **F1** | ACCEPTED | UI v0.3 je vědomá odchylka od baseline v0.2 | No-change (odchylka je zdokumentovaná v intent-and-change.md) |
| **F2** | ACCEPTED | Notifikace musela být opravena, testy to potvrdily | Action: opraveno pomocí `notify_after_commit` |
| **F3** | ACCEPTED | Měření C04 prokázalo nutnost explicitního zámku | Action: explicitní `lock_for_allocation` ponechán jako autoritativní místo |
