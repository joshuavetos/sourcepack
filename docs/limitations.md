# SourcePack limitations

SourcePack intentionally has a narrow local-first scope.

- Dynamic imports may be missed.
- Monorepos may be limited.
- Unsupported ecosystems warn rather than receive full dependency validation.
- Generated code may be difficult to classify.
- Import/package aliases are incomplete.
- Lockfile-only evidence may not be authoritative.
- SourcePack does not prove code correctness.
- SourcePack does not detect vulnerabilities or replace dependency, secret, or supply-chain scanning tools.
- Docker build semantics beyond obvious command and file evidence are limited.
