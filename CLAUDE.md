# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

DF Aggregator is networked radio Direction Finding (DF) software. It collects Direction-of-Arrival (DOA) measurements from multiple KrakenSDR/KerberosSDR receivers, computes LOB (Line of Bearing) intersections, clusters them via DBSCAN, and presents results on a CesiumJS 3D map via a Bottle web server.

## Running

```bash
python3 df-aggregator.py -d <database_file> [options]
```

Key options:
- `-d FILE` — SQLite database file (required)
- `-r FILE` — file listing receiver URLs, one per line
- `-g FILE` — GeoJSON output file (written on shutdown)
- `-e NUMBER|auto` — max clustering distance epsilon (default: auto)
- `-c NUMBER` — minimum confidence threshold (default: 10)
- `-p NUMBER` — minimum power threshold (default: 10)
- `-m NUMBER|auto` — min samples per DBSCAN cluster (default: auto)
- `--ip` / `--port` — server bind address (default: 127.0.0.1:8080)
- `-o` — offline mode (start with receiver paused)
- `--plot_intersects` — render every intersection point, not just the cluster centroid
- `--no-lob-history` — disable LOB history recording (single-receiver triangulation still records)
- `--access_token FILE` — Cesium Ion access token (enables Cesium World Terrain etc.)
- `--debug` — DEBUG-level logging and Bottle debug mode
- `--log-file PATH` — also write logs to a file

## Dependencies

```bash
pip install -r requirements.txt
```

Core: `bottle`, `waitress`, `geojson`, `numpy`, `lxml`, `czml3` (>=3.0), `scikit-learn`, `scipy`.

## Architecture

The code was modularized — `df-aggregator.py` is now just CLI parsing + wiring. Logic lives in five sibling modules:

| Module | Responsibility |
|--------|----------------|
| `df-aggregator.py` | argparse, logging setup, thread bootstrap, signal handling |
| `config.py` | `AppConfig`, `MathSettings` dataclasses, all tunable constants |
| `database.py` | `Database` class — SQLite reader/writer with a queue-fed writer thread, AOI cache, vectorized `run_aoi_rules()` |
| `receivers.py` | `Receiver`, `ReceiverManager` — HTTP polling, error backoff, LOB pairing, single-receiver historical triangulation |
| `geo.py` | DBSCAN clustering, confidence ellipses, CZML/GeoJSON serialization, pipeline stats |
| `web.py` | Bottle routes, request validation, `GzipMiddleware`, `start_server()` |
| `vincenty.py` | Geodetic math (Haversine, Vincenty inverse/direct, angular_diff_deg) |
| `sse_broker.py` | `Broker` + `ClientChannel` — fan-out SSE broker; per-client bounded queues with overflow-drop; daemon heartbeat thread |

### Data flow

```
Receivers (HTTP/XML) → Receiver.update() → ReceiverManager.run_loop()
                                              ↓
                        compute LOB intersections / single-rx triangulation
                                              ↓
                                     Database._edit_q (Queue)
                                              ↓
                            Database.writer_loop() (daemon thread) → SQLite

Browser ← CesiumJS ← CZML ← geo.write_czml() ← geo.process_data()
                                                     ↑
                                            GET /output.czml (web.py)

Browser ← SSE ← sse_broker.Broker ← rx_mgr._publish_changes()
                                            (rx_config / rx_telemetry events)
                                  ← web.py AOI mutation handlers
                                            (aoi_config events)
                    ↑
            GET /events (web.py)
```

### Threading model

Three long-lived threads share one process:

1. **Main thread** — runs `ReceiverManager.run_loop()` (~1s cycle): poll receivers, pair LOBs, triangulate single-rx, queue DB writes.
2. **DB writer thread** (`Database.writer_loop`) — owns the only write connection, drains `_edit_q`. Reads use short-lived connections per call (sqlite3 is not thread-safe across connections).
3. **Web thread** (`web.start_server`) — Bottle on waitress (`server="waitress"`, `connection_limit=64`, `threads=8`).

