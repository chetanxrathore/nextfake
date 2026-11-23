# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅        |
| 0.1.x   | ❌        |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use GitHub's private vulnerability reporting ("Security" → "Report a vulnerability") on the
nextfake repository. Include:

* a description of the issue and its impact,
* the nextfake, Python and OS versions,
* a minimal reproduction (schema, seed, call) if possible.

We aim to acknowledge reports within 3 working days and to ship a fix or mitigation for
confirmed issues within 30 days, coordinating disclosure with the reporter.

## Scope and threat model

* nextfake generates **synthetic** data. It never reads, transmits or stores real personal data
  and performs no network I/O. All locale tables are compiled into the binary.
* **The RNG is not for security.** `ChaCha8Rng` is used for speed and reproducibility; seeded
  output is predictable by design. Do not use `password()`, `uuid4()` or any other value as a
  real secret, token or credential.
* Generated credit-card numbers are Luhn-valid test numbers; they are not issued cards.
* Writers create or overwrite the exact path you pass; they do not follow user input to other
  paths. Treat output paths derived from untrusted input with the usual care.
* Unsafe Rust is limited to constructing Arrow buffers whose invariants are established by
  construction (documented `SAFETY` comments) and the Arrow C Data Interface export.

## Verifying releases

Every release is built and published by the `Wheels` GitHub Actions workflow
(`.github/workflows/wheels.yml`) using PyPI Trusted Publishing — no long-lived API tokens. Each
wheel and the sdist carry two independent, Sigstore-signed provenance records:

* **PyPI (PEP 740) attestations**, shown as *Verified details* on the PyPI file page:

  ```bash
  pip install pypi-attestations
  pypi-attestations verify pypi --repository https://github.com/chetanxrathore/nextfake \
      pypi:nextfake-1.0.0-cp310-abi3-macosx_11_0_arm64.whl
  ```

* **GitHub build provenance** (SLSA), for any downloaded file:

  ```bash
  pip download nextfake==1.0.0 --no-deps -d dist
  gh attestation verify dist/nextfake-*.whl --repo chetanxrathore/nextfake
  ```
