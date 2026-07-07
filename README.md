# TerraWard


**A free, open, organic-first early-warning system for farmers — across land and sea.**

TerraWard turns free weather data and a farmer's own sensors into clear, actionable
risk alerts: disease, frost, heat, drought, soil and water problems, pests, livestock heat
stress, pollination windows, and harmful algal blooms. It is **prevention-first and organic** —
it never recommends a synthetic chemical. It is built to be tuned to *your* farm, to learn from
what actually happens in your fields, and to stay free.

No subscription. No paywall. No ads. Funded, if at all, by the farmers who can spare a tip.

## ⚖️ Mission, License & Enforcement — READ BEFORE YOU USE THIS

### TerraWard exists to keep farm intelligence FREE.

This tool was built for one reason: to break the paywall on farmers, growers, and small producers. Early-warning intelligence about disease, frost, pests, and drought should not be a luxury sold back to the people who feed us. TerraWard is, and will always remain, free and open for every farmer on Earth. Use it. Run it. Tune it to your land. Share it with your neighbour. It costs nothing and it always will.

### The License: AGPL-3.0 — and it has teeth.

You are **FREE** to use, run, study, modify, and share this software.

You are **REQUIRED**, if you distribute it OR run a modified version as any network, web, cloud, or hosted service, to release the **COMPLETE source code of your version to every user, under this same AGPL-3.0 license, at no cost.**

You may **NOT** take this code, or anything derived from it, and make it **closed-source, proprietary, or locked behind a paywall** where users cannot freely obtain the full source. **That is a licence violation, full stop.**

The practical effect is deliberate: **no corporation can take TerraWard, wrap it, and sell it to farmers as a closed paid product.** If you build on this, the law compels you to hand your users the entire source to your version, for free, under these same terms. The paywall business model collapses by design. That is the whole point.

### ⚠️ TO ANY COMPANY, AGRIBUSINESS, OR INDIVIDUAL CONSIDERING OTHERWISE:

**Do not.** This software is protected by copyright and the AGPL-3.0, and the author **reserves every right the law grants to enforce it.** Any attempt to take TerraWard or a derivative closed, proprietary, or paywalled without releasing source **will be met hard and fast** — through DMCA takedowns, formal demands for source disclosure, and legal action pursued to the fullest extent available. The public commit history of this repository stands as dated proof of original authorship.

You were warned, in plain words, right here.

**Copyright © 2026 KultMember6Banger. Licensed under AGPL-3.0. All enforcement rights reserved.**

## Why

Most farm tech fails for the same reasons: it's expensive, fragmented across a dozen apps, it
dumps data instead of decisions, farmers don't trust its black-box alerts, and it's built for
big agribusiness running chemical inputs — not for organic or smallholder growers. TerraWard answers each:

- **One engine, many modules** instead of a dozen disconnected apps.
- **Decisions, not data** — every alert says what's happening and what to do, organically.
- **A trust loop** — you report what you actually saw; the system measures its own accuracy and
  tells you when to recalibrate.
- **Tunable to your farm** — every threshold lives in a config file you control.
- **Free, offline-capable, zero-dependency** — runs on a laptop or a Raspberry Pi in a barn.

## Opening

The app opens on a short cinematic intro — the solar system, a zoom through to the sun, then a spinning sunlit Earth as **TERRAWARD** resolves into view. It's a self-contained, dependency-free canvas animation: open `assets/intro.html` in any browser. (The command-line tool has a quieter ASCII version: `terraward --splash`.)

## Quick start

> **New to TerraWard or deploying it on a real farm?** See **[USER_MANUAL.md](USER_MANUAL.md)** —
> a full guide to devices (laptop, Raspberry Pi, phone), automation, sensors, and how to validate
> the tool against your own ground over a season.

No installation needed (Python 3.8+ only, no dependencies):

```bash
python3 terraward.py --splash   # the opening scene
python3 terraward.py --demo
```

Or install it as a command:

```bash
pip install -e .
terraward --demo
```

Run against a real location (live weather from the free Open-Meteo API):

```bash
terraward --lat 50.81 --lon 3.34 --name "My field"
```

Add your own field/water sensors:

```bash
terraward --sensor-csv examples/sample_sensors.csv
```

See your whole farm at once — several parcels, one combined board:

```bash
terraward --parcels examples/sample_parcels.json --digest
```

## Modules

