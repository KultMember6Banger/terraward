#!/usr/bin/env python3
# TerraWard -- a free, open, organic-first early-warning system for farmers.
# Copyright (C) 2026 the TerraWard contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
terraward.py -- the open, organic-first farm early-warning engine.

VERSION HISTORY:
  v0.1 blight.  v0.2 ENGINE.  v0.3 STORAGE.  v0.4 TRUST (ensemble + sightings).
  v0.5 multi-source sensing.  v0.6 LAND + SEA + PESTS.
  v0.7 CALIBRATION + LIVESTOCK + POLLINATORS.
  v0.8 DEEPER SENSING + DATA SOVEREIGNTY + CAMERA SEAM:
        * Soil chemistry: nitrogen, phosphorus (with runoff/eutrophication flag),
          potassium, pH, salinity (EC), organic matter.
        * Water chemistry: ammonia, nitrite, nitrate, pH, turbidity -- with the
          pH/temperature interaction that drives ammonia toxicity.
        * Wind: new free input (wind_speed_10m); drives cold-stress (wind chill),
          a wind/lodging module, and a wind cutoff for pollinator foraging.
        * Camera seam: --scan-image runs a pluggable on-device detector; a
          confident detection raises an alert AND auto-logs a sighting, feeding
          the same trust/calibration loop. No vision model is bundled (keeps the
          core dependency-free); a real model plugs in via @detector. See README.
        * Data sovereignty: the engine is local-first with no telemetry and no
          account. See DATA_POLICY.md. Your data is yours, never sold or shared
          with third parties; grower-to-grower sharing is opt-in only.
  v0.9 SPECIES PROFILES + UNITS + MANURE:
        * Species-aware livestock (--livestock), bees (--bees) and aquaculture
          (--aquaculture): per-species heat / cold / oxygen / ammonia thresholds.
        * Units: --units imperial (F/mph/inches); engine stays metric internally.
        * Location: --place "Name" resolves to coordinates (Open-Meteo geocoder).
        * New module manure_spreading: weather-and-ground spreading windows that
          defer closed periods and N/P caps to official sources, never faked.
  v0.10 CROP WATER:
        * New module evapotranspiration: reference ET0 (Hargreaves) + a rain/ET water
          balance that flags irrigation need -- and warns against over-watering, which
          leaches the same nitrates the manure and marine modules guard.
  v0.11 NAMED PESTS:
        * insect_pests is now per-named-pest with its own base temperature and life-stage
          degree-day thresholds (Colorado potato beetle, codling moth, cabbage root fly,
          European corn borer, generic), counted from an optional --biofix. Same weather,
          different insects, different correct timing -- organic control only.
  v0.12 TREATMENT WINDOWS:
        * New module treatment_window: when a pest module says 'treat now', this finds WHEN the
          weather allows an organic foliar treatment -- blocking on rain wash-off and wind drift,
          cautioning on heat for sulphur/oils, and steering application to the evening so foraging
          bees are protected (spinosad is bee-toxic until dry) and Bt survives UV.
  v0.13 DIGEST:
        * New --digest mode: a forward-looking lens that distils the full board down to what
          needs you in the next 48 hours, ranked by severity, hiding history and context. An
          overloaded heatwave week of 90+ lines collapses to a handful of action items.
  v0.14 DIGEST GROUPING:
        * --digest now collapses repeats of the same concern (e.g. three days of severe-heat
          livestock alerts) into one line with a "+N more through <date>" tail, so a multi-day
          heatwave reads as a few distinct concerns rather than a wall of near-identical lines.
  v0.15 APPLE SCAB:
        * New module scab_risk: a second disease brain. Apple-scab (Venturia inaequalis) primary-
          infection risk via the revised Mills criteria (MacHardy & Gadoury 1989) -- leaf wetness
          and average temperature graded to light/moderate/severe ascospore-infection periods. It
          reuses the same leaf-wetness signal as late_blight and points at organic protectant
          timing (sanitation first; sulphur/lime-sulphur only if on the leaf before the wetting).
  v0.16 WHOLE FARM + VISION ROUTE:
        * --parcels: a whole-farm view. Feed a JSON file of parcels (lat/lon or place) and get one
          combined board -- each parcel's worst next-48h concern rolled up, worst floated to the
          top; with --digest it's a one-screen farm brief, without it every parcel's full board
          follows. The leap from a field to a farm.
        * docs/VISION.md: an honest design + roadmap for the on-device vision layer (blight/scab
          lesions, pest ID, Varroa). The detector seam is wired; no model ships until field-
          validated -- a false 'all clear' is worse than no scan.
  v0.17 PER-PARCEL FARMS:
        * Parcels now declare what they ARE: each can set its own 'modules' and 'pests'/'livestock'/
          'aquaculture'/'bees', so an orchard runs scab + codling moth and a pond runs water
          chemistry, instead of every module firing everywhere. The farm roll-up now shows each
          parcel's own worst concern rather than the same region-wide weather alert on every line.
  v0.18 HARDENING + FORWARD WINDOWS:
        * Sensor CSV now skips non-numeric and non-finite (inf/nan) cells with a warning instead of
          aborting the run or poisoning a field (a nan would have silently disabled comparisons).
        * Opportunity finders (treatment_window, manure good-window) now look forward from today, so
          they stop reporting a window that is already in the past when history is included.
        * Renderers no longer crash on an empty window (defensive guard).

