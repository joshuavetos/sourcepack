(() => {
  const SNAPSHOT_ROUTE = "/api/command-center/v1/snapshot";

  function mapSnapshot(snapshot) {
    const artifacts = snapshot.artifacts || {};
    const report = artifacts.report || null;
    const posture = snapshot.posture || {};

    state.commandCenter = snapshot;
    state.overview = {
      repository: { path: snapshot.repository?.path || "Local repository" },
      git: snapshot.repository?.git || {},
      baseline: artifacts.baseline || {},
      policy_resolution_status: posture.policy_resolution_status,
      report_verdict: posture.verdict,
      blocker_count: posture.blocker_count || 0,
      warning_count: posture.warning_count || 0,
    };
    state.report = {
      report,
      report_path: ".sourcepack/reports/latest.json",
      proposed_change: null,
    };
    state.policy = { policy: artifacts.policy || {} };
    state.baseline = { baseline: artifacts.baseline || {} };
    state.status = artifacts.status || {};
    state.replay = {
      replay: report?.replay_bundle || null,
      evidence: report?.evidence_items || report?.evidence || null,
      reason_code_evidence: report?.reason_code_evidence || null,
    };
    state.overrides = { overrides: [], policy_findings: [] };
    delete state.error;
  }

  loadAll = async function loadCommandCenterSnapshot() {
    const refresh = document.getElementById("refresh");
    refresh.disabled = true;
    try {
      const payload = await api(SNAPSHOT_ROUTE);
      mapSnapshot(payload.snapshot || {});
      render();
    } catch (error) {
      state.error = error.message;
      render();
      showToast("Command Center snapshot failed: " + error.message);
    } finally {
      refresh.disabled = false;
    }
  };

  loadAll();
})();