| Module | Watches for | Reads |
|---|---|---|
| late_blight | Potato late blight (Hutton + Smith ensemble) | weather |
| scab_risk | Apple-scab infection periods (revised Mills leaf-wetness model) | weather |
| downy_mildew | Grapevine downy mildew (Plasmopara viticola): primary "3-10 rule" + secondary infection | weather |
| frost_risk | Frost & cold stress for crops | weather |
| heat_stress | Crop heat stress | weather |
| cold_stress | Livestock cold stress (wind-chill + wet-coat), per species | weather |
| wind_conditions | High-wind lodging & physical damage | weather |
| livestock_thi | Livestock heat stress (THI), per species | weather |
| pollinators | Poor bee-foraging / pollination windows, per kept species | weather |
| insect_pests | Named-pest phenology (degree-days, per pest + biofix) | weather |
| growing_degree_days | Crop development / suitability heat | weather |
| evapotranspiration | Crop water demand & irrigation need (reference ET) | weather |
| soil_conditions | Water, oxygen + chemistry (pH, N, P, K, EC, organic matter) | soil sensors |
| manure_spreading | Manure/slurry spreading windows (rain-ahead, frost, saturation, ammonia) | weather (+ soil sensor) |
| treatment_window | Organic foliar-treatment windows (rain wash-off, wind drift, bee safety) | weather |
| marine_conditions | Aquaculture oxygen, temperature, bloom + chemistry, per species | water sensors |

List them anytime: `terraward --list-modules`. Run a subset: `--modules late_blight,frost_risk`.

**Camera scanning (optional).** TerraWard has a pluggable on-device detector seam: `terraward
--scan-image leaf.jpg --crop potato`. No vision model ships with it (the core stays
dependency-free and offline), but you can register your own — e.g. a PlantVillage-trained
TFLite/ONNX classifier — with `@detector("mymodel")`. A confident detection becomes an alert
*and* is auto-logged as a confirmed sighting, so the camera feeds the same trust loop as
everything else. The full on-device vision plan (datasets, safe model loading, field validation) is in [docs/VISION.md](docs/VISION.md) — and no model ships until its field accuracy is measured.

## The trust loop (what makes it different)

1. The engine flags risk days.
2. You report what actually happened:
   `terraward --report-sighting --date 2026-06-20 --observed confirmed --db farm.db`
3. It scores itself: `terraward --accuracy --db farm.db` shows hits, false alarms, misses.
4. False alarms? Tune the thresholds for your microclimate in your config.

This is the calibration most tools skip — and the reason farmers stop trusting black-box alerts.

## Calibrating to your farm

Every threshold is in `CONFIG` and overridable with a JSON file:

```bash
terraward --demo --config examples/sample_config.json
```

```json
{
  "frost_risk": { "near_frost": 2.0 },
  "livestock_thi": { "moderate": 70 }
}
```

## Sensor CSV format

Header required; include any subset of the optional columns:

```
date,soil_moisture,soil_oxygen,soil_temp_min,dissolved_oxygen,chlorophyll,water_temp,salinity
2026-06-19,52,7,14.0,,,,
2026-06-20,,,,1.5,12,24,
```

- soil_moisture %water · soil_oxygen %O2 · soil_temp_min C
- dissolved_oxygen mg/L · chlorophyll ug/L · water_temp C · salinity PSU

## Open export, history

```bash
terraward --demo --export json --out results.json
terraward --demo --save --db farm.db    # log risk events
terraward --history --db farm.db          # risk timeline over time
```

## AI advisor — a briefing, and optional on-device chat

TerraWard can turn its alerts into a prioritized, plain-language **action briefing**, and —
optionally — let you **chat** with an AI that runs entirely on your own machine.

```bash
python3 advisor.py --demo                  # plain-language prioritized briefing
python3 advisor.py --demo --show-grounding # see exactly what an AI would be allowed to use
```

Two layers. The briefing (Layer 1) is deterministic and zero-dependency: it only restates and
prioritizes what the engine already computed, so it **cannot hallucinate**. The optional chat
(Layer 2) runs a small open model **locally** — no cloud, no account, nothing transmitted — and
is strictly constrained to the engine's verified facts; if no model is installed it falls back to
the briefing and never breaks. Because the advisor runs where your data already lives, it is the
*only* thing that ever touches that data. Full design: [docs/AI_ADVISOR_DESIGN.md](docs/AI_ADVISOR_DESIGN.md).

**Languages.** The advisor speaks the farmer's language: the local model responds natively in Dutch/Flemish, French, German, Mandarin, Russian, Ukrainian, Polish, Romanian, Turkish, Spanish, Portuguese and more (keeping the numbers exact), and the briefing's fixed labels come from a message catalog (English + Dutch/Flemish shipped, more welcome). Set it with `--lang nl`.

## Data sources

