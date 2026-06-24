# TerraWard — User Manual

A practical guide to running TerraWard on a real farm: what you need, which device, how to
start, how to automate it, and — most importantly — how to *test whether it is actually right
for your ground* before you trust it.

TerraWard is an early-warning advisor, not an oracle. It turns free weather data (and your own
sensors, if you have them) into grounded, organic-first warnings about disease, pests, frost,
heat, livestock stress, pollination, irrigation, manure timing and more. Everything it says is
traceable to a published threshold. Nothing is invented. But every farm has its own microclimate,
so the real work is validating it against *your* fields over a season. This manual shows you how.

---

## 1. What you need (the honest minimum)

- **A device that runs Python 3.8 or newer.** That's it. TerraWard is a single file with *zero*
  third-party dependencies — only the Python standard library.
- **An internet connection**, for live weather (it uses the free Open-Meteo API — no key, no
  account, no cost). Without internet you can still run `--demo` (offline, illustrative data), or
  swap in a local weather source later.
- **No sensors required.** Most modules run on weather alone. Soil and water sensors are optional
  and only feed the soil/aquaculture modules.
- **No payment, no sign-up, no cloud account.** The tool runs entirely on your own machine and
  your data never leaves it.

To check you have Python:
```bash
python3 --version
```
If that prints `Python 3.8` or higher, you are ready.

---

## 2. Which device?

Any of these work. Pick by how you want to use it.

### Your everyday computer (easiest start)
Mac, Windows, or Linux. You already have Python or can install it in minutes. Perfect for
learning the tool and for a season of morning checks. **Recommended for getting started and for
validation.**

### A Raspberry Pi (the "farm appliance")
The natural home for TerraWard once you trust it. A Pi:
- Costs roughly €50–80, sips power (run it off a phone charger), and sits silently in a shed or
  farmhouse.
- Runs headless on a schedule, emailing or saving you a fresh brief every morning.
- Handles TerraWard easily — because the tool is pure standard-library Python, even a **Pi Zero 2
  W** is more than enough; a Pi 3/4/5 is luxurious.

Setup is simple: flash **Raspberry Pi OS Lite** to an SD card, copy `terraward.py` onto it
(Python 3 is preinstalled), and schedule it with cron (see §7).

### An old laptop or mini-PC
A retired laptop makes a fine always-on farm server. Same idea as the Pi, more horsepower than you
need.

### Your phone (possible, not ideal)
TerraWard is a command-line tool, so a phone isn't its natural fit. If you want to: **Android** via
the *Termux* app (`pkg install python`, then run it); **iPhone** via *a-Shell* or *Pythonista*.
Fine for an occasional check, awkward for daily use.

**Internet note:** live weather needs a connection. A shed Pi needs Wi-Fi or a cheap LTE dongle. If
a field is truly offline, run the tool wherever you *do* have signal — it only needs the
coordinates, not to be physically on the land.

---

## 3. Five-minute first run

1. Put `terraward.py` (and the `examples/` folder) somewhere you can find it.
2. Open a terminal and go to that folder:
   ```bash
   cd ~/Downloads/terraward
   ```
   Confirm you're in the right place — this should print the filename, not an error:
   ```bash
   ls terraward.py
   ```
3. Run the offline demo to see what a full board looks like (no internet needed):
   ```bash
   python3 terraward.py --demo
   ```
4. Now a live run for your location — use your nearest town:
   ```bash
   python3 terraward.py --place "Meise"
   ```
5. And the version that fits on a phone screen at 6am — just what needs you in the next 48 hours:
   ```bash
   python3 terraward.py --place "Meise" --digest
   ```

That's the whole tool in five commands. Everything else is refinement.

> **Tip:** a new terminal window always starts in your home folder, so you'll `cd` into the
> project folder each session. If a command says "no such file," that's almost always why.

---

## 4. Daily use — the morning digest

The one command worth running every morning:
```bash
python3 terraward.py --place "Meise" --digest
```
It collapses the whole forecast into the handful of things that need you in the next 48 hours,
worst first. Read it with your coffee, act on what matters, get on with your day.

Useful additions:
- **Forward-only view** (drop the week of history): add `--past-days 0`.
- **Imperial units** (°F, mph, inches): add `--units imperial`.
- **Tell it what you grow/keep** so the right modules speak up:
  - `--pests colorado_potato_beetle` (or `codling_moth`, `cabbage_root_fly`, …)
  - `--livestock dairy_cattle` (or `sheep`, `pig`, `poultry`, …)
  - `--aquaculture trout` (or `salmon`, `carp`, `tilapia`, `shellfish`, …)
  - `--bees honeybee,bumblebee`
- **See every module and option:**
  ```bash
  python3 terraward.py --list-modules
  python3 terraward.py --help
  ```

