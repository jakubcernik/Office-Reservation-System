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

**Commit/tag:** tag `c03` → commit `cd4d180` „C03“ (47 testů). Následující commit `6880f85` „redesign“ změnil jen UI a přidal 2 testy plánu kanceláře (49). Odkazy na soubory a řádky v C03 platí vůči tomuto tagu; novější umístění viz change record „modules split by architecture element“ v [`architecture-and-decisions.md`](architecture-and-decisions.md) (commit `bf66ebb`).

## C04 — Quality & Measurement

*Zadání C04 tým nemá k dispozici. Sekce je postavená podle toho, co C04 hodnotí formulář C06 (Q1–Q3): quality concern → evaluable criterion → measurement → decision.*

**Quality concern (Q-1): spolehlivost rezervace při souběhu.** Když víc lidí ve stejný okamžik zarezervuje stejný zdroj na stejný den, smí ho dostat právě jeden. Ostatní musí dostat srozumitelné odmítnutí a nesmí po nich nic zůstat. Zdroj: REQ-04, BR-02, driver D1 a otevřená otázka A8 z C03 („kde se dělá autoritativní rozhodnutí o konfliktu“).

**Evaluable criterion:**

| Položka | Hodnota |
| --- | --- |
| Zátěž | 20 uživatelů najednou rezervuje stejný stůl na stejný den přes `create_reservation` (stejná cesta jako tlačítko Reserve); všechna vlákna mají otevřené spojení a uvolní je jedna bariéra |
| Opakování | 10 kol (každé na jiný den) |
| Prostředí | PostgreSQL 15 (produkce běží na PostgreSQL/Supabase), lokální server, výchozí izolace READ COMMITTED |
| **Vyhovuje, když** | v **každém** kole: právě 1 výsledek `CONFIRMED`, 19× `ReservationError`, žádná jiná výjimka, v DB pro ten zdroj a den právě 1 `CONFIRMED` a 0 `DRAFT` |
| Nevyhovuje | jakékoli jiné rozdělení v kterémkoli kole |

SQLite není deklarované prostředí (zapisovatele řadí zámkem celého souboru, měřil by jiný systém), proto se tam měření přeskočí.

**Measurement:** `reservations/tests/test_quality_concurrency.py`, spuštění:

```
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:54329/postgres \
    python manage.py test reservations.tests.test_quality_concurrency
```

`TEST_DATABASE_URL` použije vlastní PostgreSQL server; test runner si na něm vytvoří a smaže vlastní testovací databázi (`settings.py`). Odmítnutí se počítají zvlášť podle toho, co pokus zastavilo: aplikační kontrola (`refused_by_check`), nebo DB index (`refused_by_index`, `ReservationError` vzniklá z `IntegrityError`).

**Výsledky (22. 10. 2026):**

| Běh | Co se měřilo | Výsledek po kolech | Kritérium |
| --- | --- | --- | --- |
| M0 | původní kód; první verze měření | 10/10 kol: 1 `CONFIRMED`, 19 `refused_by_check`, 0 `refused_by_index` | splněno, ale **index nezasáhl ani jednou** → podezření, že se pokusy vůbec nepotkaly |
| — | sonda časů (dočasný test) | všech 20 vláken uvolněno do 4 ms, ale kontrolou prošlo jen první; ostatní čekaly až na jeho commit | příčina: `select_for_update().select_related("resource", "user")` generuje `... FOR UPDATE` bez `OF`, takže PostgreSQL zamkne i **řádek zdroje** a uživatele. Souběh tedy řadil vedlejší efekt dotazu, ne index |
| A | kontrola: zamčený jen vlastní řádek (`of=("self",)`), index zachován | 10/10 kol: 1 `CONFIRMED`; index zachytil 2–18 pokusů za kolo | splněno – pokusy se opravdu potkávají a index funguje jako pojistka |
| B | kontrola: zamčený jen vlastní řádek, index odstraněn | **4–17 `CONFIRMED` v každém kole** | **nesplněno** – samotná aplikační kontrola souběh neudrží; měření porušení odhalí |
| M1 | výsledné řešení: explicitně zamčený řádek zdroje (`lock_for_allocation`) + index | 10/10 kol: 1 `CONFIRMED`, 19 `refused_by_check`, žádná jiná výjimka, 0 `DRAFT`; kolo trvá 32–49 ms (opakované běhy, mj. po přesunu expirace mimo transakci v C06) | **splněno** |

