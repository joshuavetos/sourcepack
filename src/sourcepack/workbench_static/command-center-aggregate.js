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

  function statusClass(status) {
    if (status === "LIVE") return "live";
    if (["READY", "PARTIAL", "NEEDS_SETUP", "DEGRADED"].includes(status)) return "partial";
    return "planned";
  }

  function ensureMissionControlPanels() {
    const mission = document.getElementById("view-mission");
    if (!mission || document.getElementById("command-center-intelligence")) return;
    const section = document.createElement("section");
    section.id = "command-center-intelligence";
    section.className = "grid2";
    section.innerHTML = `
      <article class="panel"><h3>Operational scores</h3><div class="grid2" id="command-center-scores"></div></article>
      <article class="panel"><h3>Priority queue</h3><div class="list" id="command-center-priorities"></div></article>`;
    mission.appendChild(section);
  }

  function priorityRow(item) {
    const label = item.label || "Unavailable action";
    const supported = ["run_review", "copy_command", "navigate"].includes(item.action_type);
    const disabled = supported ? "" : " disabled";
    return `<div class="row"><b>${esc(item.priority || "P?")} · ${esc(item.id || "action")}</b><small>${esc(item.reason || "No reason recorded")}</small><button class="btn command-center-action" data-action-id="${esc(item.id || "")}" style="margin-top:9px"${disabled}>${esc(label)}</button></div>`;
  }

  async function copyCommand(value) {
    try {
      await navigator.clipboard.writeText(value);
      showToast("Copied: " + value);
    } catch {
      showToast("Clipboard unavailable. Command: " + value);
    }
  }

  async function dispatchPriorityAction(item) {
    if (item.action_type === "run_review") {
      await runReview();
      return;
    }
    if (item.action_type === "copy_command" && item.command) {
      await copyCommand(item.command);
      return;
    }
    if (item.action_type === "navigate" && item.target_surface) {
      setView(item.target_surface);
      return;
    }
    showToast("Action unavailable: unsupported snapshot metadata");
  }

  function bindPriorityActions(priorities) {
    const actionsById = new Map(priorities.map((item) => [item.id, item]));
    document.querySelectorAll(".command-center-action").forEach((button) => {
      button.addEventListener("click", async () => {
        const item = actionsById.get(button.dataset.actionId || "");
        if (!item) {
          showToast("Action unavailable: priority metadata missing");
          return;
        }
        button.disabled = true;
        try {
          await dispatchPriorityAction(item);
        } finally {
          button.disabled = false;
        }
      });
    });
  }

  function renderCommandCenter() {
    const snapshot = state.commandCenter || {};
    const scores = snapshot.scores || {};
    const priorities = Array.isArray(snapshot.priority_actions) ? snapshot.priority_actions : [];
    const capabilities = Array.isArray(snapshot.capabilities) ? snapshot.capabilities : [];
    const activity = Array.isArray(snapshot.activity) ? snapshot.activity : [];

    ensureMissionControlPanels();

    const scoreNames = [
      ["Trust", scores.trust],
      ["Automation", scores.automation],
      ["Product breadth", scores.product_breadth],
      ["Report depth", scores.report_depth],
    ];
    document.getElementById("command-center-scores").innerHTML = scoreNames
      .map(([name, value]) => row(name, `${Number(value || 0)} / 100`))
      .join("");

    document.getElementById("command-center-priorities").innerHTML = priorities.length
      ? priorities.map(priorityRow).join("")
      : '<p class="empty">No queued actions.</p>';
    bindPriorityActions(priorities);

    document.getElementById("capability-mini").innerHTML = capabilities.length
      ? capabilities.map((item) => row(item.surface || item.name || item.id, `${item.status || "UNKNOWN"} · ${item.evidence || "No evidence"}`)).join("")
      : '<p class="empty">No capability state available.</p>';

    document.getElementById("timeline").innerHTML = activity.length
      ? activity.map((item) => `<div class="event"><span class="dot" style="background:var(--cyan)"></span><div><b>${esc(item.type || "event")}</b><small>${esc(item.message || "")}</small></div><time>snapshot</time></div>`).join("")
      : '<p class="empty">No activity recorded.</p>';

    const agentModules = capabilities
      .filter((item) => ["Agent Gateway", "Mission Control"].includes(item.surface))
      .map((item) => module(item.name, item.status, item.evidence, statusClass(item.status)));
    if (agentModules.length) document.getElementById("agent-modules").innerHTML = agentModules.join("");

    const labModules = capabilities
      .filter((item) => item.surface === "Adversarial Lab")
      .map((item) => module(item.name, item.status, item.evidence, statusClass(item.status)));
    if (labModules.length) document.getElementById("lab-modules").innerHTML = labModules.join("");

    const integrationModules = capabilities
      .filter((item) => item.surface === "Integration Hub")
      .map((item) => module(item.name, item.status, item.evidence, statusClass(item.status)));
    if (integrationModules.length) document.getElementById("integration-modules").innerHTML = integrationModules.join("");
  }

  loadAll = async function loadCommandCenterSnapshot() {
    const refresh = document.getElementById("refresh");
    refresh.disabled = true;
    try {
      const payload = await api(SNAPSHOT_ROUTE);
      mapSnapshot(payload.snapshot || {});
      render();
      renderCommandCenter();
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