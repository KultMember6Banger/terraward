# Data Governance — the TerraWard covenant

**Your data belongs to you. Full stop.**

TerraWard is built so that the people whose hands are in the soil own what comes off
their land — readings, observations, history, all of it. This document is a binding
statement of intent for the project and any official service built on it.

## Local-first by design

All your data — sensor readings, confirmed sightings, the risk history database, your
calibration config — lives in plain files on **your own machine**: the SQLite `.db`
file, your CSVs, your JSON config. TerraWard does not upload, mirror, or phone any of it
home. The *only* outbound network request the tool makes is fetching **public** weather
for the coordinates you give it. Nothing about your farm leaves your computer.

## Never sold, never brokered

The project, and any official TerraWard service, will **never** sell, rent, license, or
hand your data to advertisers, agribusiness, input suppliers, insurers, lenders, or any
other third party. There is no data-as-revenue model here, by design and by promise.

## Sharing is farmer-to-farmer, and opt-in only

The roadmap includes a neighbourhood outbreak map — early warning is stronger when a
region shares it. If and when that exists:

- Participation is **explicit opt-in**. Off by default. Nothing is shared unless you turn
  it on.
- What's shared is **aggregated and anonymized** — a risk signal for an *area* (e.g.
  "blight pressure rising in this 10 km cell"), never your identity, your exact field, or
  your raw readings.
- It is **farmer-and-grower only**. Not open to companies harvesting the feed.
- You can **leave and delete** at any time.

## No telemetry, no tracking

No usage analytics, no crash-phone-home, no hidden identifiers, no "anonymous stats that
aren't really anonymous." The tool does not watch you use it.

## What is stored, and what leaves your device

**Stored locally** — in a SQLite file you own (created private, owner-only `rw` on Unix; point `--db` wherever you like):
- the farm's name/label and its coordinates;
- computed risk events (date, module, severity, confidence, message);
- your confirmed sightings and any notes you add;
- timestamps of when each was recorded.

**What leaves your device** — only your **latitude and longitude**, sent over HTTPS to the weather service (Open-Meteo) to fetch the forecast. No farm name, no stored history, no identifiers, no telemetry, no analytics. Nothing else is transmitted anywhere, ever.

**Exercising your rights, locally:**
- *Inspect* — it's a plain SQLite file; `--history` and `--accuracy` read it back.
- *Export* — `--export json` or `--export csv`.
- *Erase* — delete the `.db` file (or individual rows); nothing auto-expires, so retention is entirely yours.

**Encryption at rest** — for a stronger guarantee, use full-disk encryption (FileVault on macOS, LUKS on Linux): it protects the database at no cost to TerraWard's zero-dependency design. App-level database encryption (e.g. SQLCipher) is possible but would add a dependency; for weather and agronomic logs, private file permissions plus disk encryption are normally enough. Your call.

## Code licence vs. data covenant

The **AGPL-3.0 licence covers the software** — it keeps the code open and forces anyone
who modifies or hosts it to keep *their* code open too. But a software licence does not by
itself govern *data*. That is why this covenant exists alongside it. The intent: anyone
running a TerraWard-derived service must keep the code open (AGPL) **and**, to carry the
TerraWard name and join the community, honour this data covenant.

## Your rights, concretely

- **Access & export** — your data is already exportable to open JSON/CSV (`--export`), and
  it's your files regardless.
- **Delete** — it's your machine; remove the `.db` or CSVs and it's gone.
- **Portability** — open formats, no lock-in, ever.