Běhy A a B byly dočasné kontrolní testy (patch `lock_for_allocation`, odebrání constraintu v testovací DB); do repa se neukládají, protože B má z definice selhat. M1 je v repu a běží s celou sadou na PostgreSQL (66 testů, OK).

**Trade-off / decision:**

- **Rozhodnutí:** autoritativní místo pro BR-02 při souběhu je **zámek řádku zdroje** v `services/lifecycle.py` `lock_for_allocation` (`select_for_update(of=("self", "resource"))`), který používá potvrzení i schválení. Částečný unikátní index `unique_confirmed_resource_date` zůstává jako poslední pojistka (běh A) a jako jediná ochrana na SQLite a při ručních změnách v adminu. Tím je zodpovězená otázka A8 z C03.
- **Proč explicitně:** dosud zámek zdroje vznikal jen jako vedlejší efekt `select_related`. Kdyby ho někdo při úpravě dotazu odebral, chování by se změnilo bez povšimnutí (běh A ukazuje, že by pak souběh držel jen index).
- **Cena:** rezervace **téhož** zdroje se zpracují za sebou (20 souběžných pokusů ≈ 35–50 ms celkem). Rezervace různých zdrojů na sebe nečekají. Zámek uživatele, který dřív vznikal mimochodem, už se nebere.
- **Opravená tvrzení:** baseline v0.3 („drží to index, ne kontrola před zápisem“), BR-02 a DD-5 v C05 popisovaly souběh nepřesně; upraveno v `docs/intent-and-change.md` a v sekci C05 v `docs/architecture-and-decisions.md`.

**Zbývající nejistota:** měřeno na lokálním PostgreSQL 15, ne přímo na Supabase (sdílená data, test runner tam nesmí vytvářet DB); Supabase běží na PostgreSQL se stejnou sémantikou `FOR UPDATE` a READ COMMITTED. Výkon pod skutečnou síťovou latencí neměřen – kritérium se týká správnosti, ne rychlosti.

**Commit/tag:** tag `c06` (viz sekce C06).

## C05 DD Verification Evidence

**Unit:** Confirm Reservation v Reservation Management. Návrh je v [`docs/architecture-and-decisions.md`](architecture-and-decisions.md), sekce „C05 Detailed Design“.

**Tests derived from DD:** nové testy jsou v `reservations/tests/test_confirmation_dd.py` (třída `ConfirmationDesignTests`). Kde už test existoval, odkazuje se na něj.

