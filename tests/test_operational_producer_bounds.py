import json
from pathlib import Path

import pytest

from sourcepack import baseline as baseline_module, cli, packet as packet_module
from sourcepack.decision_ledger import new_event, read_events
from sourcepack.fleet import summarize_ledgers, summarize_reports
from sourcepack.packet import PacketCleanupError, PacketWriter, SourceScanner, verify_packet


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


def test_packet_verification_metadata_and_record_limits_fail_closed(tmp_path: Path) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "receipt.json").write_bytes(b" " * 9)
    assert verify_packet(packet, metadata_byte_limit=8) is False

    (packet / "receipt.json").write_text(
        json.dumps({"hashes": {"a": "x", "b": "y"}}), encoding="utf-8"
    )
    assert verify_packet(packet, record_limit=1) is False


def test_packet_verification_individual_and_aggregate_byte_limits_fail_closed(tmp_path: Path) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "a").write_bytes(b"aa")
    (packet / "b").write_bytes(b"bb")
    (packet / "receipt.json").write_text(
        json.dumps({"hashes": {"a": "x", "b": "y"}}), encoding="utf-8"
    )
    assert verify_packet(packet, file_byte_limit=1) is False
    assert verify_packet(packet, aggregate_byte_limit=3) is False


@pytest.mark.parametrize("unsafe_name", ["../outside.txt", "/outside.txt", "C:\\outside.txt"])
def test_packet_verification_rejects_escaping_and_absolute_receipt_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unsafe_name: str
) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("external", encoding="utf-8")
    before = outside.read_bytes()
    (packet / "receipt.json").write_text(
        json.dumps({"hashes": {unsafe_name: packet_module.sha256_file(outside)}}),
        encoding="utf-8",
    )
    hashed: list[Path] = []
    real_hash = packet_module.sha256_file

    def recording_hash(path: Path) -> str:
        hashed.append(path)
        return real_hash(path)

    monkeypatch.setattr(packet_module, "sha256_file", recording_hash)
    assert verify_packet(packet) is False
    assert hashed == []
    assert outside.read_bytes() == before


def test_packet_verification_rejects_symlinked_artifact_and_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("external", encoding="utf-8")
    before = outside.read_bytes()
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "linked.txt").symlink_to(outside)
    (packet / "receipt.json").write_text(
        json.dumps({"hashes": {"linked.txt": packet_module.sha256_file(outside)}}),
        encoding="utf-8",
    )
    assert verify_packet(packet) is False
    linked_root = tmp_path / "linked-packet"
    linked_root.symlink_to(packet, target_is_directory=True)
    assert verify_packet(linked_root) is False
    assert outside.read_bytes() == before


def test_packet_verification_rejects_external_symlinked_receipt(tmp_path: Path) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    artifact = packet / "artifact.txt"
    artifact.write_text("confined", encoding="utf-8")
    external_receipt = tmp_path / "external-receipt.json"
    external_receipt.write_text(
        json.dumps({"hashes": {"artifact.txt": packet_module.sha256_file(artifact)}}),
        encoding="utf-8",
    )
    before = external_receipt.read_bytes()
    (packet / "receipt.json").symlink_to(external_receipt)
    assert verify_packet(packet) is False
    assert external_receipt.read_bytes() == before


def test_packet_verification_rejects_external_symlinked_manifest(tmp_path: Path) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    external_manifest = tmp_path / "external-manifest.json"
    external_manifest.write_text(json.dumps({"included_files": []}), encoding="utf-8")
    before = external_manifest.read_bytes()
    (packet / "manifest.json").symlink_to(external_manifest)
    (packet / "receipt.json").write_text(json.dumps({"hashes": {}}), encoding="utf-8")
    assert verify_packet(packet, source) is False
    assert external_manifest.read_bytes() == before


def _packet_with_manifest(packet: Path, records: list[dict[str, str]]) -> None:
    manifest = packet / "manifest.json"
    manifest.write_text(json.dumps({"included_files": records}), encoding="utf-8")
    (packet / "receipt.json").write_text(
        json.dumps({"hashes": {"manifest.json": packet_module.sha256_file(manifest)}}),
        encoding="utf-8",
    )


