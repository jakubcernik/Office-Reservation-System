# C06 — Assessment Form (CZ)

## Projekt

```text
Hodnotící tým: Office Reservation System
Hodnocený tým: Rent a Partner (Pavel Marszalek, Tobias Janča)
Projekt: Rent a Partner — https://github.com/palcat13/SWI-Projekt
Assessed commit/tag: 51111fa (poslední commit na main)
Datum: 25.10.2026
```

## Shrnutí

Projekt je zpracovaný velmi pečlivě. Specifikace, architektura i detailní návrh na sebe navazují a sedí s kódem. Když tým v pozdější fázi zjistil chybu ve starším tvrzení, opravil ho s datem a původní text nechal přeškrtnutý, takže je vidět, jak se projekt vyvíjel. Našli jsme čtyři věci ke zlepšení. Nejdůležitější je F1: když selže odeslání notifikace, uživatel dostane chybu 500, přestože se rezervace ve skutečnosti potvrdila.

## Stavy

`YES / PARTLY / NO / N/A`

Každý řádek musí obsahovat Evidence.

## Baseline

| ID | Odpověď | Evidence / komentář |
| --- | --- | --- |
| B1 Stejná identifikovaná baseline pro docs/code/tests | YES | Dokumentace, kód i testy jsou v jednom commitu `51111fa`. Specifikace uvádí, že jde o verzi v0.2, a pozdější opravy mají v textu datum, takže je jasné, k jakému stavu se které tvrzení vztahuje. |
| B2 Relevantní produkt nebo testy lze spustit | PARTLY | README popisuje instalaci, spuštění testů (`pytest`), kontrolu architektury (`scripts/check_architecture.py`) i demo skript. Podle commitu `4069177` prochází 80 testů. Sami jsme testy zatím nespustili, výsledek doplníme. |

## C02 — Engineering Specification

Vybraná operace: OP-03 Potvrzení rezervace
Vybraný business rule / invariant: BR-02, tedy že jeden companion nesmí mít dvě překrývající se rezervace, a REQ-04, tedy co se stane, když dva lidé potvrzují ve stejnou chvíli

| ID | Odpověď | Evidence / komentář |
| --- | --- | --- |
| R1 Operation: input + precondition + postcondition/state | YES | V `docs/specification.md` má OP-03 popsané vstupy, podmínky před (rezervace je `DRAFT`, potvrzuje ji zákazník, companion je aktivní, termín ještě nezačal), výsledný stav a všechny chybové odpovědi včetně HTTP kódů. |
| R2 Business rule/invariant je jednoznačný | YES | BR-01 přesně definuje, kdy se dva intervaly překrývají (dotýkající se intervaly se nepřekrývají). BR-02 vyjmenovává, které stavy blokují companiona. V kódu je pravidlo napsané jen na jednom místě, ve funkci `availability.blocking_reservations()`. |
| R3 Operation/rule je konzistentní se state modelem | YES | Tabulka stavů ve specifikaci říká, které stavy blokují, a to sedí s BR-02. Stavový diagram obsahuje i větev, kdy rezervace čeká na schválení companionem, a ta je v kódu (`lifecycle.py`, ř. 87–95). |
| R4 Implementace odpovídá specifikované semantics | YES | Funkce `lifecycle.confirm` kontroluje podmínky ve stejném pořadí, jak je uvádí specifikace, a vrací stejné chybové kódy. Souběžná potvrzení řeší nastavení SQLite `transaction_mode: IMMEDIATE` (`config/settings.py:56`). |
| R5 Existuje vhodná verification evidence | YES | Příklady ze specifikace mají své testy v `test_confirm.py`. Souběh ověřuje `test_concurrency.py`: pošle dva skutečné HTTP požadavky najednou a kontroluje, že jeden uspěje a druhý dostane `409 OVERLAP`. |

## C03 — Architecture

Vybraná responsibility: Stav rezervace smí měnit jen modul `lifecycle.py`
Vybraná interaction: Diagram H1, potvrzení rezervace včetně odeslání notifikace
Vybrané ADR/decision: ADR-01 (zůstat u SQLite a mít jednoho vlastníka změn stavu) a jeho dodatek z 21.10. (`BEGIN IMMEDIATE`)