| DD element / decision | Co musí platit | Úroveň | Test |
| --- | --- | --- | --- |
| kontrakt `ensure_can_allocate` (DD-2) | při úspěchu nic nezmění | unit | `test_rule_check_passes_without_changing_the_reservation` |
| větev algoritmu: pořadí kontrol (DD-3) | neaktivní zdroj se hlásí dřív než BR-04 | unit | `test_inactive_resource_is_reported_before_the_parking_rule` |
| hranice BR-04 (DD-3) | nepočítá se cizí stůl, stůl na jiný den ani stůl jen `PENDING_APPROVAL` | unit | `test_parking_rule_ignores_desks_that_do_not_count` |
| přechod stavu: jen z `DRAFT` (DD-1) | `PENDING_APPROVAL`/`CONFIRMED`/`REJECTED`/`EXPIRED`/`CANCELLED` nejde potvrdit a stav se nezmění *(PENDING_APPROVAL a EXPIRED doplněny v C06)* | unit | `test_only_a_draft_can_be_confirmed` |
| přechod stavu: větev schválení (DD-4) | obsazený zdroj nejde ani požádat o schválení | component | `test_taken_resource_cannot_be_requested_for_approval` |
| přechod stavu: `DRAFT → PENDING_APPROVAL` | zdroj se schválením nevytvoří `CONFIRMED` | component | `test_flagged_resource_results_in_a_request_instead` (existující) |
| failure: souběh (DD-5) | prohraný souběh = `ReservationError`, zůstane jedna `CONFIRMED` (pojistka indexem) | component | `test_allocate_turns_a_lost_race_into_a_reservation_error` |
| souběh: zámek zdroje (DD-5, doplněno v C06) | 20 souběžných pokusů → právě 1 `CONFIRMED`, zbytek `ReservationError` | component (PostgreSQL) | `test_quality_concurrency.test_one_winner_per_resource_and_day` (měření C04) |
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
| DD-5 souběh: zámek zdroje + DB index *(v C05 jen index; přepsáno v C06 podle měření C04)* | YES | `lock_for_allocation` + `allocate` + `unique_confirmed_resource_date`; testy `test_quality_concurrency` a `test_allocate_turns_a_lost_race_into_a_reservation_error` | keep |
| **DD-6 notifikace až po commitu** | **NO** (před změnou) | `notify_reservation_event` se volalo uvnitř `@transaction.atomic`, tedy před commitem. Odporovalo to i H1 z C03 (commit → notify). Testy `test_notification_waits_for_the_commit` a `test_rolled_back_confirmation_is_not_announced` na původním kódu **padaly** (notifikace odešla i při rollbacku). | **update code**: `notify_after_commit` přes `transaction.on_commit`, použito u potvrzení, žádosti, schválení, zamítnutí i zrušení |
| DD-7 nic po chybě | YES | `create_reservation` v `transaction.atomic` | keep |
| vlastník potvrzuje jen svou rezervaci | PARTLY | kontrola je ve view `confirm_reservation_view`, ne ve službě (`cancel_reservation` ji má ve službě s `actor`) | **deferred**: služba se dnes volá jen z tohoto view a z `create_reservation` (vždy vlastník). Přesun by změnil podpis použitý v 16 testech a v `seed_demo_data`. Vedeno jako riziko. |
| H2 z C03: `ReservationRepository`, `Reservation.confirm()` | NO | v kódu není repository ani metody na entitě | **update design**: DD platí pro tuto jednotku, persistence je přímo ORM a logika ve funkcích služby; H2 zůstává jako záznam C03 |

**Resolution:** DD-6 opraven v kódu (`reservations/services/lifecycle.py` `notify_after_commit`, `reservations/services/approvals.py`). Po opravě prochází všech 58 testů a architektonické kontroly RULE-1 a RULE-2 dál platí.

**Remaining design risk:**
- kontrola vlastníka při potvrzení je mimo službu (viz tabulka);
- na SQLite `select_for_update` nezamyká, takže souběh tam drží jen DB index; na PostgreSQL zamyká i řádek;
- notifikace po commitu nemá retry; když proces spadne mezi commitem a odesláním, zpráva se ztratí (přijato v ADR-01);
- chyby se rozlišují jen textem hlášky, ne kódem.

**Commit/tag:** tag `c05` (commit „C05 Detailed Design: Confirm Reservation“, navazuje na `bf66ebb`).

## C06 Internal Evidence Assessment

**Assessed baseline:** tag `c06` (stav po opravách níže). Testy: `python manage.py test` → 66 testů OK (1 přeskočen: měření C04 patří na PostgreSQL); na PostgreSQL 15 přes `TEST_DATABASE_URL` → 66 testů OK. Předávací údaje: `README.md`, sekce „Assessment handover (C06)“.

**Self-check před předáním** (tým prošel vlastní projekt checklistem C06; každý bod byl ověřen spuštěním nebo dočasným testem):

