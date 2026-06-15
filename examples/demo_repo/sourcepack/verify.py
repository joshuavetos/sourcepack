import hashlib

def verify_hash(data: bytes, expected: str) -> bool:
    return hashlib.sha256(data).hexdigest() == expected