When you want the *full* board instead of the digest, just drop `--digest`.

---

## 5. Your whole farm (multiple fields)

If you manage several plots, describe them once in a JSON file and see them all on one screen.
Copy `examples/sample_parcels.json` and edit it to your real fields:

```json
{
  "farm": "My Farm",
  "parcels": [
    { "name": "Home potatoes", "lat": 50.94, "lon": 4.33,
      "modules": ["late_blight", "insect_pests", "heat_stress", "evapotranspiration"],
      "pests": ["colorado_potato_beetle"] },
    { "name": "Hill orchard", "place": "Meise",
      "modules": ["scab_risk", "insect_pests", "pollinators"],
      "pests": ["codling_moth"] },
    { "name": "Trout pond", "lat": 51.20, "lon": 2.92,
      "modules": ["marine_conditions"], "aquaculture": ["trout"] }
  ]
}
```
Each parcel can declare what it **is** — its `modules` and its `pests`/`livestock`/`aquaculture`/
`bees` — so the orchard runs apple scab and the pond runs water chemistry, instead of every module
firing on every field. A parcel can be located by `lat`/`lon` or by a `place` name. Anything you
leave out inherits the global flags.

Then:
```bash
python3 terraward.py --parcels my_farm.json --digest
```
You get a roll-up: each parcel's worst concern in the next 48 hours, the worst field floated to the
top. Drop `--digest` to print every field's full board underneath.

---

## 6. Adding real sensors (optional)

If you have soil or water probes, TerraWard can read them — but only its soil and aquaculture
modules need them; everything else works on weather alone.

Feed readings as a CSV with a `date` column (matching the forecast dates) and any of the supported
fields. See `examples/sample_sensors.csv`. Supported columns:

- **Soil:** `soil_moisture` (%), `soil_oxygen` (%), `soil_temp_min` (°C), `soil_ph`, `soil_ec`
  (dS/m), `soil_nitrogen`, `soil_phosphorus`, `soil_potassium` (ppm), `soil_organic_matter` (%)
- **Water (aquaculture):** `dissolved_oxygen` (mg/L), `water_temp` (°C), `water_ph`, `salinity`,
  `water_ammonia`, `water_nitrite`, `water_nitrate`, `chlorophyll`, `water_turbidity`

```bash
python3 terraward.py --place "Meise" --sensor-csv my_readings.csv
```

How you fill that CSV is up to you: type in weekly probe readings by hand, export it from a
sensor logger, or have a small script append a row each day. Bad or non-numeric cells are skipped
with a warning, so a single typo won't break the run. (Units are read as given — keep them
consistent with the columns above.)

---

## 7. Running it automatically (the farm appliance)

To get a brief without remembering to ask, schedule it with **cron** (built into macOS, Linux and
Raspberry Pi OS). Edit your crontab:
```bash
crontab -e
```

**Email yourself a digest at 6am daily** (needs a configured `mail` command):
```cron
0 6 * * * cd /home/pi/terraward && /usr/bin/python3 terraward.py --place "Meise" --digest --save | mail -s "TerraWard brief" you@example.com
```

**Or write it to a file you check** (no mail setup needed):
```cron
0 6 * * * cd /home/pi/terraward && /usr/bin/python3 terraward.py --place "Meise" --digest > /home/pi/brief.txt 2>&1
```

The `--save` flag also records each day's warnings to a local history database (see §8), which is
what makes season-long validation possible. On a Pi in a shed, this is your whole deployment: flash
the card, copy the file, add the cron line, walk away.

---

## 8. The real test: validating on YOUR ground

**This is the most important section.** TerraWard's thresholds are sound in general, but your farm
has its own frost pockets, its own humidity, its own history. "Testing on real ground" means
finding out where the tool is right *for you* — and that takes a season, not an afternoon. Do it in
stages.

### Stage 1 — Shadow mode (don't act blindly)
For the first few weeks, run it daily and **compare its advice to your own judgement.** Don't follow
it blindly. Where does it agree with what you'd already do? Where does it differ, and who turns out
right? You're building a feel for its blind spots and its strengths. Keep running it with `--save`
so it quietly logs what it flagged:
```bash
python3 terraward.py --place "Meise" --save
```

### Stage 2 — Log what actually happened (the trust loop)
This is how you measure accuracy instead of guessing. When you observe a real outcome, record it:
```bash
# blight actually appeared on this date:
python3 terraward.py --report-sighting --date 2026-06-20 --observed confirmed --modules late_blight

# you scouted and there was nothing, despite a warning:
python3 terraward.py --report-sighting --date 2026-06-21 --observed clear --modules late_blight
```
Then ask the tool how it's doing against reality:
```bash
python3 terraward.py --accuracy
```
It reports **precision** (when it warned, how often was it right?) and **recall** (when something
happened, did it catch it?). Over a season these numbers tell you exactly how much to trust each
module on your land.

