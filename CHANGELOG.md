# Changelog

## 1.1.0 -- 2026-07-07
Sixteenth module and a science-accuracy pass over the disease, livestock, and marine models.

- **New module `downy_mildew`** (grapevine *Plasmopara viticola*): the primary "3-10 rule"
  (temperature + rain half of the classic Baldacci criteria) plus the secondary wet-spell
  infection cycle, with organic-first cultural advice.
- **Cross-midnight leaf wetness:** contiguous wet spells are now tracked across calendar-day
  boundaries (`max_wet_run`), so an overnight wetting no longer fragments below the scab/blight
  infection thresholds -- a real missed-infection bug in the daily model.
- **Apple scab:** finely-split cold-temperature bands from the published Mills-Jones table.
- **Livestock heat stress:** poultry are now graded on a degC poultry index (wet-bulb based),
  not the cattle NRC THI they can't be compared to; pigs use St-Pierre (2003) swine onsets; new
  `sow` species; consecutive-heat-day streak tracking; warnings for unknown `--livestock` species.
- **Aquaculture/marine:** un-ionized ammonia (NH3, Emerson 1975) graded instead of raw TAN;
  dissolved oxygen reported as percent-of-saturation (Weiss 1970); new pond-turnover risk
  (warm, stratified pond + heavy rain or a cold front).
- **Soil:** root-zone temperature alerts (frozen / too-cold-to-sow / warm-enough-to-sow).
- **Evapotranspiration:** crop coefficient (Kc) applied to reference ET0.
- **Pollinators:** per-species wind thresholds, plus a positive "good foraging window" alert.
- 138 tests pass (up from 129).

## 1.0.0 -- first public release
TerraWard's first stable release: a free, open, organic-first farm early-warning engine.
One Python file, zero dependencies, runs on a laptop or a Raspberry Pi. Fifteen risk
modules across land and sea, a 48-hour digest, a whole-farm multi-parcel view, an honest
deterministic advisor in 14 languages, and a trust loop that scores its own accuracy
against your sightings. Live weather via Open-Meteo; fully offline --demo. AGPL-3.0.

- Fully documented CLI (grouped --help, every flag explained, worked examples).
- Four audit passes: 129 tests, security-clean, verified on Python 3.8/3.11/3.12.

## 0.22.0
- `--save` now works alongside `--parcels`. Each parcel's risk events are written to history under
  its own name, so the validation/trust loop runs per field (`--accuracy --name "<parcel>"`). This
  means a single scheduled command can assess an entire multi-field farm *and* build the season-long
  accuracy record at once -- previously saving was single-location only.

## 0.21.0
- Added **USER_MANUAL.md**: a full deployment-and-testing guide for end users (which device,
  Raspberry Pi farm-appliance setup, cron automation, sensor CSV, and a staged season-long
  validation method via the trust loop), linked from the README.
- Assembly and fine-tuning pass over the whole program:
  - **Single-source version**: the runtime version is now one `VERSION` constant; the three
    banners, both User-Agent strings, and the new `--version` flag all derive from it. A test
    pins it to `pyproject.toml` so the two cannot drift -- replacing the old seven-location manual
    bump.
  - **New `--version` flag** and `__version__` attribute.
  - **Guard tests**: engine output (report/digest/farm) must stay pure ASCII, and the banner must
    reflect `VERSION` -- locking in the consistency the audits established.
  - Re-read all fifteen modules and the assembled pipeline end to end: no behavioural bugs found.

## 0.20.0
- Test-coverage pass: overall line coverage raised from ~70% to ~88% (engine 71% -> 88%, advisor
  64% -> 90%). The big previously-untested surface was `main()` itself -- the orchestration a user
  actually runs. Added end-to-end smoke tests through `main()` covering the board, `--digest`,
  imperial units, `--export` (json/csv), `--save`/`--history`, the full `--report-sighting` ->
  `--accuracy` trust loop, the `--parcels` farm path (with mocked network), and clean non-zero
  exits on bad input; plus smoke tests through the advisor CLI (briefing, language fallback,
  `--show-grounding`, and the no-model `--ask` deferral). No new bugs surfaced -- the wiring held.

