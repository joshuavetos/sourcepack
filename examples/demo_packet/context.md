# SourcePack Context Packet

## Source Manifest Summary

Input path: /workspace/sourcepack/examples/demo_repo
Generated at: 2026-06-15T23:18:19.282210+00:00
Files included: 6
Estimated tokens: 205

## File: README.md

Metadata:
- sha256: a7e1752b33efa2da5769f5e7aeb6e23498350f9c59a902341f8863a58c607900
- bytes: 153
- estimated_tokens: 39

Content:

# Demo Repo

This is a local-first CLI demo. PDF parsing is not supported. There is no web server. There is no Docker setup. There is no React frontend.


---

## File: pyproject.toml

Metadata:
- sha256: 8bcd24bacf5a5936e911c814331afe1fab6bf036fcda5983c6eb143a89013cb9
- bytes: 99
- estimated_tokens: 25

Content:

[project]
name = "demo-repo"
version = "0.1.0"
requires-python = ">=3.8"
dependencies = ["pytest"]


---

## File: sourcepack/cli.py

Metadata:
- sha256: 27fae75b5f5b55d891fc89682bae49ff7f47f6bcd7b6c188fdb011be5e3c4a92
- bytes: 134
- estimated_tokens: 34

Content:

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    return parser.parse_args()


---

## File: sourcepack/judge.py

Metadata:
- sha256: 409cce4f25abdd804048f4c0630d237e19a0b37a6e4b7feb946fd19cd98b9ffc
- bytes: 133
- estimated_tokens: 34

Content:

def judge(answer: str, known_files: set[str]) -> list[str]:
    return [line for line in answer.splitlines() if "server.py" in line]


---

## File: sourcepack/verify.py

Metadata:
- sha256: 1fe61bada9b2a55f096e3f103d43730040a0eb39ecd8d6048a7e64367ff69ebc
- bytes: 125
- estimated_tokens: 32

Content:

import hashlib

def verify_hash(data: bytes, expected: str) -> bool:
    return hashlib.sha256(data).hexdigest() == expected


---

## File: tests/test_verify.py

Metadata:
- sha256: cb2d232eb2353dd9807728eb487b3fbc42fc8112d96cd49fbbaec6c2b428bc68
- bytes: 164
- estimated_tokens: 41

Content:

from sourcepack.verify import verify_hash

def test_verify_hash():
    assert verify_hash(b"x", "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881")


---