Adding a capability = write ONE function and tag it @module(...).
Action layer is ORGANIC: no synthetic-chemical recommendations, ever.
Live weather: Open-Meteo (free, no key). --demo runs fully offline.
Dependencies: NONE (Python 3 standard library only).
"""

from __future__ import annotations

import argparse
import csv
import enum
import json
import math
import os
import sqlite3
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Dict, List, Optional

# ============================================================================
# CONFIG  (every threshold; override per farm via --config FILE)
# ============================================================================

DEFAULT_CONFIG: Dict[str, dict] = {
    "late_blight": {"min_temp": 10.0, "hutton_humid_hours": 6, "smith_humid_hours": 11,
                    "leaf_wet_corroborate": 10},
    "scab_risk": {"upper_temp": 26.0},
    "downy_mildew": {"primary_temp": 10.0, "primary_rain": 10.0, "secondary_temp_min": 13.0,
                     "secondary_temp_max": 30.0, "secondary_wet_hours": 4.0},
    "frost_risk": {"hard_frost": -2.0, "frost": 0.0, "near_frost": 3.0},
    "heat_stress": {"extreme": 32.0, "high": 28.0},
    "cold_stress": {"livestock_severe": -15.0, "livestock_warning": -5.0,
                    "wet_precip": 1.0, "wet_warning": 12.0, "wet_severe": 2.0},
    "wind_conditions": {"gale": 62.0, "strong": 38.0},
    "livestock_thi": {"mild": 68.0, "moderate": 72.0, "severe": 80.0},
    "manure_spreading": {"rain_ahead": 10.0, "rain_ahead_heavy": 20.0, "good_ahead_max": 3.0,
                         "saturated_recent": 25.0, "frozen_min": 0.0, "uptake_temp": 6.0,
                         "ammonia_wind": 20.0, "sat_moisture": 80.0},
    "evapotranspiration": {"deficit_watch": 20.0, "deficit_warning": 35.0, "kc": 1.0},
    "treatment_window": {"rain_today": 1.0, "rain_next": 5.0, "wind_max": 20.0,
                         "heat_caution": 28.0},
    "pollinators": {"rain_mm": 1.0},  # temp/wind thresholds are per-species in POLLINATOR_PROFILES
    "soil_conditions": {"waterlogged": 50.0, "wet": 40.0, "severe_drought": 7.0,
                        "drought": 12.0, "low_o2": 8.0, "reduced_o2": 12.0,
                        "ph_acidic": 5.5, "ph_low": 6.0, "ph_high": 7.3, "ph_alkaline": 7.8,
                        "n_low": 10.0, "p_low": 20.0, "p_excess": 50.0, "k_low": 80.0,
                        "ec_high": 2.0, "ec_severe": 4.0, "om_low": 3.0,
                        "soil_frozen": 0.0, "soil_cold_sow": 5.0, "soil_warm_sow": 10.0},
    "insect_pests": {"base": 10.0,
                     "milestones": [[50, "early development"],
                                    [220, "likely egg hatch / first activity"],
                                    [450, "peak activity / next generation"]]},
    "growing_degree_days": {"base": 5.0},
    "marine_conditions": {"do_lethal": 2.0, "do_low": 4.0, "do_optimum": 5.0, "chl_severe": 10.0,
                          "chl_elevated": 3.0, "warm_water": 23.0,
                          "turnover_rain": 25.0, "turnover_temp_drop": 5.0,
                          "ammonia_warn": 0.25, "ammonia_danger": 1.0,
                          "nitrite_warn": 0.1, "nitrite_danger": 1.0,
                          "nitrate_watch": 50.0, "nitrate_high": 100.0,
                          "ph_low": 6.5, "ph_high": 9.0, "turbidity_high": 50.0},
    "camera": {"sighting_confidence": 0.6, "danger_confidence": 0.8, "warn_confidence": 0.5},
}

CONFIG: Dict[str, dict] = {k: dict(v) for k, v in DEFAULT_CONFIG.items()}


def load_config(path: str) -> None:
    """Merge a JSON file of threshold overrides into the active CONFIG.

    Unknown module names or threshold keys are reported on stderr rather than
    silently ignored, so a typo in your config never quietly disables a
    calibration you thought was active.
    """
    with open(path) as f:
        overrides = json.load(f)
    if not isinstance(overrides, dict):
        raise ValueError("config file must be a JSON object of {module: {threshold: value}}.")
    for mod, params in overrides.items():
        if mod not in DEFAULT_CONFIG:
            print(f"WARNING: config: unknown module '{mod}' ignored "
                  f"(known: {', '.join(sorted(DEFAULT_CONFIG))}).", file=sys.stderr)
            continue
        if not isinstance(params, dict):
            print(f"WARNING: config: '{mod}' must be an object of thresholds; ignored.",
                  file=sys.stderr)
            continue
        clean = {}
        for key, val in params.items():
            if key not in DEFAULT_CONFIG[mod]:
                print(f"WARNING: config: unknown key '{mod}.{key}' ignored "
                      f"(known: {', '.join(sorted(DEFAULT_CONFIG[mod]))}).", file=sys.stderr)
                continue
            dv = DEFAULT_CONFIG[mod][key]
            ok = (isinstance(val, bool) and isinstance(dv, bool)) or (
                isinstance(val, (int, float)) and not isinstance(val, bool)
                and isinstance(dv, (int, float)))
            if not ok:
                print(f"WARNING: config: '{mod}.{key}' should be {type(dv).__name__}, "
                      f"got {type(val).__name__}; ignored.", file=sys.stderr)
                continue
            clean[key] = val
        CONFIG[mod].update(clean)


# ============================================================================
# DATA LAYER
# ============================================================================

VERSION = "1.0"  # single source of truth for the runtime version (keep pyproject.toml in step)
__version__ = VERSION
DEFAULT_LAT, DEFAULT_LON, DEFAULT_NAME = 50.93, 4.33, "Meise"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

SENSOR_FIELDS = ("soil_moisture", "soil_oxygen", "soil_temp_min", "soil_nitrogen",
                 "soil_phosphorus", "soil_potassium", "soil_ph", "soil_ec",
                 "soil_organic_matter", "dissolved_oxygen", "chlorophyll", "water_temp",
                 "salinity", "water_ph", "water_ammonia", "water_nitrite",
                 "water_nitrate", "water_turbidity")


@dataclass
class DaySummary:
    date: str
    min_temp: float
    max_temp: float
    mean_temp: float
    humid_hours: int
    mean_rh: float = 0.0
    thi_max: Optional[float] = None  # daily-max THI from COINCIDENT hourly temp+RH (None if not from hourly data)
    precip_mm: float = 0.0
    leaf_wet_hours: int = 0
    # Longest CONTIGUOUS leaf-wet run (hours) tracked across midnight, so a wet spell spanning
    # calendar days isn't fragmented below disease thresholds. None when not built from hourly data.
    max_wet_run: Optional[int] = None
    max_wind: Optional[float] = None
    mean_wind: Optional[float] = None
    # soil sensors
    soil_moisture: Optional[float] = None
    soil_oxygen: Optional[float] = None
    soil_temp_min: Optional[float] = None
    soil_nitrogen: Optional[float] = None
    soil_phosphorus: Optional[float] = None
    soil_potassium: Optional[float] = None
    soil_ph: Optional[float] = None
    soil_ec: Optional[float] = None
    soil_organic_matter: Optional[float] = None
    # water sensors
    dissolved_oxygen: Optional[float] = None
    chlorophyll: Optional[float] = None
    water_temp: Optional[float] = None
    salinity: Optional[float] = None
    water_ph: Optional[float] = None
    water_ammonia: Optional[float] = None
    water_nitrite: Optional[float] = None
    water_nitrate: Optional[float] = None
    water_turbidity: Optional[float] = None


def _summarise(hourly: List[tuple]) -> List[DaySummary]:
    # Sort chronologically first so contiguous leaf-wetness runs can be tracked ACROSS calendar-day
    # boundaries -- a wet spell from late evening into the next morning is one infection event, not
    # two fragments. Without this, a 10h overnight wetting splits into (say) 4h + 6h and slips under
    # the scab/blight thresholds on both days, silently missing a real infection period.
    hourly = sorted(hourly, key=lambda x: x[0])
    run = 0
    run_at: List[int] = []
    for _t, _temp, rh, pr, _wind in hourly:
        run = run + 1 if (rh >= 90.0 or pr > 0.0) else 0
        run_at.append(run)  # length of the unbroken wet run ENDING at this hour
    by_day: Dict[str, List[tuple]] = defaultdict(list)
    for (t, temp, rh, pr, wind), wr in zip(hourly, run_at):
        by_day[t[:10]].append((temp, rh, pr, wind, wr))
    days: List[DaySummary] = []
    for d in sorted(by_day):
        rows = by_day[d]
        temps = [x[0] for x in rows]
        hums = [x[1] for x in rows]
        precs = [x[2] for x in rows]
        winds = [x[3] for x in rows if x[3] is not None]
        runs = [x[4] for x in rows]
        leaf_wet = sum(1 for rh, pr in zip(hums, precs) if rh >= 90.0 or pr > 0.0)
        days.append(DaySummary(d, min(temps), max(temps), sum(temps) / len(temps),
                               sum(1 for h in hums if h >= 90.0),
                               mean_rh=sum(hums) / len(hums),
                               thi_max=max((_thi(tp, rh) for tp, rh in zip(temps, hums)), default=None),
                               precip_mm=sum(precs), leaf_wet_hours=leaf_wet,
                               max_wet_run=(max(runs) if runs else 0),
                               max_wind=(max(winds) if winds else None),
                               mean_wind=(sum(winds) / len(winds) if winds else None)))
    return days


def _parse_weather_json(data) -> List[DaySummary]:
    """Validate and parse an Open-Meteo response, treating it as UNTRUSTED input.
    A wrong shape raises a clear error; an individual bad value is skipped rather
    than crashing the whole run."""
    if not isinstance(data, dict):
        raise RuntimeError("weather API: unexpected response (not a JSON object).")
    if data.get("error"):
        raise RuntimeError(str(data.get("reason", "weather API returned an error")))
    h = data.get("hourly")
    if not isinstance(h, dict):
        raise RuntimeError("weather API: response is missing the 'hourly' data block.")
    times = h.get("time")
    if not isinstance(times, list):
        raise RuntimeError("weather API: 'hourly.time' is missing or not a list.")
    arr = lambda k: h.get(k) if isinstance(h.get(k), list) else []
    temps, rhs, prs, winds = arr("temperature_2m"), arr("relative_humidity_2m"), \
        arr("precipitation"), arr("wind_speed_10m")
    rows = []
    for i, t in enumerate(times):
        if not isinstance(t, str):
            continue
        tp = temps[i] if i < len(temps) else None
        rh = rhs[i] if i < len(rhs) else None
        try:
            if tp is None or rh is None:
                continue
            row = (t, float(tp), float(rh),
                   float(prs[i]) if i < len(prs) and prs[i] is not None else 0.0,
                   float(winds[i]) if i < len(winds) and winds[i] is not None else None)
        except (TypeError, ValueError):
            continue  # skip a malformed hour, don't fail the whole fetch
        rows.append(row)
    if not rows:
        raise RuntimeError("No usable hourly data returned from the weather API.")
    return _summarise(rows)


def fetch_weather(lat, lon, past_days, forecast_days) -> List[DaySummary]:
    """SWAP POINT: replace with Agromet/CRA-W (land) or Copernicus Marine (sea)."""
    params = {"latitude": lat, "longitude": lon,
              "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
              "timezone": "auto", "past_days": past_days, "forecast_days": forecast_days}
    url = OPEN_METEO_URL + "?" + urllib.parse.urlencode(params)
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError("weather endpoint must be HTTPS.")  # refuse file:// or other schemes
    req = urllib.request.Request(url, headers={"User-Agent": f"terraward/{VERSION}"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 - https enforced above
        data = json.load(resp)
    return _parse_weather_json(data)


def apply_sensor_csv(days: List[DaySummary], path: str) -> int:
    readings: Dict[str, dict] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            d = (row.get("date") or "").strip()
            if d:
                readings[d] = row
    n = 0
    skipped: List[str] = []
    for day in days:
        r = readings.get(day.date)
        if not r:
            continue
        touched = False
        for field in SENSOR_FIELDS:
            val = (r.get(field) or "").strip()
            if not val:
                continue
            try:
                num = float(val)
            except ValueError:
                skipped.append(f"{day.date}/{field}='{val}'")
                continue
            if not math.isfinite(num):  # reject inf/nan -- nan silently disables every comparison
                skipped.append(f"{day.date}/{field}='{val}'")
                continue
            setattr(day, field, num)
            touched = True
        if touched:
            n += 1
    if skipped:
        shown = ", ".join(skipped[:5]) + ("..." if len(skipped) > 5 else "")
        print(f"WARNING: ignored {len(skipped)} non-numeric/invalid sensor value(s): {shown}",
              file=sys.stderr)
    return n


def _parse_geocode_json(data, place: str):
    """Validate a geocoding response (UNTRUSTED) and return (lat, lon, label)."""
    if not isinstance(data, dict):
        raise RuntimeError("geocoding: unexpected response (not a JSON object).")
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise RuntimeError(f"could not find a place called '{place}'. "
                           f"Try adding the country, e.g. '{place}, Belgium'.")
    top = results[0]
    if not isinstance(top, dict) or "latitude" not in top or "longitude" not in top:
        raise RuntimeError("geocoding: response missing coordinates.")
    try:
        lat, lon = float(top["latitude"]), float(top["longitude"])
    except (TypeError, ValueError):
        raise RuntimeError("geocoding: coordinates were not numbers.")
    parts = [top.get("name"), top.get("admin1"), top.get("country")]
    label = ", ".join(str(p) for p in parts if p)
    return lat, lon, (label or str(top.get("name") or place))


def geocode(place: str):
    """Resolve a place name to (lat, lon, label) via Open-Meteo's free geocoder.
    Treats the response as untrusted, exactly like the weather fetch."""
    params = {"name": place, "count": 1, "language": "en", "format": "json"}
    url = GEOCODE_URL + "?" + urllib.parse.urlencode(params)
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError("geocoding endpoint must be HTTPS.")
    req = urllib.request.Request(url, headers={"User-Agent": f"terraward/{VERSION}"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 - https enforced above
        data = json.load(resp)
    return _parse_geocode_json(data, place)


def demo_weather() -> List[DaySummary]:
    def synth(d, tmin, tmax, humid_hours, wind):
        rows = []
        for hr in range(24):
            temp = tmin if hr == 5 else (tmax if 13 <= hr <= 16 else (tmin + tmax) / 2)
            rh = 95.0 if hr < humid_hours else 65.0
            rows.append((f"{d}T{hr:02d}:00", float(temp), rh, 0.0, float(wind)))
        return rows
    pattern = [("2026-01-15", -8.0, -2.0, 2, 35.0), ("2026-04-10", 2.0, 12.0, 3, 65.0),
               ("2026-06-13", 12.5, 19.0, 7, 12.0), ("2026-06-14", 11.0, 18.0, 9, 10.0),
               ("2026-06-15", 14.0, 21.0, 5, 40.0), ("2026-06-18", 11.5, 20.0, 6, 15.0),
               ("2026-06-19", 12.0, 22.0, 12, 8.0), ("2026-06-20", 13.0, 24.0, 13, 10.0),
               ("2026-07-02", 17.0, 33.0, 1, 5.0)]
    rows = []
    for d, tmin, tmax, hh, wind in pattern:
        rows += synth(d, tmin, tmax, hh, wind)
    return _summarise(rows)


# ============================================================================
# ALERTS + MODULE REGISTRY
# ============================================================================

class Severity(enum.IntEnum):
    INFO = 0
    WATCH = 1
    WARNING = 2
    DANGER = 3


SEV_LABEL = {Severity.INFO: "INFO", Severity.WATCH: "WATCH",
             Severity.WARNING: "WARNING", Severity.DANGER: "DANGER"}


@dataclass
class Alert:
    module: str
    severity: Severity
    message: str
    date: Optional[str] = None
    confidence: Optional[str] = None


@dataclass
class ModuleSpec:
    key: str
    description: str
    fn: Callable[[List[DaySummary]], List[Alert]]


_REGISTRY: List[ModuleSpec] = []


def module(key, description):
    def deco(fn):
        _REGISTRY.append(ModuleSpec(key, description, fn))
        return fn
    return deco


def _thi(temp_c: float, rh_pct: float) -> float:
    """NRC Temperature-Humidity Index."""
    rh_pct = max(0.0, min(100.0, rh_pct))  # guard bad sensor data (RH must be 0-100, not a 0-1 fraction)
    return (1.8 * temp_c + 32) - (0.55 - 0.0055 * rh_pct) * (1.8 * temp_c - 26)


def _wind_chill(temp_c: float, wind_kmh: Optional[float]) -> float:
    """Environment Canada wind-chill 'feels like' (C). Only meaningful when cold
    and breezy; returns air temp otherwise."""
    if wind_kmh is None or wind_kmh < 5.0 or temp_c > 10.0:
        return temp_c
    v = wind_kmh ** 0.16
    return 13.12 + 0.6215 * temp_c - 11.37 * v + 0.3965 * temp_c * v


def _nh3_fraction(temp_c: float, ph: float) -> float:
    """Un-ionized ammonia (NH3) fraction of total ammonia (TAN), per Emerson et al. (1975).
    NH3 is the toxic form; its share of TAN rises ~10x per pH unit and with temperature."""
    pka = 0.09018 + 2729.92 / (temp_c + 273.15)
    return 1.0 / (1.0 + 10 ** (pka - ph))


def _wet_bulb(temp_c: float, rh_pct: float) -> float:
    """Wet-bulb temperature (C) from dry-bulb + RH, Stull (2011) empirical approximation.
    Valid ~ -20..50C, RH 5-99%; good to ~+/-1C at sea-level pressure. Stdlib-only (no psychro
    tables), which is why it is used here for the poultry heat index below."""
    rh = max(1.0, min(100.0, rh_pct))
    return (temp_c * math.atan(0.151977 * math.sqrt(rh + 8.313659))
            + math.atan(temp_c + rh) - math.atan(rh - 1.676331)
            + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh) - 4.686035)


def _poultry_thi(temp_c: float, rh_pct: float) -> float:
    """Poultry temperature-humidity index (degC scale): THI = 0.85*Tdb + 0.15*Twb (Tao & Xin
    2003 / broiler thermal-comfort form). This is a DIFFERENT scale from the cattle NRC THI in
    _thi() -- birds cannot sweat and the published thresholds are in degC, so the two indices
    must not be compared. Air velocity (which lowers effective load) is omitted, so still-air is
    assumed: the conservative, slightly over-warning direction for a free farmer tool."""
    return 0.85 * temp_c + 0.15 * _wet_bulb(temp_c, rh_pct)


def _do_saturation(temp_c: float, salinity_psu: Optional[float]) -> float:
    """Dissolved-oxygen solubility (mg/L) at 100% saturation for the given water temperature and
    salinity, via the Weiss (1970) equation (Benson & Krause coefficients). Warmer AND saltier
    water holds less oxygen, so the same mg/L reading sits closer to the lethal floor in a warm or
    brackish pond -- this lets a raw DO be read as a percent of what the water can actually hold."""
    s = max(0.0, salinity_psu or 0.0)
    tk = temp_c + 273.15
    ln_ml = (-173.4292 + 249.6339 * (100.0 / tk) + 143.3483 * math.log(tk / 100.0)
             - 21.8492 * (tk / 100.0)
             + s * (-0.033096 + 0.014259 * (tk / 100.0) - 0.0017000 * (tk / 100.0) ** 2))
    return math.exp(ln_ml) * 1.42905  # mL/L -> mg/L for O2


# ============================================================================
# CAMERA SEAM  (pluggable on-device detectors; no model bundled)
# ============================================================================

@dataclass
class Detection:
    label: str          # e.g. "late_blight" -- ideally matches a module key
    confidence: float   # 0.0 - 1.0
    note: str = ""


_DETECTORS: Dict[str, Callable[[str, Optional[str]], List[Detection]]] = {}


def detector(name):
    def deco(fn):
        _DETECTORS[name] = fn
        return fn
    return deco


@detector("placeholder")
def placeholder_detector(image_path: str, crop: Optional[str] = None) -> List[Detection]:
    """Default no-op detector. No vision model ships with TerraWard, so the core
    stays dependency-free and fully offline. To get real detection, register your
    own on-device model (e.g. a PlantVillage-trained TFLite/ONNX classifier) with
    @detector("mymodel") and select it via --detector mymodel. See README."""
    return [Detection("model_not_loaded", 0.0,
                      "Image received and validated, but no vision model is loaded. "
                      "Plug in an on-device detector (see README) to enable scanning.")]


def run_scan(image_path, crop, detector_fn, store, location) -> List[Alert]:
    """Run a detector over one image. A confident detection becomes an alert AND
    is auto-logged as a confirmed sighting, so the camera feeds the same trust/
    calibration loop as everything else."""
    c = CONFIG["camera"]
    today = date.today().isoformat()
    known = {s.key for s in _REGISTRY}
    alerts: List[Alert] = []
    for r in detector_fn(image_path, crop):
        if r.confidence <= 0.0:
            alerts.append(Alert("camera", Severity.INFO, r.note or f"No detection ({r.label})."))
            continue
        sev = (Severity.DANGER if r.confidence >= c["danger_confidence"]
               else Severity.WARNING if r.confidence >= c["warn_confidence"]
               else Severity.WATCH)
        extra = f" {r.note}" if r.note else ""
        alerts.append(Alert("camera", sev,
            f"Image scan: '{r.label}' detected (confidence {r.confidence:.0%}).{extra} "
            f"Organic response: confirm by scouting, isolate affected plants, improve "
            f"airflow, remove affected material.", date=today, confidence=f"{r.confidence:.0%}"))
        if store is not None and r.confidence >= c["sighting_confidence"] and r.label in known:
            store.save_sighting(location, today, r.label, "confirmed", note="camera scan")
    return alerts


# ============================================================================
# MODULES -- LAND
# ============================================================================

# ---- display units (all computation stays metric; only the *shown* values convert) ----
UNITS = "metric"   # "metric" (C, km/h, mm) or "imperial" (F, mph, in); set via --units


def _set_units(u):
    global UNITS
    UNITS = u if u in ("metric", "imperial") else "metric"


# ---- site latitude (set from --lat/--place); used by the evapotranspiration module ----
LATITUDE = DEFAULT_LAT


def _set_latitude(v):
    global LATITUDE
    try:
        LATITUDE = float(v)
    except (TypeError, ValueError):
        LATITUDE = DEFAULT_LAT


AS_OF = None  # YYYY-MM-DD "today"; when set, opportunity finders (treatment/manure) look forward


def _set_as_of(v):
    global AS_OF
    AS_OF = v if v else None


def T(c, prec=1):
    """Temperature for display."""
    return f"{c * 9 / 5 + 32:.{prec}f}F" if UNITS == "imperial" else f"{c:.{prec}f}C"


def W(kmh, prec=0):
    """Wind speed for display."""
    return f"{kmh * 0.621371:.{prec}f} mph" if UNITS == "imperial" else f"{kmh:.{prec}f} km/h"


def R(mm):
    """Rainfall for display."""
    return f"{mm / 25.4:.2f} in" if UNITS == "imperial" else f"{mm:.1f}mm"


def _dd(v):
    """Accumulated growing degree-days for display."""
    return f"{v * 1.8:.0f} degF-days" if UNITS == "imperial" else f"{v:.0f} degC-days"


def _ddn(v):
    """Degree-day total, number only (unit basis implied by the stated base temp)."""
    return f"{v * 1.8:.0f}" if UNITS == "imperial" else f"{v:.0f}"


@module("late_blight", "Potato late-blight forecast: ensemble of Hutton + Smith models")
def late_blight(days: List[DaySummary]) -> List[Alert]:
    c = CONFIG["late_blight"]
    hutton = [(d.min_temp >= c["min_temp"] and d.humid_hours >= c["hutton_humid_hours"]) for d in days]
    smith = [(d.min_temp >= c["min_temp"] and d.humid_hours >= c["smith_humid_hours"]) for d in days]
    alerts: List[Alert] = []
    for i, d in enumerate(days):
        if i > 0 and hutton[i] and hutton[i - 1]:
            conf = "HIGH" if (smith[i] and smith[i - 1]) else "MEDIUM"
            agree = "both models agree" if conf == "HIGH" else "sensitive model only"
            corrob = (f" Prolonged leaf wetness ({d.leaf_wet_hours}h) corroborates."
                      if d.leaf_wet_hours >= c["leaf_wet_corroborate"] else "")
            alerts.append(Alert("late_blight", Severity.DANGER,
                f"Hutton period ({days[i-1].date} + {d.date}): high late-blight "
                f"pressure ({agree}).{corrob} Organic: scout, improve airflow, "
                f"remove inoculum. No spray.", date=d.date, confidence=conf))
        elif hutton[i]:
            alerts.append(Alert("late_blight", Severity.WATCH,
                f"Conditions favourable to blight (min {T(d.min_temp)}, "
                f"{d.humid_hours}h >=90% RH).", date=d.date, confidence="LOW"))
    return alerts


# Revised Mills criteria (Mills 1944; MacHardy & Gadoury 1989), banded by average temperature
# during the wet period -> minimum continuous leaf-wetness hours for LIGHT / MODERATE / SEVERE(heavy)
# ascospore infection by Venturia inaequalis (light <10%, moderate 10-40%, heavy >40% foliage
# scabbed; Schwabe 1980). Light = minimum for any infection; severe = the wetness that drives a
# heavy lesion load. The COLD bands (0-13C) are finely split and set to the published Mills-Jones
# hour values (New England Tree Fruit Management Guide / netreefruit.org, reproducing MacHardy &
# Gadoury 1989): wetness requirements rise STEEPLY as temperature falls (light ~21h at 6C but ~48h
# near freezing), so the old single 0-6C band fit poorly -- too eager when cold, too slow at the
# warm edge. Still a daily-resolution simplification; the true model integrates hourly temperature
# over a rain-triggered wet period. Verified against the published table 2026-06-26.
SCAB_MILLS = [   # (temp_low, temp_high, light, moderate, severe) hours of leaf wetness
    (0.0,  2.5,  48.0, 72.0, 96.0),   # 32-36F: near-freezing, very long wetness needed (Mills-Jones)
    (2.5,  4.5,  33.0, 45.0, 60.0),   # ~37-40F
    (4.5,  6.0,  23.0, 33.0, 50.0),   # ~41-43F
    (6.0,  8.0,  17.0, 26.0, 40.0),   # ~43-46F
    (8.0,  10.0, 15.0, 20.0, 30.0),   # ~47-50F
    (10.0, 13.0, 12.0, 17.0, 25.0),   # ~50-55F
    (13.0, 16.0, 10.0, 14.0, 20.0),
    (16.0, 24.0,  9.0, 13.0, 18.0),   # optimum: shortest wetness needed (~9h light)
    (24.0, 26.0, 11.0, 16.0, 23.0),   # requirement climbs again at high temperature
]


def _scab_mills(temp, upper):
    """Return (light, moderate, severe) wetness-hour thresholds for the average wet-period
    temperature, or None outside the model's validated range (sub-zero, or at/above `upper`)."""
    if temp is None or temp >= upper:
        return None
    for lo, hi, light, mod, sev in SCAB_MILLS:
        if lo <= temp < hi:
            return (light, mod, sev)
    return None