| ID | Odpověď | Evidence / komentář |
| --- | --- | --- |
| A1 Responsibility + owner jsou explicitní | YES | Sekce C2 a G2 přiřazují každé odpovědnosti konkrétní modul a data, která vlastní. Sekce G3 říká, kdo provádí který přechod mezi stavy. |
| A2 Skutečný code ownership odpovídá architektuře | PARTLY | V aplikačním kódu se stav opravdu mění jen v `lifecycle.py`, view a management command ho jen volají. Výjimkou je Django admin, ve kterém jde stav přepsat ručně (viz F2). |
| A3 Dynamic interaction odpovídá skutečnému call path | PARTLY | Průběh až po uložení sedí s diagramem H1. Konec nesedí: podle diagramu dostane klient odpověď 200 a notifikace se odešle až potom. Ve skutečnosti se notifikace odesílá ještě před odpovědí a její chyba odpověď shodí (viz F1). |
| A4 ADR/decision odpovídá současné implementaci | PARTLY | ADR-01 i jeho dodatek odpovídají kódu. Kontrolní skript ale umí odhalit jen přímé zápisy do stavu v kódu, změnu přes admin nevidí (F2). Starší rozhodnutí D6 navíc tvrdí, že přihlášení musí vzniknout dřív než potvrzení. Potvrzení je dnes hotové bez přihlášení a D6 nikdo neopravil (F3). |

## C04 — Quality & Measurement

Quality concern: Spolehlivost potvrzení, když se o stejný termín snaží víc lidí najednou
Criterion: Při souběžných potvrzeních uspěje právě jeden (200), ostatní dostanou `409 OVERLAP` a jejich rezervace zůstanou `DRAFT`. Nesmí vzniknout chyba 500 ani dvojí rezervace.

*Poznámka: Repozitář nemá samostatnou část C04, proto hodnotíme nejbližší obdobu, tedy měření souběhu v dodatku k ADR-01 a test `test_concurrency.py`.*

| ID | Odpověď | Evidence / komentář |
| --- | --- | --- |
| Q1 Criterion je skutečně evaluable | YES | Výsledek je jednoznačný a test ho kontroluje automaticky (`test_concurrency.py:86`). |
| Q2 Measurement měří criterion ve správném contextu | PARTLY | Dobře: test posílá skutečné HTTP požadavky na běžící server a používá databázi v souboru, stejně jako produkce. Tým vysvětluje i to, proč nestačí běžný testovací klient. Slabší místo: měří se jen dva souběžné požadavky a umělé zdržení 0,2 s. Uvedený limit (po 5 s čekání vznikne chyba 500) je jen odvozený, nikdo ho nezměřil. |
| Q3 Decision odpovídá výsledku měření | YES | První měření ukázalo, že dvojí rezervace nevznikne, ale druhý uživatel dostane chybu 500 místo 409. Tým proto zapnul `BEGIN IMMEDIATE`, změřil to znovu a vyšlo 200 + 409. Původní mylná tvrzení nechal v dokumentu přeškrtnutá s opravou. |

## C05 — Detailed Design & Unit Verification

Vybraná software unit: Approval Policy (`src/reservations/approval.py`), tedy pravidla pro schvalování rezervací companionem

