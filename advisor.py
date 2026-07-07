#!/usr/bin/env python3
# TerraWard advisor (Layer 1 + grounding seam for Layer 2).
# Copyright (C) 2026 the TerraWard contributors
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version. Distributed WITHOUT ANY WARRANTY. See the GNU AGPL for details
# <https://www.gnu.org/licenses/>.
"""advisor.py -- TerraWard deterministic advisory (Layer 1) + grounding seam (Layer 2).

Layer 1 turns the engine's verified alerts into a prioritized, plain-language, organic
action briefing. No model, no network, no invention: it only restates and prioritizes what
the engine already computed, so it cannot hallucinate. The same structured briefing becomes
the GROUNDING CONTEXT that the optional local-LLM layer (Layer 2) is constrained to.

LANGUAGES: the local model answers in the farmer's chosen language (the real multilingual
engine); the deterministic briefing's fixed labels come from a message catalog (UI_STRINGS),
English shipped, more welcome as contributions. See docs/AI_ADVISOR_DESIGN.md.

  python3 advisor.py --demo
  python3 advisor.py --demo --lang nl
  python3 advisor.py --demo --show-grounding
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, List, Optional

import terraward as tw
from terraward import Severity

# Languages the advisor targets. The local model handles any it supports; lower-resource
# ones (e.g. Ukrainian, Romanian) are stronger on larger models than on tiny ones.
LANGUAGES = {
    "en": "English", "nl": "Dutch (incl. Flemish)", "fr": "French", "de": "German",
    "zh": "Mandarin Chinese", "ru": "Russian", "uk": "Ukrainian", "pl": "Polish",
    "ro": "Romanian", "tr": "Turkish", "es": "Spanish", "pt": "Portuguese",
    "it": "Italian", "ar": "Arabic",
}
DEFAULT_LANG = "en"
ADVISOR_NAME = "Hayward"  # the advisor introduces itself by this name

# Deterministic briefing chrome (fixed labels only). English is complete; add languages here.
# Flemish is the Belgian variety of Dutch -- the written labels are shared.
UI_STRINGS = {
    "en": {"title": "TERRAWARD BRIEFING", "do": "DO SOMETHING:",
           "watch": "KEEP AN EYE ON:", "readings": "FIELD READINGS & FIGURES:"},
    "nl": {"title": "TERRAWARD BRIEFING", "do": "ONDERNEEM ACTIE:",
           "watch": "IN DE GATEN HOUDEN:", "readings": "VELDMETINGEN & CIJFERS:"},
}


def _t(key: str, lang: str) -> str:
    """Translate a fixed UI label, falling back to English for any missing language/key."""
    return UI_STRINGS.get(lang, UI_STRINGS["en"]).get(key, UI_STRINGS["en"][key])


LABELS = {
    "late_blight": "Potato late blight", "scab_risk": "Apple scab",
    "downy_mildew": "Grape downy mildew",
    "frost_risk": "Frost / cold", "heat_stress": "Crop heat stress",
    "cold_stress": "Cold stress", "wind_conditions": "Wind",
    "livestock_thi": "Livestock heat stress", "pollinators": "Pollination window",
    "insect_pests": "Insect pests", "growing_degree_days": "Crop development (GDD)",
    "soil_conditions": "Soil", "marine_conditions": "Water / aquaculture",
    "manure_spreading": "Manure spreading window", "treatment_window": "Treatment window",
    "evapotranspiration": "Irrigation / water balance", "camera": "Image scan",
}
URGENCY = {Severity.DANGER: "ACT NOW", Severity.WARNING: "Act soon",
           Severity.WATCH: "Watch", Severity.INFO: "Info"}


def _label(mod: str) -> str:
    return LABELS.get(mod, mod)


@dataclass
class Briefing:
    name: str
    window: tuple
    headline: str
    urgent: List[tw.Alert] = field(default_factory=list)   # DANGER + WARNING
    watch: List[tw.Alert] = field(default_factory=list)    # WATCH
    facts: List[tw.Alert] = field(default_factory=list)    # INFO


def build_briefing(name: str, days, alerts) -> Briefing:
    """Prioritize verified alerts into an action briefing. Adds NO new facts."""
    worst = max((a.severity for a in alerts), default=Severity.INFO)
    n_urgent = sum(1 for a in alerts if a.severity >= Severity.WARNING)
    if worst >= Severity.DANGER:
        headline = f"{n_urgent} thing(s) need action -- at least one is urgent."
    elif worst == Severity.WARNING:
        headline = f"{n_urgent} thing(s) need attention soon."
    elif worst == Severity.WATCH:
        headline = "Nothing urgent -- a few conditions worth watching."
    else:
        headline = "All clear. No action needed from the current data."
    urgent = sorted([a for a in alerts if a.severity >= Severity.WARNING],
                    key=lambda a: (-int(a.severity), a.date or ""))
    watch = [a for a in alerts if a.severity == Severity.WATCH]
    facts = [a for a in alerts if a.severity == Severity.INFO]
    window = (days[0].date, days[-1].date) if days else ("n/a", "n/a")
    return Briefing(name, window, headline, urgent, watch, facts)


def render_briefing(b: Briefing, lang: str = "en") -> str:
    out = ["=" * 70, f" {_t('title', lang)}  --  {b.name}",
           f" {b.window[0]} -> {b.window[1]}   |  {date.today().isoformat()}",
           "=" * 70, f" {b.headline}", "=" * 70]
    if b.urgent:
        out += ["", _t("do", lang)]
        for i, a in enumerate(b.urgent, 1):
            tag = f"[{a.date}] " if a.date else ""
            conf = f"  (confidence: {a.confidence})" if a.confidence else ""
            out.append(f"  {i}. {URGENCY[a.severity]} - {tag}{_label(a.module)}{conf}")
            out.append(f"       {a.message}")
    if b.watch:
        out += ["", _t("watch", lang)]
        for a in b.watch:
            tag = f"[{a.date}] " if a.date else ""
            out.append(f"  - {tag}{_label(a.module)}: {a.message}")
    if b.facts:
        out += ["", _t("readings", lang)]
        out += [f"  - {a.message}" for a in b.facts]
    out += ["", f"             -- {ADVISOR_NAME}"]
    return "\n".join(out + ["=" * 70])


# ---- Layer 2 seam: grounding for a LOCAL model (no model is called here) ----

ADVISOR_SYSTEM_PROMPT = (
    "You are Hayward, TerraWard's advisor, speaking to an organic farmer. You may discuss ONLY the "
    "facts in the GROUNDING DATA below. Do not invent risks, numbers, thresholds, dates, or "
    "recommendations that are not in it. If the data does not answer the question, say so "
    "plainly. Never recommend synthetic pesticides or fungicides -- organic prevention only. "
    "For shellfish-biotoxin or other safety-critical questions, tell the farmer to check "
    "official monitoring; never give an all-clear yourself. Be brief and practical."
)


def build_system_prompt(language: str = "English") -> str:
    """The grounding rules plus the farmer's language. Translating the wording is the model's
    job; the numbers must pass through unchanged."""
    return (ADVISOR_SYSTEM_PROMPT +
            f" Respond entirely in {language}, in clear plain wording a farmer will understand. "
            f"Translate the wording, but keep every number, threshold and date exactly as given.")


def build_grounding_context(b: Briefing, days, config) -> str:
    """Serialize the verified briefing + readings + active thresholds into the text block a
    local model is given. This is the model's ENTIRE permitted world of facts."""
    lines = [f"FARM: {b.name}", f"WINDOW: {b.window[0]} to {b.window[1]}",
             f"SUMMARY: {b.headline}", "", "ACTIVE ALERTS:"]
    shown = b.urgent + b.watch
    if shown:
        lines += [f"- [{tw.SEV_LABEL[a.severity]}] {(a.date + ' ') if a.date else ''}"
                  f"{_label(a.module)}{(' (confidence ' + a.confidence + ')') if a.confidence else ''}"
                  f": {a.message}" for a in shown]
    else:
        lines.append("- none")
    lines += ["", "FIELD READINGS & FIGURES:"]
    if b.facts:
        lines += [f"- {a.message}" for a in b.facts]
    else:
        lines.append("- none")
    lines += ["", "ACTIVE THRESHOLDS (the farm's calibration):"]
    lines += [f"- {mod}: {params}" for mod, params in config.items()]
    return "\n".join(lines)