Synchronization:
- `ReceiverManager._lock` guards list **structure** (append/del) and `d_2_last_intersection` writeback. Per-attribute reads/writes (`isActive`, `doa`, ...) rely on CPython attribute-write atomicity. **Never iterate `self.receivers` directly from a worker thread** — always use `_snapshot()`.
- `Database._aoi_cache_lock` guards the AOI cache. Use `commit_and_invalidate_aoi_cache()` after AOI mutations — invalidating *before* the writer commits leaves a stale cache pinned.
- Multiprocessing for DBSCAN uses an explicit **forkserver** context (in `geo.py`, not via `set_start_method`) to avoid fork-after-thread deadlocks.

### Database schema (SQLite)

| Table | Columns / Purpose |
|-------|---|
| `receivers` | `station_id`, `station_url`, `isAuto`, `isMobile`, `isSingle`, `latitude`, `longitude` |
| `lobs` | Historical LOBs: `id`, `time`, `station_id`, `latitude`, `longitude`, `confidence`, `power`, `frequency`, `lob` |
| `intersects` | Computed intersections: `id`, `time`, `latitude`, `longitude`, `num_parents`, `confidence`, `aoi_id` |
| `interest_areas` | `uid`, `aoi_type` (`"aoi"` or `"exclusion"`), `latitude`, `longitude`, `radius` |

