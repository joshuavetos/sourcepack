import json
from pathlib import Path

import pytest

from sourcepack.decision_ledger import new_event, read_events
from sourcepack.fleet import summarize_ledgers, summarize_reports
from sourcepack.packet import PacketCleanupError, PacketWriter, SourceScanner


def _report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"schema_version":"traffic_report.v1","verdict":"WARN","findings":[]}', encoding="utf-8")


def _ledger(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    events = [new_event("reviewed", command="test", repo=path.parent) for _ in range(count)]
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")


def test_fleet_exact_entry_boundary_and_deterministic_order(tmp_path: Path) -> None:
    _report(tmp_path / "b.json")
    _report(tmp_path / "a.json")
    first = summarize_reports(tmp_path, max_entries=2)
    second = summarize_reports(tmp_path, max_entries=2)
    assert first["producer"]["status"] == "complete"
    assert first["producer"]["consumed"] == 2
    assert first["accepted_report_paths"] == second["accepted_report_paths"] == ["a.json", "b.json"]


def test_fleet_entry_depth_and_read_boundaries_are_incomplete(tmp_path: Path) -> None:
    _report(tmp_path / "a.json")
    _report(tmp_path / "b.json")
    overflow = summarize_reports(tmp_path, max_entries=1)
    assert overflow["producer"]["status"] == "incomplete"
    assert overflow["producer"]["source_exhausted"] is False
    assert overflow["producer"]["total_is_lower_bound"] is True

    nested = tmp_path / "nested" / "too-deep.json"
    _report(nested)
    assert summarize_reports(tmp_path, max_depth=0)["producer"]["limit_reached"] == "nesting_depth"

    size = (tmp_path / "a.json").stat().st_size
    one_byte = summarize_reports(tmp_path / "a.json", max_file_bytes=size - 1)
    assert one_byte["producer"]["limit_reached"] == "individual_file_bytes"
    aggregate = summarize_reports(tmp_path, max_read_bytes=size)
    assert aggregate["producer"]["limit_reached"] == "aggregate_read_bytes"


def test_fleet_skips_symlinks_without_leaking_or_mutating_trust_state(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-fleet.json"
    _report(outside)
    (tmp_path / "linked.json").symlink_to(outside)
    before = outside.read_bytes()
    summary = summarize_reports(tmp_path)
    assert summary["accepted_report_paths"] == []
    assert outside.read_bytes() == before
    assert "verdict" not in summary["producer"]
    explicit = summarize_reports(tmp_path / "linked.json")
    assert explicit["producer"]["status"] == "failed"


def test_packet_cleanup_exact_boundary_and_symlink_confinement(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    scanner = SourceScanner(source, trust_git_tracked=False).scan()
    output = tmp_path / "packet"
    output.mkdir()
    (output / "b.txt").write_text("b", encoding="utf-8")
    (output / "a.txt").write_text("a", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    (output / "link").symlink_to(outside)

    writer = PacketWriter(output, scanner, force=True, cleanup_entry_limit=3)
    writer.prepare_out()
    assert writer.cleanup_result == {
        "status": "complete", "complete": True, "consumed": 3, "retained": 0,
        "source_exhausted": True, "total": 3, "total_is_lower_bound": False,
        "configured_limit": 3, "limit_reached": None, "error": None,
    }
    assert outside.read_text(encoding="utf-8") == "keep"


def test_packet_partial_cleanup_is_explicit_and_output_root_symlink_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    scanner = SourceScanner(source, trust_git_tracked=False).scan()
    output = tmp_path / "packet"
    output.mkdir()
    for name in ("a", "b"):
        (output / name).write_text(name, encoding="utf-8")
    with pytest.raises(PacketCleanupError) as limited:
        PacketWriter(output, scanner, force=True, cleanup_entry_limit=1).prepare_out()
    assert limited.value.result["status"] == "incomplete"
    assert limited.value.result["source_exhausted"] is False
    assert any(output.iterdir())

    real = tmp_path / "real"
    real.mkdir()
    sentinel = real / "sentinel"
    sentinel.write_text("keep", encoding="utf-8")
    link = tmp_path / "linked-output"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(PacketCleanupError) as escaped:
        PacketWriter(link, scanner, force=True).prepare_out()
    assert escaped.value.result["status"] == "failed"
    assert sentinel.exists()


@pytest.mark.parametrize(("count", "reached", "consumed", "exhausted", "total"), [
    (3, False, 3, True, 3),
    (4, True, 4, False, None),
])
def test_ledger_event_metadata_exact_and_one_event_overflow(tmp_path: Path, count: int, reached: bool, consumed: int, exhausted: bool, total: int | None) -> None:
    _ledger(tmp_path / "one.jsonl", count)
    producer = summarize_ledgers(tmp_path, max_events=3)["producer"]
    assert producer["discovery"]["artifact_paths_retained"] == 1
    assert producer["events"] == {
        "events_consumed": consumed,
        "events_retained": 3,
        "events_source_exhausted": exhausted,
        "event_total": total,
        "event_total_lower_bound": None if exhausted else consumed,
        "event_retention_limit": 3,
        "event_limit_reached": reached,
    }


def test_ledger_aggregate_event_limit_is_separate_from_artifact_discovery(tmp_path: Path) -> None:
    _ledger(tmp_path / "a.jsonl", 2)
    _ledger(tmp_path / "b.jsonl", 2)
    producer = summarize_ledgers(tmp_path, max_events=3)["producer"]
    assert producer["discovery"]["artifact_paths_retained"] == 2
    assert producer["discovery"]["limit_reached"] is None
    assert producer["events"]["events_consumed"] == 4
    assert producer["events"]["events_retained"] == 3
    assert producer["events"]["event_limit_reached"] is True


def test_bounded_ledger_reader_stops_after_single_event_probe(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    _ledger(ledger, 5)
    with ledger.open("a", encoding="utf-8") as stream:
        stream.write("malformed after probe\n")
    result = read_events(ledger, max_events=3)
    assert len(result.events) == 3
    assert result.events_consumed == 4
    assert result.events_source_exhausted is False
    assert result.malformed_lines == []


def test_ledger_discovery_limit_does_not_claim_event_retention_limit(tmp_path: Path) -> None:
    _ledger(tmp_path / "a.jsonl", 1)
    _ledger(tmp_path / "b.jsonl", 1)
    producer = summarize_ledgers(tmp_path, max_records=1, max_events=10)["producer"]
    assert producer["status"] == "incomplete"
    assert producer["discovery"]["artifact_paths_retained"] == 1
    assert producer["discovery"]["limit_reached"] == "artifact_paths"
    assert producer["events"]["events_retained"] == 1
    assert producer["events"]["event_retention_limit"] == 10
    assert producer["events"]["event_limit_reached"] is False
    assert "retained" not in producer
