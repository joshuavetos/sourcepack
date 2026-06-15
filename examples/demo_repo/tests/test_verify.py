from sourcepack.verify import verify_hash

def test_verify_hash():
    assert verify_hash(b"x", "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881")