| Nález (checklist) | Ověření | Akce |
| --- | --- | --- |
| B1 – evidence C02 uvádí tag `v0.2`, který neexistoval | `git tag`, `git ls-remote --tags` | tag `v0.2` vytvořen na merge `e90a2af` (obsahuje oba commity „approval process v0.2“) |
| B2 – příkaz z README `…WalkingSkeletonReservationCreateTests` končil chybou; walking skeleton CP1 nebyl implementovaný | spuštění příkazu | implementován `POST /reservations` + `WalkingSkeletonReservationCreateTests` (3 testy), README opraven |
| R5 – C02 uvádí jako spuštěné příklady „neplatné datum → dnešek“ a „cizí potvrzení → 403“, test pro ně nebyl | dočasný test: chování správné, chyběl doklad | doplněny `test_invalid_date_falls_back_to_today`, `test_confirming_someone_elses_reservation_is_forbidden` |
| R5/A – „souběh je pokryt testem“ (C02, C03 L1), žádný takový test nebyl | inspekce testů | měření C04 + odkazy opraveny |
| A/C02 – tvrzení „souběh drží index“ (v0.3, BR-02, DD-5) neodpovídá chování na PostgreSQL | měření C04 + sonda časů + kontrolní běhy A/B | zámek zdroje explicitní (`lock_for_allocation`), tvrzení opravena |
| D5 – pořadí kontrol v DD-3 a testu se lišilo od diagramů aktivit OP-03/OP-05 v C02 | porovnání diagramu s kódem | kód a DD sjednoceny se specifikací (aktivní → obsazenost → parkování), nový test `test_conflict_is_reported_before_the_parking_rule` |
| R2 – BR-04 nebylo jednoznačné, zda platí i po zrušení stolu | dočasný test: parkování zůstane `CONFIRMED` | v BR-04 upřesněn rozsah (podmínka v okamžiku potvrzení/schválení), chování beze změny |
| Q1–Q3 – C04 chyběl | – | doplněna sekce „C04 — Quality & Measurement“ |
| B1 – odkazy na soubory/řádky v C03 neodpovídají současnému rozložení | inspekce | v C03 a Části A uvedeno, že platí pro tag `c03`; převodní tabulka v change recordu |
| D4 – DD-1 nebylo ověřeno pro `PENDING_APPROVAL` a `EXPIRED` *(nezávislá kontrola)* | dočasný test: chování správné, doklad chyběl | oba stavy doplněny do `test_only_a_draft_can_be_confirmed` |
| C02/C05 – potvrzení a zrušení spouštěly expiraci uvnitř své transakce, takže ji odmítnutí vrátilo (stejná chyba, kterou C02 evidence nález 2 opravila u schválení) *(nezávislá kontrola)* | dočasný test na SQLite i PostgreSQL | expirace přesunuta před transakci v `confirm_reservation`, `cancel_reservation` a `create_reservation`; test `test_expiry_survives_a_refused_confirmation_and_cancellation`; DD sekvence a pseudokód upraveny |
| D2 – evidence C05 u DD-5 uváděla jen index | porovnání s přepsaným DD-5 | řádky DD-5 doplněny o zámek zdroje a měření C04 |
| B1 – odkazy na řádky a „47 testů“ v C03 patří commitu `cd4d180`, ne `6880f85` *(nezávislá kontrola)* | `git show cd4d180:reservations/services.py` | tag `c03` přesunut na `cd4d180`, texty opraveny |
| docs ↔ kód – tři místa tvrdila „testy vždy na SQLite“ | grep | přeformulováno (výchozí SQLite, volitelně `TEST_DATABASE_URL`) |

**Verified findings:** viz sekce „C07 — Vypořádání nálezů C06“ níže.

**Owner disposition:** viz sekce „C07 — Vypořádání nálezů C06“ níže.

**Actions / justified no-change decisions:** viz self-check výše; další podle nálezů.

**Remaining evidence gaps:**
- C04 nemá k dispozici původní zadání; sekce sleduje strukturu Q1–Q3 z formuláře C06.
- Měření C04 běželo na lokálním PostgreSQL 15, ne přímo na Supabase.
- Kontrola vlastníka při potvrzení je ve view, ne ve službě (C05, odloženo).
- Notifikace nemají retry (ADR-01, přijatý důsledek).

## Po C06 — reporting baseline (C07/C08)

Změny proti assessed baseline `c06`. Reporting tag: `c08`.