| ID | Odpověď | Evidence / komentář |
| --- | --- | --- |
| D1 Design intent je explicitní a pochopitelný | YES | Návrh má vypsané odpovědnosti s důvody (AR-1 až AR-6) a kontrakt rozhraní s podmínkami. Dvě klíčové vlastnosti jsou pojmenované: AGREEMENT (Python a SQL verze pravidla dávají stejný výsledek) a TOTALITY (každá čekající žádost je buď platná, nebo prošlá, nikdy obojí ani nic z toho). |
| D2 DD odpovídá skutečné implementaci | YES | Kód odpovídá návrhu: žádost bez termínu se bere jako prošlá a stav „prošlá“ zapisuje jen `lifecycle.py`. Tým v sekci DD-6 sám popsal dvě neshody mezi návrhem a kódem a opravil je podle návrhu. |
| D3 Unit/component tests jsou odvoditelné z DD | YES | Každý test T-1 až T-9 v `test_approval_policy.py` je napojený na konkrétní část návrhu a u dvou testů je vysvětlené, proč jde o component test, a ne unit test. |
| D4 Relevantní branches/boundaries/states/failures jsou ověřeny | PARTLY | Pokryté jsou obě větve výpočtu termínu, chybějící termín, zrušení prošlé žádosti i schválení po termínu. Chybí test pro případ, kdy termín schválení vyprší přesně teď (viz F4). |
| D5 Vybraný test má smysluplný oracle/expected result | YES | Test T-4 nekontroluje opsaný výstup kódu. Kontroluje, že se čekající žádosti rozdělí na platné a prošlé beze zbytku a bez překryvu, což přímo ověřuje vlastnost TOTALITY z návrhu. |

## Candidate findings

### F1 — Chyba notifikace vrátí uživateli 500, i když se rezervace potvrdila

```text
Source: diagram H1 a DR-3 v docs/architecture-and-decisions.md; src/reservations/lifecycle.py:41-42 a 96; tests/test_notifications.py:52-68
Engineering claim: Podle dokumentace se notifikace posílá až po uložení a její selhání nemá vliv na výsledek. Diagram H1 ukazuje, že klient nejdřív dostane 200 a notifikace se odešle až pak.
Expected: Když notifikační služba spadne, rezervace zůstane potvrzená a uživatel dostane 200.
Observed: Notifikace se registruje přes transaction.on_commit() bez parametru robust=True. Django v takovém případě spustí notifikaci hned po uložení, ještě uvnitř funkce confirm, a pokud notifikace vyhodí výjimku, pošle ji dál. View zachytává jen chyby typu TransitionRefused, takže uživatel dostane 500. Rezervace přitom v databázi zůstane CONFIRMED. Uživatel si myslí, že se potvrzení nepovedlo, zkusí to znovu a dostane 409, protože rezervace už potvrzená je.
Evidence: Test test_a_failing_notification_does_not_undo_the_committed_state ověřuje jen to, že v databázi zůstane CONFIRMED. Co přijde uživateli v HTTP odpovědi, netestuje.
Verification performed: Prošli jsme kód lifecycle.py a views.py a zdrojový kód Django 5.2 (funkce on_commit a run_and_clear_commit_hooks). Test jsme nespouštěli.
Result: VERIFIED FINDING. Doporučení: použít on_commit(..., robust=True) nebo chybu zachytit a zalogovat v notifikačním portu, přidat test, že při chybě notifikace přijde 200, a upravit diagram H1.
```

### F2 — Přes Django admin jde stav rezervace přepsat mimo lifecycle.py

```text
Source: architektonické pravidlo v sekci L2, ADR-01 (negativní důsledek 2); src/reservations/admin.py:11-22; scripts/check_architecture.py
Engineering claim: Stav rezervace smí měnit jen lifecycle.py. Kontrolní skript hlásí, že pravidlo platí.
Expected: Stav se nedá změnit jinudy, nebo je výjimka v pravidle uvedená.
Observed: Admin pro rezervace nemá žádná pole jen pro čtení, takže administrátor může ručně přepnout rezervaci z DRAFT na CONFIRMED bez kontroly překryvu. Kontrolní skript hledá jen zápisy přímo v Python kódu, nastavení adminu nevidí. ADR-01 sice přiznává, že admin může obejít kontrolu překryvu, ale pravidlo L2 i výstup skriptu tvrdí, že stav mění jen lifecycle.py.
Evidence: admin.py nemá readonly_fields a pole status v models.py:46 není označené jako needitovatelné.
Verification performed: Prošli jsme admin.py, models.py a check_architecture.py.
Result: VERIFIED FINDING. Doporučení: v adminu nastavit readonly_fields = ("status", "approval_deadline", "decided_by"), nebo admin výslovně uvést jako výjimku v pravidle L2.
```

### F3 — Bez přihlášení si zákazník může schválit vlastní žádost