@module("scab_risk", "Apple-scab infection forecast (revised Mills leaf-wetness model)")
def scab_risk(days: List[DaySummary]) -> List[Alert]:
    """Primary apple-scab (Venturia inaequalis) infection risk via the revised Mills criteria:
    from the hours of leaf wetness and the average temperature during the wet period, it flags
    light / moderate / severe ascospore-infection periods. Most relevant in the primary-scab
    season -- green-tip through early summer, while overwintered ascospores discharge on rain.
    Uses the same leaf-wetness signal as late_blight. The organic protectant (sulphur/lime-sulphur)
    must be on the leaf BEFORE the wet period, so pair this with treatment_window for timing. A
    daily-resolution approximation of an hourly model; thresholds banded from the published table."""
    c = CONFIG["scab_risk"]
    alerts: List[Alert] = []
    for d in days:
        # Mills needs CONTINUOUS wetness: prefer the cross-midnight contiguous run when we have
        # hourly data, falling back to the daily wet-hour count only for sensor/direct input.
        wet = (d.max_wet_run if d.max_wet_run is not None
               else (d.leaf_wet_hours if d.leaf_wet_hours is not None else 0))
        if wet <= 0:
            continue
        bands = _scab_mills(d.mean_temp, c["upper_temp"])
        if bands is None:
            continue
        light, mod, sev = bands
        if wet < light:
            continue
        conf = "MEDIUM" if 6.0 <= d.mean_temp < 24.0 else "LOW"
        if wet >= sev:
            level, sevr = "SEVERE", Severity.DANGER
        elif wet >= mod:
            level, sevr = "moderate", Severity.WARNING
        else:
            level, sevr = "light", Severity.WATCH
        alerts.append(Alert("scab_risk", sevr,
            f"{level} scab-infection period ({d.date}): {wet:.0f}h continuous leaf wetness at {T(d.mean_temp)} "
            f"avg meets the revised-Mills {level.lower()} threshold ({light:.0f}/{mod:.0f}/{sev:.0f}h "
            f"for light/moderate/severe). Organic: sanitation is the main lever -- shred or remove "
            f"fallen leaves to cut overwintering ascospores, prune and space for fast drying, grow "
            f"scab-resistant cultivars. Sulphur/lime-sulphur is the organic protectant, but only if "
            f"already on the leaf before this wetting -- see treatment_window for timing.",
            date=d.date, confidence=conf))
    return alerts


@module("downy_mildew", "Grapevine downy mildew (Plasmopara viticola): 3-10 primary + secondary risk")
def downy_mildew(days: List[DaySummary]) -> List[Alert]:
    """Grapevine downy mildew (Plasmopara viticola) risk at daily resolution.

    PRIMARY (oosporic) infection -- the classic Baldacci (1947) '3-10 rule': the season's first
    primary infection needs all three of mean temp >= 10C, >= 10mm rain (over ~24-48h), and shoots
    >= 10cm. We can see the two WEATHER conditions but not shoot length, so this fires as a WATCH
    and says so -- it only matters once spring shoots have reached ~10cm.

    SECONDARY infection -- once the disease is present, each wet, mild spell drives another cycle:
    sporangia form and zoospores infect green tissue above ~13C (optimum 18-25C, stops ~30C) given
    a leaf-wetness period (short when warm, longer when cool). Fires as a WARNING.

    Daily proxy for an hourly model (Blaeser & Weltzien 1979; Caffi et al. 2016; Brischetto et al.
    2021; OSU PLPATH-FRU-33). Organic-first advice: there is no organic cure once infected, so the
    levers are cultural -- open the canopy, remove leaves/laterals for airflow, avoid overhead/late
    irrigation that wets leaves, and grow resistant varieties; copper is the only organic protectant
    and must be on the leaf BEFORE the wet period (see treatment_window for timing)."""
    c = CONFIG["downy_mildew"]
    alerts: List[Alert] = []
    for d in days:
        wet = d.max_wet_run if d.max_wet_run is not None else (d.leaf_wet_hours or 0)
        # Secondary cycle: present disease + mild temperature + a leaf-wetness period.
        if (c["secondary_temp_min"] <= d.mean_temp <= c["secondary_temp_max"]
                and wet >= c["secondary_wet_hours"] and d.precip_mm > 0):
            conf = "MEDIUM" if 18.0 <= d.mean_temp <= 25.0 else "LOW"
            alerts.append(Alert("downy_mildew", Severity.WARNING,
                f"Downy mildew secondary-infection conditions ({d.date}): {wet:.0f}h leaf wetness at "
                f"{T(d.mean_temp)} (favourable 13-30C). If the disease is already in the block, this "
                f"drives a new cycle. Organic: open the canopy and remove leaves for airflow, stop "
                f"overhead/evening irrigation; copper only works if applied before the wetting.",
                date=d.date, confidence=conf))
        # Primary 3-10 rule: weather half (temp + rain); shoot length is the grower's to confirm.
        elif d.mean_temp >= c["primary_temp"] and d.precip_mm >= c["primary_rain"]:
            alerts.append(Alert("downy_mildew", Severity.WATCH,
                f"Downy mildew primary-infection weather ({d.date}): mean {T(d.mean_temp)} and "
                f"{R(d.precip_mm)} rain meet the 3-10 rule's weather part. Primary infection is "
                f"possible IF spring shoots have reached ~10cm. Organic: ready cultural controls "
                f"(canopy airflow, no overhead irrigation); pre-position copper if you use it.",
                date=d.date, confidence="LOW"))
    return alerts


@module("frost_risk", "Frost and cold-stress danger zones")
def frost_risk(days: List[DaySummary]) -> List[Alert]:
    c = CONFIG["frost_risk"]
    alerts: List[Alert] = []
    for d in days:
        if d.min_temp <= c["hard_frost"]:
            alerts.append(Alert("frost_risk", Severity.DANGER,
                f"HARD/killing frost ({T(d.min_temp)}): severe, even hardy crops at risk; protect everything.", date=d.date))
        elif d.min_temp <= c["frost"]:
            alerts.append(Alert("frost_risk", Severity.DANGER,
                f"Frost ({T(d.min_temp)}): protect tender crops/seedlings.", date=d.date))
        elif d.min_temp <= c["near_frost"]:
            alerts.append(Alert("frost_risk", Severity.WARNING,
                f"Near-frost ({T(d.min_temp)}): cover sensitive plants.", date=d.date))
    return alerts


@module("heat_stress", "Heat-stress danger zones for crops")
def heat_stress(days: List[DaySummary]) -> List[Alert]:
    c = CONFIG["heat_stress"]
    alerts: List[Alert] = []
    for d in days:
        if d.max_temp >= c["extreme"]:
            alerts.append(Alert("heat_stress", Severity.DANGER,
                f"Extreme heat ({T(d.max_temp)}): crop heat stress. Water, shade.", date=d.date))
        elif d.max_temp >= c["high"]:
            alerts.append(Alert("heat_stress", Severity.WARNING,
                f"High heat ({T(d.max_temp)}): monitor water needs.", date=d.date))
    return alerts


# Per-species livestock profiles: heat thresholds (mild/moderate/severe) and cold-stress
# 'feels-like' thresholds. Most species are graded on the NRC Temperature-Humidity Index (_thi):
# dairy cattle most heat-sensitive (lactation heat, onset ~68); beef and sheep/goats more
# tolerant. PIGS use the same NRC THI scale, but with the SWINE onset published by St-Pierre,
# Cobanov & Schnitkey (2003): growing-finishing hogs 72, sows 74 (the moderate/severe bands are
# interpolated, not published). POULTRY are different: birds cannot sweat and are graded on a
# degC-scale poultry index (_poultry_thi, scale="poultry"), NOT the cattle NRC scale -- onset
# ~28C (Tao & Xin 2003 broiler / Kim et al. 2020 layer). Mixing the two scales is the bug this
# fixes. For cold, full-fleece sheep are hardy while pigs/poultry are cold-sensitive. Shorn sheep
# and young stock are far more vulnerable to cold than these woolly-adult defaults. Calibratable.
LIVESTOCK_PROFILES = {
    "dairy_cattle": {"label": "dairy cattle", "mild": 68.0, "moderate": 72.0, "severe": 80.0,
                     "cold_warning": -5.0,  "cold_severe": -15.0},
    "beef_cattle":  {"label": "beef cattle",  "mild": 72.0, "moderate": 79.0, "severe": 84.0,
                     "cold_warning": -8.0,  "cold_severe": -18.0},
    "sheep":        {"label": "sheep",        "mild": 72.0, "moderate": 82.0, "severe": 88.0,
                     "cold_warning": -15.0, "cold_severe": -25.0},
    "goat":         {"label": "goats",        "mild": 70.0, "moderate": 80.0, "severe": 88.0,
                     "cold_warning": -3.0,  "cold_severe": -12.0},
    # Pigs: NRC THI scale, St-Pierre (2003) grow-finish hog onset 72 (mild); +4/+8 bands interpolated.
    "pig":          {"label": "pigs",         "mild": 72.0, "moderate": 76.0, "severe": 80.0,
                     "cold_warning": 2.0,   "cold_severe": -8.0},
    # Sows: more heat-tolerant per St-Pierre's index (onset 74); separate option for breeding herds.
    "sow":          {"label": "sows",         "mild": 74.0, "moderate": 78.0, "severe": 82.0,
                     "cold_warning": 0.0,   "cold_severe": -10.0},
    # Poultry: degC poultry-THI scale (NOT cattle NRC). Onset ~28C; mortality region ~32C+.
    "poultry":      {"label": "poultry",      "scale": "poultry",
                     "mild": 27.8, "moderate": 30.0, "severe": 32.0,
                     "cold_warning": 2.0,   "cold_severe": -6.0},
}
KEPT_LIVESTOCK = ["dairy_cattle"]   # which animals the grower keeps; set via --livestock


def _kept_livestock():
    for s in KEPT_LIVESTOCK:
        if s not in LIVESTOCK_PROFILES:
            print(f"WARNING: unknown livestock '{s}' ignored "
                  f"(known: {', '.join(sorted(LIVESTOCK_PROFILES))}).", file=sys.stderr)
    p = [LIVESTOCK_PROFILES[s] for s in KEPT_LIVESTOCK if s in LIVESTOCK_PROFILES]
    return p or [LIVESTOCK_PROFILES["dairy_cattle"]]


@module("cold_stress", "Cold stress for livestock via wind-chill 'feels-like', per kept species")
def cold_stress(days: List[DaySummary]) -> List[Alert]:
    """Wind makes cold far more dangerous, and a WET coat worse still (dry-coat lower critical
    temp ~ -7C, wet/soaked ~ +15C; US extension). Dry 'feels-like' thresholds are per kept
    species (LIVESTOCK_PROFILES: fleeced sheep hardy, pigs/poultry cold-sensitive); set with
    --livestock. Freshly shorn sheep and young stock are far more vulnerable than these defaults."""
    profiles = _kept_livestock()
    cw = CONFIG["cold_stress"]
    alerts: List[Alert] = []
    for d in days:
        eff = _wind_chill(d.min_temp, d.max_wind)
        wet = d.precip_mm is not None and d.precip_mm > cw["wet_precip"]
        windnote = (f" (air {T(d.min_temp)}, wind chill from {W(d.max_wind)})"
                    if d.max_wind and eff < d.min_temp - 0.5 else "")
        wetnote = " A wet coat sharply raises the danger." if wet else ""
        graded, worst = [], Severity.INFO
        for p in profiles:
            if eff <= p["cold_severe"] or (wet and eff <= cw["wet_severe"]):
                lvl, sev = "severe", Severity.DANGER
            elif eff <= p["cold_warning"] or (wet and d.min_temp <= cw["wet_warning"]):
                lvl, sev = "at risk", Severity.WARNING
            else:
                continue
            graded.append((p["label"], lvl))
            if sev > worst:
                worst = sev
        if not graded:
            continue
        parts = "; ".join(f"{lvl} for {label}" for label, lvl in graded)
        advice = ("Shelter, dry bedding, windbreak, extra energy feed, unfrozen water."
                  if worst >= Severity.DANGER else
                  "Ensure shelter and extra feed for vulnerable stock.")
        alerts.append(Alert("cold_stress", worst,
            f"Cold stress (feels {T(eff, 0)}){windnote}: {parts}.{wetnote} {advice}",
            date=d.date))
    return alerts