| Změna | Expected ↔ Observed na `c06` | Akce | Evidence |
| --- | --- | --- | --- |
| Defekt: jeden uživatel mohl rezervovat více stolů na tentýž den | Expected: jeden uživatel drží na den nejvýše jeden stůl (jinak blokuje stoly ostatním). Observed: dva `create_reservation` téhož uživatele na dva různé stoly a stejný den oba skončí `CONFIRMED`; `ensure_can_allocate` hlídal jen BR-02 (stejný zdroj) a BR-04. | Nové pravidlo BR-08 ve specifikaci; kontrola v `ensure_can_allocate` (platí pro potvrzení i schválení); `lock_for_allocation` zamyká i řádek uživatele kvůli souběhu dvou různých stolů | `CreateReservationTests.test_second_desk_on_the_same_day_is_refused`, `test_second_desk_on_another_day_or_after_cancel_is_allowed`, `test_desk_and_parking_on_the_same_day_are_allowed`, souběh viz níže |
| Struktura: vrstvená MVC se service layer | Adresáře byly pojmenované podle prvků C03 (`web/`, `availability/`) | Přejmenování `web/` na `controllers/`, `availability/` přesunuto do `services/`; ADR-01 beze změny; nové pravidlo RULE-3 (směr závislostí) | change record „layered MVC with a service layer“ v [`architecture-and-decisions.md`](architecture-and-decisions.md); `LayerDirectionTests` (ověřeno dočasným modulem `services/` → `controllers`, test selhal) |

**Souběh BR-08:** `ConcurrentReservationMeasurement.test_one_desk_per_user_and_day` — jeden uživatel, 20 vláken, 20 různých stolů, stejný den. Se zámkem řádku uživatele: 1 `CONFIRMED`, 19 odmítnuto kontrolou. Kontrolní běh bez zámku uživatele (`of=("self", "resource")`): 7 `CONFIRMED` — kontrola v aplikaci sama nestačí.

**Testy:** `python manage.py test` na SQLite → 71 testů OK (2 přeskočeny: souběžné testy patří na PostgreSQL); na PostgreSQL 15 (lokální kontejner) přes `TEST_DATABASE_URL` → 71 testů OK.

**Otevřené:**
- BR-08 při souběhu drží jen zámek řádku uživatele, tj. jen na PostgreSQL; databázová pojistka (jako index u BR-02) chybí, protože pravidlo závisí na typu zdroje v jiné tabulce.

## C07 — Vypořádání nálezů C06

Assessment od týmu EduGrid: [`SWI_C06_Assessment_Form_Vyplnene.md`](SWI_C06_Assessment_Form_Vyplnene.md) (assessed tag `c06`, 26. 10. 2026). Všechny checklisty B, R, A, Q, D hodnoceny YES; tři candidate findings F1–F3. Nálezy jsme reprodukovali proti `c06` (`a3cfb3f`) 1. 11. 2026; opravy a aktuální stav platí pro reporting baseline `c08`.

| | F1 — UI dělá Create + Confirm jednou akcí | F2 — notifikace uvnitř transakce | F3 — souběh nedrží DB index |
| --- | --- | --- | --- |
| Claim (zdroj) | C03 evidence: UI odpovídá statechartu v0.2 | C05: notifikace se posílá až po commitu (DD-6) | C04/BR-02: souběh drží částečný unikátní index |
| Expected | OP-01 a OP-03 jsou dva kroky uživatele | notifikace jen po úspěšném commitu | konflikt zachytí index |
| Observed | tlačítko Reserve volá `create_reservation` = vytvoření + potvrzení v jedné transakci (`web/views/reservations.py` na `c06`) | před C05 (`bf66ebb`) se `notify_reservation_event` volalo uvnitř transakce | na PostgreSQL rozhoduje zámek řádku zdroje, index je až pojistka (běhy M0, A, B, M1) |
| Verify na `c06` | inspekce kódu; `test_create_and_confirm_desk_reservation` ukazuje, že DRAFT → Confirm zůstává dosažitelné přes službu | `test_notification_waits_for_the_commit`, `test_rolled_back_confirmation_is_not_announced` → OK | `test_quality_concurrency` na PostgreSQL 15 → 10/10 kol, vždy 1 `CONFIRMED`, 19 odmítnuto |
| Disposition | VERIFIED FINDING → **ACCEPT, no-change**: vědomá odchylka v0.3 (rozhodnutí týmu 26. 9. 2026), zapsaná v `intent-and-change.md`, „Baseline v0.3“ | VERIFIED FINDING → **ACCEPT**, opraveno | VERIFIED FINDING → **ACCEPT**, opraveno |
| Action / closure | žádná změna kódu; owner Vojtěch Korduliak | `notify_after_commit` přes `transaction.on_commit`, commit `e0673ab` (C05), testy výše | `lock_for_allocation` se zámkem zdroje `select_for_update(of=("self", "resource"))`, commit `a3cfb3f`; tvrzení v BR-02, v0.3 a DD-5 opravena |

