# Architecture and Stack Decision

## Decision summary

Build a small browser-based Django application for local use. Use Django's built-in server, templates, forms, authentication, admin, ORM, and SQLite database. Keep the frontend server-rendered with plain HTML and CSS. Do not add a separate desktop client, JavaScript framework, REST API, background worker, or external database for the first version.

This is intentionally a monolithic application. One Python process and one SQLite file should be enough to run it locally.

## Minimal stack

| Area | Choice |
| --- | --- |
| Language | Python |
| Framework | Django |
| Database | SQLite, using Django ORM and migrations |
| UI | Django templates, standard HTML forms, and a small CSS file |
| Authentication | Django's built-in users, login, logout, and groups |
| Administration | Django admin for resources and users |
| Notifications | Django console email backend or a simple log message during local development |
| Server | Django development server on localhost |

## Application shape

Use one Django project and one main `reservations` app. Keep the initial structure small:

- `models/`: users' reservations, desks, parking spots, dates, and statuses.
- `web/views/`: browser pages and form handling.
- `web/forms.py`: validation for selecting dates, resources, and actions.
- `services/`: the few operations that change reservation state.
- `availability/`: read-only queries for free resources and the floor plan.
- `integrations/`: the notification boundary.

(The first version used flat files `models.py`, `views.py`, `forms.py` and `services.py`; see the change record "modules split by architecture element" below.)
- `templates/`: server-rendered pages.
- `static/`: plain CSS.
- Django admin: resource maintenance and basic user management.

Use Django's built-in `User` model unless the project later requires additional employee fields. Use a Django group such as `Office Manager` for administrative permissions. There is no need for a separate accounts app at this stage.

## Core behavior

The application should support:

1. Login and logout.
2. Viewing available desks and parking spots for a selected date.
3. Creating a draft reservation.
4. Confirming a reservation.
5. Cancelling the current user's confirmed reservation.
6. Managing resources through Django admin.

Reservation state changes should be handled by small explicit Python functions such as `create_draft`, `confirm_reservation`, and `cancel_reservation`. Views should call these functions rather than embedding all business rules in templates.

The parking rule remains part of confirmation: a user can confirm a parking reservation only when they also have a confirmed desk reservation for the same date. If the first version uses a cart, confirm all items in one `transaction.atomic()` block.

## Data and consistency

Start with whole-day reservations. A reservation needs:

- user
- resource
- date
- status: `DRAFT`, `CONFIRMED`, or `CANCELLED`; the C02 change added `PENDING_APPROVAL`, `REJECTED`, and `EXPIRED` for resources that require approval

Only active resources should be available for new reservations. Confirmed reservations for the same resource and date must not overlap. Add a conditional unique constraint for confirmed reservations and also check availability in the service function. The database constraint protects the rule even if two browser requests arrive close together.

Use `transaction.atomic()` when confirming a reservation or cart. If a confirmation fails, no partial confirmation should remain. Draft expiry can be handled simply by ignoring old drafts when displaying the cart; a scheduled cleanup task is unnecessary for the local version.

If timed reservations or multiple simultaneous users become important, move the database to PostgreSQL and revisit the concurrency model. That is an upgrade path, not part of the initial stack.

## Notifications

Do not build a worker or message queue initially. After a successful confirmation or cancellation, write a simple notification to the console or use Django's development email backend. Keep the notification call behind a small Python function so a real external Notification Service can be added later without changing reservation logic.

## Local setup

The expected developer workflow is:

1. Create a Python virtual environment.
2. Install Django with `pip`.
3. Run migrations to create the SQLite file.
4. Create a superuser for Django admin.
5. Start the Django development server.
6. Open the local address in a browser.

Configuration should stay in Django settings and local environment variables. No credentials or generated database files should be committed.

## Implementation order

1. Create the Django project and `reservations` app.
2. Add resource and reservation models with migrations.
3. Register resources and reservations in Django admin.
4. Add login, availability, reservation, confirmation, and cancellation views.
5. Add the parking prerequisite and no-overlap validation.
6. Add simple templates and CSS for the employee workflow.
7. Add console/email notification hooks.

## Future upgrade triggers

Only add more infrastructure when a concrete need appears:

- PostgreSQL for higher concurrency or deployment beyond one local instance.
- HTMX or a JavaScript framework if server-rendered interactions become awkward.
- Celery or another worker if notifications must be retried asynchronously.
- SSO when the company identity provider is available.
- A separate API when a mobile or external client is actually required.

