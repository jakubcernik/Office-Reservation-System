# C01 Engineering Spike
Question / unknown: What is the first functional version of the app, and what still needs to be fixed after the initial implementation?
What we did: Implemented a functional version of the application with Django, including authentication, reservation flows, admin management, demo data seeding, and initial scripts for setup and run.
Observed result: The app is working with a few bugs to solve.
Decision / what changes because of the result: Keep the current Django stack, fix the remaining bugs incrementally, and continue refining the registration flow, demo data, and reservation UX based on testing and user feedback.

---

# Evidence C02: specifikace → běžící aplikace

**Přijatá baseline:** `Specification Baseline v0.1` (čtyři základní operace, BR-01…BR-04) a po změně C02 `Baseline v0.2` (nová operace OP-05 a pravidla BR-05…BR-07). Obě jsou v `docs/intent-and-change.md`.

**Předvedené základní operace:**

| Operace | Kde je v aplikaci vidět |
| --- | --- |
| OP-01 Vytvoření rezervace | stránka Availability, tlačítko „Reserve“ (`POST /reservations/create/`) |
| OP-02 Zjištění dostupnosti | stránka Availability (`GET /`) |
| OP-03 Potvrzení rezervace | stránka My reservations, tlačítko „Confirm“ (`POST /reservations/<pk>/confirm/`) |
| OP-04 Zrušení rezervace | stránka My reservations, tlačítko „Cancel“ / „Withdraw request“ |
| OP-05 Rozhodnutí o žádosti | stránka Approvals, dostupná jen Office Managerovi |

**Skutečně provedené příklady ověření:** `python manage.py test` — **44 testů, výsledek `OK`** (spuštěno 26. 9. 2026). Mapování na operace:

| Operace | Úspěšný příklad | Negativní / hraniční příklad |
| --- | --- | --- |
| OP-01 | `CreateReservationTests.test_one_action_creates_a_confirmed_reservation` — jeden krok vytvoří potvrzenou rezervaci | `test_parking_still_requires_a_confirmed_desk`, `test_nothing_is_left_behind_when_the_check_fails`, `test_inactive_resource_cannot_be_reserved` |
| OP-02 | `test_confirmed_reservation_removes_resource_from_availability` | `test_inactive_resource_is_never_offered`, `test_pending_approval_does_not_block_availability` |
| OP-03 | `test_create_and_confirm_desk_reservation`, `test_parking_can_be_confirmed_after_desk` | `test_cannot_confirm_overlapping_resource`, `test_parking_requires_confirmed_desk` |
| OP-04 | `test_cancelling_confirmed_frees_the_resource`, `test_draft_can_be_cancelled` | `test_already_cancelled_reservation_is_rejected`, `test_finished_state_cannot_be_cancelled`, `test_only_owner_can_cancel` |
| OP-05 | `test_manager_approves_the_request`, `test_member_of_the_office_manager_group_can_decide` | `test_manager_rejects_the_request`, `test_owner_can_withdraw_a_pending_request`, `test_request_expires_when_its_day_is_over`, `test_expired_request_cannot_be_approved`, `test_second_request_for_the_same_resource_and_day_cannot_be_approved`, `test_approval_rechecks_the_parking_rule`, `test_regular_user_cannot_decide_about_approval` |

Nad rámec testů byl spuštěn běh proti databázi Supabase: migrace `reservations.0002_approval_process` proběhla úspěšně a seed obsahuje dva zdroje vyžadující schválení (`VED-01` v Ředitelském křídle, `P-VIP` na návštěvním vjezdu) z celkem 20 zdrojů. Na živé databázi byl ověřen i přechod žádosti: z návrhu na `VED-01` se potvrzením stala žádost `PENDING_APPROVAL` a objevila se ve frontě pro schvalovatele (`services.pending_approval_requests`). Prohlídka rozhraní v prohlížeči je na tým (dochází k ní při obhajobě).

Nové stránky jsou ověřené i přes HTTP (`ApprovalViewTests`): manažer stránku žádostí otevře a žádost schválí, běžný uživatel dostane `403`, neznámé rozhodnutí stav nemění, dostupnost označí zdroje vyžadující schválení a vlastník u žádosti vidí tlačítko pro její stažení. Potvrdit nebo zrušit jde i přímo na stránce dostupnosti (`AvailabilityActionViewTests`), takže uživatel nemusí přecházet na stránku svých rezervací; testy ověřují i to, že adresa mimo systém v parametru `next` se ignoruje.

**Nalezený nesoulad a způsob vyřešení:**

