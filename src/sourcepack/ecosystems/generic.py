from __future__ import annotations

UNSUPPORTED_ECOSYSTEM_FILES = {
    "Cargo.toml": "Rust/Cargo",
    "go.mod": "Go modules",
    "pom.xml": "Java/Maven",
    "build.gradle": "Java/Gradle",
    "Gemfile": "Ruby/Bundler",
    "composer.json": "PHP/Composer",
    "*.csproj": ".NET/NuGet",
    "main.tf": "Terraform",
    "flake.nix": "Nix",
}
