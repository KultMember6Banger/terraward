# Security Policy

TerraWard is a local-first, open-source tool that runs on a farmer's own machine. We take
its security and the privacy of the data it holds seriously, and we'd rather hear about a
problem than have it sit unreported.

A note up front, in the spirit of honesty: no software — open or closed — is "unhackable" or
"crack-proof," and we make no such claim. Security here means reducing risk in depth and being
auditable. Because TerraWard is open source, its security does **not** depend on hiding the
code; anyone can read it, check it, and improve it. That is a strength, not a weakness.

## Reporting a vulnerability

**Please do not open a public issue for a security vulnerability.** Public issues are visible
to everyone and can put users at risk before a fix exists.

Instead, report it privately:

- Use the project's private vulnerability reporting (GitHub → **Security** → *Report a
  vulnerability*) once the repository is published, **or**
- contact the maintainer directly at the address listed in the repository profile.

> Maintainers: replace this line with a real security contact (a dedicated address or GitHub
> private advisories) before publishing.

Please include what you found, how to reproduce it, and the impact you think it has. If you
have a suggested fix, even better — but it isn't required.

**What to expect:** TerraWard is a volunteer, non-commercial project, so responses are
best-effort. We aim to acknowledge a credible report within a few days, agree on a disclosure
timeline with you, fix it, and credit you (unless you'd prefer to stay anonymous). We will not
take legal action against good-faith security research.

## Supported versions

Security fixes target the latest released version on the `main` branch. Older versions are not
maintained — please update.

## Scope

**In scope:** the TerraWard engine, the Hayward advisor, input parsing/validation, the local
storage layer, and the build/release pipeline.

**Out of scope:** the security of the host operating system; third-party services TerraWard
reads from (e.g. the weather API); and any external model files or plugins you choose to load
yourself. We can still help you use those safely — see below.

## Security posture (what TerraWard already does)

- **Minimal attack surface** — zero third-party runtime dependencies, so there is no
  dependency supply chain to be poisoned.
- **No dangerous execution paths** — no `eval`, `exec`, `pickle`, `shell=True`, `os.system`,
  or `subprocess` anywhere in the codebase.
- **Network safety** — the only outbound call is an HTTPS request to the weather API, with
  TLS certificate verification left intact and a request timeout. It sends only the
  coordinates needed for the forecast.
- **Untrusted input is validated** — API responses and user config files are treated as
  hostile: a wrong shape produces a clear error, and a bad value is skipped rather than
  crashing the run or poisoning the engine's thresholds.
- **No secrets** — TerraWard needs no API keys or credentials, so there are none to leak.
- **Private data at rest** — the local database is created owner-only (`0600`) on Unix.
- **A grounded AI** — the Hayward advisor can only see the engine's verified facts and cannot
  take actions, so a prompt-injection attempt has nothing to act on.

## If you extend TerraWard

- **Loading ML models?** Use a safe format such as **safetensors**. Never load a pickled model
  from an untrusted source — unpickling can execute arbitrary code (remote code execution).
- **Adding a network input?** Keep TLS verification on, set timeouts, and validate the response
  shape before trusting it — the same way the weather parser does.
- **Adding write/control capability to hardware?** Gate it behind least privilege and explicit
  confirmation, and never run TerraWard as root to get it.

## Verifying a release

Every release ships a `SHA256SUMS` file. To confirm a download is authentic and untampered:

    sha256sum -c SHA256SUMS      # Linux
    shasum -a 256 -c SHA256SUMS  # macOS

A mismatch means the file was altered — do not run it. Signed Git tags let you verify
provenance from the source side too: `git verify-tag <tag>`.

## Data protection

TerraWard is built to keep the farmer's data on the farmer's machine. What is stored, what (if
anything) leaves the device, and how to inspect, export, or erase it are documented in
[DATA_GOVERNANCE.md](DATA_GOVERNANCE.md).