## Change record: PostgreSQL (Supabase) instead of SQLite

The first version stored everything in a local SQLite file. The project now needs a database that is reachable from more than one machine, so the storage layer moved to PostgreSQL hosted on Supabase.

How it was done, keeping the "no code change" promise:

- Only `settings.py` changed. `models.py`, `services.py`, `views.py`, and `forms.py` are untouched, because the Django ORM and the existing migrations target PostgreSQL as well.
- The database is selected by the `DATABASE_URL` environment variable (`.env`, git-ignored). No URL means the old local SQLite file, so a fresh checkout still runs without any cloud account.
- Secrets stay out of the repository; `requirements.txt` gained `psycopg2-binary`, `dj-database-url`, and `python-dotenv`.

Evidence: `manage.py migrate` was run first against a local PostgreSQL 18 instance and then against the Supabase project itself; all 19 migrations applied without modification in both cases.

Consequences for the rules from the section above:

- The business rule "confirmed reservations for the same resource must not overlap" is now enforced by a **partial unique index** (`unique_confirmed_resource_date`) instead of SQLite's partial index. The service-level check stays as a friendly error message; the constraint remains the last line of defence.
- The stated upgrade trigger ("PostgreSQL for higher concurrency") is now met, so the concurrency model can be revisited next.
- Tests keep running on SQLite locally, so `manage.py test` never touches the shared database.
- Draft expiry, notifications, and the missing capacity numbers are still out of scope, exactly as decided above.

## Change record: modules split by architecture element

The `reservations` app outgrew its flat layout: `services.py` held Reservation Management, the Availability read model and the permission rule together, and `views.py` held every page. The files were split into directories that follow the C03 elements (G2). The architecture itself did not change: still one Django app, one process, one database, and every `Reservation.status` change stays inside Reservation Management.

| Before | After |
| --- | --- |
| `models.py` | `models/resource.py`, `models/reservation.py` |
| `services.py` — create / confirm / cancel | `services/lifecycle.py` |
| `services.py` — approve / reject, pending requests | `services/approvals.py` |
| `services.py` — `expire_stale_approvals` | `services/expiry.py` |
| `services.py` — `user_can_approve`, `MANAGER_GROUP_NAME` | `services/permissions.py` |
| `services.py` — `ReservationError` | `services/errors.py` |
| `services.py` — active / available resources, user's reservations | `availability/queries.py` |
| `floor_plan.py` | `availability/floor_plan.py` |
| `notifications.py` | `integrations/notifications.py` |
| `views.py` | `web/views/{auth,availability,reservations,approvals}.py` |
| `forms.py`, `context_processors.py` | `web/forms.py`, `web/context_processors.py` |
| `tests.py` | `tests/test_{lifecycle,approvals,availability,floor_plan,views_*}.py` |
| `tests_architecture.py` | `tests/test_architecture.py` |

One change inside the code: the allocation checks (active resource, BR-04, BR-02) were written twice, in `confirm_reservation` and in `_apply_approval_decision`. They now live once in `services/rules.py` (`ensure_can_allocate`), and saving as `CONFIRMED` with the DB-index fallback lives once in `services/lifecycle.py` (`allocate`). BR-07 ("approval re-checks the rules") therefore holds by construction, not by keeping two copies equal. Behaviour is unchanged: the same 49 tests pass and no migration was generated.

Part A below and the C03 evidence describe the code as it was at that time; file and line references there point to the old layout and can be followed with the table above.

---

# Part A — AS-IS: mapování scénáře Confirm Reservation

Ověřený AS-IS podklad pro C03. Sledovaný scénář je jedna operace ze Specification Baseline v0.2 a jeho realizace v běžícím kódu.

## A1. Scénář, který sledujeme

| Položka | Hodnota |
| --- | --- |
| Scénář / operace | Confirm Reservation (OP-03), včetně větve, kde zdroj vyžaduje schválení |
| Požadavky | REQ-03, REQ-04, REQ-05; pro approval větev REQ-07 |
| Pravidla / invarianty | BR-02 (exkluzivita zdroje), BR-04 (parkování vyžaduje stůl), BR-05 (schvalované zdroje), BR-07 (schválení znovu ověřuje pravidla) |
| Baseline | v0.2 ([`docs/intent-and-change.md`](intent-and-change.md)) |

## A2. Hlavní průchod scénáře v kódu