def ask(question: str, context: str,
        runner: Optional[Callable[[str, str, str], str]] = None,
        language: str = "English") -> str:
    """Layer 2 entry point. `runner` wraps a LOCAL model: runner(system_prompt, context,
    question) -> str (e.g. an Ollama/llama.cpp call). The system prompt carries the language,
    so the model answers natively. If no runner is supplied we DO NOT guess -- we defer to the
    deterministic briefing, by design."""
    if runner is None:
        return ("[Local AI advisor not configured -- the grounded briefing above is the answer.\n"
                " Wire a local model via the `runner` seam in advisor.py to enable chat. The\n"
                " deterministic briefing is always available and never hallucinates.]")
    return runner(build_system_prompt(language), context, question)


def _cli() -> int:
    p = argparse.ArgumentParser(description="TerraWard advisor (deterministic briefing + grounding).")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--lat", type=float, default=tw.DEFAULT_LAT)
    p.add_argument("--lon", type=float, default=tw.DEFAULT_LON)
    p.add_argument("--name", type=str, default=tw.DEFAULT_NAME)
    p.add_argument("--sensor-csv", type=str, default=None)
    p.add_argument("--config", type=str, default=None)
    p.add_argument("--lang", type=str, default=DEFAULT_LANG,
                   help="language code: " + ", ".join(LANGUAGES))
    p.add_argument("--ask", type=str, default=None, help="ask the advisor a question (needs a model)")
    p.add_argument("--show-grounding", action="store_true",
                   help="print the grounding context a local model would receive")
    args = p.parse_args()
    lang = args.lang if args.lang in LANGUAGES else DEFAULT_LANG
    if args.lang not in LANGUAGES:
        print(f"WARNING: unknown language '{args.lang}', using English. "
              f"Known: {', '.join(LANGUAGES)}", file=sys.stderr)
    if args.config:
        tw.load_config(args.config)
    try:
        days = tw.demo_weather() if args.demo else tw.fetch_weather(args.lat, args.lon, 7, 7)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: could not get weather data: {exc}", file=sys.stderr)
        print("       (try --demo for an offline run)", file=sys.stderr)
        return 1
    if args.sensor_csv:
        try:
            tw.apply_sensor_csv(days, args.sensor_csv)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR reading sensor CSV: {exc}", file=sys.stderr)
            return 1
    alerts = tw.run_modules(days, [s.key for s in tw._REGISTRY])
    b = build_briefing(args.name, days, alerts)
    print(render_briefing(b, lang))
    ctx = build_grounding_context(b, days, tw.CONFIG)
    if args.show_grounding:
        print("\n----- GROUNDING CONTEXT (what a local model would be given) -----")
        print(ctx)
    if args.ask:
        print("\n" + ask(args.ask, ctx, runner=None, language=LANGUAGES[lang]))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