## 0.19.0
- Advisor audit pass (the engine was audited in 0.18; this covers `advisor.py`):
  - **Label coverage**: apple scab, manure spreading, treatment window, and evapotranspiration were
    added since the advisor's label map was written, so they showed as raw keys (`scab_risk`) in the
    briefing. All engine modules now have proper display names, enforced by a test.
  - **Duplicate "- none"**: an empty grounding-context section printed `- none` twice (a redundant
    `or`-fallback plus an explicit append). Fixed to one.
  - **ASCII output**: the briefing used non-ASCII em-dashes against the engine's ASCII `--`
    convention; `advisor.py` is now pure ASCII, locked by a test.
  - **Empty window**: `build_briefing` raised `IndexError` on an empty day list; now degrades to an
    "n/a" window like the engine renderers.

## 0.18.0
- Hardening and bug fixes from an audit pass:
  - **Sensor CSV**: non-numeric cells no longer abort the whole run, and `inf`/`nan` are rejected
    rather than written into a sensor field (a `nan` silently disables every `>=` comparison). Bad
    cells are skipped with a warning; the rest of the file still applies.
  - **Forward windows**: `treatment_window` and the manure good-window now look forward from today,
    so they no longer surface an application window that is already in the past when the run
    includes history. (Previously needed `--past-days 0` to work around.)
  - **Renderers**: guarded against an empty window so they return a clean "no data" line instead of
    raising `IndexError` if ever reached with no days.
- Security review: no `eval`/`exec`/`pickle`/`subprocess`, all SQL is parameterized, the DB stays
  `0600` on POSIX, HTTPS is enforced on both fetch and geocode, and imperial output has no metric
  leaks. No vulnerabilities found.

## 0.17.0
- Parcels are now per-parcel configurable. Each parcel in a `--parcels` file may declare its own
  `modules` to run and its own `pests` / `livestock` / `aquaculture` / `bees` profiles (anything
  omitted inherits the global flags). So an orchard parcel runs apple scab and codling moth while a
  pond runs water chemistry and trout -- instead of every module firing on every parcel. The
  farm roll-up now surfaces each parcel's own worst concern rather than the same region-wide
  weather alert repeated on every line. All per-parcel names are validated against the registry.

## 0.16.0
- New `--parcels` whole-farm view: point it at a JSON file of parcels (each lat/lon or a place
  name) and TerraWard assesses every one and prints a combined roll-up -- per parcel, its worst
  next-48h severity, the count of concerns, and the single most urgent one, with the worst parcel
  floated to the top. With `--digest` the roll-up is a one-screen farm brief; without it, each
  parcel's full board follows. See `examples/sample_parcels.json`. The jump from field to farm.
- New `docs/VISION.md`: an honest design and roadmap for the on-device vision layer (leaf-disease
  lesions, pest ID, Varroa counts). The pluggable detector seam already exists and is wired to the
  trust loop; this documents the real climb -- datasets, on-device models, safe model loading, and
  field validation -- and commits to shipping no model until its field accuracy is measured.

## 0.15.0
- New module `scab_risk`: a second disease model alongside late blight. It forecasts primary
  apple-scab (Venturia inaequalis) infection periods using the revised Mills criteria (MacHardy &
  Gadoury 1989) -- grading leaf-wetness hours against the average wet-period temperature into
  light, moderate, and severe ascospore-infection risk. It reuses the same leaf-wetness signal as
  late_blight, carries a confidence flag, and steers organic protection (sanitation first;
  sulphur/lime-sulphur only as a protectant applied before the wet period, paired with
  treatment_window for timing). Thresholds banded from the published table; calibratable.

## 0.14.0
- `--digest` now groups repeats: consecutive alerts of the same module and severity (a heatwave
  that flags severe livestock heat three days running) collapse into a single concern line with a
  "+N more, through <date>" tail. The digest now reports distinct concerns, not raw alert counts,
  so a parked weather system reads as a few things to act on rather than a repeating list.

## 0.13.0
- New `--digest` mode: a compact, forward-looking view that answers "what needs me in the next
  48 hours?" It ranks the dated alerts by severity, hides history and low-signal context, and
  footnotes what lies further out -- so an overloaded week (a heatwave can throw 90+ lines)
  collapses to a short action list. The full board remains the default.

## 0.12.0
- New module `treatment_window`: pairs with the pest models. Once a pest says "treat now", this
  answers *when* the weather lets you apply an organic foliar treatment -- it blocks on rain
  wash-off and wind drift, flags heat as a caveat for sulphur and oils, finds the next clear
  window, and steers application to the evening to protect foraging bees (spinosad is bee-toxic
  until dry) and reduce UV breakdown of Bt. Day-resolution; thresholds calibratable.

