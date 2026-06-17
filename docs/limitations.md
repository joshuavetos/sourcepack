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

## Public-alpha unsupported ecosystem handling

SourcePack now warns with `unsupported_ecosystem` for recognized but not fully modeled ecosystem markers including Cargo, Go modules, Maven, Gradle, Ruby/Bundler, PHP/Composer, .NET project files, Terraform, and Nix flakes. This is uncertainty evidence, not semantic validation of those ecosystems.