1. Kontrola konzistence odhalila rozpor mezi politikou rušení (BR-03: `DRAFT` i `CONFIRMED`) a kódem, který dovoloval jen `CONFIRMED`. Rozhodnuto ve prospěch specifikace: služba `cancel_reservation` používá `CANCELLABLE_STATUSES`, doplněny testy `test_draft_can_be_cancelled` a `test_finished_state_cannot_be_cancelled`.
2. Test `test_expired_request_cannot_be_approved` nejdřív **selhal**: expirace běžela uvnitř transakce rozhodnutí, takže se při odmítnutí rollbackem vrátila zpět a žádost zůstala `PENDING_APPROVAL`. Příčina byla v implementaci, ne ve specifikaci ani v příkladu ověření. Opraveno rozdělením na `decide_approval` (expirace mimo transakci) a `_apply_approval_decision` (vlastní rozhodnutí v transakci).
3. `makemigrations` chtěla přejmenovat indexy z migrace 0001, protože `models.py` je neměl pojmenované. Ponecháno jako součást migrace `0002_approval_process` (názvy indexů generuje Django); `makemigrations --check` je nyní čistý, takže se rozpor nebude vracet.
4. Dokumentace vs. realita: `README.md` zmiňuje test walking skeletonu (`WalkingSkeletonReservationCreateTests`), který v repu není. Podle README patří do C03 — vedený jako známý rozdíl, ne jako chybějící prvek C02.

**Shrnutí dopadu změny:** Přibyl příznak `Resource.requires_approval` (výchozí stav vypnuto, nastavuje manažer), tři nové stavy rezervace (`PENDING_APPROVAL`, `REJECTED`, `EXPIRED`), operace OP-05 s vlastní stránkou pro Office Managera a rozšířená politika rušení. Chování běžných zdrojů zůstalo doslova stejné: potvrzení je okamžité, dostupnost blokuje jen `CONFIRMED`, vytvoření dál jen zakládá návrh.

**Zbývající předpoklad / neznámá:** Kapacita zdrojů (neznámá už z C01) — systém ji neřeší. Oznámení zůstává stub do logu. Varianta BR-04 „nebo současně v jedné transakci vytváří“ nemá chování, protože aplikace nepotvrzuje více rezervací najednou.

**Samostatné rozhodnutí týmu — rezervace jedním krokem (baseline v0.3):** Uživatel nechce potvrzovat návrh zvlášť, proto OP-01 a OP-03 probíhají jako jedna akce (`create_reservation` vytvoří rezervaci a ve stejné transakci na ni použije pravidla potvrzení). Ověřeno `CreateReservationTests`: jeden krok vede k `CONFIRMED`, u schvalovaného zdroje k `PENDING_APPROVAL` a neúspěšná kontrola nezanechá žádný záznam. Stav `DRAFT` i operace Confirm zůstávají v modelu a ve specifikaci, aby čtyři základní operace zůstaly oddělené a ověřitelné.

**Architektonické drivery přenesené do C03:** notifikace jako skutečná externí závislost (rozšířila se na žádost, schválení, zamítnutí a vypršení); čas bez časovače (expirace se vyhodnocuje při čtení); BR-02 vynucené v aplikaci i v databázi; dvě role a potřeba jediného místa pro kontrolu oprávnění; nedokončený walking skeleton z CP1 (`POST /reservations`). Podrobněji v `docs/intent-and-change.md`.

**Commit / tag aplikace:** commit „approval process v0.2 (C02 change)“, tag `v0.2`.

---

## C03 — Architecture Evidence

**Baseline:** v0.2 (architektura je nad statechartem/požadavky v0.2). Aplikace navíc realizuje týmové rozhodnutí v0.3 (rezervace jedním krokem) — vedeno jako cross-view nález, ne opraveno.

**Part A:** [`docs/architecture-and-decisions.md`](architecture-and-decisions.md), sekce „Part A — AS-IS: mapování scénáře Confirm Reservation" (A1–A9). Klíčové zjištění: `Reservation.status` mění jen `services.py` (views jen čtou), ale notifikace byla volaná inline uvnitř doménové služby.

**Drivers:** D1 `BR-02` při souběhu; D2 odložené schválení přežívá původní request; D3 `Notification Service` může selhat; D4 jedno místo pro oprávnění; D5 expirace bez časovače.

**Decision question:** Kde má být vlastněn odložený approval workflow — uvnitř stejného deployable, nebo v samostatném runtime prvku?

