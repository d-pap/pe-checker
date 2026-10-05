# PE Checker development notes

- Run `npm start` (or `python3 server.py`) and open `http://localhost:4173`. Use `PORT=...` when that port is occupied.
- Run `npm test` for offline importer, parser, and identity matching checks.
- `core.py` owns the source adapters and SQLite schema; `server.py` serves the API and refresh scheduler; `live.js` renders research results. The SQLite database is generated and ignored by Git.
- The first run downloads the intentionally published veterinary XLSX and HVAC CSV. Each is checked again after 24 hours while the server runs; on a failed refresh, the previous SQLite rows remain available.
- Do not present a missing row as independent ownership, apply a same-name clinic from another city, or turn a historical deal into a current-control claim.
- Private Equity Vet's 2026-08-12 terms restrict republishing a material part of its compilation without written permission. The local import is for personal research; resolve data rights before public deployment.
