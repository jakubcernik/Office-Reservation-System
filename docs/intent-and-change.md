# Project Frame

## Reservation domain
Pracovní místa k sezení a parkovací místa v rámci firemních prostor.

## Purpose
Systém slouží zaměstnancům firmy k plynulému a organizovanému plánování dnů v open office prostředí. Cílem je eliminovat stres z nedostatku pracovních a parkovacích míst a zabránit rannímu chaosu při nekoordinovaných příchodech.

## Users / Stakeholders
- Employee (Zaměstnanec – vyhledává dostupnost, vytváří a spravuje své vlastní rezervace).

- Office Manager (Admin – spravuje zdroje, přidává nové stoly/parkovací místa, řeší konflikty).

## Core concepts
- Reservation
- Resource (Desk nebo Parking Spot)
- User

## Core operations
- Create reservation: Založí novou rezervaci.

- Confirm / approve reservation: Zvaliduje pravidla a rezervaci závazně potvrdí.

- Cancel reservation: Zruší rezervaci a uvolní zdroje pro ostatní.

- Check availability: Zjistí, jaké stoly a parkovací místa jsou volná pro zadané datum.

## Persistent state
- Reservation ukládáme: ID rezervace, User ID (kdo rezervuje), Resource ID (co rezervuje), datum (date), časový slot (pokud je podporován, jinak celodenní), stav rezervace (status).

- Resource ukládáme: ID zdroje, typ zdroje (Desk / Parking Spot), označení/lokace (např. "Stůl A12" nebo "Místo P4"), stav zdroje (aktivní/vyřazený z provozu).

## State-changing operation
- Drafting: null → DRAFT (Při volání Create reservation)

- Confirmation: DRAFT → CONFIRMED (Při volání Confirm reservation)

- Cancellation: CONFIRMED → CANCELLED (Při volání Cancel reservation)

## Common business rule
Confirmed reservations for the same resource must not overlap.

## Domain-specific business rule
Uživatel si smí vytvořit a potvrdit rezervaci parkovacího místa na konkrétní den pouze tehdy, pokud již má (nebo současně v jedné transakci vytváří) potvrzenou rezervaci pracovního místa k sezení na ten samý den.

## External / system boundary
Notification Service – Externí závislost, která asynchronně odesílá uživatelům potvrzení o úspěšném vytvoření nebo zrušení rezervace.

## Assumption
Předpokládáme, že zaměstnanci budou své rezervace poctivě stornovat, pokud zjistí, že do kanceláře nakonec nedorazí. Systém tak nebude uměle blokován.

## Unknown
Neznáme potřebnou kapacitu.