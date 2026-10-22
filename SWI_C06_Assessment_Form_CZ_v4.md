# C06 — Assessment Form (CZ)

## Projekt

```text
Hodnotící tým: Office Reservation System
Hodnocený tým: Rent a Partner
Projekt: Rent a Partner
Assessed commit/tag: 51111fa
Datum: 22.10.2026
```

## Stavy

`YES / PARTLY / NO / N/A`

Každý řádek musí obsahovat Evidence.

## Baseline

| ID                                                    | Odpověď | Evidence / komentář                                                                                                                                                                       |
| ----------------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B1 Stejná identifikovaná baseline pro docs/code/tests | YES     | Repozitář obsahuje prolinkovanou dokumentaci ve složce `docs/`, kód ve `src/reservations/` a testy ve `src/reservations/tests/` v rámci jednoho commitu                                   |
| B2 Relevantní produkt nebo testy lze spustit          | YES     | Projekt obsahuje `pytest.ini`, `requirements.txt` a testovací moduly (např. `test_architecture.py`), které lze lokálně spustit. Dále je přítomen spustitelný skript `scripts/demo_c02.sh` |

## C02 — Engineering Specification

Vybraná operace: Create / Confirm reservation 
Vybraný business rule / invariant: Zamezení překrývání rezervací a řešení souběhu (Concurrency)

| ID                                                       | Odpověď | Evidence / komentář                                                                                                                            |
| -------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| R1 Operation: input + precondition + postcondition/state | YES     | Definice jsou zaznamenány v `docs/specification.md` a `docs/intent-and-change.md`, stavy jsou implementovány v `src/reservations/lifecycle.py` |
| R2 Business rule/invariant je jednoznačný                | YES     | Pravidla pro schvalování a dostupnost jsou separována do explicitních modulů `approval.py` a `availability.py`                                 |
| R3 Operation/rule je konzistentní se state modelem       | YES     | Moduly testů `test_approve.py`, `test_cancel.py` a `test_confirm.py` jasně mapují state transitions nad entitou rezervace                      |
| R4 Implementace odpovídá specifikované semantics         | YES     | Existence `test_concurrency.py` dokazuje, že implementace skutečně řeší byznys požadavek na zamezení překryvu při paralelních požadavcích      |
| R5 Existuje vhodná verification evidence                 | YES     | Důkazy o provedení spike řešení jsou v `docs/evidence-and-evolution.md` a otestovány pomocí `test_persistence_spike.py`                        |

## C03 — Architecture

Vybraná responsibility: Správa životního cyklu rezervace a notifikace 
Vybraná interaction: Volání notifikační služby při změně stavu 
Vybrané ADR/decision: Architektonické rozhodnutí o separaci doménové logiky od view vrstvy

| ID                                                   | Odpověď | Evidence / komentář                                                                                                                      |
| ---------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| A1 Responsibility + owner jsou explicitní            | YES     | Dokument `docs/architecture-and-decisions.md` obsahuje architektonická rozhodnutí. Logika je jasně delegována (např. `notifications.py`) |
| A2 Skutečný code ownership odpovídá architektuře     | YES     | Kód nevyužívá pouze `views.py` a `models.py`, ale deleguje logiku do specializovaných souborů jako `availability.py` a `approval.py`     |
| A3 Dynamic interaction odpovídá skutečnému call path | YES     | Interakce jsou ověřovány testem architektury `test_architecture.py` a nezávislým skriptem `check_architecture.py` v adresáři `scripts/`  |
| A4 ADR/decision odpovídá současné implementaci       | YES     | Skript `check_architecture.py` slouží k automatizovanému ověření, že kód neporušuje pravidla definovaná v ADR                            |

## C04 — Quality & Measurement

Quality concern: Concurrency / Transakční stabilita 
Criterion: Systém musí zabránit dvojité rezervaci stejného zdroje ve stejném čase při paralelních requestech

