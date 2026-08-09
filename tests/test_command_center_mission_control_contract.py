from pathlib import Path
CLIENT=Path('src/sourcepack/workbench_static/command-center-aggregate.js')
HTML=Path('src/sourcepack/workbench_static/index.html')

def test_mission_control_renders_canonical_scores_priorities_capabilities_activity():
    text=CLIENT.read_text(); html=HTML.read_text()
    for token in ('command-center-scores','command-center-priorities','snapshot.scores','snapshot.priority_actions','snapshot.capabilities','snapshot.activity'): assert token in text+html

def test_priority_queue_dispatches_only_backend_owned_safe_actions():
    text=CLIENT.read_text()
    for token in ('dispatchPriorityAction(item)','item.action_type === "run_review"','item.action_type === "copy_command"','item.action_type === "navigate"','item.command','item.target_surface'): assert token in text
    for forbidden in ('sourcepack baseline .','sourcepack install-hook .','exec(','spawn(','subprocess','shell=True'): assert forbidden not in text

def test_mission_control_preserves_single_snapshot_boundary():
    text=CLIENT.read_text()+HTML.read_text(); assert text.count('/api/command-center/v1/snapshot') == 1; assert '/api/dashboard/v1/' not in text
