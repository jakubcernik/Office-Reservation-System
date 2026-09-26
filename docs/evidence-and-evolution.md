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

**Commit / tag aplikace:** *doplnit po commitu* — návrh zprávy: „approval process v0.2 (C02 change)“.