**Alternatives:** A = stejný deployable (approval stav vlastní Reservation Management, expirace při čtení); B = samostatný Approval Worker / služba se schedulerem.

**Scenario walkthrough:** scénář E3 (Confirm → `PENDING_APPROVAL` → konkurující `CONFIRMED` → schválení odmítnuto dle `BR-02` → failure notifikace spolknut). Obě varianty chování umí; liší se vlastnictvím odloženého stavu a runtime.

**ADR:** ADR-01 — zvolena **Alternativa A** (jeden owner drží `BR-02` bez distribuovaného zámku, jeden runtime odpovídá AS-IS). Negativní důsledky: expirace až při čtení, žádný retry notifikací, approval zátěž v web procesu. Reopen: víc instancí / proaktivní expirace / SLA notifikací / oddělení runtime.

**Views:** domain class (C1), context (G1), static architecture (G2), state ownership (G3), runtime/deployment (G4), design sequence (H1), focused design class (H2) — vše v [`docs/c03-architecture.md`](c03-architecture.md).

**Cross-view issues found/resolved:** žádný tvrdý rozpor mezi diagramy; jediný nález je známá odchylka baseline v0.2 vs běžící v0.3.

**AS-IS → TO-BE delta:** `KEEP` (vlastnictví stavu, approval stav, persistence, žádný worker); `CHANGE` (izolace notifikací + best-effort failure); `VERIFY` (směr závislostí views → services, kryto architektonickým testem).

**Implementation changes:** nový `reservations/notifications.py` (Notification Integration, best-effort doručení); `services.py` volá notifikaci přes tento modul (chování rezervace beze změny); nový `reservations/tests_architecture.py`.

**Behaviour verification:** `python manage.py test` — **47 testů, `OK`** (44 původních + 3 architektonické).

**Architecture conformance rule + result:** RULE-1 „jen `reservations/services.py` mění `Reservation.status`" (+ RULE-2 „doručení notifikace definuje jen `notifications.py`") — `reservations/tests_architecture.py`, **OK**. Kontrola je netriviální: injektované `r.status = ...` i `.update(status=...)` odhalí.

**Remaining uncertainty / risk:** expirace jen při čtení (na stav se dá zapomenout); notifikace bez retry; `DRAFT` v běžném UI toku není pozorovatelný (v0.3); kapacita zdrojů stále neznámá z C01.

**Commit/tag:** tag `c03` → commit `6880f85` (stav C03 včetně redesignu, před rozdělením do modulů). Odkazy na soubory a řádky v C03 platí vůči tomuto tagu; novější umístění viz change record „modules split by architecture element“ v [`architecture-and-decisions.md`](architecture-and-decisions.md) (commit `bf66ebb`).

## C05 DD Verification Evidence

**Unit:** Confirm Reservation v Reservation Management. Návrh je v [`docs/architecture-and-decisions.md`](architecture-and-decisions.md), sekce „C05 Detailed Design“.

**Tests derived from DD:** nové testy jsou v `reservations/tests/test_confirmation_dd.py` (třída `ConfirmationDesignTests`). Kde už test existoval, odkazuje se na něj.

| DD element / decision | Co musí platit | Úroveň | Test |
| --- | --- | --- | --- |
| kontrakt `ensure_can_allocate` (DD-2) | při úspěchu nic nezmění | unit | `test_rule_check_passes_without_changing_the_reservation` |
| větev algoritmu: pořadí kontrol (DD-3) | neaktivní zdroj se hlásí dřív než BR-04 | unit | `test_inactive_resource_is_reported_before_the_parking_rule` |
| hranice BR-04 (DD-3) | nepočítá se cizí stůl, stůl na jiný den ani stůl jen `PENDING_APPROVAL` | unit | `test_parking_rule_ignores_desks_that_do_not_count` |
| přechod stavu: jen z `DRAFT` (DD-1) | `CONFIRMED`/`CANCELLED`/`REJECTED` nejde potvrdit a stav se nezmění | unit | `test_only_a_draft_can_be_confirmed` |
| přechod stavu: větev schválení (DD-4) | obsazený zdroj nejde ani požádat o schválení | component | `test_taken_resource_cannot_be_requested_for_approval` |
| přechod stavu: `DRAFT → PENDING_APPROVAL` | zdroj se schválením nevytvoří `CONFIRMED` | component | `test_flagged_resource_results_in_a_request_instead` (existující) |
| failure: souběh (DD-5) | prohraný souběh = `ReservationError`, zůstane jedna `CONFIRMED` | component | `test_allocate_turns_a_lost_race_into_a_reservation_error` |
| failure: notifikace (DD-6, D3) | selhání doručení nezmění `CONFIRMED` | component | `test_failed_notification_keeps_the_reservation_confirmed` |
| spolupráce s notifikací (DD-6) | notifikace až po commitu | component | `test_notification_waits_for_the_commit` |
| spolupráce s notifikací (DD-6) | při rollbacku se nic neoznámí | component | `test_rolled_back_confirmation_is_not_announced` |
| spolupráce: tok v0.3 (DD-7) | po chybě nezůstane `DRAFT` | component | `test_nothing_is_left_behind_when_the_check_fails` (existující) |

