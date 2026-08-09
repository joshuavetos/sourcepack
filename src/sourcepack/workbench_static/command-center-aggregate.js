(() => {
  const SNAPSHOT_ROUTE = "/api/command-center/v1/snapshot";
  const PRIORITY_ACTION_IDS = new Set(["run_review", "resolve_findings", "repair_policy", "create_baseline", "refresh_baseline", "install_hooks", "build_adversarial_runner", "add_integration_adapter", "build_improvement_loop"]);
  const SURFACE_TARGETS = {review: "verdict-card", policy: "policy-studio", lab: "adversarial-lab", integrations: "integration-hub", agents: "remediation-panel"};

  function summaries(id, rows) {
    const parent = clear(id);
    for (const [label, value] of rows) addSummary(parent, label, value);
  }

  function renderReportDetails(snapshot) {
    const report = snapshot.artifacts.report;
    const action = snapshot.workbench.review_action;
    $('raw-report').textContent = JSON.stringify(report, null, 2);
    $('policy-raw').textContent = JSON.stringify(snapshot.artifacts.policy, null, 2);
    $('replay-raw').textContent = JSON.stringify(report === null ? null : report.replay_bundle, null, 2);
    $('systems-raw').textContent = JSON.stringify(snapshot.artifacts, null, 2);
    const omitted = Object.entries(snapshot.bounds.collections).filter(([, value]) => value.truncated).map(([key, value]) => `${key}: ${value.omitted_count} omitted`);
    if (omitted.length) $('systems-raw').textContent = `Bounded diagnostics (${omitted.join(', ')}).\n` + $('systems-raw').textContent;
    const copyAvailable = action.action_type === 'copy_prompt' && action.available === true && typeof action.prompt === 'string' && action.prompt.trim() !== '';
    currentPrompt = copyAvailable ? action.prompt : '';
    $('correction-prompt').textContent = currentPrompt || 'No correction prompt is available in the canonical report.';
    for (const id of ['copy-prompt', 'copy-prompt-secondary']) {
      $(id).hidden = !copyAvailable;
      $(id).disabled = !copyAvailable;
      $(id).textContent = action.label;
    }
    $('correction-prompt').closest('details').hidden = !copyAvailable;
    $('run-review').hidden = action.action_type !== 'run_review';
    $('run-review').disabled = !action.available;
    $('run-review').textContent = action.label;
    setText('reason-code', action.reason);
  }

  function renderChange(snapshot) {
    const parent = clear('change-summary');
    const proposed = snapshot.workbench.proposed_change;
    const excerpts = proposed === null ? [] : proposed.excerpts;
    if (!excerpts.length) { const empty=document.createElement('p'); empty.className='empty'; empty.textContent='No bounded changed-line excerpt is available from the canonical report paths.'; parent.append(empty); return; }
    for (const excerpt of excerpts) {
      const row=document.createElement('div'); row.className='summary-box';
      const title=document.createElement('div'); title.className='summary-title'; title.textContent=excerpt.path;
      const pre=document.createElement('pre'); pre.textContent=excerpt.lines.map((line)=>`${String(line.number).padStart(4, ' ')}  ${line.text}`).join('\n');
      const note=document.createElement('p'); note.className='empty'; note.textContent=excerpt.status === 'truncated' ? `Excerpt truncated at ${excerpt.byte_limit} bytes.` : excerpt.status === 'omitted' ? `Excerpt omitted: ${excerpt.reason}.` : 'Current worktree context; may differ from the reviewed report content.';
      row.append(title,note,pre); parent.append(row);
    }
  }

  function renderEvidence(snapshot) {
    const parent=clear('evidence-list'); const cards=snapshot.workbench.evidence_cards;
    if (!cards.length) { const empty=document.createElement('p'); empty.className='empty'; empty.textContent='No structured evidence items are recorded in the canonical report.'; parent.append(empty); return; }
    for (const card of cards) { const row=document.createElement('div'); row.className=`evidence-item${card.problem ? ' problem' : ''}`; const head=document.createElement('div'); head.className='evidence-head'; const name=document.createElement('span'); name.textContent=card.name; const tag=document.createElement('span'); tag.className='chip'; tag.textContent=card.tag; head.append(name,tag); const body=document.createElement('div'); body.className='evidence-body'; body.textContent=card.body; row.append(head,body); parent.append(row); }
  }

  function renderCorrectionSummary(snapshot) {
    const parent=clear('correction-summary'); const rows=snapshot.workbench.correction_rows;
    if (!rows.length) { const empty=document.createElement('p'); empty.className='empty'; empty.textContent='No concise correction summary is available in the canonical report.'; parent.append(empty); return; }
    for (const item of rows) addSummary(parent,item.label,item.value);
  }

  function showActionError(message) { setText('explanation', message); }

  async function copyCommand(value) {
    try { await navigator.clipboard.writeText(value); }
    catch (_) { showActionError(`Clipboard unavailable. Command: ${value}`); }
  }

  async function dispatchPriorityAction(item) {
    if (!PRIORITY_ACTION_IDS.has(item.id)) { showActionError("Action unavailable: unsupported snapshot metadata"); return; }
    if (item.action_type === "run_review") return runReview();
    if (item.action_type === "copy_command" && typeof item.command === "string") return copyCommand(item.command);
    if (item.action_type === "navigate" && SURFACE_TARGETS[item.target_surface]) return document.getElementById(SURFACE_TARGETS[item.target_surface]).scrollIntoView();
    showActionError("Action unavailable: unsupported snapshot metadata");
  }

  function renderCommandCenter(snapshot) {
    summaries('command-center-scores', Object.entries(snapshot.scores));
    summaries('command-center-capabilities', snapshot.capabilities.map((item) => [item.name, `${item.status} · ${item.evidence}`]));
    summaries('command-center-activity', snapshot.activity.map((item) => [item.type, item.message]));
    const queue = clear('command-center-priorities');
    for (const item of snapshot.priority_actions) {
      const row = document.createElement('div'); row.className = 'summary-box';
      const reason = document.createElement('span'); reason.textContent = `${item.priority} · ${item.label} — ${item.reason}`;
      const button = document.createElement('button'); button.className = 'secondary'; button.textContent = item.label;
      button.disabled = !PRIORITY_ACTION_IDS.has(item.id);
      button.addEventListener('click', () => dispatchPriorityAction(item)); row.append(reason, button); queue.append(row);
    }
  }

  function renderSnapshot(snapshot) {
    const posture = snapshot.posture;
    const report = snapshot.artifacts.report;
    const display = snapshot.display;
    $('verdict-card').className = `verdict-card ${display.verdict_class}`;
    setText('verdict-pill-text', display.verdict_label);
    setText('fact-verdict', display.verdict_label);
    setText('verdict-icon', display.verdict_icon);
    setText('verdict-title', display.verdict_title);
    setText('explanation', snapshot.activity[snapshot.activity.length - 1].message);
    setText('fact-findings', display.findings_summary);
    setText('nav-findings', display.navigation_findings_summary);
    setText('fact-policy', posture.policy_resolution_status);
    setText('fact-evidence', display.evidence_summary);
    setText('repo-path', snapshot.repository.path);
    setText('branch-name', display.branch);
    setText('version', display.version_label);
    setText('review-time', display.report_time);
    summaries('policy-summary', [['Resolution', posture.policy_resolution_status], ['State', snapshot.state.policy]]);
    summaries('replay-summary', [['State', snapshot.state.replay]]);
    summaries('override-list', [['Persisted decisions', 'Available through raw diagnostic endpoint']]);
    renderReportDetails(snapshot);
    renderChange(snapshot);
    renderEvidence(snapshot);
    renderCorrectionSummary(snapshot);
    renderCommandCenter(snapshot);
  }

  window.loadCommandCenterSnapshot = async function loadCommandCenterSnapshot() {
    $('refresh').disabled = true;
    try { const payload = await api(SNAPSHOT_ROUTE); renderSnapshot(payload.snapshot); }
    catch (error) { setText('verdict-title', 'Workbench Error'); setText('explanation', error.message); $('verdict-card').setAttribute('role', 'alert'); }
    finally { $('refresh').disabled = false; }
  };
  $('refresh').addEventListener('click', loadCommandCenterSnapshot);
  loadCommandCenterSnapshot();
})();
