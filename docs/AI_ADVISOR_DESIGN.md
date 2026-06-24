# TerraWard AI Advisor — design

The advisor is named **Hayward** — historically the village officer who guarded the fields and kept livestock out of the crops. Hayward is the part of TerraWard that *talks* to the farmer. You've made it the heart
of the project — and the answer to the data question. Because it runs **on the farmer's own
machine**, it is the only thing that ever touches their data, and that data never leaves the
device. Privacy stops being a promise and becomes structural.

This document is the design. It needs no cloud, no account, and no one's permission to run.

## The one rule that makes it trustworthy

**The engine decides. The AI explains.**

TerraWard's deterministic engine — the nine modules, the grounded thresholds, the calibration
loop — is the single source of truth for *what the risks are*. The AI's job is never to invent
a risk, a number, or a recommendation. Its job is to make the engine's verified output
understandable, prioritized, and answerable in plain language.

That is how the hallucination problem is solved: not by hoping a model behaves, but by
structurally denying it the authority to assert agronomic facts the engine didn't compute.

## Two layers

**Layer 1 — Deterministic briefing (no model).** Turns the engine's alerts into a prioritized,
plain-language, organic action briefing using rules and templates. It cannot hallucinate
because it only restates and orders verified data. Zero-dependency, runs offline on anything,
works *today*. It is also the foundation Layer 2 stands on. *(Prototype shipped as `advisor.py`.)*

**Layer 2 — Conversational advisor (local model).** A small open language model, running
locally, that answers free-form questions ("why is blight risk high this week?", "what do I do
first?", "what does THI mean?"). It is **constrained** to the briefing's grounded facts. If no
model is installed, the tool falls back to Layer 1 — it never breaks.

Most of the value is in Layer 1. Layer 2 is the conversation on top.

## The grounding contract (the technical heart)

Before the model is asked anything, the advisor assembles a **grounding context** from the
engine's current output:

- every active alert (module, severity, date, the exact message, confidence)
- the field readings that produced them (the actual weather/sensor values)
- the thresholds that fired, and the farm's calibration config
- a small fixed knowledge base of organic-practice notes and "what each model means"

The model receives this context plus a strict instruction (verbatim in `advisor.py` as
`ADVISOR_SYSTEM_PROMPT`):

> You are TerraWard's advisor. You may discuss ONLY the facts in the grounding data below. Do
> not invent risks, numbers, thresholds, dates, or recommendations that are not in it. If the
> data doesn't answer the question, say so plainly. Never recommend synthetic pesticides or
> fungicides — organic prevention only. For shellfish-biotoxin or other safety-critical
> questions, defer to official monitoring; never give an all-clear.

And three structural guards:

1. **The engine is authoritative.** Any risk level, number, or date in an answer must trace to
   the grounding data. The model explains; it does not overrule.
2. **No-data honesty.** Asked beyond the grounding set, it says "TerraWard doesn't have data on
   that," rather than guessing.
3. **Fallback over failure.** No model, weak hardware, or low confidence → the Layer 1 briefing.

## Privacy architecture — why on-device is the whole point

The advisor runs where the data already lives: on the farmer's machine. Model weights sit on
disk; inference runs locally (CPU, or the Mac's GPU via Metal). The data — alerts, sensor
history, sightings — is read from local files and handed to the local model. **Nothing is
transmitted.** No cloud API, no account, no telemetry.

This is what lets the data covenant say "the AI is the only thing that uses your data": the AI
is co-located with the data and never phones home. The improvement loop you wanted — the AI
getting more useful from crop and marine data — happens *for that farmer, on that farmer's
machine*, and stops there.

## Model options (honest, hardware-dependent)

Local inference needs a runtime — the one place TerraWard's zero-dependency rule relaxes, which
is why the LLM layer is **optional and isolated** in its own file and behind a `runner` seam.

Common local paths (pick by hardware; verify current versions when you build):
- **Ollama** — easiest; runs a local model server you talk to over localhost.
- **llama.cpp** — lighter; runs quantized GGUF models directly.
- Small open models that run on a workstation: Llama 3.x 8B, Mistral 7B, Phi-3, Gemma 2,
  quantized.

On your Mac Pro these run comfortably. On a Raspberry Pi, only the smallest quantized models,
slowly — which is exactly why Layer 1 carries the load on weak hardware and Layer 2 is optional.

## Interfaces

- **Now (CLI):** `advisor.py --demo` (Layer 1 briefing) and `--show-grounding` (inspect the exact
  facts a model would be allowed to use). Chat (`ask()`) is wired and waits for a local `runner`.
- **Later:** the briefing and chat behind the phone/web face on the roadmap.

## Languages

TerraWard speaks the farmer's language, through two mechanisms matching the two layers:

- **The local model is the real multilingual engine.** A language setting is injected into the
  system prompt, so the model answers natively — Dutch/Flemish, French, German, Mandarin,
  Russian, Ukrainian, Polish, Romanian, Turkish, Spanish, Portuguese, and more — while the
  verified numbers pass through unchanged (it translates the wording, never the values). Honest
  caveat: small on-device models are strong in major languages and weaker in lower-resource
  ones (e.g. Ukrainian, Romanian); larger local models cover more.
- **The deterministic briefing uses a message catalog** (`UI_STRINGS`) for its fixed labels.
  English ships complete; Dutch/Flemish is included as a worked example, and more languages are
  a natural community contribution. The briefing's alert *content* stays in the engine's
  language and is translated conversationally by the model — machine-translating safety-critical
  agronomic text (e.g. biotoxin warnings) deterministically is a job for careful native or
  professional translation, not a quick auto-translate.

Flemish is the Belgian variety of Dutch; the written labels are shared, and tone can be tuned.

## Safety

- **Organic guardrail** — never synthetic chemicals, enforced in the prompt and inherited from
  the engine's advice.
- **Safety-critical deferral** — marine biotoxin and similar: point to official monitoring,
  never reassure.
- **Advisory, not authority** — consistent with the disclaimer; it informs decisions, it does
  not make them.

## Build order

1. **Layer 1 briefing** — deterministic, tested, zero-dep. *(Done — `advisor.py`.)*
2. **Grounding-context builder** — serialize briefing + readings + thresholds into the block the
   model is given. *(Done — `advisor.py`, testable without a model.)*
3. **Layer 2 wiring** — connect a local runtime via the `runner` seam, apply the system prompt,
   return grounded answers with the briefing as fallback. *(Needs a machine with a model — your
   home test.)*
4. **Knowledge base** — a small curated organic-practice + model-explanation set, reviewable in
   the repo.
5. **Phone/web face** — later.

## Where it plugs into TerraWard

The engine already emits structured alerts (the `Alert` records, and `--export`). The advisor is
a *consumer* of that output, so the engine stays pure and dependency-free, and the optional model
dependency is quarantined in the advisor. Clean seam, no contamination.