```text
Source: BR-04 a BR-06 v docs/specification.md; rozhodnutí D6 a D7; src/config/settings.py:79-83; src/reservations/views.py:31-34
Engineering claim: Podle BR-04 nesmí žádost schválit nikdo jiný než companion. Podle D6 musí přihlášení vzniknout dřív, než se naimplementuje potvrzení.
Expected: Identita uživatele se ověřuje, nebo je v dokumentaci jasně napsané, že pravidlo zatím vynucené není.
Observed: Přihlášení je vypnuté a to, kdo akci provádí, posílá klient sám v těle požadavku jako actor_user_id. Zákazník tam může dát ID companiona a schválit si vlastní žádost. Potvrzení i schvalování jsou hotové, přestože D6 chtělo přihlášení už předtím.
Evidence: Tým riziko zná a popisuje ho v D7 a DR-5 ("nesmí jít do produkce"). Text D6 ale zůstal beze změny a BR-04 působí, jako by se opravdu vynucovalo.
Verification performed: Prošli jsme settings.py, views.py, serializers.py a dokumentaci D6, D7 a DR-5.
Result: VERIFIED FINDING (nízká závažnost, riziko je přiznané). Doporučení: u D6 poznamenat, že ho nahradilo D7, a k BR-04 dopsat, že ho dnes nic skutečně nevynucuje.
```

### F4 — Chybí test pro okamžik, kdy termín schválení vyprší přesně teď

```text
Source: vlastnosti TOTALITY a AGREEMENT v DD-3, testy T-3 a T-4 v DD-5; src/reservations/approval.py:50-60; tests/test_approval_policy.py:40-75
Engineering claim: Každá čekající žádost je buď platná, nebo prošlá, nikdy obojí ani nic z toho. Testy T-3 a T-4 to mají ověřovat.
Expected: Testy pokrývají i hraniční případ, kdy je termín schválení přesně teď. Právě tam se rozhoduje, jestli je žádost ještě platná.
Observed: Testy používají jen termíny o hodinu (nebo o sekundu) dříve či později a žádost bez termínu. Kdyby někdo v kódu změnil "větší než" na "větší nebo rovno", pravidlo by v okamžiku vypršení přestalo platit, a přesto by všechny testy prošly.
Evidence: V testech není žádný případ s approval_deadline = now. Nejblíž je test_availability.py:145, který používá ± 1 s.
Verification performed: Prošli jsme všechny testy, které pracují s termínem schválení.
Result: VERIFIED FINDING. Doporučení: přidat do T-3 a T-4 žádost s termínem přesně now.
```

### F5 — Podezření na dvojí rezervaci při souběhu (zamítnuto)

```text
Source: REQ-04 v docs/specification.md; src/reservations/lifecycle.py; src/reservations/models.py
Engineering claim: Ze souběžných potvrzení uspěje nejvýš jedno.
Expected: Kód má zámek nebo databázové omezení proti dvojí rezervaci.
Observed: V kódu není select_for_update ani databázové omezení na překryv a kontrola překryvu a uložení jsou dva samostatné kroky. Původně jsme proto čekali, že při souběhu může vzniknout dvojí rezervace.
Evidence: SQLite má nastavené transaction_mode = "IMMEDIATE" (settings.py:56), takže druhé potvrzení počká, až první doběhne, a pak překryv uvidí. Ověřuje to test_concurrency.py. Že by při přechodu na PostgreSQL bylo potřeba řešení změnit, tým uvádí v dodatku k ADR-01.
Verification performed: Prošli jsme settings.py, test_concurrency.py a dodatek k ADR-01.
Result: REJECTED CANDIDATE. Na SQLite, kterou projekt používá, pravidlo platí a omezení jsou zdokumentovaná.
```

## Owner disposition

| Finding | ACCEPTED / REJECTED / DEFERRED | Reason/evidence | Action / no-change |
| ------- | ------------------------------ | --------------- | ------------------ |
| F1      |                                |                 |                    |
| F2      |                                |                 |                    |
| F3      |                                |                 |                    |
| F4      |                                |                 |                    |
| F5      |                                |                 |                    |