@module("wind_conditions", "High-wind lodging and physical-damage risk")
def wind_conditions(days: List[DaySummary]) -> List[Alert]:
    c = CONFIG["wind_conditions"]
    alerts: List[Alert] = []
    for d in days:
        if d.max_wind is None:
            continue
        if d.max_wind >= c["gale"]:
            alerts.append(Alert("wind_conditions", Severity.DANGER,
                f"Gale-force wind ({W(d.max_wind)}): crop lodging, structural and "
                f"polytunnel damage. Secure structures and equipment.", date=d.date))
        elif d.max_wind >= c["strong"]:
            alerts.append(Alert("wind_conditions", Severity.WARNING,
                f"Strong wind ({W(d.max_wind)}): lodging risk for tall crops; check "
                f"supports, covers and young trees.", date=d.date))
    return alerts


@module("livestock_thi", "Livestock heat stress via Temperature-Humidity Index, per kept species")
def livestock_thi(days: List[DaySummary]) -> List[Alert]:
    """Heat stress per kept species (LIVESTOCK_PROFILES), set with --livestock. Cattle, sheep,
    goats and pigs are graded on the NRC Temperature-Humidity Index (pigs use St-Pierre's 2003
    swine onsets on that same scale). Poultry are graded on a SEPARATE degC poultry index
    (_poultry_thi) because birds cannot sweat and their published thresholds are in degC -- the
    two indices are reported as distinct alerts and must not be compared."""
    profiles = _kept_livestock()
    # Poultry are graded on a degC poultry index, every other species on the NRC THI -- the two
    # scales are not comparable, so they are tracked and reported separately.
    thi_profiles = [p for p in profiles if p.get("scale") != "poultry"]
    poultry_profiles = [p for p in profiles if p.get("scale") == "poultry"]
    alerts: List[Alert] = []
    thi_streak = poultry_streak = 0  # consecutive days at moderate+ heat (no overnight recovery)
    for d in days:
        # NRC THI species (cattle, sheep, goats, pigs). Use the day's true peak coincident-hour
        # THI; fall back to (max_temp, mean_rh) only when hourly data isn't available.
        thi = d.thi_max if d.thi_max is not None else _thi(d.max_temp, d.mean_rh)
        graded, worst = [], Severity.INFO
        for p in thi_profiles:
            if thi >= p["severe"]:
                lvl, sev = "severe", Severity.DANGER
            elif thi >= p["moderate"]:
                lvl, sev = "moderate", Severity.WARNING
            elif thi >= p["mild"]:
                lvl, sev = "mild", Severity.WATCH
            else:
                continue
            graded.append((p["label"], lvl))
            if sev > worst:
                worst = sev
        if graded:
            thi_streak = thi_streak + 1 if worst >= Severity.WARNING else 0
            parts = "; ".join(f"{lvl} for {label}" for label, lvl in graded)
            advice = ("Provide shade, water, airflow; avoid handling; risk to yield and welfare."
                      if worst >= Severity.DANGER else
                      "Ensure water and shade; handle in cool hours."
                      if worst >= Severity.WARNING else "Watch vulnerable stock.")
            load = (f" Day {thi_streak} of sustained heat without a cool recovery day -- cumulative "
                    f"stress builds; prioritise overnight cooling." if thi_streak >= 3 else "")
            alerts.append(Alert("livestock_thi", worst,
                f"Heat stress (THI {thi:.0f}): {parts}. {advice}{load}", date=d.date))
        else:
            thi_streak = 0
        # Poultry on the degC poultry-THI scale (birds: no sweat glands, faster to die in heat).
        if poultry_profiles:
            pthi = _poultry_thi(d.max_temp, d.mean_rh)
            pg, pworst = [], Severity.INFO
            for p in poultry_profiles:
                if pthi >= p["severe"]:
                    lvl, sev = "severe", Severity.DANGER
                elif pthi >= p["moderate"]:
                    lvl, sev = "moderate", Severity.WARNING
                elif pthi >= p["mild"]:
                    lvl, sev = "mild", Severity.WATCH
                else:
                    continue
                pg.append((p["label"], lvl))
                if sev > pworst:
                    pworst = sev
            if pg:
                poultry_streak = poultry_streak + 1 if pworst >= Severity.WARNING else 0
                pparts = "; ".join(f"{lvl} for {label}" for label, lvl in pg)
                padvice = ("Max ventilation/air speed, cool water, do not crowd: heat kills birds "
                           "fast." if pworst >= Severity.DANGER else
                           "Add ventilation and cool water; watch for open-beak panting."
                           if pworst >= Severity.WARNING else "Watch birds for early panting.")
                pload = (f" Day {poultry_streak} of sustained heat -- an ACUTE spike on top of this "
                         f"is the deadliest case for poultry." if poultry_streak >= 3 else "")
                alerts.append(Alert("livestock_thi", pworst,
                    f"Poultry heat stress (poultry index {pthi:.0f}C): {pparts}. {padvice}{pload}",
                    date=d.date))
            else:
                poultry_streak = 0
    return alerts


# Per-species forage profiles. The grower picks which bees they keep (--bees); the module
# reports which can work each day. Grounded in extension/peer sources: honeybees forage from
# ~13C (full ~19C, decline >~32C, immobile <~7-10C); bumblebees are woolly and cold-tolerant,
# foraging from ~7-10C and in more wind; mason/solitary bees sit in between. Calibratable.
POLLINATOR_PROFILES = {
    "honeybee":  {"label": "honeybees",     "forage_min": 13.0, "good_temp": 19.0,
                  "hot_ceiling": 32.0, "wind_stop": 24.0},
    "bumblebee": {"label": "bumblebees",    "forage_min": 8.0,  "good_temp": 15.0,
                  "hot_ceiling": 32.0, "wind_stop": 32.0},
    "solitary":  {"label": "solitary bees", "forage_min": 11.0, "good_temp": 16.0,
                  "hot_ceiling": 32.0, "wind_stop": 26.0},
}
KEPT_POLLINATORS = ["honeybee"]   # which bees the grower keeps; set via --bees


@module("pollinators", "Bee foraging suitability, per kept species (poor pollination windows)")
def pollinators(days: List[DaySummary]) -> List[Alert]:
    """Per-species forage windows. Bumblebees work in cold/wind honeybees won't, so the module
    reports which of the grower's kept bees can forage each day. Thresholds are grounded
    defaults (POLLINATOR_PROFILES); kept species are chosen with --bees."""
    profiles = [POLLINATOR_PROFILES[s] for s in KEPT_POLLINATORS if s in POLLINATOR_PROFILES]
    if not profiles:
        profiles = [POLLINATOR_PROFILES["honeybee"]]
    rain_mm = CONFIG["pollinators"]["rain_mm"]
    alerts: List[Alert] = []
    for d in days:
        if d.precip_mm > rain_mm:
            alerts.append(Alert("pollinators", Severity.WARNING,
                f"Rain ({R(d.precip_mm)}) suppresses foraging: poor pollination window.",
                date=d.date))
            continue
        grounded = [p for p in profiles if d.max_temp < p["forage_min"]]
        active = [p for p in profiles if d.max_temp >= p["forage_min"]]
        if not active:                       # too cold for every kept bee
            alerts.append(Alert("pollinators", Severity.WARNING,
                f"Too cold for foraging (max {T(d.max_temp)}): no bee activity; poor "
                f"pollination.", date=d.date))
            continue
        if grounded:                         # some kept bees grounded, some still working
            g = ", ".join(p["label"] for p in grounded)
            a = ", ".join(p["label"] for p in active)
            alerts.append(Alert("pollinators", Severity.WATCH,
                f"Cool (max {T(d.max_temp)}): too cold for {g}, but {a} still foraging.",
                date=d.date))
            continue
        if d.max_wind is not None:
            wind_ok = [p for p in active if d.max_wind < p["wind_stop"]]
            wind_stopped = [p for p in active if d.max_wind >= p["wind_stop"]]
            if not wind_ok:                  # too windy for every active bee
                alerts.append(Alert("pollinators", Severity.WATCH,
                    f"Strong wind ({W(d.max_wind)}) limits foraging.", date=d.date))
                continue
            if wind_stopped:                 # some grounded by wind, hardier bees still fly
                ws = ", ".join(p["label"] for p in wind_stopped)
                wa = ", ".join(p["label"] for p in wind_ok)
                alerts.append(Alert("pollinators", Severity.WATCH,
                    f"Strong wind ({W(d.max_wind)}): too windy for {ws}, but {wa} still foraging.",
                    date=d.date))
                continue
        if all(d.max_temp < p["good_temp"] for p in active):
            alerts.append(Alert("pollinators", Severity.WATCH,
                f"Marginal foraging (max {T(d.max_temp)}): reduced bee activity.", date=d.date))
            continue
        if d.max_temp > max(p["hot_ceiling"] for p in active):
            alerts.append(Alert("pollinators", Severity.WATCH,
                f"Heat (max {T(d.max_temp)}) reduces midday foraging.", date=d.date))
            continue
        # Reaching here = a genuinely good window for every kept bee: warm enough, not too hot,
        # calm, dry. Surface it as INFO so growers can TIME pollination-critical work (orchard
        # bloom, caged/insect-pollinated crops), not just dodge the bad days.
        a = ", ".join(p["label"] for p in active)
        alerts.append(Alert("pollinators", Severity.INFO,
            f"Good foraging window (max {T(d.max_temp)}, calm, dry): {a} active -- favourable "
            f"for pollination-dependent bloom and open-flower field work.", date=d.date))
    return alerts


@module("soil_conditions", "Soil water, oxygen and chemistry (from field sensors)")
def soil_conditions(days: List[DaySummary]) -> List[Alert]:
    c = CONFIG["soil_conditions"]
    chem_fields = ("soil_moisture", "soil_oxygen", "soil_temp_min", "soil_nitrogen",
                   "soil_phosphorus", "soil_potassium", "soil_ph", "soil_ec",
                   "soil_organic_matter")
    alerts: List[Alert] = []
    latest = None
    for d in days:
        if all(getattr(d, a) is None for a in chem_fields):
            continue
        latest = d
        m = d.soil_moisture
        if m is not None:
            if m >= c["waterlogged"]:
                alerts.append(Alert("soil_conditions", Severity.DANGER,
                    f"Waterlogged soil ({m:.0f}% water): root anoxia/rot risk. Hold "
                    f"irrigation; improve drainage.", date=d.date))
            elif m >= c["wet"]:
                alerts.append(Alert("soil_conditions", Severity.WARNING,
                    f"Wet soil ({m:.0f}% water): poor aeration.", date=d.date))
            elif m <= c["severe_drought"]:
                alerts.append(Alert("soil_conditions", Severity.DANGER,
                    f"Severe drought ({m:.0f}% water): irrigate if able.", date=d.date))
            elif m <= c["drought"]:
                alerts.append(Alert("soil_conditions", Severity.WARNING,
                    f"Drought stress ({m:.0f}% water).", date=d.date))
        if d.soil_oxygen is not None:
            if d.soil_oxygen <= c["low_o2"]:
                alerts.append(Alert("soil_conditions", Severity.DANGER,
                    f"Low soil oxygen ({d.soil_oxygen:.0f}%): roots suffocating. Aerate.",
                    date=d.date))
            elif d.soil_oxygen <= c["reduced_o2"]:
                alerts.append(Alert("soil_conditions", Severity.WARNING,
                    f"Reduced soil oxygen ({d.soil_oxygen:.0f}%).", date=d.date))
        if d.soil_temp_min is not None:
            st = d.soil_temp_min
            if st <= c["soil_frozen"]:
                alerts.append(Alert("soil_conditions", Severity.DANGER,
                    f"Soil at/below freezing ({T(st)}): root-zone frost, no germination, frost-heave "
                    f"risk. Hold planting; mulch to insulate; protect shallow roots.", date=d.date))
            elif st < c["soil_cold_sow"]:
                alerts.append(Alert("soil_conditions", Severity.WATCH,
                    f"Cold soil ({T(st)}): too cold for most seed -- sowings will sit and rot rather "
                    f"than sprout. Wait for warmer soil before sowing.", date=d.date))
            elif st < c["soil_warm_sow"]:
                alerts.append(Alert("soil_conditions", Severity.INFO,
                    f"Soil {T(st)}: cool-season crops can be sown, but warm-season crops (maize, "
                    f"beans, squash, tomato) need soil >= {T(c['soil_warm_sow'])} to germinate well.",
                    date=d.date))
        if d.soil_ph is not None:
            if d.soil_ph < c["ph_acidic"]:
                alerts.append(Alert("soil_conditions", Severity.WARNING,
                    f"Acidic soil (pH {d.soil_ph:.1f}): locks up P, K, Ca, Mg. Organic: lime, "
                    f"wood ash, compost.", date=d.date))
            elif d.soil_ph > c["ph_alkaline"]:
                alerts.append(Alert("soil_conditions", Severity.WARNING,
                    f"Alkaline soil (pH {d.soil_ph:.1f}): locks up Fe, Mn, Zn. Organic: compost, "
                    f"elemental sulphur, acidifying mulches.", date=d.date))
            elif d.soil_ph < c["ph_low"] or d.soil_ph > c["ph_high"]:
                alerts.append(Alert("soil_conditions", Severity.WATCH,
                    f"Soil pH {d.soil_ph:.1f} drifting from the 6.0-7.3 sweet spot.", date=d.date))
        if d.soil_phosphorus is not None and d.soil_phosphorus > c["p_excess"]:
            alerts.append(Alert("soil_conditions", Severity.WARNING,
                f"Excess soil phosphorus ({d.soil_phosphorus:.0f} ppm): runoff drives algal "
                f"blooms downstream. Stop P/manure inputs; use cover crops and buffer strips.",
                date=d.date))
        elif d.soil_phosphorus is not None and d.soil_phosphorus < c["p_low"]:
            alerts.append(Alert("soil_conditions", Severity.WATCH,
                f"Low phosphorus ({d.soil_phosphorus:.0f} ppm). Organic: compost, manure, rock "
                f"phosphate, mycorrhizae.", date=d.date))
        if d.soil_potassium is not None and d.soil_potassium < c["k_low"]:
            alerts.append(Alert("soil_conditions", Severity.WATCH,
                f"Low potassium ({d.soil_potassium:.0f} ppm). Organic: compost, wood ash, "
                f"kelp, greensand.", date=d.date))
        if d.soil_nitrogen is not None and d.soil_nitrogen < c["n_low"]:
            alerts.append(Alert("soil_conditions", Severity.WATCH,
                f"Low nitrogen ({d.soil_nitrogen:.0f} ppm; note soil N tests are unreliable). "
                f"Organic: legumes/cover crops, compost, manure.", date=d.date))
        if d.soil_ec is not None:
            if d.soil_ec >= c["ec_severe"]:
                alerts.append(Alert("soil_conditions", Severity.DANGER,
                    f"Saline soil (EC {d.soil_ec:.1f} dS/m): osmotic stress, poor germination. "
                    f"Leach with clean water; improve drainage.", date=d.date))
            elif d.soil_ec >= c["ec_high"]:
                alerts.append(Alert("soil_conditions", Severity.WARNING,
                    f"Elevated salinity (EC {d.soil_ec:.1f} dS/m): sensitive crops affected.",
                    date=d.date))
        if d.soil_organic_matter is not None and d.soil_organic_matter < c["om_low"]:
            alerts.append(Alert("soil_conditions", Severity.WATCH,
                f"Low organic matter ({d.soil_organic_matter:.1f}%): build it with cover crops, "
                f"compost and reduced tillage -- the foundation of organic fertility.", date=d.date))
    if latest:
        parts = []
        for label, attr, unit in (("moisture", "soil_moisture", "%"), ("O2", "soil_oxygen", "%"),
                                  ("soil-temp-min", "soil_temp_min", "C"),
                                  ("pH", "soil_ph", ""), ("N", "soil_nitrogen", "ppm"),
                                  ("P", "soil_phosphorus", "ppm"), ("K", "soil_potassium", "ppm"),
                                  ("EC", "soil_ec", "dS/m"), ("OM", "soil_organic_matter", "%")):
            v = getattr(latest, attr)
            if v is not None:
                parts.append(f"{label} {v:g}{unit}")
        alerts.append(Alert("soil_conditions", Severity.INFO,
            f"Latest soil sensors ({latest.date}): {', '.join(parts)}."))
    return alerts