## 0.11.0
- `insect_pests` is now a named-pest degree-day model. Each pest accumulates heat above its own
  base temperature from an optional `--biofix` (first eggs / first moth catch / first flight) and
  maps to real life stages with stage-specific organic actions. Ships Colorado potato beetle,
  codling moth, cabbage root fly, European corn borer, and the original `generic` default.
  Thresholds converted from published extension models; all calibratable. Set with `--pests`.

## 0.10.0
- New module `evapotranspiration`: reference ET0 by the Hargreaves method (temperature + site
  latitude, no extra dependencies) feeding a simple rain/ET soil-water balance. Flags when crops
  are likely water-stressed and need irrigation, and explicitly warns against applying more than
  the deficit, since over-watering leaches nutrients. Reference ET (multiply by crop Kc for
  crop-specific need); a soil-moisture sensor is a more direct signal where available.

## 0.9.0
- Species-aware livestock: `--livestock` picks the animals you keep (dairy/beef cattle, sheep,
  goat, pig, poultry); both heat (THI) and cold-stress thresholds are now per species. Dairy
  cattle remains the default, so existing behaviour is unchanged.
- Species-aware pollinators: `--bees` (honeybee, bumblebee, solitary) with per-species foraging
  temperatures.
- New module `manure_spreading`: weather-and-ground spreading windows -- rain forecast within
  ~48h, recent-rain saturation, frozen ground, and ammonia-loss timing. It defers closed
  periods, N/P caps and organic harvest intervals to official sources instead of hardcoding a
  legal calendar.
- Species-aware aquaculture: `--aquaculture` (trout, salmon, carp, tilapia, shellfish, mixed)
  sets per-species dissolved-oxygen, temperature and ammonia thresholds; marine_conditions now
  also flags species cold/heat stress and lethal bounds. `mixed` is the default and keeps prior
  behaviour.
- Units: `--units imperial` (F / mph / inches) for display; engine computation stays metric.
- Location: `--place "Name"` resolves a place name to coordinates via Open-Meteo's free geocoder.

## 0.8.0
- Security: untrusted-input validation (API responses + config files), private (0600) local database, SECURITY.md disclosure policy, and a data inventory in DATA_GOVERNANCE.md.
- Expanded to 11 modules: added cold_stress (livestock wind-chill + wet-coat) and
  wind_conditions (lodging / physical damage).
- soil_conditions extended with chemistry: pH, N, P, K, EC, organic matter (organic advice).
- marine_conditions extended with water chemistry: ammonia, nitrite, nitrate, pH, turbidity.
- Pluggable on-device camera detector seam (--scan-image / @detector); confident scans
  auto-log as sightings into the trust loop. No vision model bundled.
- New thresholds grounded in extension/peer sources; test suite reconciled and green (33 tests).
- Advisor multilingual seam: per-language model responses + UI message catalog (English + Dutch/Flemish), 14 languages registered. Suite now 36 tests.

## 0.7.0
- Calibration layer: all thresholds in CONFIG, overridable via --config JSON.
- livestock_thi module (Temperature-Humidity Index for animal heat stress).
- pollinators module (bee foraging / pollination windows).
- Test suite (unittest) covering all modules and the config layer.
- Config loader validates keys and warns on unknown module/threshold names.
- Live weather fetch surfaces the upstream API error message.
- Continuous-integration workflow runs the test suite on every push.
- Data-governance covenant (DATA_GOVERNANCE.md): local-first, never sold, opt-in sharing only.

## 0.6.0
- marine_conditions module: dissolved oxygen + algal-bloom / biotoxin risk (the sea).
- insect_pests module: degree-day pest phenology with organic IPM guidance.
- Sensor import extended to water columns.

## 0.5.0
- Multi-source sensing: derived leaf wetness; farmer soil/oxygen sensor import.
- soil_conditions module (waterlogging / drought / low oxygen).

## 0.4.0
- Ensemble + confidence in the blight model (Hutton + Smith).
- Confirmed-sightings trust loop and --accuracy calibration metric.
- Open export (JSON / CSV).

## 0.3.0
- SQLite storage and --history risk timeline.

## 0.2.0
- Refactored into an extensible engine: modules + severity/danger-zone report.

## 0.1.0
- Initial potato late-blight (Hutton Criteria) tool.