- **Weather:** [Open-Meteo](https://open-meteo.com) — free, no API key. Swappable for regional
  feeds like Belgium's Agromet (CRA-W).
- **Satellite (planned):** Copernicus Sentinel (land) and Copernicus Marine (sea) — free, EU-funded.
- **Field & water sensors:** your own probes, via CSV.

## Running the tests

```bash
python3 -m unittest test_terraward -v
```

## Organic commitment

TerraWard never recommends synthetic pesticides or fungicides. Its action advice is
prevention and organic management: resistant varieties, airflow, rotation, inoculum removal,
biological control, and timing.

## Your data — and who it belongs to

Your data belongs to you. TerraWard is **local-first**: your sensor readings, sightings, and
history live in files on your own machine, and the tool never uploads them. The only network
request it makes is fetching public weather for your coordinates. Your data is **never sold,
brokered, or shared with third parties**. Any future farmer-to-farmer sharing (such as a
neighbourhood outbreak map) is strictly **opt-in, aggregated, anonymized, and revocable**. The
AGPL-3.0 licence keeps the *code* open; the data covenant in
[DATA_GOVERNANCE.md](DATA_GOVERNANCE.md) governs the *data*.

## Accuracy & known limitations

TerraWard is an honest tool, which means being clear about what it does *not* yet know:

- **Thresholds are literature defaults, not validated for your fields.** The Hutton/Smith, THI,
  degree-day and marine numbers come from published research and extension guidance — sensible
  starting points, not truth for your microclimate. Treat the first season as calibration:
  report what you actually see (`--report-sighting`), watch `--accuracy`, and tune your
  `--config` until the alerts match your ground.
- **The blight model approximates Smith periods** with an hours-of-high-humidity proxy rather
  than the full original definition. Good for relative risk; calibrate before operational use.
- **Livestock THI uses the day's peak temperature with mean humidity** as a deliberately
  protective estimate of peak heat stress; actual peak-hour humidity may differ.
- **The live weather path depends on a third-party API.** It is built to Open-Meteo's current
  spec, but sanity-check the first live runs against local observations.
- **Marine alerts are a prompt to check official monitoring, never a substitute for it.**
  Shellfish-biotoxin and harvesting-closure decisions belong to accredited labs and the
  competent authority. A bloom-risk flag means "go check the official source," not "it's safe."

None of this is a flaw to hide — it is exactly why the calibration loop exists. A tuned tool
that has earned a season of agreement is worth far more than impressive-looking defaults.

## Threshold sources

The new modules' thresholds are grounded in published guidance, not guesswork: livestock
heat stress on the standard cattle THI; **livestock cold stress** on lower-critical-temperature
and wind-chill data from US extension services (the wet-coat escalation reflects that a soaked
coat raises the critical temperature from roughly -7C to ~+15C); **aquaculture water quality**
on extension toxicity guidance (total ammonia ~0.25-2.0 mg/L safe band, nitrite toxic from
~0.1 mg/L, nitrate relatively non-toxic below ~100 mg/L, pH ~6.5-9.0) — with the honest caveat
that ammonia toxicity is strongly pH/temperature-driven, so the total-ammonia threshold is a
conservative proxy. **Soil chemistry** thresholds (pH band, N/P/K, EC, organic matter) are
sensible agronomic starting points that genuinely depend on your crop and your soil-test method
— calibrate them. As always: these are defaults to be tuned against your own ground, not
verdicts.

## Roadmap

**Done:** 16 modules (land + sea + livestock + pollinators + three disease models + named-pest phenology), a whole-farm multi-parcel view, the next-48h digest, ensemble confidence, the
trust/calibration loop, multi-source sensor import, open export, history, config layer, tests, and a deterministic AI briefing (Layer 1) with a grounding seam for a local model.

**Planned:** wiring a local model into the advisor (Layer 2, grounded by the briefing so it can't hallucinate), a plain-language action calendar, satellite inputs, a neighbourhood outbreak map
from shared sightings, market/price intelligence, multilingual output, an open module library,
and a friendly web/mobile front-end.

## Contributing

Adding a capability is one function — see [CONTRIBUTING.md](CONTRIBUTING.md). The goal is a
community library of crop, pest, livestock and marine modules contributed by farmers,
agronomists and researchers.

## License

GNU Affero General Public License v3.0 (AGPL-3.0) — see [LICENSE](LICENSE). This guarantees that anyone who uses or modifies this software — including running it as a network service — must keep their version open and free under the same terms. The tool stays a commons; it cannot be captured behind a paywall.

## Disclaimer

This is an early-warning aid, not a guarantee. Alerts flag *conditions favourable* to a risk,
not confirmed events. Always calibrate to your local conditions, keep scouting your fields, and
consult qualified agronomic, veterinary, or food-safety authorities — especially for
shellfish-harvesting and biotoxin safety.

## Sharing & the Commons (proposed)

A future, fully optional layer would let growers share *minimized, anonymized* early-warning signals with each other — federated, self-hostable, no central data lake, no accounts, identity held as a local key. It is a proposal under discussion and never changes how the local tool works. See [docs/COMMONS.md](docs/COMMONS.md).

## Giving back (proposed)

Every tip (from 1 €) plants a tree and earns a place in *the Grove* — a transparent supporters list, with a yearly thank-you for supporters and top corroborated contributors. No surveillance, no jackpot, funding kept public. See [docs/GIVING_BACK.md](docs/GIVING_BACK.md).

## Machinery & mobile (proposed)

TerraWard isn't installed on a tractor's closed display; instead it runs on a companion computer you control and *reads* the machine's CAN bus (ISOBUS / J1939) over USB-to-CAN. A phone front-end starts as an offline, installable PWA (no app-store gatekeepers), going native only if camera/Bluetooth demand it. See [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md).