@module("manure_spreading", "Manure/slurry spreading windows from weather and ground state")
def manure_spreading(days: List[DaySummary]) -> List[Alert]:
    """Spreading is highly weather-dependent: nutrients run off into waterways when manure is
    applied to frozen, waterlogged or saturated ground, or before rain -- a near-universal rule
    across nitrate regulations. This module judges ONLY what weather and ground state can tell us
    (rain forecast within ~48h, recent rain as a saturation proxy, frost, and ammonia-loss
    conditions) and points to the legal calendar rather than faking it. It does NOT know closed
    periods, N/P application caps, buffer-zone distances, or organic raw-manure-to-harvest
    intervals; those vary by region and change, so confirm them with your nitrates authority and,
    if certified, your organic certifier. A soil-moisture sensor, if present, overrides the
    weather saturation proxy. All thresholds calibratable."""
    c = CONFIG["manure_spreading"]
    alerts: List[Alert] = []
    p = [d.precip_mm if d.precip_mm is not None else 0.0 for d in days]
    good_emitted = False
    for i, d in enumerate(days):
        ahead = sum(p[i:i + 3])            # this day + next ~48h of forecast
        recent = sum(p[max(0, i - 2):i])   # preceding forecast days -> saturation proxy
        sensor_wet = d.soil_moisture is not None and d.soil_moisture >= c["sat_moisture"]
        if d.min_temp <= c["frozen_min"]:
            alerts.append(Alert("manure_spreading", Severity.DANGER,
                f"Frozen/near-frozen ground (min {T(d.min_temp)}): manure runs off on thaw -- "
                f"do not spread.", date=d.date))
            continue
        if ahead >= c["rain_ahead_heavy"]:
            alerts.append(Alert("manure_spreading", Severity.DANGER,
                f"Heavy rain forecast within ~48h ({R(ahead)}): high runoff/leaching risk -- "
                f"do not spread.", date=d.date))
            continue
        if sensor_wet or recent >= c["saturated_recent"]:
            why = (f"soil moisture {d.soil_moisture:.0f}%" if sensor_wet
                   else f"{R(recent)} rain in prior days")
            alerts.append(Alert("manure_spreading", Severity.WARNING,
                f"Ground likely saturated ({why}): runoff risk -- hold until it drains.",
                date=d.date))
            continue
        if ahead >= c["rain_ahead"]:
            alerts.append(Alert("manure_spreading", Severity.WARNING,
                f"Rain forecast within ~48h ({R(ahead)}): runoff risk -- hold off spreading.",
                date=d.date))
            continue
        if (not good_emitted and ahead <= c["good_ahead_max"] and d.max_temp >= c["uptake_temp"]
                and (AS_OF is None or d.date >= AS_OF)):
            lossy = d.max_wind is not None and d.max_wind >= c["ammonia_wind"]
            ammonia = (" Warm and breezy -- inject or incorporate promptly to limit nitrogen "
                       "loss to air." if lossy else "")
            alerts.append(Alert("manure_spreading", Severity.INFO,
                f"Good spreading window ({d.date}): dry, no significant rain for ~48h, soil warm "
                f"enough for uptake.{ammonia} First confirm it is not a closed period and you are "
                f"within N/P limits -- check your nitrates authority and, if certified organic, "
                f"your certifier.", date=d.date))
            good_emitted = True
    return alerts


@module("treatment_window", "Organic foliar-treatment windows (rain wash-off, wind drift, bees)")
def treatment_window(days: List[DaySummary]) -> List[Alert]:
    """When a pest module says 'treat now', this says WHEN the weather lets you. An organic foliar
    treatment (Bt, spinosad, neem, sulphur, kaolin, compost tea) needs dry leaves to set, calm air
    to stay on target, and -- critically -- application when bees are not foraging: spinosad is
    toxic to bees until it dries. Blockers are rain wash-off and wind drift; heat is a caveat for
    sulphur/oils. This is day-resolution, so the safe default it gives is an evening application.
    It finds the next clear window and names what is blocking until then. All thresholds calibratable."""
    c = CONFIG["treatment_window"]
    alerts: List[Alert] = []
    fdays = [d for d in days if AS_OF is None or d.date >= AS_OF]  # look forward from "today"
    good = None
    blocked = []
    for i, d in enumerate(fdays):
        nxt = fdays[i + 1] if i + 1 < len(fdays) else None
        rain = d.precip_mm if d.precip_mm is not None else 0.0
        rain_next = nxt.precip_mm if nxt and nxt.precip_mm is not None else 0.0
        if rain > c["rain_today"] or rain_next > c["rain_next"]:
            blocked.append((d.date, f"rain will wash it off ({R(max(rain, rain_next))} due)"))
        elif d.max_wind is not None and d.max_wind > c["wind_max"]:
            blocked.append((d.date, f"too windy -- spray drift ({W(d.max_wind)})"))
        else:
            good = d
            break
    if good is not None:
        for date, why in blocked[:4]:
            alerts.append(Alert("treatment_window", Severity.WATCH,
                f"Hold treatment {date}: {why}.", date=date))
        heatnote = (" Skip sulphur and oils in the day's heat (leaf scorch); Bt/spinosad are fine."
                    if good.max_temp > c["heat_caution"] else "")
        alerts.append(Alert("treatment_window", Severity.INFO,
            f"Treatment window {good.date}: dry and calm enough to apply. Spray in the evening -- "
            f"bees are not foraging (spinosad is bee-toxic until dry) and Bt lasts longer out of "
            f"UV.{heatnote}", date=good.date))
    elif fdays:
        alerts.append(Alert("treatment_window", Severity.WARNING,
            "No clear treatment window in the forecast: rain or wind throughout. Wait for a calm, "
            "rain-free day and apply in the evening to protect bees."))
    return alerts


# Named degree-day pest models. Each insect develops on heat accumulated above ITS OWN base
# temperature, counted from a BIOFIX (a field event: first eggs, first sustained moth catch, or
# first spring flight). Milestones are DD in C above base from biofix, converted from published
# F-based extension models (Wisconsin, WSU, UC IPM, MOFGA). With --biofix set and enough history
# the readout tracks real life-stage timing; without it, named pests show a window-relative count.
# 'generic' reproduces the calibrate-it-yourself default. Organic throughout: control targets the
# vulnerable life stage, never a synthetic calendar spray.
PEST_PROFILES = {
    "generic": {"label": "generic pest", "base": 10.0,
        "milestones": [[50.0, "early development", "scout now"],
                       [220.0, "likely egg hatch / first activity", "scout; time biocontrol"],
                       [450.0, "peak activity / next generation", "expect peak; protect the crop"]],
        "organic": "encourage natural enemies (ladybirds, lacewings, parasitoids), resistant "
                   "varieties, timed biocontrol. Calibrate thresholds to your pest."},
    "colorado_potato_beetle": {"label": "Colorado potato beetle", "base": 10.0,
        "milestones": [[103.0, "egg hatch / 1st instar", "best organic control window opens"],
                       [133.0, "2nd-instar larvae", "treat small larvae now (Btt or spinosad)"],
                       [222.0, "4th instar (most feeding)", "large larvae resist control -- too late"],
                       [375.0, "pupation / summer adults", "next generation incoming"]],
        "organic": "Bt var. tenebrionis (Btt) or spinosad on 1st-2nd instars only; straw mulch, "
                   "crop rotation 200m+, plastic-lined trenches, hand-pick adults and egg masses."},
    "codling_moth": {"label": "codling moth", "base": 10.0,
        "milestones": [[139.0, "first egg hatch (1st gen)", "act now -- larvae bore into fruit fast"],
                       [364.0, "peak egg hatch", "peak risk; keep cover on"],
                       [511.0, "2nd-generation flight", "reset the watch for the next hatch"]],
        "organic": "pheromone mating disruption, codling moth granulosis virus (CpGV), kaolin "
                   "clay, sanitation of dropped fruit; target egg hatch, not adults."},
    "cabbage_root_fly": {"label": "cabbage root fly", "base": 6.0,
        "milestones": [[167.0, "1st-generation egg-laying", "protect transplants now: collars, mesh"],
                       [820.0, "2nd generation", "re-protect brassicas"],
                       [1473.0, "3rd generation", "late-season root risk"]],
        "organic": "brassica stem collars/discs, fleece or insect mesh from transplanting, firm "
                   "soil; there is no rescue once larvae are in the root."},
    "european_corn_borer": {"label": "European corn borer", "base": 10.0,
        "milestones": [[208.0, "first spring moths", "scout leaf undersides for egg masses"],
                       [250.0, "first eggs", "release Trichogramma; Bt (Btk) at egg hatch"]],
        "organic": "Trichogramma egg-parasitoid releases timed to egg-laying, Bt kurstaki on "
                   "young larvae before they bore in, shred and plough crop residue."},
}
KEPT_PESTS = ["generic"]   # which pests to model; set via --pests
BIOFIX = None              # YYYY-MM-DD start for DD accumulation; set via --biofix


def _kept_pests():
    p = [PEST_PROFILES[s] for s in KEPT_PESTS if s in PEST_PROFILES]
    return p or [PEST_PROFILES["generic"]]


def _set_biofix(v):
    global BIOFIX
    BIOFIX = v if v else None


@module("insect_pests", "Insect-pest phenology via degree-days, per named pest (--pests/--biofix)")
def insect_pests(days: List[DaySummary]) -> List[Alert]:
    """Degree-day phenology for the pests you select. Each accumulates heat above ITS OWN base
    temperature -- so the same weather advances codling moth and cabbage root fly differently --
    from a biofix if you set one. Milestones map to life stages; advice targets the vulnerable
    stage with organic methods only. Without --biofix, named pests show a window-relative count."""
    alerts: List[Alert] = []
    for p in _kept_pests():
        if BIOFIX:
            acc = [d for d in days if d.date >= BIOFIX]
            note = f" since biofix {BIOFIX}"
            short = bool(days) and (not acc or acc[0].date > BIOFIX)
        else:
            acc = days
            note = ("" if p["label"] == "generic pest"
                    else " (window total; set --biofix + --past-days for staging)")
            short = False
        total = sum(max(0.0, d.mean_temp - p["base"]) for d in acc)
        when = acc[-1].date if acc else (days[-1].date if days else None)
        reached = [m for m in p["milestones"] if total >= m[0]]
        if reached:
            _, stage, action = reached[-1]
            tail = " (history may not reach biofix; add --past-days)" if short else ""
            alerts.append(Alert("insect_pests", Severity.WATCH,
                f"{p['label']}: {_ddn(total)} DD (base {T(p['base'], 0)}){note} -> '{stage}'. "
                f"{action.capitalize()}.{tail} Organic: {p['organic']}", date=when))
        else:
            alerts.append(Alert("insect_pests", Severity.INFO,
                f"{p['label']}: {_ddn(total)} DD (base {T(p['base'], 0)}){note}; "
                f"below first milestone."))
    return alerts


@module("growing_degree_days", "GDD heat accumulation (crop suitability / timing)")
def growing_degree_days(days: List[DaySummary]) -> List[Alert]:
    base = CONFIG["growing_degree_days"]["base"]
    gdd = sum(max(0.0, d.mean_temp - base) for d in days)
    return [Alert("growing_degree_days", Severity.INFO,
                  f"GDD(base {T(base, 0)}) over {len(days)} days: {_dd(gdd)}.")]


# ============================================================================
# MODULES -- SEA
# ============================================================================

def _doy(date_str: str) -> int:
    return datetime.strptime(date_str, "%Y-%m-%d").timetuple().tm_yday


def _ra_mm(lat_deg: float, doy: int) -> float:
    """Extraterrestrial radiation (mm/day water-equivalent) per FAO-56 (Allen et al. 1998),
    from latitude and day-of-year. The arccos argument is clamped so polar day/night don't
    raise. The simple form is less accurate poleward of ~55-60 degrees."""
    phi = math.radians(lat_deg)
    b = 2 * math.pi * doy / 365.0
    dr = 1 + 0.033 * math.cos(b)              # inverse relative Earth-Sun distance
    decl = 0.409 * math.sin(b - 1.39)         # solar declination (rad)
    x = max(-1.0, min(1.0, -math.tan(phi) * math.tan(decl)))
    ws = math.acos(x)                         # sunset hour angle
    gsc = 0.0820                              # solar constant, MJ/m^2/min
    ra_mj = (24 * 60 / math.pi) * gsc * dr * (
        ws * math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.sin(ws))
    return max(0.0, ra_mj * 0.408)            # MJ/m^2/day -> mm/day equivalent


def _et0_hargreaves(tmin: float, tmax: float, lat_deg: float, doy: int) -> float:
    """Reference evapotranspiration (mm/day), Hargreaves 1982/1985: temperature-only, FAO's
    recommended fallback when solar/humidity/wind are unavailable. ET0 = 0.0023 * Ra *
    (Tmean + 17.8) * sqrt(Tmax - Tmin)."""
    tmean = (tmin + tmax) / 2.0
    tr = max(0.0, tmax - tmin)
    return max(0.0, 0.0023 * _ra_mm(lat_deg, doy) * (tmean + 17.8) * (tr ** 0.5))