| Krok scénáře z C02 (OP-03) | Realizace v kódu | Doklad |
| --- | --- | --- |
| přijmout požadavek na potvrzení | `confirm_reservation_view` (POST `/reservations/<pk>/confirm/`) | `reservations/views.py:148` |
| načíst Reservation | `get_object_or_404(Reservation.objects.select_related(...), pk=pk)`; služba pak znovu načte se zámkem řádku | `reservations/views.py:152`; `reservations/services.py:105` |
| ověřit, že přechod je povolený | `if reservation.status != Reservation.Status.DRAFT: raise ReservationError` | `reservations/services.py:107` |
| ověřit aktivnost zdroje | `if not reservation.resource.is_active: raise` | `reservations/services.py:110` |
| ověřit BR-04 (parkování) | `user_has_confirmed_desk(...)` → `raise` | `reservations/services.py:113` |
| vyhodnotit konflikt (BR-02) | `Reservation.objects.filter(resource=..., reservation_date=..., status=CONFIRMED).exclude(pk=...).exists()` | `reservations/services.py:117` |
| změnit stav | `reservation.status = PENDING_APPROVAL` (zdroj vyžaduje schválení) nebo `= CONFIRMED` | `reservations/services.py:127`, `:132` |
| uložit výsledek | `reservation.save(update_fields=["status", "updated_at"])` uvnitř `@transaction.atomic`; pojistka je DB index | `reservations/services.py:102`, `:128`, `:134`; `reservations/models.py:48` |
| oznámit uživateli | `notify_reservation_event("confirmed" / "requested approval", reservation)` | `reservations/notifications.py` |

## A3. Alternativní / chybová větev: konflikt existuje → odmítnout

| Co říká v0.2 | Kde se podmínka zjistí | Kde se rozhodne výsledek | Co dostane volající |
| --- | --- | --- | --- |
| konflikt s existující `CONFIRMED` → odmítnuto, rezervace zůstává `DRAFT` | `Reservation.objects.filter(...).exclude(pk=...).exists()` — `reservations/services.py:117` | `raise ReservationError("The selected resource is already confirmed for that date.")` — `reservations/services.py:122` | view chytí `ReservationError` → `messages.error(str(exc))` a přesměruje — `reservations/views.py:162` |

Druhá vrstva téhož pravidla: pokud by kontrola v aplikaci prosla a řádek se ukládal, částečný unikátní index `unique_confirmed_resource_date` vyhodí `IntegrityError`, který se přeloží na stejnou `ReservationError` (`reservations/services.py:135`; `reservations/models.py:48`).

**Rozdíl specifikace ↔ implementace (nález):**

| Specifikace (v0.2) | Implementace | Doklad |
| --- | --- | --- |
| Confirm je samostatný krok uživatele (`DRAFT → CONFIRMED`), `DRAFT` je pozorovatelný stav | Běžící UI dělá Create + Confirm jako **jednu akci** (`create_reservation`); `DRAFT` v běžném toku není vidět. Vrstva služeb i `DRAFT` pořád existují. | `reservations/views.py:76` (`create_reservation_view`), `reservations/services.py:80` (`create_reservation`); vysvětleno v [`docs/intent-and-change.md`](intent-and-change.md) „Baseline v0.3" |

## A4. Hlavní části implementace, které scénář realizují

| Část implementace | Typ / obsah | Role v tomto scénáři | Doklad |
| --- | --- | --- | --- |
| Reservation API | modul (Django function views) | přijme confirm command | `reservations/views.py` |
| Reservation logic | doménová služba + agregát | rozhodne potvrzení a zapíše stav | `reservations/services.py`, `reservations/models.py` |
| Policy / invariant | kontrola ve službě + DB constraint | vynutí BR-02 a BR-04 | `reservations/services.py:110`–`:122`, `reservations/models.py:48` |
| Authorization | dekorátor + funkce oprávnění | ověří vlastníka / schvalovatele | `reservations/views.py:147`, `:153`; `reservations/services.py:35` |
| Persistence | Django ORM | načte a uloží stav, zámek řádku | `reservations/services.py:105` |
| Notification integration | modul | odešle oznámení (dnes log) | `reservations/notifications.py` |

*Podbloky:* **Reservation API** = `confirm_reservation_view`, `create_reservation_view`. **Reservation logic** = `confirm_reservation`, `_apply_approval_decision`, `Reservation`. **Persistence** = Django ORM (`select_for_update`, `save`, `transaction.atomic`).

