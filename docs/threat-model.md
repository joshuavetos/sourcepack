# SourcePack threat model

SourcePack is trust-boundary-adjacent, but it is not a security scanner.

## Defends against

- Invented files referenced or edited by AI output.
- Undeclared dependencies introduced by changed code.
- Unsupported project commands suggested or added without repo evidence.
- Protected baseline edits under `.sourcepack/baseline/`.
- Prompt context laundering, where prompt text claims something exists but the trusted baseline does not support it.

## Does not defend against

- Malicious but valid code that is consistent with the baseline.
- Logic bugs or incorrect implementations.
- Vulnerable declared dependencies.
- Test bypasses or inadequate test coverage.
- Secret exfiltration.
- Full supply-chain compromise.
- Full semantic code correctness.

## Reporting trust-boundary issues

Please report bypasses, false negatives, baseline trust-boundary failures, or prompt-laundering issues privately using the process in `SECURITY.md` when available.

## Public-alpha trust-boundary hardening

Prompt context remains non-authoritative: enforcement uses the trusted baseline, diff evidence, and declared dependency or command manifests, not AI prompt claims. Changes under `.sourcepack/baseline/` and `.git/` fail closed as protected or Git-internal artifact modifications. CI mode does not create new trust from a changed or missing baseline; baseline changes are treated as protected artifacts until reviewed locally.