@module("evapotranspiration", "Crop water demand & irrigation need (reference ET water balance)")
def evapotranspiration(days: List[DaySummary]) -> List[Alert]:
    """Estimates how much water crops are losing (reference ET0, Hargreaves) and runs a simple
    water balance: ET0 adds to the soil-water deficit, rain subtracts. When the deficit reaches
    the irrigation trigger, it flags a need to water -- and reminds you not to apply more than the
    deficit, since over-watering leaches the very nitrates the manure and marine modules guard.
    This is REFERENCE ET for a grass surface; multiply by a crop coefficient (Kc) for crop- and
    stage-specific need. A soil-moisture sensor, where present, is a more direct signal. All
    thresholds calibratable; uses site latitude (--lat/--place)."""
    c = CONFIG["evapotranspiration"]
    alerts: List[Alert] = []
    deficit = total_et = total_rain = 0.0
    state = "ok"
    kc = c["kc"]
    for d in days:
        et0 = _et0_hargreaves(d.min_temp, d.max_temp, LATITUDE, _doy(d.date))
        etc = et0 * kc  # crop water demand = reference ET0 x crop coefficient
        rain = d.precip_mm if d.precip_mm is not None else 0.0
        deficit = max(0.0, deficit + etc - rain)
        total_et += etc
        total_rain += rain
        if deficit >= c["deficit_warning"] and state != "warning":
            alerts.append(Alert("evapotranspiration", Severity.WARNING,
                f"Soil-water deficit ~{R(deficit)} by {d.date} (ET0 {R(et0)}/day): crops likely "
                f"stressing without water. Irrigate about {R(deficit)} -- and no more, or you "
                f"leach nutrients below the roots.", date=d.date))
            state = "warning"
        elif c["deficit_watch"] <= deficit < c["deficit_warning"] and state == "ok":
            alerts.append(Alert("evapotranspiration", Severity.WATCH,
                f"Soil-water deficit building (~{R(deficit)} by {d.date}, ET0 {R(et0)}/day): "
                f"plan to irrigate soon.", date=d.date))
            state = "watch"
        elif deficit < c["deficit_watch"] and state != "ok":
            if rain > etc:
                alerts.append(Alert("evapotranspiration", Severity.INFO,
                    f"Rain reset the water balance by {d.date} (deficit ~{R(deficit)}): hold "
                    f"irrigation.", date=d.date))
            state = "ok"
    if days:
        hint = (f"(crop Kc {kc:g} applied)" if kc != 1.0
                else "(multiply ET0 by crop Kc for crop-specific need)")
        label = "crop ET" if kc != 1.0 else "reference ET0"
        alerts.append(Alert("evapotranspiration", Severity.INFO,
            f"Crop water balance over {len(days)} days: {R(total_et)} {label} demand vs "
            f"{R(total_rain)} rain; net deficit ~{R(deficit)} {hint}."))
    return alerts


# Per-species aquaculture profiles. Three axes differ enormously by species: dissolved-oxygen
# need (cold-water salmonids want 6-8 mg/L; warm-water carp/tilapia tolerate 2-3), temperature
# tolerance (trout/salmon cold-water, tilapia/carp warm-water, bivalves heat-limited), and
# ammonia sensitivity (salmonids ~10x more sensitive than tilapia/carp). do_* in mg/L; temp
# bounds in C (None = not the limiting concern for that species); ammonia_* are practical TOTAL-
# ammonia thresholds (true toxicity also climbs with pH/temperature, flagged separately).
# 'mixed' reproduces the species-agnostic defaults. Grounded in extension/peer sources; all
# calibratable. Bivalve risk is dominated by biotoxins/blooms -- see the chlorophyll logic.
AQUACULTURE_PROFILES = {
    "mixed":     {"label": "mixed stock", "do_low": 4.0, "do_lethal": 2.0, "cold_stress": None,
                  "cold_lethal": None, "heat_stress": None, "heat_lethal": None,
                  "ammonia_warn": 0.25, "ammonia_danger": 1.0},
    "trout":     {"label": "trout", "do_low": 6.0, "do_lethal": 3.0, "cold_stress": None,
                  "cold_lethal": None, "heat_stress": 18.0, "heat_lethal": 24.0,
                  "ammonia_warn": 0.10, "ammonia_danger": 0.5},
    "salmon":    {"label": "salmon", "do_low": 6.0, "do_lethal": 3.0, "cold_stress": None,
                  "cold_lethal": None, "heat_stress": 18.0, "heat_lethal": 22.0,
                  "ammonia_warn": 0.10, "ammonia_danger": 0.5},
    "carp":      {"label": "carp", "do_low": 3.0, "do_lethal": 1.5, "cold_stress": None,
                  "cold_lethal": None, "heat_stress": 30.0, "heat_lethal": 36.0,
                  "ammonia_warn": 0.50, "ammonia_danger": 2.0},
    "tilapia":   {"label": "tilapia", "do_low": 3.0, "do_lethal": 1.5, "cold_stress": 15.0,
                  "cold_lethal": 11.0, "heat_stress": 35.0, "heat_lethal": 40.0,
                  "ammonia_warn": 0.50, "ammonia_danger": 2.0},
    "shellfish": {"label": "shellfish", "do_low": 3.0, "do_lethal": 1.0, "cold_stress": None,
                  "cold_lethal": None, "heat_stress": 22.0, "heat_lethal": 28.0,
                  "ammonia_warn": 0.50, "ammonia_danger": 2.0},
}
KEPT_AQUACULTURE = ["mixed"]   # which farmed species; set via --aquaculture


def _kept_aquaculture():
    for s in KEPT_AQUACULTURE:
        if s not in AQUACULTURE_PROFILES:
            print(f"WARNING: unknown aquaculture species '{s}' ignored — falling back to "
                  f"'mixed', which has NO temperature kill-limits "
                  f"(known: {', '.join(sorted(AQUACULTURE_PROFILES))}).", file=sys.stderr)
    p = [AQUACULTURE_PROFILES[s] for s in KEPT_AQUACULTURE if s in AQUACULTURE_PROFILES]
    return p or [AQUACULTURE_PROFILES["mixed"]]


@module("marine_conditions", "Aquaculture: oxygen, temperature, bloom, and chemistry, per species")
def marine_conditions(days: List[DaySummary]) -> List[Alert]:
    c = CONFIG["marine_conditions"]
    profiles = _kept_aquaculture()
    water_fields = ("dissolved_oxygen", "chlorophyll", "water_temp", "salinity",
                    "water_ph", "water_ammonia", "water_nitrite", "water_nitrate",
                    "water_turbidity")
    alerts: List[Alert] = []
    latest = None
    warm = False
    prev_air_mean = None  # prior processed day's mean air temp, for cold-front turnover detection
    for d in days:
        if all(getattr(d, a) is None for a in water_fields):
            continue
        latest = d
        warm = d.water_temp is not None and d.water_temp >= c["warm_water"]
        if d.dissolved_oxygen is not None:
            do = d.dissolved_oxygen
            opt = c["do_optimum"]
            graded, worst = [], Severity.INFO
            for p in profiles:
                if do < p["do_lethal"]:
                    lvl, sev = "lethal", Severity.DANGER
                elif do < p["do_low"]:
                    lvl, sev = "stress", Severity.WARNING
                elif do < opt and p["do_low"] < opt:
                    lvl, sev = "below optimum", Severity.WATCH
                else:
                    continue
                graded.append((p["label"], lvl))
                if sev > worst:
                    worst = sev
            if graded:
                parts = "; ".join(f"{lvl} for {label}" for label, lvl in graded)
                # Express the reading against what the water can actually hold (warmer/saltier
                # water holds less O2), and flag that DO bottoms out just before dawn.
                sat = _do_saturation(d.water_temp, d.salinity) if d.water_temp is not None else None
                satnote = f" -- {do / sat * 100:.0f}% of saturation" if sat and sat > 0 else ""
                advice = ("Aerate now; cut feeding/stocking; move stock if you can."
                          if worst >= Severity.DANGER else
                          "Check aeration, especially before dawn (DO bottoms out at first light).")
                alerts.append(Alert("marine_conditions", worst,
                    f"Low dissolved oxygen ({do:.1f} mg/L{satnote}): {parts}. {advice}", date=d.date))
        if d.water_ammonia is not None:
            am = d.water_ammonia  # total ammonia nitrogen (TAN), mg/L
            graded, worst = [], Severity.INFO
            if d.water_ph is not None and d.water_temp is not None:
                # Grade the TOXIC un-ionized form (NH3), not raw TAN. NH3's share of TAN
                # is pH- and temperature-driven (Emerson 1975); pH is the dominant lever,
                # so a high-pH pond is dangerous even at a modest total-ammonia reading.
                nh3 = am * _nh3_fraction(d.water_temp, d.water_ph)
                if nh3 >= 0.05:
                    graded, worst = [("stock", "toxic")], Severity.DANGER
                elif nh3 >= 0.02:
                    graded, worst = [("stock", "elevated")], Severity.WARNING
                detail = (f"NH3 {nh3:.3f} mg/L un-ionized (from {am:.2f} TAN at "
                          f"pH {d.water_ph:.1f}, {T(d.water_temp)})")
            else:
                # No pH/temp: fall back to coarse per-species total-ammonia thresholds.
                for p in profiles:
                    if am >= p["ammonia_danger"]:
                        lvl, sev = "toxic", Severity.DANGER
                    elif am >= p["ammonia_warn"]:
                        lvl, sev = "elevated", Severity.WARNING
                    else:
                        continue
                    graded.append((p["label"], lvl))
                    if sev > worst:
                        worst = sev
                detail = (f"total ammonia {am:.2f} mg/L (add pH + water_temp for true "
                          f"NH3 toxicity; using coarse TAN thresholds)")
            if graded:
                parts = "; ".join(f"{lvl} for {label}" for label, lvl in graded)
                advice = ("Stop feeding; water change; boost aeration and biofiltration."
                          if worst >= Severity.DANGER else "Reduce feeding; check biofilter.")
                alerts.append(Alert("marine_conditions", worst,
                    f"Ammonia: {detail}: {parts}. {advice}", date=d.date))
        if d.water_temp is not None:
            wt = d.water_temp
            graded, worst = [], Severity.INFO
            for p in profiles:
                if p["heat_lethal"] is not None and wt >= p["heat_lethal"]:
                    lvl, sev = "heat-lethal", Severity.DANGER
                elif p["cold_lethal"] is not None and wt <= p["cold_lethal"]:
                    lvl, sev = "cold-lethal", Severity.DANGER
                elif p["heat_stress"] is not None and wt >= p["heat_stress"]:
                    lvl, sev = "heat stress", Severity.WARNING
                elif p["cold_stress"] is not None and wt <= p["cold_stress"]:
                    lvl, sev = "cold stress", Severity.WARNING
                else:
                    continue
                graded.append((p["label"], lvl))
                if sev > worst:
                    worst = sev
            if graded:
                parts = "; ".join(f"{lvl} for {label}" for label, lvl in graded)
                alerts.append(Alert("marine_conditions", worst,
                    f"Water temperature {T(wt)}: {parts}. Adjust depth, shade, flow or stocking "
                    f"as feasible.", date=d.date))
        if d.water_nitrite is not None:
            if d.water_nitrite >= c["nitrite_danger"]:
                alerts.append(Alert("marine_conditions", Severity.DANGER,
                    f"Toxic nitrite ({d.water_nitrite:.2f} mg/L): blocks blood oxygen "
                    f"('brown blood'). Water change; support biofilter.", date=d.date))
            elif d.water_nitrite >= c["nitrite_warn"]:
                alerts.append(Alert("marine_conditions", Severity.WARNING,
                    f"Elevated nitrite ({d.water_nitrite:.2f} mg/L): biofilter not keeping up.",
                    date=d.date))
        if d.water_nitrate is not None:
            if d.water_nitrate >= c["nitrate_high"]:
                alerts.append(Alert("marine_conditions", Severity.WARNING,
                    f"High nitrate ({d.water_nitrate:.0f} mg/L): water change / denitrify; also "
                    f"fuels algal blooms downstream.", date=d.date))
            elif d.water_nitrate >= c["nitrate_watch"]:
                alerts.append(Alert("marine_conditions", Severity.WATCH,
                    f"Rising nitrate ({d.water_nitrate:.0f} mg/L): plan a water change.", date=d.date))
        if d.chlorophyll is not None:
            if d.chlorophyll > c["chl_severe"]:
                alerts.append(Alert("marine_conditions", Severity.DANGER,
                    f"Severe algal bloom (chl-a {d.chlorophyll:.0f} ug/L): oxygen-crash and "
                    f"biotoxin risk. Do NOT harvest shellfish; check official monitoring and "
                    f"test for biotoxins.", date=d.date))
            elif d.chlorophyll > c["chl_elevated"]:
                alerts.append(Alert("marine_conditions", Severity.WARNING,
                    f"Elevated bloom risk (chl-a {d.chlorophyll:.0f} ug/L): check official "
                    f"monitoring before any shellfish harvest.", date=d.date))
        if d.water_ph is not None and (d.water_ph < c["ph_low"] or d.water_ph > c["ph_high"]):
            alerts.append(Alert("marine_conditions", Severity.WARNING,
                f"Water pH {d.water_ph:.1f} outside safe band ({c['ph_low']:g}-{c['ph_high']:g}): "
                f"stresses stock and shifts ammonia toxicity.", date=d.date))
        if d.water_turbidity is not None and d.water_turbidity > c["turbidity_high"]:
            alerts.append(Alert("marine_conditions", Severity.WATCH,
                f"High turbidity ({d.water_turbidity:.0f} NTU): clogs gills, cuts light.", date=d.date))
        if warm:
            alerts.append(Alert("marine_conditions", Severity.WARNING,
                f"Warm water ({T(d.water_temp)}): lowers oxygen capacity and fuels blooms.",
                date=d.date))
        # Stratification turnover: a warm (stratified) pond that is suddenly mixed -- by heavy rain
        # and runoff or a cold front -- can flip oxygen-dead bottom water to the surface, crashing
        # whole-column DO and releasing H2S/ammonia. A classic, fast, whole-pond kill. Flag the
        # RISK from the trigger; a post-event DO reading is what confirms an actual crash.
        cold_front = (prev_air_mean is not None
                      and (prev_air_mean - d.mean_temp) >= c["turnover_temp_drop"])
        heavy_rain = d.precip_mm >= c["turnover_rain"]
        if warm and (heavy_rain or cold_front):
            trigger = "heavy rain and runoff" if heavy_rain else "a sharp drop in air temperature"
            alerts.append(Alert("marine_conditions", Severity.WARNING,
                f"Pond turnover risk ({d.date}): {trigger} on a warm, likely-stratified pond can "
                f"mix oxygen-dead bottom water up and crash dissolved oxygen pond-wide -- a sudden "
                f"kill risk. Run aerators, hold feeding, and check DO before dawn.", date=d.date))
        prev_air_mean = d.mean_temp
    if latest:
        parts = []
        for label, attr, unit in (("DO", "dissolved_oxygen", " mg/L"), ("chl-a", "chlorophyll", " ug/L"),
                                  ("water", "water_temp", "C"), ("pH", "water_ph", ""),
                                  ("NH3", "water_ammonia", " mg/L"), ("NO2", "water_nitrite", " mg/L"),
                                  ("NO3", "water_nitrate", " mg/L"), ("turb", "water_turbidity", " NTU"),
                                  ("salinity", "salinity", " PSU")):
            v = getattr(latest, attr)
            if v is not None:
                parts.append(f"{label} {v:g}{unit}")
        alerts.append(Alert("marine_conditions", Severity.INFO,
            f"Latest water sensors ({latest.date}): {', '.join(parts)}."))
    return alerts


