# Security policy

SourcePack is not a vulnerability scanner, secret scanner, or supply-chain protection product. It is a local-first guardrail that checks whether AI-assisted repository changes rely on unsupported local evidence before commit.

## What to report

Please report issues that affect SourcePack's trust boundary, including:

- Baseline bypasses or cases where `.sourcepack/baseline/` edits are trusted silently.
- Prompt context laundering, where prompt context becomes enforcement evidence.
- False negatives for invented files, undeclared dependencies, unsupported commands, or unsafe paths.
- JSON/CI output issues that could hide WARN or FAIL results from automation.

## What is out of scope

- Vulnerabilities in projects analyzed by SourcePack.
- Malicious but baseline-consistent code.
- General dependency vulnerability reports.
- Secret scanning requests.

## Reporting process

Open a private security advisory if the hosting platform supports it. If not, open a minimal public issue that states a trust-boundary problem exists without exploit details, and maintainers can coordinate a private channel.
