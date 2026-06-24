# Integrations — machinery & mobile

> **Status: roadmap / proposal.** None of this is built, and none of it changes the local tool
> today. It follows the same rule as everything else: TerraWard runs on hardware the **grower
> controls**, reads the data it's entitled to, and never depends on a manufacturer's blessing or
> a cloud it doesn't own.

---

## Tractors & machinery (John Deere, New Holland, Case, Fendt, …)

### Can TerraWard run *on* the tractor's own display? No.

The in-cab displays — Deere **GreenStar / Gen4 / G5**, New Holland **IntelliView**, Case
**AFS Pro**, etc. — are closed, locked-down embedded systems. You cannot install third-party
software on them except through the maker's own developer program (and Deere in particular is
famously locked — the whole right-to-repair fight is about exactly this). So "a TerraWard app on
the Deere screen" is not on the table, and chasing it would mean asking permission from the very
gatekeepers this project routes around.

### The ports don't change that

- **USB** on these displays is for **data exchange** — maps, prescriptions, exported field logs
  (ISOXML task data, shapefiles) — *not* for running programs.
- **Ethernet** appears on newer machines but is reserved for the manufacturer's own use.
- The live data actually lives on a **CAN bus**:
  - **ISOBUS (ISO 11783)** — the standard language between tractor and implement.
  - **J1939 (SAE)** — engine/powertrain diagnostics.
  - Note: this is **not OBD2** (that's cars — your Leaf). Tractors speak CAN / J1939 / ISOBUS.

### The pattern that fits — a companion computer

The same approach you already chose for the Leaf: run TerraWard on a small computer **you own**,
mounted in the cab — a rugged Raspberry Pi, a mini-PC, or your tablet — and interface to the
machine to **read** the bus:

- a **USB-to-CAN adapter** (PEAK, Kvaser, or budget CANable/Korlan) or a **Pi CAN HAT**
  (PiCAN, Waveshare);
- on Linux, **SocketCAN** + the **python-can** library; for ISOBUS specifically, an open stack
  like **AgIsoStack** can decode implement messages.

**Reading is safe.** It opens up genuinely useful things to feed the engine: GPS position and
speed, implement and section status, as-applied data (what was sprayed/seeded where), and
engine/diagnostic health — which TerraWard can log per field, correlate with its risk picture,
and use for organic record-keeping. (TerraWard reads and advises organically; it never pushes
synthetic prescriptions back.)

> ⚠️ **Writing / control is a different universe.** Sending commands to a multi-tonne machine is
> safety-critical, increasingly **encrypted/authenticated** by manufacturers, and entangled with
> warranty and liability. Treat it with the exact caution you flagged for the Leaf: read first,
> gate any write behind explicit confirmation and least privilege, and accept that "never" is a
> legitimate answer.

**Precedent that proves the pattern:** Climate FieldView's "Drive" dongle plugs into the
vehicle's CAN port and pairs with an iPad app. TerraWard would sit on *your* side of that fence —
reading the bus, owning the data — not as something a manufacturer blesses.

**Per-machine reality:** exact ports, protocols, and what's readable vary by make / model / year /
display, and some buses are read-restricted. Tell me your specific machine and I'll dig into that
one.

---

## A TerraWard phone app

Yes — and the cinematic intro you've seen is literally the first frame of this front-end.

### Start as a PWA (installable web app)

- **One codebase, both platforms** — runs on iOS *and* Android.
- **Works offline**, installs to the home screen like a native app.
- **No app-store gatekeepers or fees** — which fits free-and-open perfectly, and local-first maps
  cleanly onto a phone.

What it does first: view briefings and alerts, see the Commons aggregate (the k-anonymised area
picture, never a pin), and log sightings — reading from your local TerraWard node.

### Architecture

The phone is best as a **thin client talking to your local TerraWard node** over the farm network
(running Python directly on a phone is clunky). For fully standalone use, a slimmed engine could
be bundled later. Either way: offline-first, syncing when connected — the same store-and-forward
model as the Commons.

### Go native later, only if hardware demands it

**Flutter**, or **Swift/Kotlin**, distributed via the stores *and* **F-Droid** (the FOSS-friendly
Android route). Reach for this when you need deep device access:

- **Bluetooth** to a CAN/OBD dongle (bridging to the tractor or the Leaf);
- the **camera** for on-device disease scanning (the detector seam is already there);
- **background push alerts** for fast-moving risks.

> One honest trade-off: phone **push notifications route through Apple's (APNs) and Google's (FCM)
> servers** by design — a dependency the rest of TerraWard avoids. Local/LAN alerts (the app
> nudging you while on the farm network) sidestep that; cloud push is opt-in if you want
> off-property alerts.

---

## Phased rollout

1. **PWA front-end** — wrap the local node's output; the intro becomes the loading screen.
2. **Companion-computer CAN reader** — USB-to-CAN, SocketCAN + python-can, *read* ISOBUS/J1939,
   feed the engine.
3. **Native app** — BLE dongle + camera disease-scan + (opt-in) push.
4. **Write/control exploration** — gated, cautious, possibly never.

Each step stands alone and keeps the local tool whole and serverless.

---

## Decisions for you

- **Which machine(s)** to target first (make / model / year / display)?
- **PWA first, or jump to native** — depends on whether camera/BLE matter early. *(Lean: PWA
  first.)*
- **Thin-client to your node, or a bundled on-phone engine?** *(Lean: thin-client first.)*
- **Push notifications** — accept the Apple/Google dependency for off-farm alerts, or keep alerts
  local-only? *(Lean: local-only by default, cloud push opt-in.)*