**Vlastní nález po C06:**

| Položka | F4 — jeden uživatel může mít více stolů na tentýž den |
| --- | --- |
| Claim | Stůl má mít ten, kdo ten den přijde; specifikace C01–C05 to výslovně neuváděla (BR-02 hlídá jen stejný zdroj, BR-04 jen parkování). |
| Expected | Druhý potvrzený stůl téhož uživatele na tentýž den je odmítnut. |
| Observed / verify na `c06` | Jednorázový test na čistém checkoutu `a3cfb3f` (1. 11. 2026): 2 potvrzené stoly pro jednoho uživatele. |
| Disposition | VERIFIED FINDING → **ACCEPT**. Mezera ve specifikaci, doplněno jako BR-08. Owner: Vojtěch Korduliak. |
| Closure evidence | commit `53f72bc` (v `c08`); `test_second_desk_on_the_same_day_is_refused`, `test_second_desk_on_another_day_or_after_cancel_is_allowed`, `test_desk_and_parking_on_the_same_day_are_allowed`, souběžný `test_one_desk_per_user_and_day` (bez zámku uživatele 7 stolů, se zámkem 1). |
| Zbývá | Databázová pojistka pro BR-08 chybí → riziko R-04. |

**Souhrn (max. 3 nejdůležitější):**
1. F3 — souběh: ověřeno na `c06` měřením na PostgreSQL, přijato, uzavřeno už v `c06` (explicitní zámek zdroje).
2. F4 — více stolů na den: ověřeno na `c06`, přijato, opraveno v `c08` (BR-08); otevřená akce = DB pojistka (R-04).
3. F1 — UI jednou akcí: ověřeno, přijato bez změny jako zdokumentovaná odchylka v0.3.

F2 je ověřený a uzavřený už v C05. Otevřené z assessmentu nezůstalo nic; ruční změna stavu v Django administraci (zjištěno inspekcí `reservations/admin.py`) je vedená jako riziko R-01.

## Registr rizik — C07/C08

### R-01
- **Popis rizika:** `ReservationAdmin` dovoluje ručně měnit `status` → správce potvrdí parkování bez stolu nebo druhý stůl → poruší se BR-04, BR-08 a stavový diagram
- **Kategorie:** Security
- **Počáteční riziko (L/I/priorita/důvod):** 2 / 3 / HIGH (6) — cesta v kódu existuje, dopad na hlavní pravidla
- **Strategie ošetření a zdůvodnění:** MITIGATE — stav v administraci jde zamknout jednou změnou; administraci ale potřebujeme pro správu míst, takže AVOID (administraci vypnout) nepřipadá v úvahu
- **Opatření, vlastník, termín:** `readonly_fields = ("status",)` v `ReservationAdmin` + test formuláře; Vojtěch Korduliak, do 5. 11. 2026
- **Důkaz účinnosti a stav ověření:** zatím žádný; opatření neprovedeno, NOT VERIFIED
- **Očekávané reziduální riziko:** 1 / 3 / MEDIUM (3)
- **Skutečné reziduální riziko / NOT VERIFIED:** NOT VERIFIED
- **Přijetí reziduálního rizika, vlastník, zdůvodnění:** přijme Jakub Černík po zeleném testu; dopad zůstává vysoký, ale jediná zbývající cesta je přímý zápis do databáze, který tým nepoužívá
- **Monitoring, trigger, contingency, další review:** trigger: nové pole nebo nový účet správce v adminu; contingency: když se opatření nestihne, přijmout riziko vědomě do CP2; další review 5. 11. 2026