# ============================================================================
# STORAGE / HISTORY / SIGHTINGS
# ============================================================================

class Storage:
    def __init__(self, path: str):
        self.path = path
        new = path != ":memory:" and not os.path.exists(path)
        with self._c() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS assessment (
                location TEXT, obs_date TEXT, module TEXT, severity INTEGER,
                confidence TEXT, message TEXT, recorded_at TEXT,
                PRIMARY KEY (location, obs_date, module))""")
            c.execute("""CREATE TABLE IF NOT EXISTS sighting (
                location TEXT, obs_date TEXT, module TEXT, observed TEXT,
                note TEXT, recorded_at TEXT,
                PRIMARY KEY (location, obs_date, module))""")
        if new and os.name == "posix":
            try:
                os.chmod(path, 0o600)  # the farm's data is private to its owner by default
            except OSError:
                pass

    def _c(self):
        return sqlite3.connect(self.path)

    def save(self, location, alerts) -> int:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows = [(location, a.date, a.module, int(a.severity), a.confidence, a.message, now)
                for a in alerts if a.date and a.severity >= Severity.WATCH]
        if rows:
            with self._c() as c:
                c.executemany("INSERT OR REPLACE INTO assessment VALUES (?,?,?,?,?,?,?)", rows)
        return len(rows)

    def timeline(self, location):
        with self._c() as c:
            return c.execute("SELECT obs_date, MAX(severity), GROUP_CONCAT(DISTINCT module) "
                             "FROM assessment WHERE location=? GROUP BY obs_date ORDER BY obs_date",
                             (location,)).fetchall()

    def save_sighting(self, location, obs_date, module, observed, note=""):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._c() as c:
            c.execute("INSERT OR REPLACE INTO sighting VALUES (?,?,?,?,?,?)",
                      (location, obs_date, module, observed, note, now))

    def sightings(self, location):
        with self._c() as c:
            return c.execute("SELECT obs_date, module, observed FROM sighting "
                             "WHERE location=? ORDER BY obs_date", (location,)).fetchall()

    def flagged(self, location):
        with self._c() as c:
            return {(r[0], r[1]) for r in c.execute(
                "SELECT obs_date, module FROM assessment WHERE location=? AND severity>=?",
                (location, int(Severity.WARNING)))}


def render_history(location, rows) -> str:
    out = ["=" * 70, f" RISK TIMELINE  --  {location}", "=" * 70]
    if not rows:
        return "\n".join(out + [" (no logged events -- run with --save first)", "=" * 70])
    out += [f"{'date':<12}{'overall':<10}modules", "-" * 70]
    for obs_date, sev, modules in rows:
        out.append(f"{obs_date:<12}{SEV_LABEL[Severity(sev)]:<10}{modules}")
    return "\n".join(out + ["-" * 70, f" {len(rows)} day(s) with events.", "=" * 70])


def render_accuracy(location, sightings, flagged) -> str:
    hits = false_alarms = misses = 0
    lines = []
    for obs_date, mod, observed in sightings:
        was = (obs_date, mod) in flagged
        if observed == "confirmed" and was:
            hits += 1; o = "HIT (flagged, confirmed)"
        elif observed == "confirmed":
            misses += 1; o = "MISS (not flagged, but occurred)"
        elif observed == "clear" and was:
            false_alarms += 1; o = "FALSE ALARM (flagged, nothing seen)"
        else:
            o = "true negative"
        lines.append(f"  {obs_date}  {mod:<18} {observed:<10} -> {o}")
    out = ["=" * 70, f" ACCURACY / CALIBRATION  --  {location}", "=" * 70]
    if not sightings:
        return "\n".join(out + [" No sightings yet (--report-sighting).", "=" * 70])
    prec = hits / (hits + false_alarms) if (hits + false_alarms) else None
    rec = hits / (hits + misses) if (hits + misses) else None
    out += lines + ["-" * 70, f" hits={hits}  false_alarms={false_alarms}  misses={misses}",
        f" precision: {f'{prec:.0%}' if prec is not None else 'n/a'}   "
        f"recall: {f'{rec:.0%}' if rec is not None else 'n/a'}"]
    if false_alarms:
        out.append(" -> false alarms: recalibrate thresholds locally (edit --config).")
    return "\n".join(out + ["=" * 70])


# ============================================================================
# ENGINE + REPORT + EXPORT
# ============================================================================

def run_modules(days, enabled) -> List[Alert]:
    alerts: List[Alert] = []
    for spec in _REGISTRY:
        if spec.key in enabled:
            alerts.extend(spec.fn(days))
    return alerts


def render_report(name, lat, lon, days, enabled, alerts, demo) -> str:
    if not days:
        return "\n".join(["=" * 70, " TERRAWARD -- no daily data to report", "=" * 70])
    today = date.today().isoformat()
    worst = max((a.severity for a in alerts), default=Severity.INFO)
    headline = {Severity.DANGER: "DANGER - action needed", Severity.WARNING: "WARNING - watch closely",
                Severity.WATCH: "WATCH - rising risk", Severity.INFO: "All clear"}[worst]
    out = ["=" * 70, f" TERRAWARD v{VERSION}" + ("   [DEMO - illustrative, NOT live]" if demo else ""),
           f" Location : {name}  ({lat}, {lon})",
           f" Window   : {days[0].date} -> {days[-1].date}   |  Generated: {today}",
           f" Modules  : {', '.join(enabled)}", "=" * 70, f" OVERALL: {headline}", "=" * 70]

    def section(title, sev):
        items = [a for a in alerts if a.severity == sev]
        if not items:
            return
        out.append("")
        out.append(f"[{title}]")
        for a in items:
            tag = f"({a.date}) " if a.date else ""
            conf = f" [conf: {a.confidence}]" if a.confidence else ""
            out.append(f"  - {tag}{a.module}: {a.message}{conf}")

    section("DANGER ZONE", Severity.DANGER)
    section("WARNINGS", Severity.WARNING)
    section("WATCH", Severity.WATCH)
    out += ["", "[MODULE STATUS]"]
    for spec in _REGISTRY:
        if spec.key not in enabled:
            continue
        n = sum(1 for a in alerts if a.module == spec.key and a.severity >= Severity.WATCH)
        out.append(f"  - {spec.key:<20} {f'{n} alert(s)' if n else 'clear'}")
    infos = [a for a in alerts if a.severity == Severity.INFO]
    if infos:
        out += ["", "[FIELD DATA & CALCULATIONS]"] + [f"  - {a.message}" for a in infos]
    return "\n".join(out + ["=" * 70])


def render_digest(name, lat, lon, days, enabled, alerts, demo) -> str:
    """A compact, forward-looking lens: what needs the farmer in the next 48 hours, ranked by
    severity. Unlike the full board it hides history and low-signal context, so an overloaded
    week collapses to a short action list. 'Now' is today for a live run; for --demo (illustrative
    dates) it anchors on the window start so the digest still shows something."""
    if not days:
        return "\n".join(["=" * 70, " TERRAWARD -- no daily data to report", "=" * 70])
    today_real = date.today().isoformat()
    ref = days[0].date if demo else today_real
    ref_d = date.fromisoformat(ref)
    horizon = date.fromordinal(ref_d.toordinal() + 2).isoformat()  # today + 48h, inclusive
    worst = max((a.severity for a in alerts), default=Severity.INFO)
    headline = {Severity.DANGER: "DANGER - action needed", Severity.WARNING: "WARNING - watch closely",
                Severity.WATCH: "WATCH - rising risk", Severity.INFO: "All clear"}[worst]
    out = ["=" * 70, f" TERRAWARD v{VERSION}  --  DIGEST" + ("   [DEMO - illustrative]" if demo else ""),
           f" Location : {name}  ({lat}, {lon})",
           f" Generated: {today_real}   |  Horizon: {ref} -> {horizon}  (next 48h)",
           "=" * 70, f" OVERALL: {headline}", "=" * 70, ""]
    inwin = [a for a in alerts if a.date and ref <= a.date <= horizon and a.severity >= Severity.WATCH]
    groups = {}  # collapse repeats of the same (module, severity) into one concern
    for a in sorted(inwin, key=lambda x: x.date):
        key = (a.module, a.severity)
        if key in groups:
            groups[key]["count"] += 1
            groups[key]["last"] = a.date
        else:
            groups[key] = {"rep": a, "count": 1, "last": a.date}
    reps = sorted(groups.values(), key=lambda g: (-int(g["rep"].severity), g["rep"].date))
    cap = 8
    if reps:
        out.append(f" NEXT 48 HOURS -- {len(reps)} concern(s) across {len(inwin)} alert(s):")
        for g in reps[:cap]:
            a = g["rep"]
            mark = ">>" if a.severity == Severity.DANGER else "  "
            conf = f" [conf: {a.confidence}]" if a.confidence else ""
            more = f"  (+{g['count'] - 1} more, through {g['last']})" if g["count"] > 1 else ""
            out.append(f" {mark} {SEV_LABEL[a.severity]:<7} {a.date}  {a.module}: {a.message}{conf}{more}")
        if len(reps) > cap:
            out.append(f"     ... and {len(reps) - cap} more concern(s) (full board has them all).")
    else:
        out.append(" NEXT 48 HOURS: nothing urgent -- a quiet window ahead.")
    later = sum(1 for a in alerts if a.date and a.date > horizon and a.severity >= Severity.WATCH)
    past = sum(1 for a in alerts if a.date and a.date < ref and a.severity >= Severity.WATCH)
    tail = []
    if later:
        tail.append(f"{later} further out in the window")
    if past:
        tail.append(f"{past} earlier than today")
    if tail:
        out += ["", f" (+{'; '.join(tail)} -- run without --digest for the full board.)"]
    return "\n".join(out + ["=" * 70])


def load_parcels(path):
    """Read a parcels file: {"farm": "...", "parcels": [...]}. Each parcel needs a 'name' and
    either 'lat'+'lon' or a 'place', and may optionally declare what it IS -- 'modules' to run and
    'pests'/'livestock'/'aquaculture'/'bees' profiles -- so an orchard runs scab and an apple pest
    while a pond runs water chemistry, instead of every module firing on every parcel. Anything
    omitted inherits the global flags. Validated like any untrusted input: structure, types,
    coordinate ranges, and every named module/profile must exist."""
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("parcels"), list) or not data["parcels"]:
        raise ValueError("parcels file needs a non-empty 'parcels' list")
    farm = str(data.get("farm", "Farm"))
    mod_keys = {s.key for s in _REGISTRY}
    opt_profiles = {"pests": PEST_PROFILES, "livestock": LIVESTOCK_PROFILES,
                    "aquaculture": AQUACULTURE_PROFILES, "bees": POLLINATOR_PROFILES}
    out = []
    for i, pc in enumerate(data["parcels"]):
        if not isinstance(pc, dict) or "name" not in pc:
            raise ValueError(f"parcel #{i + 1} needs a 'name'")
        name = str(pc["name"])
        entry = {"name": name}
        if pc.get("place"):
            entry["place"] = str(pc["place"])
        else:
            try:
                lat, lon = float(pc["lat"]), float(pc["lon"])
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"parcel '{name}' needs numeric lat+lon (or a 'place')")
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                raise ValueError(f"parcel '{name}' lat/lon out of range")
            entry["lat"], entry["lon"] = lat, lon
        if "modules" in pc:
            mods = pc["modules"]
            if not isinstance(mods, list) or not all(isinstance(m, str) for m in mods):
                raise ValueError(f"parcel '{name}': 'modules' must be a list of names")
            bad = [m for m in mods if m not in mod_keys]
            if bad:
                raise ValueError(f"parcel '{name}': unknown module(s): {', '.join(bad)}")
            entry["modules"] = mods
        for key, profiles in opt_profiles.items():
            if key in pc:
                sel = pc[key]
                if not isinstance(sel, list) or not all(isinstance(x, str) for x in sel):
                    raise ValueError(f"parcel '{name}': '{key}' must be a list of names")
                bad = [x for x in sel if x not in profiles]
                if bad:
                    raise ValueError(f"parcel '{name}': unknown {key}: {', '.join(bad)}")
                entry[key] = sel
        out.append(entry)
    return farm, out


def _next48(days, alerts, demo):
    """The next-48h window (ref date, horizon date, in-window WATCH+ alerts). Shared by the single
    digest and the farm roll-up so both define 'now' the same way (today live, window-start in demo)."""
    ref = days[0].date if demo else date.today().isoformat()
    horizon = date.fromordinal(date.fromisoformat(ref).toordinal() + 2).isoformat()
    inwin = [a for a in alerts if a.date and ref <= a.date <= horizon and a.severity >= Severity.WATCH]
    return ref, horizon, inwin


def render_farm(farm, results, demo, digest) -> str:
    """One combined view across parcels. Always shows a farm-wide roll-up: per parcel, its worst
    next-48h severity, how many concerns, and the single most urgent one. With --digest that roll-up
    is the whole output; without it, each parcel's full board follows (using that parcel's own
    module set) so nothing is lost. Each result is (name, lat, lon, days, alerts, enabled)."""
    today_real = date.today().isoformat()
    worst_all = max((a.severity for _, _, _, _, al, _ in results for a in al), default=Severity.INFO)
    headline = {Severity.DANGER: "DANGER - action needed", Severity.WARNING: "WARNING - watch closely",
                Severity.WATCH: "WATCH - rising risk", Severity.INFO: "All clear"}[worst_all]
    out = ["=" * 70, f" TERRAWARD v{VERSION}  --  FARM" + ("   [DEMO - illustrative]" if demo else ""),
           f" Farm     : {farm}  ({len(results)} parcel{'s' if len(results) != 1 else ''})",
           f" Generated: {today_real}", "=" * 70, f" OVERALL: {headline}", "=" * 70, "",
           " PARCELS (worst in the next 48h):"]
    for name, lat, lon, days, alerts, _en in results:
        _ref, _hz, inwin = _next48(days, alerts, demo)
        pworst = max((a.severity for a in inwin), default=Severity.INFO)
        label = SEV_LABEL[pworst] if inwin else "clear"
        mark = ">>" if pworst == Severity.DANGER else "  "
        out.append(f" {mark} {name:<18} {label:<7} {len(inwin)} concern(s)")
        top = sorted(inwin, key=lambda a: (-int(a.severity), a.date))[:1]
        if top:
            t = top[0]
            out.append(f"        -> {t.module}: {t.message.split('. ')[0].rstrip('.')}.")
    if not digest:
        for name, lat, lon, days, alerts, en in results:
            out += ["", render_report(name, lat, lon, days, en, alerts, demo)]
        return "\n".join(out)
    return "\n".join(out + ["=" * 70])


def export_results(path, fmt, name, lat, lon, days, alerts) -> None:
    records = [{"date": a.date, "module": a.module, "severity": SEV_LABEL[a.severity],
                "confidence": a.confidence, "message": a.message} for a in alerts]
    if fmt == "json":
        with open(path, "w") as f:
            json.dump({"location": name, "lat": lat, "lon": lon,
                       "window": [days[0].date, days[-1].date],
                       "generated": date.today().isoformat(), "alerts": records}, f, indent=2)
    else:
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["date", "module", "severity", "confidence", "message"])
            w.writeheader(); w.writerows(records)


# ============================================================================
# CLI
# ============================================================================

ADVISOR_NAME = "Hayward"  # the AI advisor's name (set once chosen); shown in the opening scene

_SCENE = r"""
======================================================================

                      \     |     /
                       \    |    /              .  .  .
                        \   |   /
            - - - - - - - ( o ) - - - - - - -
                        /   |   \
                       /    |    \
                      /     |     \

        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        / / / / / / / / / / / / / / / / / / / / / / / / / / /
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

             T E R R A W A R D
             the land and the water, watched over
