# TerraWard Commons — design proposal

> **Status: proposal. Not built.** Nothing in this document changes how the local tool works
> today. The Commons is an *optional* layer. If you never opt in — or if every server on earth
> running it disappears — TerraWard on your machine keeps working exactly as it does now.

This is the concrete shape of "farmers and growers learning from each other" — sharing intel,
pooling early warning, helping each other — built so it **strengthens** TerraWard's founding
promise (local-first, sovereign, no surveillance, can't be paywalled) instead of trading it
away. Read it, push back, and we decide before a line of it is written.

---

## The one rule everything else serves

**The grower's machine is the source of truth, and it is complete on its own.** The Commons is
purely additive. Three hard invariants follow:

1. **Nothing leaves a device except what the grower explicitly chooses to publish** — and even
   then only in *minimized, coarsened, identity-free* form.
2. **The local tool never depends on the Commons.** No login to use it, no server to reach, no
   degraded mode offline. The Commons is a window you can open, never a gate you must pass.
3. **No central data lake, ever.** No single server holds growers' data; no single party owns
   the network.

If a proposed feature breaks one of these, it doesn't go in.

---

## What problem it solves

A disease or pest doesn't respect field boundaries. If late blight is confirmed on three farms
in your district this week, you want to know *today* — that's days of warning the weather model
alone can't give you. The Commons turns many growers' confirmed observations into shared,
neighbourly early warning, and lets a region build a picture no single farm could.

The substrate already exists: TerraWard already logs confirmed sightings and scores them
(the trust loop). The Commons is the opt-in way to let those signals help your neighbours, and
theirs help you.

---

## Architecture at a glance

```
   your machine (full data, private)          a neighbour's machine
   ┌───────────────────────────┐              ┌───────────────────────────┐
   │ engine + Hayward + local  │              │ engine + Hayward + local  │
   │ DB (0600, never shared)   │              │ DB (0600, never shared)   │
   │                           │              │                           │
   │  you choose to publish →  │              │  ← they choose to publish │
   │  a *minimized signal*,    │              │                           │
   │  signed with your key     │              │                           │
   └─────────────┬─────────────┘              └─────────────┬─────────────┘
                 │  (only minimized, coarse, identity-free) │
                 ▼                                          ▼
        ┌───────────────── Relay(s) you choose ─────────────────┐
        │  a co-op / region / university / self-hosted          │
        │  • verifies signatures   • aggregates by area+week    │
        │  • shows a cell ONLY when ≥ K distinct growers report │
        │  • stores minimized signals only — never raw farm data│
        │  • may federate aggregates with peer relays (optional)│
        └───────────────────────────────────────────────────────┘
```

The local node is whole. Relays are optional, multiple, independent, and self-hostable. The
protocol is open, so anyone can run a relay or write a client — no lock-in.

---

## What gets shared: a "Signal"

A Signal is the *only* thing that can leave a device, and it is deliberately thin:

| Field | Example | Notes |
|---|---|---|
| `kind` | `late_blight_confirmed` | from a controlled vocabulary tied to the engine's modules |
| `severity` | `WARNING` | the engine's level |
| `confidence` | `HIGH` | the engine's confidence |
| `window` | `2026-W25` | a **coarse time bucket** (ISO week), not a timestamp |
| `cell` | `grid:50.8,3.3` or a district code | a **coarse area**, *never* exact coordinates |
| `pubkey` | `ed25519:ab12…` | the grower's pseudonymous key |
| `sig` | … | signature over the above |

**Never included:** exact coordinates, farm name, any personal identifier, raw sensor readings,
field-level detail, or free-text about the grower. What you publish is closer to "blight,
confirmed, this week, roughly this district" than to anything that points back at you.

---

## Protecting the grower: coarsening + k-anonymity

This is the heart of the design, because the obvious risk is real: **a confirmed disease at a
precise location *is* a specific farm.** Anonymity here is engineered, not assumed.

- **Spatial coarsening.** Location is reduced to a coarse cell (a grid of ~10–25 km, or an
  administrative district) before anything is shared. The raw coordinates never leave the node.
- **Temporal bucketing.** Time is reduced to a week, not a timestamp.
- **k-anonymity threshold.** A relay surfaces an aggregate for a cell+window **only once at
  least `K` distinct growers** have reported it (`K` ≈ 3–5). Below the threshold: nothing is
  shown. This protects the first or lone reporter from being singled out.
- **Aggregates only.** The Commons shows *counts and heat per cell* once `K` is met — never an
  individual Signal on a map, never a pin.

The result: you can contribute to "blight is active in your area" without anyone — including a
relay operator — being able to tell it was *your* farm.

---

## Identity you hold: self-sovereign keys

No accounts. No email. No password database to leak.

- On first opt-in, the node generates an **Ed25519 keypair** locally. The **private key never
  leaves the device.** The public key (or a short fingerprint) is your pseudonymous identity.
- You **sign** what you publish; relays and peers verify signatures. Forgery is infeasible;
  impersonation is impossible without your key.
- An optional human-readable nickname is purely local and non-authoritative.
- **Trade-off to accept:** your reputation is tied to your key. Lose the key and you start
  fresh; so the node lets you back it up and (carefully) rotate it. This is the price of having
  no central authority to "reset your password" — and the reason there's no honeypot to breach.

This is the model behind tools like minisign, age, SSB, and Nostr: identity is something you
*hold*, not something a server grants.

---

## Federated relays, not a central server

A **Relay** is a small, optional service that a community runs:

- **Accepts** signed Signals, **verifies** their signatures, and **aggregates** them under the
  k-anonymity rule.
- **Serves** aggregate queries — "what's active near cell X this week" — and nothing finer.
- **Stores only minimized Signals.** It never holds raw farm data, so a compromised relay
  leaks little, and forged Signals are rejected by signature.
- **May federate** (gossip aggregates) with peer relays, or stand entirely alone as a single
  co-op's private commons.

It's deliberately lightweight — runnable on modest hardware, self-hostable by a co-op, a
region, a university, or you. Multiple independent relays mean no single owner and no single
point of failure. The protocol is documented and open; a reference relay ships with the
project. **Think email or Mastodon — federated — not Facebook.**

This also keeps cost distributed and avoids the trap that kills free tools: a central server is
an ongoing bill that creates pressure to monetize (ads, data sales, subscriptions). Federation
sidesteps that entirely.

---

## Offline-first, online-optional

Everything works offline. Signals you choose to publish queue locally and send when you're next
online; aggregates you've fetched are cached for offline viewing. "Online" is for sync only —
the tool never *needs* it.

---

## Reputation, not rewards

You asked about rewarding growers. Here's the honest trap and the way around it.

**The trap:** any reward for *submitting* data is an incentive to submit *fake* data — which
poisons the shared intel everyone relies on. Tokens or cash add fraud, regulation, and pull the
project away from mutual aid toward points-farming.

**The design:** reward **reputation and reciprocity**, earned through accuracy, not volume.

- A grower's standing rises when their Signals are **corroborated** (others in the cell confirm;
  the engine's own confirmation logic validates) and falls when they're contradicted — driven
  by the trust loop you already have.
- Reputation **weights** how much a Signal counts toward an aggregate, so one bad actor (or a
  pile of fresh throwaway keys) barely moves the picture.
- **Reciprocity, gently:** the coarse aggregate is open to everyone; contributors who help keep
  the picture accurate get the richer, finer views. It's a thank-you, not a paywall — the full
  *local* tool is always free and complete regardless.

The reward is the collective intelligence itself, and standing among peers who know you give
good data. Mutual aid, made durable.

---

## Threat model

| Threat | Mitigation |
|---|---|
| **Re-identifying a farm** from a shared observation | spatial coarsening + week buckets + k-anonymity + aggregates-only + zero identity in Signals |
| **Poisoned / false reports** | trust-loop reputation weighting; corroboration thresholds; new/low-rep keys down-weighted; engine confirmation |
| **Sybil attack** (many fake keys) | counts are *reputation-weighted*, not raw-key-counted, so empty keys add little; closed co-op relays may add their own lightweight vetting (their choice, never mandated) |
| **Relay compromise** | relays hold only minimized data; Signals are signed and can't be forged; growers can switch or use several relays |
| **Replay / forgery** | signatures + timestamps/nonces; stale or duplicate Signals rejected |
| **Censorship / eclipse** | multiple independent relays + federation; connect to several |
| **Abuse / harassment** | v1 is **structured vocabulary only — no free-text messaging**, which removes most of the abuse surface; relays moderate their own membership |
| **Metadata leakage** (IP, timing) | relays shouldn't log IPs; support batching and Tor/onion for the privacy-conscious |
| **Operator becoming a legal data controller** | Signals are anonymized, identity-free, and self-published; each relay operator owns their own compliance. *(Documentation, not legal advice.)* |

---

## Governance & the covenant

The Commons extends [DATA_GOVERNANCE.md](../DATA_GOVERNANCE.md): minimized, opt-in, never sold,
no surveillance, growers own their keys and data. A relay operator agrees to that covenant — a
relay that violates it is simply not part of the TerraWard Commons. The protocol and a reference
relay are open; moderation lives at the relay/community level, close to the people it affects.

## What the Commons will never do

- No central data lake; no single owner.
- No mandatory accounts; no email or password.
- No selling, brokering, or advertising on the data.
- No sharing of precise location or identity — ever.
- No requirement to be online; no weakening of the local tool.
- No tokens, points, or cash rewards.

---

## Phased rollout

Each phase is independently useful and keeps every invariant above.

- **Phase 0 — today.** The local trust loop and export already exist: the data substrate is
  here.
- **Phase 1 — file-based exchange.** A grower exports a minimized, signed *Signal bundle*; a
  co-op imports and aggregates it. Proves the schema, coarsening, and signing with **no live
  server at all**.
- **Phase 2 — reference relay.** A self-hostable relay with k-anonymity aggregation and a query
  API; the node can publish to and subscribe from a chosen relay.
- **Phase 3 — federation + reputation.** Relays gossip aggregates; reputation weighting and
  reciprocity come online.
- **Phase 4 — enrichment.** Discovery, richer regional models, optional satellite cross-checks
  feeding the picture.

---

## Decisions for you

These are yours to set; my leanings are noted, but they're starting points, not defaults.

1. **k-anonymity threshold `K`** — how many distinct growers before an aggregate appears.
   *Lean: 3–5.*
2. **Cell size** — grid (~10–25 km) vs administrative districts. Granularity vs anonymity.
   *Lean: start coarse; a grower can never opt into finer than the floor.*
3. **Time bucket** — day vs week. *Lean: week (safer).*
4. **Reciprocity** — fully open aggregate to all, or contributor-gated finer views.
   *Lean: coarse open to all, finer to contributors.*
5. **Relay model** — one co-op private commons first, or federated from day one.
   *Lean: start single/self-hosted, design for federation.*
6. **Signal content** — structured-vocabulary-only vs allow free-text in v1.
   *Lean: structured only (less abuse, easier across 14 languages).*
7. **Signature scheme** — *Lean: Ed25519.*

---

## Why not just a central platform?

It would be easier to ship — and it's the exact thing TerraWard was built to avoid. A central
server is a honeypot to breach, a bill that breeds pressure to monetize, an owner who can be
pressured or bought, and — the moment it holds farmers' data — it makes its operator a legal
data controller carrying everyone's risk. The federated, minimized, key-signed design above is
more work up front and buys you a Commons that can't be captured, can't surveil, and can't be
switched off from the outside. That's the version worth building.