### R-02
- **Popis rizika:** souběh (Q-1) měřen jen na lokálním PostgreSQL 15, aplikace běží na Supabase → zámek řádků se tam může chovat jinak (verze, pooler) → v provozu vznikne dvojí rezervace, porušené BR-02
- **Kategorie:** External dependency / Release
- **Počáteční riziko (L/I/priorita/důvod):** 2 / 3 / HIGH (6) — na Supabase nikdy neměřeno, dopad na hlavní invariant
- **Strategie ošetření a zdůvodnění:** MITIGATE — test souběhu už existuje, stačí ho pustit proti Supabase; AVOID by znamenalo změnit provozní databázi
- **Opatření, vlastník, termín:** zopakovat `test_quality_concurrency` proti samostatnému testovacímu projektu Supabase (ne produkce); Ondřej Kania, do 9. 11. 2026
- **Důkaz účinnosti a stav ověření:** zatím žádný; testovací projekt Supabase ještě není, NOT VERIFIED
- **Očekávané reziduální riziko:** 1 / 3 / MEDIUM (3)
- **Skutečné reziduální riziko / NOT VERIFIED:** NOT VERIFIED
- **Přijetí reziduálního rizika, vlastník, zdůvodnění:** přijme Jakub Černík po 10/10 kolech na Supabase; dopad zůstává vysoký, proto zbytkové riziko MEDIUM, ne LOW
- **Monitoring, trigger, contingency, další review:** trigger: změna verze nebo nastavení databáze na Supabase; contingency: při selhání ponechat explicitní zámek a doplnit DB constraint; další review 9. 11. 2026

### R-03
- **Popis rizika:** check-in a noční vypršení (plán do CP2) přidají časem řízené přechody stavů → přechod mimo `services/` nebo bez kontroly pravidel → porušený stavový diagram nebo BR-02
- **Kategorie:** Technical / Quality
- **Počáteční riziko (L/I/priorita/důvod):** 2 / 2 / MEDIUM (4) — nové přechody, zatím bez specifikace
- **Strategie ošetření a zdůvodnění:** MITIGATE — obě funkce jsou v plánu do CP2, proto je nevynecháme (AVOID), ale nejdřív je specifikujeme
- **Opatření, vlastník, termín:** nejdřív doplnit specifikaci a statechart, přechody jen ve službách (RULE-1), testy přechodů; Jakub Černík, do 9. 11. 2026
- **Důkaz účinnosti a stav ověření:** zatím žádný; specifikace nezačata, NOT VERIFIED
- **Očekávané reziduální riziko:** 1 / 2 / LOW (2)
- **Skutečné reziduální riziko / NOT VERIFIED:** NOT VERIFIED
- **Přijetí reziduálního rizika, vlastník, zdůvodnění:** přijme Vojtěch Korduliak, až budou nové stavy ve specifikaci a přechody pokryté testy; RULE-1 pak hlídá, že stav mění jen `services/`
- **Monitoring, trigger, contingency, další review:** trigger: nový stav nebo přechod mimo `services/`; contingency: když specifikace nebude hotová, check-in odložit za CP2; další review 9. 11. 2026

### R-04
- **Popis rizika:** BR-08 drží jen aplikační kontrola + zámek uživatele, DB pojistka chybí → zápis mimo službu vytvoří druhý stůl → porušené BR-08
- **Kategorie:** Technical / Quality
- **Počáteční riziko (L/I/priorita/důvod):** 1 / 2 / LOW (2) — jediná cesta mimo službu je admin (R-01)
- **Strategie ošetření a zdůvodnění:** MITIGATE — index je levný a BR-08 dostane stejnou pojistku, jakou už má BR-02
- **Opatření, vlastník, termín:** typ místa uložit i k rezervaci a přidat částečný unikátní index (uživatel, den, stůl, `CONFIRMED`); Vojtěch Korduliak, do 23. 11. 2026
- **Důkaz účinnosti a stav ověření:** zatím žádný, NOT VERIFIED; `test_architecture.py` RULE-1 hlídá, že stav mění jen `services/`
- **Očekávané reziduální riziko:** 1 / 1 / LOW (1)
- **Skutečné reziduální riziko / NOT VERIFIED:** NOT VERIFIED
- **Přijetí reziduálního rizika, vlastník, zdůvodnění:** přijme Vojtěch Korduliak po zelené migraci a testu; databáze pak druhý stůl odmítne i mimo službu
- **Monitoring, trigger, contingency, další review:** trigger: nový kód zapisující `Reservation` mimo `services/`; contingency: do zavedení indexu drží BR-08 zámek uživatele (jen na PostgreSQL); další review 23. 11. 2026

**Issues (už nastalo, nejsou to rizika):**
- I-1: kontrola vlastníka při potvrzení je v controlleru, ne ve službě (odloženo z C05) — owner Ondřej Kania.