__NAME__
             free  .  organic  .  open  .  yours
======================================================================
"""


def splash() -> str:
    """The opening scene shown on startup (python3 terraward.py --splash)."""
    name_line = (f"             meet {ADVISOR_NAME}, your on-device advisor"
                 if ADVISOR_NAME else "             your honest, on-device advisor")
    return _SCENE.replace("__NAME__", name_line)


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="terraward.py",
        description="TerraWard -- an open, organic-first farm early-warning engine. Turns free "
                    "weather data into grounded warnings about disease, pests, frost, heat, livestock "
                    "stress, pollination, irrigation and more. It never recommends synthetic sprays.",
        epilog="examples:\n"
               "  python3 terraward.py --place \"Meise\" --digest\n"
               "      today's 48-hour action list for one location\n"
               "  python3 terraward.py --place \"Meise\" --pests colorado_potato_beetle --livestock sheep\n"
               "      tailor the warnings to what you grow and keep\n"
               "  python3 terraward.py --parcels farm.json --digest --save\n"
               "      whole-farm view, logging each field for season-long validation\n"
               "  python3 terraward.py --demo\n"
               "      offline illustrative run -- no internet needed\n\n"
               "full guide: see USER_MANUAL.md. Free software under AGPL-3.0.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    loc = p.add_argument_group("location")
    loc.add_argument("--place", type=str, default=None,
                     help='find by place name instead of coordinates, e.g. --place "Meise"')
    loc.add_argument("--lat", type=float, default=DEFAULT_LAT, help="latitude (default: %(default)s)")
    loc.add_argument("--lon", type=float, default=DEFAULT_LON, help="longitude (default: %(default)s)")
    loc.add_argument("--name", type=str, default=DEFAULT_NAME,
                     help="label for this location (default: %(default)s)")
    farm = p.add_argument_group("what you farm (so the right modules speak up)")
    farm.add_argument("--pests", type=str, default="generic",
                      help="pests to model (comma list): " + ", ".join(PEST_PROFILES))
    farm.add_argument("--livestock", type=str, default="dairy_cattle",
                      help="animals you keep (comma list): " + ", ".join(LIVESTOCK_PROFILES))
    farm.add_argument("--aquaculture", type=str, default="mixed",
                      help="farmed aquatic species (comma list): " + ", ".join(AQUACULTURE_PROFILES))
    farm.add_argument("--bees", type=str, default="honeybee",
                      help="bees you keep (comma list): " + ", ".join(POLLINATOR_PROFILES))
    farm.add_argument("--biofix", type=str, default=None,
                      help="degree-day start date YYYY-MM-DD (e.g. first moth catch / first eggs)")
    view = p.add_argument_group("view & data")
    view.add_argument("--digest", action="store_true",
                      help="compact next-48h action view instead of the full board")
    view.add_argument("--parcels", type=str, default=None,
                      help="JSON file of parcels for a whole-farm combined view (see examples/)")
    view.add_argument("--units", choices=["metric", "imperial"], default="metric",
                      help="display units (metric=C/km/h/mm, imperial=F/mph/in)")
    view.add_argument("--past-days", type=int, default=7,
                      help="days of history to include (default: %(default)s)")
    view.add_argument("--forecast-days", type=int, default=7,
                      help="days of forecast to include (default: %(default)s)")
    view.add_argument("--sensor-csv", type=str, default=None,
                      help="CSV of soil/water sensor readings to merge in (see examples/)")
    view.add_argument("--config", type=str, default=None,
                      help="JSON file of threshold overrides, to calibrate to your farm")
    view.add_argument("--demo", action="store_true",
                      help="run offline with illustrative data (no internet)")
    view.add_argument("--modules", type=str, default=None,
                      help="comma list of only the modules to run (default: all)")
    view.add_argument("--list-modules", action="store_true",
                      help="list every available module and exit")
    view.add_argument("--splash", action="store_true", help="show the opening scene and exit")
    p.add_argument("--version", action="version", version="TerraWard " + VERSION,
                   help="show the version and exit")
    hist = p.add_argument_group("history & validation (the trust loop)")
    hist.add_argument("--save", action="store_true",
                      help="log this run's warnings to the history database")
    hist.add_argument("--history", action="store_true",
                      help="show the saved history for this location and exit")
    hist.add_argument("--report-sighting", action="store_true",
                      help="record what you actually observed (use with --date and --observed)")
    hist.add_argument("--date", type=str, help="date of the observation, YYYY-MM-DD")
    hist.add_argument("--observed", choices=["confirmed", "clear"],
                      help="what you saw: 'confirmed' (it happened) or 'clear' (nothing)")
    hist.add_argument("--note", type=str, default="", help="optional note to store with a sighting")
    hist.add_argument("--accuracy", action="store_true",
                      help="score saved warnings against your sightings (precision/recall) and exit")
    hist.add_argument("--db", type=str, default="terraward_history.db",
                      help="history database file (default: %(default)s)")
    hist.add_argument("--export", choices=["json", "csv"], default=None,
                      help="also export this run's results to a file")
    hist.add_argument("--out", type=str, default=None, help="output path for --export")
    scan = p.add_argument_group("experimental image scan (no model ships -- see docs/VISION.md)")
    scan.add_argument("--scan-image", type=str, default=None, help="image file to scan with a detector")
    scan.add_argument("--scan-crop", type=str, default=None, help="optional crop context for the scan")
    scan.add_argument("--detector", type=str, default="placeholder", help="registered detector name")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    all_keys = [s.key for s in _REGISTRY]

    if args.config:
        try:
            load_config(args.config)
            print(f"[loaded config overrides from {args.config}]\n")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR reading config: {exc}", file=sys.stderr)
            return 1

    if args.splash:
        print(splash())
        return 0
    if args.list_modules:
        print("Available modules:")
        for spec in _REGISTRY:
            print(f"  {spec.key:<20} {spec.description}")
        print("\nDetectors (camera):", ", ".join(sorted(_DETECTORS)))
        return 0
    if args.scan_image:
        if not os.path.exists(args.scan_image):
            print(f"ERROR: image not found: {args.scan_image}", file=sys.stderr)
            return 1
        det = _DETECTORS.get(args.detector)
        if det is None:
            print(f"ERROR: unknown detector '{args.detector}' "
                  f"(have: {', '.join(sorted(_DETECTORS))})", file=sys.stderr)
            return 1
        store = Storage(args.db)
        scan_alerts = run_scan(args.scan_image, args.scan_crop, det, store, args.name)
        print("=" * 70)
        print(f" CAMERA SCAN  --  {args.scan_image}")
        print("=" * 70)
        for a in scan_alerts:
            tag = f"[{SEV_LABEL[a.severity]}] " if a.severity > Severity.INFO else ""
            print(f"  {tag}{a.message}")
        print("=" * 70)
        return 0
    if args.report_sighting:
        if not args.date or not args.observed:
            print("ERROR: --report-sighting needs --date and --observed confirmed|clear "
                  "(disease via --modules, default late_blight)", file=sys.stderr)
            return 1
        mod = (args.modules or "late_blight").split(",")[0].strip()
        Storage(args.db).save_sighting(args.name, args.date, mod, args.observed, args.note)
        print(f"Recorded: {args.name} {args.date} {mod} -> {args.observed}")
        return 0
    if args.accuracy:
        s = Storage(args.db)
        print(render_accuracy(args.name, s.sightings(args.name), s.flagged(args.name)))
        return 0
    if args.history:
        print(render_history(args.name, Storage(args.db).timeline(args.name)))
        return 0

    if args.modules:
        enabled = [k.strip() for k in args.modules.split(",") if k.strip()]
        unknown = [k for k in enabled if k not in all_keys]
        if unknown:
            print(f"ERROR: unknown module(s): {', '.join(unknown)}", file=sys.stderr)
            return 1
    else:
        enabled = all_keys

    kept = [b.strip() for b in args.bees.split(",") if b.strip()]
    unknown_bees = [b for b in kept if b not in POLLINATOR_PROFILES]
    if unknown_bees:
        print(f"WARNING: unknown bee type(s): {', '.join(unknown_bees)}; "
              f"known: {', '.join(POLLINATOR_PROFILES)}.", file=sys.stderr)
    KEPT_POLLINATORS[:] = [b for b in kept if b in POLLINATOR_PROFILES] or ["honeybee"]
    _set_units(args.units)
    herd = [a.strip() for a in args.livestock.split(",") if a.strip()]
    unknown_herd = [a for a in herd if a not in LIVESTOCK_PROFILES]
    if unknown_herd:
        print(f"WARNING: unknown animal(s): {', '.join(unknown_herd)}; "
              f"known: {', '.join(LIVESTOCK_PROFILES)}.", file=sys.stderr)
    KEPT_LIVESTOCK[:] = [a for a in herd if a in LIVESTOCK_PROFILES] or ["dairy_cattle"]
    stock = [s.strip() for s in args.aquaculture.split(",") if s.strip()]
    unknown_stock = [s for s in stock if s not in AQUACULTURE_PROFILES]
    if unknown_stock:
        print(f"WARNING: unknown aquatic species: {', '.join(unknown_stock)}; "
              f"known: {', '.join(AQUACULTURE_PROFILES)}.", file=sys.stderr)
    KEPT_AQUACULTURE[:] = [s for s in stock if s in AQUACULTURE_PROFILES] or ["mixed"]
    bugs = [b.strip() for b in args.pests.split(",") if b.strip()]
    unknown_bugs = [b for b in bugs if b not in PEST_PROFILES]
    if unknown_bugs:
        print(f"WARNING: unknown pest(s): {', '.join(unknown_bugs)}; "
              f"known: {', '.join(PEST_PROFILES)}.", file=sys.stderr)
    KEPT_PESTS[:] = [b for b in bugs if b in PEST_PROFILES] or ["generic"]
    if args.biofix:
        try:
            bf = date.fromisoformat(args.biofix)
            _set_biofix(args.biofix)
            if not args.demo:
                back = (date.today() - bf).days
                if back > 0:
                    args.past_days = max(args.past_days, min(back, 92))
        except ValueError:
            print(f"WARNING: --biofix '{args.biofix}' is not a valid YYYY-MM-DD date; ignoring.",
                  file=sys.stderr)
    if args.parcels:
        if args.demo:
            print("ERROR: --parcels needs live weather; drop --demo.", file=sys.stderr)
            return 1
        try:
            farm, parcels = load_parcels(args.parcels)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR reading parcels file: {exc}", file=sys.stderr)
            return 1
        g_pests, g_live = list(KEPT_PESTS), list(KEPT_LIVESTOCK)
        g_aqua, g_bees = list(KEPT_AQUACULTURE), list(KEPT_POLLINATORS)
        _set_as_of(date.today().isoformat())  # parcels are live-only -> look forward from today
        results = []
        for pc in parcels:
            try:
                if pc.get("place"):
                    plat, plon, _r = geocode(pc["place"])
                else:
                    plat, plon = pc["lat"], pc["lon"]
                pdays = fetch_weather(plat, plon, args.past_days, args.forecast_days)
            except Exception as exc:  # noqa: BLE001
                print(f"[{pc['name']}: skipped -- {exc}]", file=sys.stderr)
                continue
            if not pdays:
                continue
            KEPT_PESTS[:] = pc.get("pests") or g_pests          # parcel's own crop/animal/water, or
            KEPT_LIVESTOCK[:] = pc.get("livestock") or g_live   # inherit the global flags
            KEPT_AQUACULTURE[:] = pc.get("aquaculture") or g_aqua
            KEPT_POLLINATORS[:] = pc.get("bees") or g_bees
            p_enabled = pc.get("modules") or enabled
            _set_latitude(plat)
            results.append((pc["name"], plat, plon, pdays, run_modules(pdays, p_enabled), p_enabled))
        if not results:
            print("ERROR: no parcels could be assessed.", file=sys.stderr)
            return 1
        print(render_farm(farm, results, args.demo, args.digest))
        if args.save:
            store = Storage(args.db)
            total = sum(store.save(name, al) for (name, _la, _lo, _d, al, _en) in results)
            print(f"\n[saved {total} risk event(s) across {len(results)} parcel(s) to {args.db}"
                  f" -- each under its own name, so --accuracy --name \"<parcel>\" tracks it]")
        return 0

    if args.place and not args.demo:
        try:
            args.lat, args.lon, resolved = geocode(args.place)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: could not locate '{args.place}': {exc}", file=sys.stderr)
            return 1
        if args.name == DEFAULT_NAME:
            args.name = resolved
        print(f"[located: {resolved}  ->  {args.lat:.4f}, {args.lon:.4f}]", file=sys.stderr)
    try:
        days = demo_weather() if args.demo else fetch_weather(
            args.lat, args.lon, args.past_days, args.forecast_days)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: could not get weather data: {exc}", file=sys.stderr)
        print("       (try --demo for an offline illustrative run)", file=sys.stderr)
        return 1
    if not days:
        print("ERROR: no daily data derived.", file=sys.stderr)
        return 1

    if args.sensor_csv:
        try:
            print(f"[merged sensors for {apply_sensor_csv(days, args.sensor_csv)} day(s) "
                  f"from {args.sensor_csv}]\n")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR reading sensor CSV: {exc}", file=sys.stderr)
            return 1

    _set_latitude(args.lat)
    _set_as_of(days[0].date if args.demo else date.today().isoformat())
    alerts = run_modules(days, enabled)
    if args.digest:
        print(render_digest(args.name, args.lat, args.lon, days, enabled, alerts, args.demo))
    else:
        print(render_report(args.name, args.lat, args.lon, days, enabled, alerts, args.demo))
    if args.save:
        print(f"\n[saved {Storage(args.db).save(args.name, alerts)} risk event(s) to {args.db}]")
    if args.export:
        out = args.out or f"terraward_results.{args.export}"
        export_results(out, args.export, args.name, args.lat, args.lon, days, alerts)
        print(f"[exported {len(alerts)} record(s) to {out} as {args.export}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