### Stage 3 — Calibrate to your microclimate
When the accuracy record shows a module is too jumpy or too quiet for your conditions, tune its
thresholds (see §9). Re-run, keep logging, watch precision/recall improve.

### Stage 4 — Graduate to trust
Once a module has earned a good track record on *your* fields, lean on it for real decisions. Keep
the others in shadow mode until they've earned the same.

> **The one-season test:** pick a single field and one or two risks you care about most (say, blight
> and irrigation). Run TerraWard daily with `--save`, log every outcome with `--report-sighting`, and
> at season's end read `--accuracy`. That number — measured on your own ground — is the honest answer
> to "does this work for me?"

---

## 9. Calibrating to your farm

Every threshold is adjustable without touching code. Put overrides in a JSON file and pass it with
`--config`. For example, if frost forms in your hollow before the air station reads freezing, raise
the frost trigger:

```json
{
  "frost_risk": { "frost": 1.0, "near_frost": 3.5 },
  "heat_stress": { "high": 28.0, "extreme": 33.0 }
}
```
```bash
python3 terraward.py --place "Meise" --config my_farm_config.json
```
Only include the keys you want to change; everything else keeps its grounded default. Unknown keys
and wrong types are warned about and ignored, so you can't silently break it. Let your `--accuracy`
record guide what to tune.

---

## 10. Testing options at a glance

| Option | What it is | What you need | Best for |
|---|---|---|---|
| **Manual daily** | Run `--digest` each morning | Any computer + internet | Getting started, learning the tool |
| **Forward digest** | `--digest --past-days 0` | Same | A clean "next 48h" with no history |
| **Whole-farm** | `--parcels farm.json` | A parcels file | Several fields on one screen |
| **With sensors** | `--sensor-csv readings.csv` | Soil/water probes + a CSV | Deeper soil & aquaculture insight |
| **Scheduled** | cron job on a Pi/PC | An always-on device | Hands-off daily briefs |
| **Validation** | `--save` + `--report-sighting` + `--accuracy` | A season of logging | Proving it works on *your* ground |
| **Offline demo** | `--demo` | Nothing (no internet) | Trying it, training, no signal |

You'll likely move down this list over time: start manual, add a farm file, schedule it on a Pi,
and run the validation loop underneath the whole time.

---

## 11. Troubleshooting

- **`command not found: terraward`** — run it as `python3 terraward.py ...` (with the `python3`
  prefix), from inside the project folder.
- **`No such file or directory: 'terraward.py'`** — you're not in the project folder. `cd` into it
  first (`cd ~/Downloads/terraward`), then `ls terraward.py` to confirm.
- **`Ran 0 tests`** — same cause: you're in the wrong folder. Tests only run from the folder that
  contains them.
- **Can't reach weather / network error** — check your connection, or use `--demo` for an offline
  run. The error message will say what failed.
- **`externally-managed-environment` when installing optional tools** — use a throwaway virtual
  environment: `python3 -m venv ~/venv && ~/venv/bin/pip install <tool>`. (You don't need to install
  anything to *run* TerraWard — only for optional extras like coverage.)
- **A sensor value looks ignored** — non-numeric or infinite cells are skipped with a warning on
  purpose; check that column for a typo.
- **Which version am I running?** — `python3 terraward.py --version`, or look at the banner: the
  `TERRAWARD vX.XX` line never lies about which build you're on.

---

## 12. Honest limits & safety

- **It is an advisor, not an oracle.** Treat it as a well-informed second opinion that you validate
  over time — never a replacement for your own eyes on the crop.
- **Day-resolution.** It reasons in daily steps, so "apply in the evening" is its safe default for
  spray timing rather than an exact hour.
- **Disease models flag conditions, not certainty.** A blight or scab warning means the weather
  favours infection — you judge the crop stage and scout to confirm.
- **It defers on the law and on food safety.** For manure closed-periods, nutrient caps, buffer
  distances, and especially **shellfish-biotoxin or other food-safety questions**, it points you to
  official monitoring and never gives an all-clear itself. Always check your nitrates authority,
  your certifier, and official safety bodies.
- **Organic by principle.** It will never recommend a synthetic pesticide or fungicide — only
  cultural and approved organic measures.
- **Your data is yours.** Everything runs locally; nothing is uploaded or sold. The history database
  is created private to your user account.

---

*TerraWard is free and open-source under the AGPL-3.0. Built to help, honest about its limits, and
yours to keep, run, and change. Put it on real ground, log what happens, and let it earn its trust
the only way that counts.*