**Vysvětlení úrovně u dvou testů:**

`test_rule_check_passes_without_changing_the_reservation`
- Úroveň: unit.
- Proč: `ensure_can_allocate` je samostatná funkce s jasným kontraktem a volá se přímo, bez view a bez `confirm_reservation`.
- Co ověřuje: rozhodnutí DD-2, že kontrola pravidel nic nemění. Díky tomu ji smí volat potvrzení i schválení. Kdyby do ní někdo přidal zápis, test spadne.

`test_allocate_turns_a_lost_race_into_a_reservation_error`
- Úroveň: component (služba + skutečná DB s indexem).
- Proč: chování závisí na unikátním indexu v databázi a mock by ho neověřil. Test volá `allocate` bez předchozí kontroly, stejně jako druhý request v souběhu, který kontrolou prošel dřív, než první uložil.
- Co ověřuje: rozhodnutí DD-5, že poslední slovo při souběhu má DB index a volající dostane `ReservationError`, ne databázovou chybu.

**Unit/component tests executed:** `python manage.py test`, **58 testů, OK** (49 dřívějších + 9 nových z DD).

**Design ↔ implementation mismatch:**

| DD decision | Implementováno? | Doklad | Akce |
| --- | --- | --- | --- |
| DD-1 jen z `DRAFT` | YES | `lifecycle.py` `confirm_reservation`; test výše | keep |
| DD-2 čistá kontrola pravidel | YES | `rules.py` `ensure_can_allocate` | keep |
| DD-3 pořadí kontrol a hranice BR-04 | YES | `rules.py` | keep |
| DD-4 pravidla před větví schválení | YES | `lifecycle.py` | keep |
| DD-5 souběh přes DB index | YES | `allocate` + `unique_confirmed_resource_date` | keep |
| **DD-6 notifikace až po commitu** | **NO** (před změnou) | `notify_reservation_event` se volalo uvnitř `@transaction.atomic`, tedy před commitem. Odporovalo to i H1 z C03 (commit → notify). Testy `test_notification_waits_for_the_commit` a `test_rolled_back_confirmation_is_not_announced` na původním kódu **padaly** (notifikace odešla i při rollbacku). | **update code**: `notify_after_commit` přes `transaction.on_commit`, použito u potvrzení, žádosti, schválení, zamítnutí i zrušení |
| DD-7 nic po chybě | YES | `create_reservation` v `transaction.atomic` | keep |
| vlastník potvrzuje jen svou rezervaci | PARTLY | kontrola je ve view `confirm_reservation_view`, ne ve službě (`cancel_reservation` ji má ve službě s `actor`) | **deferred**: služba se dnes volá jen z tohoto view a z `create_reservation` (vždy vlastník). Přesun by změnil podpis použitý v 15 testech a v `seed_demo_data`. Vedeno jako riziko. |
| H2 z C03: `ReservationRepository`, `Reservation.confirm()` | NO | v kódu není repository ani metody na entitě | **update design**: DD platí pro tuto jednotku, persistence je přímo ORM a logika ve funkcích služby; H2 zůstává jako záznam C03 |

**Resolution:** DD-6 opraven v kódu (`reservations/services/lifecycle.py` `notify_after_commit`, `reservations/services/approvals.py`). Po opravě prochází všech 58 testů a architektonické kontroly RULE-1 a RULE-2 dál platí.

**Remaining design risk:**
- kontrola vlastníka při potvrzení je mimo službu (viz tabulka);
- na SQLite `select_for_update` nezamyká, takže souběh tam drží jen DB index; na PostgreSQL zamyká i řádek;
- notifikace po commitu nemá retry; když proces spadne mezi commitem a odesláním, zpráva se ztratí (přijato v ADR-01);
- chyby se rozlišují jen textem hlášky, ne kódem.

**Commit/tag:** tag `c05` (commit „C05 Detailed Design: Confirm Reservation“, navazuje na `bf66ebb`).
