# Kitchen Manager

A mobile-first personal food inventory application. No package installation or paid services required. Python 3.12+ and a modern browser are sufficient.

## Run

From this repository:

```sh
python3 server.py
```

Open port 3000 in your development environment. No account or password is required. A persistent private browser cookie opens your kitchen automatically. Keep that cookie: a different browser or cleared cookies creates a separate kitchen. Existing signed-in sessions retain their data. Export backups regularly. Inventory starts empty. Data persists in `data/kitchen.sqlite3`; retain this directory between restarts. Environment variables are documented in `.env.example`; the server reads exported variables, not .env files automatically.

```sh
python3 -m unittest discover -s tests -v
node --check static/app.js
```

## Included

- Automatic private kitchens with persistent HttpOnly session cookies, same-origin mutation checks and owner-scoped database queries. Existing account sessions are preserved.
- Persistent, separate acquisition batches, decimal quantities, units, sources, storage, printed date types, notes and conditions.
- Search and storage filters, quantity adjustments, consume/discard, freeze/thaw, version checks, transactionally recorded history and compensating undo of the latest eligible action.
- Request IDs prevent duplicate application of the same request. Conflicting versions return HTTP 409; invalid quantities return 422.
- Use First explains printed dates and user condition flags, without invented freshness estimates or safety guarantees.
- Shopping list with purchase check-off and a separate, explicit inventory-add form.
- Link to the supplied original cookbook, JSON backup, inventory CSV, delete kitchen data and sign out.
- Responsive layout, native labeled forms, keyboard controls and live status announcements.

## Deployment

Use a single persistent Linux host with Python 3.12+, an HTTPS reverse proxy, and a durable disk. Set `COOKIE_SECURE=1`, `PORT=3000`, and `KITCHEN_DB=/persistent/path/kitchen.sqlite3`. Run `python3 server.py` from the checkout as an unprivileged supervised process. Forward HTTPS requests through the reverse proxy to the server; restrict direct public access to its HTTP port. Schema creation is idempotent and automatic from `migrations/001.sql`.

Back up SQLite using its backup API or SQLite backup command rather than copying during a write. JSON export is a readable backup; automated restore/import is not implemented. Do not put database files under `static/`. For a public launch add reverse-proxy request throttling, operational backups/monitoring and password recovery. The bundled Python HTTP server is suitable for local development and a small controlled pilot, not a hardened public production service.

There is no live deployment URL yet. Deploying requires a hosting target and HTTPS configuration. This task does not publish the cloud environment.

## Scope and limitations

This is the first functional implementation, not the completed PRD. SQLite provides server persistence, not a managed multi-region sync service. Kitchens are tied to browser cookies; there is no cross-device account sync or live push sync. During a connection failure, only the currently loaded session remains readable; reload while offline is not supported. Offline mutations are blocked, and ambiguous network failures require refreshing before trying again.

Photo upload/AI recognition, Google Sheet import, cookbook parsing and seeded recipes, recipe matching/cooking transactions, notifications, installable PWA caching, batch metadata editing, arbitrary storage transfers, catalog normalization and account deletion/password recovery are not implemented. Zero-quantity batches remain in exports/history but are hidden in the main list. Undo is available on nonempty batch details for the latest eligible action; full history navigation and restoring depleted batches still need UI work. Source documents were read only from the uploaded PRD; linked Google documents have not been imported or represented as verified data.

Google Fonts is an optional external typography request; system fonts are used if unavailable. No grocery data or photos are sent to third parties. No paid AI APIs are called. Hosting and backup costs depend on your provider. Accessibility has implementation support but still needs manual VoiceOver/device testing.