| ID                                                 | Odpověď | Evidence / komentář                                                                                                       |
| -------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------- |
| Q1 Criterion je skutečně evaluable                 | YES     | Scénář lze nasimulovat pomocí paralelních testovacích threadů                                                             |
| Q2 Measurement měří criterion ve správném contextu | YES     | Modul `test_concurrency.py` exekvuje paralelní testy nad databází (ověřeno integrací DB přes `test_persistence_spike.py`) |
| Q3 Decision odpovídá výsledku měření               | YES     | Výsledky měření a rozhodnutí jsou zaznamenávány do `docs/evidence-and-evolution.md`                                       |

## C05 — Detailed Design & Unit Verification

Vybraná software unit: Approval Policy (`approval.py`)

| ID                                                             | Odpověď | Evidence / komentář                                                                                                                        |
| -------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| D1 Design intent je explicitní a pochopitelný                  | YES     | Logika schvalování je izolována v samostatném souboru `approval.py`                                                                        |
| D2 DD odpovídá skutečné implementaci                           | YES     | Implementace v repozitáři odpovídá specifikaci v `docs/specification.md`                                                                   |
| D3 Unit/component tests jsou odvoditelné z DD                  | YES     | Testy jasně reflektují design. Modul `approval.py` je přímo testován souborem `test_approval_policy.py`[cite: 1]                           |
| D4 Relevantní branches/boundaries/states/failures jsou ověřeny | YES     | Ve `src/reservations/tests/` se nacházejí separátní testy pro různé stavy: `test_approve.py`, `test_cancel.py`, `test_confirm.py`[cite: 1] |
| D5 Vybraný test má smysluplný oracle/expected result           | YES     | Soubory jako `test_notifications.py` a `test_availability.py` kontrolují explicitní očekávané výstupy po operacích[cite: 1]                |

## Candidate findings

### F1

```text
Source: Struktura testů a nástrojů (scripts/check_architecture.py, test_architecture.py)[cite: 1]
Engineering claim: Architektura je validována automatizovaně.
Expected: Repozitář dodržuje architektonické hranice.
Observed: Tým vytvořil vlastní mechanismy pro statickou a dynamickou kontrolu architektury.
Evidence: Soubor check_architecture.py a test_architecture.py jasně vynucují oddělení logiky[cite: 1].
Verification performed: Statická analýza výpisu repozitáře[cite: 1].
Result: VERIFIED FINDING
```

### F2

```text
Source: Kořenový adresář repozitáře[cite: 1]
Engineering claim: CI/CD pipeline pro spouštění testů a skeletonu.
Expected: Existence konfiguračního souboru pro kontinuální integraci (např. .github/workflows/ nebo .gitlab-ci.yml).
Observed: Výpis repozitáře neobsahuje konfigurační soubory pro CI pipeline[cite: 1].
Evidence: Žádný CI soubor není v kořenové složce ani ve složce src/[cite: 1].
Verification performed: Kontrola stromové struktury commitu 51111fa421f001b606ccf4f50ad8a084579a5fd9[cite: 1].
Result: REJECTED CANDIDATE (Lze nastavit později)
```

### F3

```text
Source: Root directory, správa závislostí[cite: 1]
Engineering claim: Reprodukovatelné prostředí.
Expected: Závislosti jsou pevně zafixovány (např. requirements.txt s přesnými verzemi).
Observed: Soubor requirements.txt existuje[cite: 1]. Je třeba ověřit, zda obsahuje pinned verze nebo jen obecné názvy balíčků.
Evidence: Přítomnost requirements.txt v root adresáři[cite: 1].
Verification performed: Vizualizace obsahu kořenové složky[cite: 1].
Result: VERIFIED FINDING[cite: 2]
```

## Owner disposition

| Finding | ACCEPTED / REJECTED / DEFERRED | Reason/evidence | Action / no-change |
| ------- | ------------------------------ | --------------- | ------------------ |
| F1      |                                |                 |                    |
| F2      |                                |                 |                    |
| F3      |                                |                 |                    |