def test_packet_verification_rejects_escaping_and_symlinked_source_paths(tmp_path: Path) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("external", encoding="utf-8")
    before = outside.read_bytes()
    expected = packet_module.sha256_text("external")

    _packet_with_manifest(packet, [{"relative_path": "../outside.txt", "source_sha256": expected}])
    assert verify_packet(packet, source) is False

    (source / "linked.txt").symlink_to(outside)
    _packet_with_manifest(packet, [{"relative_path": "linked.txt", "source_sha256": expected}])
    assert verify_packet(packet, source) is False
    linked_source = tmp_path / "linked-source"
    linked_source.symlink_to(source, target_is_directory=True)
    assert verify_packet(packet, linked_source) is False
    assert outside.read_bytes() == before


def test_packet_verification_accepts_confined_regular_files_and_cli_delegates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    artifact = packet / "manifest.json"
    artifact.write_text('{"included_files": []}', encoding="utf-8")
    (packet / "receipt.json").write_text(
        json.dumps({"hashes": {"manifest.json": packet_module.sha256_file(artifact)}}),
        encoding="utf-8",
    )
    assert verify_packet(
        packet,
        metadata_byte_limit=(packet / "receipt.json").stat().st_size,
        record_limit=1,
        file_byte_limit=artifact.stat().st_size,
        aggregate_byte_limit=artifact.stat().st_size,
    ) is True

    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        cli,
        "canonical_verify_packet",
        lambda packet_path, against=None: calls.append((packet_path, against)) or True,
    )
    assert cli.verify_packet(packet, tmp_path) is True
    assert calls == [(packet, tmp_path)]


@pytest.mark.parametrize("value", [123, "x" * 64, "G" * 64])
def test_packet_verification_rejects_malformed_receipt_hashes(
    tmp_path: Path, value: object
) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    manifest = packet / "manifest.json"
    manifest.write_text('{"included_files": []}', encoding="utf-8")
    (packet / "receipt.json").write_text(
        json.dumps({"hashes": {"manifest.json": value}}), encoding="utf-8"
    )
    assert verify_packet(packet) is False


@pytest.mark.parametrize("hashes", [
    {"receipt.json": "0" * 64, "manifest.json": "0" * 64},
    {"artifact.txt": "0" * 64},
])
def test_packet_verification_rejects_incoherent_receipt_coverage(
    tmp_path: Path, hashes: dict[str, str]
) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "receipt.json").write_text(json.dumps({"hashes": hashes}), encoding="utf-8")
    assert verify_packet(packet) is False


def test_packet_verification_rejects_duplicate_manifest_paths(tmp_path: Path) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_text("a", encoding="utf-8")
    record = {"relative_path": "a.txt", "source_sha256": packet_module.sha256_text("a")}
    _packet_with_manifest(packet, [record, record.copy()])
    assert verify_packet(packet, source) is False


def test_packet_verification_rejects_file_growth_during_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packet = tmp_path / "packet"
    packet.mkdir()
    manifest = packet / "manifest.json"
    manifest.write_text('{"included_files": []}', encoding="utf-8")
    (packet / "receipt.json").write_text(
        json.dumps({"hashes": {"manifest.json": packet_module.sha256_file(manifest)}}),
        encoding="utf-8",
    )
    real_fstat = packet_module.os.fstat
    calls = 0

    def growing_fstat(fd: int):
        nonlocal calls
        result = real_fstat(fd)
        calls += 1
        if calls == 1:
            with manifest.open("ab") as handle:
                handle.write(b" ")
        return result

    monkeypatch.setattr(packet_module.os, "fstat", growing_fstat)
    assert verify_packet(packet) is False


def test_baseline_validation_delegates_to_canonical_packet_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(
        packet_module,
        "verify_packet",
        lambda path: calls.append(path) or False,
    )
    result = baseline_module._validate_packet_artifacts(tmp_path, tmp_path / "packet")
    assert result is not None
    assert result["details"]["reason"] == "canonical packet verification failed"
    assert calls == [tmp_path / "packet"]


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