PRAGMAs set by the writer at startup: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`. Schema migrations are introspected via `PRAGMA table_info`, not blind `ALTER ... swallow OperationalError` — keep that pattern when adding columns. Indexes covering `(aoi_id, confidence DESC)`, `lobs(station_id, time)`, etc. are created on init.

### Web routes (all defined in `web.create_routes`)

| Route | Purpose |
|-------|---------|
| `GET /` (also `/index`, `/cesium`) | Render CesiumJS UI from `views/cesium.tpl` |
| `GET /update` | Update runtime thresholds (`minconf`, `minpower`, `rx`, `lob_history`) via query params |
| `GET /rx_params` | Receiver state snapshot JSON |
| `PUT /rx_params/<action>` | `new` / `del` / `activate` / `<index>` (configure mobile/inverted/single) |
| `GET /interest_areas` | AOI list JSON |
| `PUT /interest_areas/<action>` | `new` / `del` / `purge` (purge defined only for exclusion zones) |
| `GET /run_all_aoi_rules` | Re-run AOI rules across all intersections (vectorized haversine) |
| `GET /output.czml` | Run clustering, return CZML |
| `GET /receivers.czml` | Receiver positions + LOB lines as CZML |
| `GET /aoi.czml` | AOI boundary polygons as CZML |
| `GET /lob_history.czml` | Replay LOBs in a time window (used by the timeline scrubber) |
| `GET /api/pipeline-stats` | Pipeline counters JSON (consumed by the status bar) |
| `GET /events` | SSE stream (`text/event-stream`); pushes `rx_config`, `rx_telemetry`, `aoi_config`, and `heartbeat` events |
| `GET /static/<path>` | Static assets |

**Security:** there is intentionally no authentication. Default bind is `127.0.0.1`; binding to a non-loopback address exposes mutating endpoints to the network. Receiver URL validation only blocks non-http(s) schemes and unresolvable hosts — RFC1918/loopback are allowed because receivers normally live on the LAN. Adding auth is a product decision (see top-of-file note in `web.py`).

### Frontend

`views/cesium.tpl` is a Bottle SimpleTemplate (not Jinja2). Static assets in `static/`:
- `receiver_configurator.js` — receiver cards
- `interest_areas.js` — AOI management
- `cardsmenu.js` — card menu system
- `lob_history.js` — timeline scrub for historical LOBs
- `statusbar.js` — pipeline stats / hamburger menu
- `mobile.js` / `mobile_scrub.js` — mobile layout (≤768px)
- `style.css`, `ui.css` — design-token CSS

CesiumJS 1.135 loaded from CDN. The UI polls `/output.czml` every 2.5 seconds.

**Cesium docs:** use the `docs-mcp-server` MCP — the `cesium` library is already indexed there. Prefer `mcp__docs-mcp-server__search_docs` (library: `cesium`) over web search for CesiumJS API questions; results are pinned and far more precise than google. Note that keyword-only matching can return irrelevant hits — verify findings against actual source before acting (the `mcp-doc-verifier` skill formalizes this).

## Tunable constants (all in `config.py`)

| Constant | Value | Meaning |
|----------|-------|---------|
| `LOB_DRAW_DISTANCE_METERS` | 40,000 | How far to draw each bearing line |
| `HEADING_DRAW_DISTANCE_METERS` | 20,000 | Receiver heading indicator length |
| `MAX_INTERSECTION_DISTANCE_METERS` | 100,000 | Reject intersections beyond this range |
| `MIN_SPATIAL_DIVERSITY_METERS` | 500 | Single-rx mode: minimum baseline between current and historical LOB |
| `MAX_TIME_DIFF_MS` | 5,000 | Max time gap between paired LOB measurements |
| `SINGLE_RX_MIN_TIME_DIFF_MS` | 10,000 | Min gap before a single-rx receiver triangulates again |
| `HISTORICAL_LOB_WINDOW_MS` | 1,200,000 | Single-rx mode: how far back to pull historical LOBs (20 min) |
| `MAX_INTERSECTS_PER_AOI` | 25,000 | Cap intersections fed to DBSCAN per AOI |
| `AUTOEPS_SAMPLE_SIZE` | 2,000 | Subsample size for auto-epsilon k-NN |
| `BEARING_CHECK_TOLERANCE_DEG` | 5 | Bearing-match tolerance |
| `MIN_LOB_PAIR_BEARING_DIFF_DEG` | 5 | Single-rx: min bearing difference between paired LOBs (uses wrap-aware `angular_diff_deg`) |
| `AUTOEPS_SLOPE_THRESHOLD` | 0.003 | Auto-epsilon sensitivity |
| `GAUSSIAN_ELLIPSE_SIGMA` | 3.0 | Confidence ellipse sigma (~99.7%) |
| `RECEIVER_MAX_RETRIES_TRANSIENT` | 5 | Retry budget for 5xx / network errors |
| `RECEIVER_MAX_RETRIES_PERSISTENT` | 2 | Retry budget for 4xx / parse errors |
| `RECEIVER_BACKOFF_BASE_S` | 2 | Exponential backoff base, capped at 64s |
| `RECEIVER_PROBE_INTERVAL_S` | 30 | Probe cadence for deactivated receivers |

## Gotchas

- **`czml3 >= 3.0`** uses Pydantic v2 with strict typing. Use `czml3.Packet` (not `Preamble` for subsequent packets) and pass values as the correct `czml3` types — bare Python numerics are rejected.
- **forkserver, not fork**: `geo.py` uses a private `multiprocessing.get_context("forkserver")` for DBSCAN. Don't switch to default-context `Process()` — the parent has live threads and fork would deadlock or warn.
- **lxml XXE hardening**: `receivers.py` uses a module-level `_secure_parser` (`resolve_entities=False`, `load_dtd=False`) and a `_no_redirect_opener`. Receiver responses come from arbitrary network endpoints — never let `lxml` fetch the URL itself, and don't swap to `requests` or bare `urlopen`.
- **Single-receiver mode** (`isSingle and isMobile`): the receiver triangulates against its own historical LOBs from the `lobs` table within `HISTORICAL_LOB_WINDOW_MS`. This requires LOB recording even when `--no-lob-history` is set; the recording path in `_record_lobs` honors that.
- **AOI assignment is "last match wins"**: `Database.run_aoi_rules` iterates AOIs in row order; an intersection inside multiple AOIs gets the largest column-index uid. Preserved deliberately — changing it is a behavior change.
- **`purge` only valid for `exclusion` AOIs.** `Database.purge_database` raises `ValueError` otherwise; the web layer rejects non-exclusion purges with HTTP 400 before reaching it.
- **GzipMiddleware** wraps the WSGI app in `start_server()`. It bypasses gzip entirely for `PATH_INFO == "/events"` because SSE is a streaming generator — buffering would deadlock. Requires `Accept-Encoding: gzip` for all other routes, and merges (not replaces) any upstream `Vary` header.
- **Receiver URL validation** (`web._validate_receiver_url`) explicitly allows loopback and RFC1918 — receivers normally live on the LAN. This is not SSRF protection; auth is.