## A5. Stav, změna stavu a jedno pravidlo

**Stav**

| Otázka | Odpověď | Doklad |
| --- | --- | --- |
| Kde je stav Reservation trvale uložen? | sloupec `status` tabulky `reservations_reservation` v relační DB vybrané přes `DATABASE_URL` (aktuálně PostgreSQL/Supabase; bez URL lokální SQLite) | `reservations/models.py:41`; `office_reservation_system/settings.py` (`DATABASE_URL`) |
| Který kód provádí přechod použitý ve scénáři? | `services.confirm_reservation` (a pro approval `services._apply_approval_decision`) | `reservations/services.py:103`, `:176` |

**Business pravidlo / invariant — BR-02**

| Otázka | Odpověď | Doklad |
| --- | --- | --- |
| Kde se zjistí podmínka pravidla? | dotaz na existující `CONFIRMED` pro stejný zdroj a den | `reservations/services.py:117`, `:195` |
| Kde se podle výsledku rozhodne? | `raise ReservationError(...)` | `reservations/services.py:122`, `:200` |
| Kde se provede výsledná změna stavu? | při odmítnutí nikde; při úspěchu `save()` a kontrola indexem v DB | `reservations/services.py:134`; `reservations/models.py:48` |

Stejné rozhodnutí dělají **dvě místa záměrně**: aplikační kontrola (přátelská chyba) a databázový částečný unikátní index (poslední linie obrany při souběhu).

## A6. Relevantní závislosti

| Závislost | Kde se napojuje na náš kód | Která část zná její technické API | Doklad |
| --- | --- | --- | --- |
| databáze | `settings.py` vybírá `DATABASE_URL`; modely a služby | Django ORM (`models.py`, `services.py`) | `office_reservation_system/settings.py` |
| Notification Service | volá se při změně stavu | dnes jen `notifications.py` (`_send()` — log); reálné API by znal jen tento modul | `reservations/notifications.py` |
| IdP | Django vestavěná autentizace (`login_required`) | Django `django.contrib.auth` — **interní**, ne externí služba | `reservations/views.py:4`, `settings.py` INSTALLED_APPS |

## A7. AS-IS strukturální diagram

```mermaid
flowchart TB
    subgraph APP["Application code"]
        API["Reservation API<br/>(module)<br/>role: accepts confirm command"]
        LOGIC["Reservation logic<br/>(module)<br/>role: decides confirmation, writes state"]
        INTEG["Notification integration<br/>(module)<br/>role: delivers notification"]
        PERS["Persistence<br/>(Django ORM)<br/>role: loads / saves state"]
    end
    DB[("Reservation DB<br/>(database, PostgreSQL)")]
    NS(["Notification Service<br/>(external system; today log stub)")]

    API -->|"confirm(id)"| LOGIC
    LOGIC -->|"load / save Reservation"| PERS
    LOGIC -->|"send notification"| INTEG
    PERS -->|"read / write"| DB
    INTEG -->|"send event"| NS
```

*Obsah bloků:* **Reservation API** = `confirm_reservation_view`, `create_reservation_view` (views.py). **Reservation logic** = `confirm_reservation`, `_apply_approval_decision` (services.py) + `Reservation` (models.py). **Persistence** = Django ORM. **Notification integration** = `notify_reservation_event` (notifications.py). Policy/invariant není samostatný blok, žije uvnitř Reservation logic + v DB indexu.

## A8. Otázka pro další C03

| Položka | Obsah |
| --- | --- |
| Otázka | Kde se má udělat **autoritativní** rozhodnutí o konfliktu, aby BR-02 platilo i při dvou souběžných confirm requestech? |
| Doklad | kontrola `filter(...).exists()` (`services.py:118`) a `save()` (`services.py:133`) jsou dvě oddělené operace oddělené v čase; drží to až částečný unikátní index v DB (`models.py:48`) |
| Proč je důležitá | REQ-04/BR-02: souběh nesmí vytvořit dvě potvrzené rezervace téhož zdroje a dne |

## A9. Použití AI

AI byla použita na navigaci v repozitáři a první verzi diagramu. Do tohoto výstupu jsou zapsaná pouze tvrzení ověřená v kódu (`reservations/views.py`, `services.py`, `models.py`, `notifications.py`) a v běžících testech (`python manage.py test`).
