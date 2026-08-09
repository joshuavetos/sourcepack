from pathlib import Path
CLIENT = Path("src/sourcepack/workbench_static/command-center-aggregate.js")

def test_client_uses_single_canonical_snapshot_route():
    text=CLIENT.read_text(); assert text.count('/api/command-center/v1/snapshot') == 1; assert 'Promise.all' not in text; assert '/api/dashboard/v1/' not in text

def test_client_consumes_snapshot_without_legacy_state_assembly():
    text=CLIENT.read_text(); assert 'renderSnapshot(payload.snapshot)' in text; assert 'state.overview' not in text; assert 'mapSnapshot' not in text

def test_client_preserves_error_visibility():
    text=CLIENT.read_text(); assert "setText('verdict-title', 'Workbench Error')" in text; assert "finally { $('refresh').disabled = false; }" in text
