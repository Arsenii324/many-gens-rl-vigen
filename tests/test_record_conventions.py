"""The record envelope's conventions must agree with the protocol and the cadence audit.

normalize_curves.py runs on the container, where `rlgen` is not a payload member, so it carries
its own copy of the per-baseline conventions. A copy that can drift silently is worse than no
copy: these tests are what make it one source of truth in practice.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(path: pathlib.Path, name: str):
    """Register before exec: dataclasses resolve their module through sys.modules."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NORMALIZE = _load(ROOT / "datasphere" / "native" / "normalize_curves.py", "normalize_curves")
AUDIT = _load(ROOT / "scripts" / "audit_eval_cadence.py", "audit_eval_cadence")
from rlgen import protocol as PROTOCOL  # noqa: E402  -- needs sys.path above

BASELINES = sorted(NORMALIZE.CONVENTIONS)


def test_all_twelve_baselines_carry_conventions():
    assert len(BASELINES) == 12, BASELINES


@pytest.mark.parametrize("baseline", BASELINES)
def test_time_limit_handling_matches_protocol(baseline):
    assert NORMALIZE.CONVENTIONS[baseline]["time_limit_handling"] == \
        PROTOCOL.TIME_LIMIT_HANDLING[baseline], (
            f"{baseline}: the record envelope and rlgen/protocol.py disagree about C1's split")


@pytest.mark.parametrize("baseline", BASELINES)
def test_observation_geometry_matches_protocol(baseline):
    size, stack = PROTOCOL.OBSERVATION_GEOMETRY[baseline]
    conventions = NORMALIZE.CONVENTIONS[baseline]
    assert (conventions["render_size"], conventions["frame_stack"]) == (size, stack)


@pytest.mark.parametrize("baseline", BASELINES)
def test_training_time_eval_shape_matches_the_audit(baseline):
    """`none` and `continuous` are verdicts from source; they must not drift into a cadence."""
    audited = AUDIT.UNITS[baseline]
    declared = NORMALIZE.CONVENTIONS[baseline]["training_time_eval"]
    if audited["unit"] == "none":
        assert declared == "none", f"{baseline}: audit says no training-time eval, record says {declared}"
    elif audited["unit"] == "continuous":
        assert declared == "continuous"
    else:
        assert declared.startswith("periodic"), f"{baseline}: {declared}"
        assert len(audited["regimes"]) >= 1


def test_a_record_carries_its_conventions():
    row = NORMALIZE.record(cell="drqv2-s1", baseline="drqv2", family="rlvigen", seed=1, frame=1000)
    assert row["schema"] == 2
    assert row["conventions"]["time_limit_handling"] == "terminal"
    assert row["conventions"]["scene_axis"] if "scene_axis" in row["conventions"] else True


def test_grid_record_schema_has_checkpoint_provenance():
    """A normalized row must identify checkpoint bytes, not only the role-name snapshot.pt."""
    row = NORMALIZE.record(cell="x", baseline="drqv2", family="rlvigen", seed=1, frame=1000,
                           checkpoint_sha256="a" * 64)
    assert row["checkpoint_sha256"] == "a" * 64


def test_grid_record_schema_can_identify_the_evaluator_revision():
    row = NORMALIZE.record(cell="x", baseline="drqv2", family="rlvigen", seed=1, frame=1000,
                           evaluator_revision="b" * 64)
    assert row["evaluator_revision"] == "b" * 64


def test_record_carries_run_provenance_without_internal_fields():
    row = NORMALIZE.record(cell="x", baseline="drqv2", family="rlvigen", seed=1, frame=1000,
                           _run_provenance={"manifest_sha256": "b" * 64})
    assert row["native"]["run_provenance"]["manifest_sha256"] == "b" * 64
    assert "_run_provenance" not in row


def test_an_unknown_baseline_states_that_it_has_none():
    row = NORMALIZE.record(cell="x", baseline="not-a-baseline", family="rlvigen", seed=1, frame=0)
    assert row["conventions"] is None


# --- the evaluation-policy axis, added 2026-09-02 ---------------------------------------------

AUDIT_STATE = _load(ROOT / "scripts" / "audit_eval_state.py", "audit_eval_state")


@pytest.mark.parametrize("baseline", BASELINES)
def test_every_record_declares_how_its_policy_was_read(baseline):
    """Four baselines sample their evaluation actions; eight others take the mode. A return produced by
    sampling and one produced by a mode are different estimators of different things, and until
    this field existed nothing in the data said which had been used."""
    mode = NORMALIZE.CONVENTIONS[baseline]["eval_policy_mode"]
    assert mode in {"mode", "sample"}, mode


def test_the_policy_mode_agrees_with_the_evaluator_audit():
    audited = AUDIT_STATE.STATE
    for baseline, entry in NORMALIZE.CONVENTIONS.items():
        described = audited[baseline]["policy_mode"]
        if baseline == "ppg" and "not chosen anywhere" in described:
            # PPG's repository ships no evaluator; the completed offline path is ours and is
            # independently pinned to its stochastic PpoModel.act call in eval_grid.py.
            continue
        if entry["eval_policy_mode"] == "sample":
            assert "STOCHASTIC" in described, baseline
        elif entry["eval_policy_mode"] == "mode":
            assert described.startswith("deterministic"), baseline


def test_the_two_baselines_needing_evaluator_work_are_named():
    """Neither needs a policy written. `ctrl`'s eval loop calls a discrete-only helper while
    `algo.select_action` already handles both action spaces; `ppg` has the distribution and no
    loop. Naming them keeps two work items from becoming folklore -- and the first version of this
    test said "authored", which overstated both."""
    needs_work = {b for b, e in AUDIT_STATE.STATE.items() if e["reusable"].startswith("ADAPT")}
    assert needs_work == {"ppg", "ctrl"}, needs_work
    assert not any(e["reusable"].startswith("NO") for e in AUDIT_STATE.STATE.values()), \
        "nothing should be unreachable now that ctrl is repointable rather than unusable"


def test_eval_state_audit_anchors_still_hold():
    import subprocess, sys as _sys
    result = subprocess.run([_sys.executable, str(ROOT / "scripts" / "audit_eval_state.py"), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


# --- the aggregator must not answer "what is outstanding?" more narrowly than the record --------

def test_open_findings_are_visible_in_the_aggregator():
    """`open_decisions.py` read four sources and not REGISTER.md, so a finding recorded there and
    never dispositioned was invisible to the one command that claims to list what is outstanding.
    Its own disclaimer -- "a decision written down nowhere is invisible here" -- was understating
    it: these were written down."""
    aggregator = _load(ROOT / "scripts" / "open_decisions.py", "open_decisions")
    findings = aggregator.undispositioned_findings()
    assert findings, "no open findings parsed from REGISTER.md; the parser or the format moved"
    dates = {date for date, _ in findings}
    assert any(d.startswith("2026-09-02") for d in dates), "today's open findings are missing"
    for date, headline in findings:
        assert headline.strip(), f"{date}: empty headline"
        assert not headline.startswith("|"), f"{date}: cell splitting is off"


def test_open_findings_are_not_counted_as_decisions():
    """A finding needing a run is not a decision waiting on a person, and merging the two would
    make the decision count meaningless."""
    source = (ROOT / "scripts" / "open_decisions.py").read_text()
    assert "Not decisions and not counted above" in source
    assert "findings = undispositioned_findings()" in source


# --- the offline grid: the harness the base version calls for ---------------------------------

def test_the_grid_refuses_a_checkpoint_whose_x_axis_is_unknown(tmp_path, capsys):
    """A record whose frame is unknown is not a record. P18 stamps snapshot_<frame>.pt, so the
    frame is recoverable there; a bare snapshot.pt must be told."""
    import subprocess, sys as _sys
    bare = tmp_path / "snapshot.pt"
    bare.write_bytes(b"not a real checkpoint")
    result = subprocess.run(
        [_sys.executable, str(ROOT / "scripts" / "eval_grid.py"), "--snapshot", str(bare)],
        capture_output=True, text=True, timeout=180)
    assert result.returncode == 1
    assert "--frame is required" in result.stderr


def test_the_grid_reads_the_frame_from_a_stamped_snapshot_name():
    """P18's stamped files carry it, which is the whole reason the cadence form was worth having."""
    source = (ROOT / "scripts" / "eval_grid.py").read_text()
    assert 'stem.startswith("snapshot_")' in source
    assert "int(stem[9:])" in source


def test_the_grid_emits_per_scene_rows_beside_the_aggregate():
    """A mean over ten scenes hides which scene collapsed, and that is usually the finding."""
    source = (ROOT / "scripts" / "eval_grid.py").read_text()
    assert 'scene_set=str(scene)' in source, "per-scene rows are not emitted"
    assert 'per_scene_mean' in source, "the aggregate does not carry its per-scene breakdown"
    assert 'phase="offline-eval"' in source, "records do not distinguish offline from training-time"


def test_the_grid_states_which_families_it_covers():
    """The production grid names all seven evaluator families and the historical audit remains linked."""
    source = (ROOT / "scripts" / "eval_grid.py").read_text()
    assert "It evaluates all seven implementation families" in source
    assert "audit_eval_state" in source


# --- the W&B sink reader -------------------------------------------------------------------
# `ctrl` and `alda` log metric dicts that reach no other file. The shim captures them; these pin
# the two properties that make the capture safe to read.

def _sink_cell(tmp_path, lines):
    (tmp_path / "wandb_offline.jsonl").write_text("\n".join(lines) + "\n")
    return tmp_path


def test_wandb_sink_merges_calls_that_share_a_step(tmp_path):
    """ctrl issues three `wandb.log` calls per iteration at ONE step.

    Emitting three records would triple the row count and scatter one instant across rows a
    reader has to rejoin on `wandb_step` -- and rejoining is exactly the operation that goes
    wrong silently when one of the three is missing.
    """
    import json as _json
    cell = _sink_cell(tmp_path, [
        _json.dumps({"_event": "log", "step": 4096, "data": {"Door/pg_loss": 0.5}}),
        _json.dumps({"_event": "log", "step": 4096, "data": {"Door/ep_return_200": 3.0}}),
        _json.dumps({"_event": "log", "step": 8192, "data": {"Door/pg_loss": 0.25}}),
        "{ this line is truncated",          # a killed process must not cost the rest of the file
    ])
    rows = NORMALIZE.read_wandb_sink(cell, {"baseline": "ctrl", "family": "ctrl", "seed": "1",
                                            "cell": "ctrl-s1"})
    assert len(rows) == 2, f"expected one record per step, got {len(rows)}"
    first = rows[0]["native"]
    assert first["Door/pg_loss"] == 0.5 and first["Door/ep_return_200"] == 3.0, (
        "both calls at step 4096 must land in ONE record; got " + repr(first))
    assert rows[0]["frame"] == 4096


def test_wandb_sink_promotes_nothing_to_a_shared_column(tmp_path):
    """The whole point of the reader, and the way it would quietly become wrong.

    `Door/ep_return_200` is ctrl's `Eprew200`: a trailing window over ~200 episodes of SUCCESSIVE
    policies, which COMPARABILITY_CONTRACT §5d records as a different estimand from every other
    baseline's saved-policy evaluation. A future edit that "helpfully" maps it to
    `episode_return_mean` would pool it into a cross-baseline column and put a declared
    difference back underground -- while making every table look more complete.
    """
    import json as _json
    cell = _sink_cell(tmp_path, [_json.dumps(
        {"_event": "log", "step": 1, "data": {"Door/ep_return_200": 3.0, "Door/success": 1.0}})])
    row = NORMALIZE.read_wandb_sink(cell, {"baseline": "ctrl", "family": "ctrl", "seed": "1",
                                           "cell": "ctrl-s1"})[0]
    assert row["episode_return_mean"] is None, "a native key was promoted to the shared return column"
    assert row["success_rate"] is None, "a native key was promoted to the shared success column"
    assert row["phase"] == "native-metrics"
    assert row["native"]["Door/ep_return_200"] == 3.0, "the value must still be reachable, verbatim"


# --- C61 policy health, across the four continuous PPO heads -------------------------------
# `scripts/metrics.py::gaussian_policy_health` says in its own comment that it exists "so the four
# PPO-family baselines report the same quantity rather than four near-misses of it". For a while
# only two of the four called it, and nothing failed: a diagnostic that is absent looks exactly
# like one whose value never moved. This is that guard.

CONTINUOUS_PPO_HEADS = {
    "idaac": "runnable/idaac/train.py",
    "ibac_sni": "runnable/ibac_sni/torch_rl/scripts/train.py",
    "ppg": "runnable/ppg/phasic_policy_gradient/ppo.py",
    "ctrl": "runnable/ctrl/train_ppo.py",
}


@pytest.mark.parametrize("baseline", sorted(CONTINUOUS_PPO_HEADS))
def test_each_continuous_ppo_head_reports_shared_policy_health(baseline):
    """The four unsquashed-Gaussian heads, and only those four.

    The squashed families (`rad`/`soda`/`alda` and the RL-ViGen five) are deliberately absent:
    `boundary_fraction` is the mass outside the action box, and a tanh puts that at zero by
    construction, so the same call there would report a constant and read as evidence.
    """
    source = (ROOT / CONTINUOUS_PPO_HEADS[baseline]).read_text(errors="replace")
    assert "gaussian_policy_health" in source, (
        f"{baseline} does not call the shared policy-health definition; a private near-miss of it "
        "is the thing scripts/metrics.py exists to prevent")


def test_ppg_separates_the_clamped_policy_from_its_raw_parameter():
    """PPG is the only one of the four that clamps, so its `mean_log_std` is not idaac's.

    `distr_builder.py:31` clips the log-stdev to [-5, 2] before exponentiating. Logging the raw
    parameter under the shared key would put a DIFFERENT quantity in a column named the same as
    three others -- and once the clamp binds, the raw value keeps climbing while the policy that
    acted does not move at all.
    """
    source = (ROOT / CONTINUOUS_PPO_HEADS["ppg"]).read_text(errors="replace")
    assert "log_std_raw_mean" in source and "log_std_clamped_fraction" in source, (
        "ppg must report the raw parameter under its OWN keys, and report whether the clamp is "
        "binding -- a bound clamp cancels the entropy gradient with no logged number moving")
    assert "clip(-5.0, 2.0)" in source, "the shared keys must be computed on the CLAMPED values"


def test_wandb_sink_finds_the_step_when_it_is_a_data_field(tmp_path):
    """ctrl passes `step=` on one of its three calls per iteration and not on the other two.

    The other two carry the same count as a data field named `<env_name>/step`. Reading only the
    kwarg scattered one iteration across three records — the losses on a stepped one, the two
    return summaries on unstepped ones — which is exactly what the merge exists to prevent, and it
    did so while the docstring claimed merging. Verified against a real archive
    (bt1fer7809i7bpob7g2f): six records collapsed to two of twelve keys each.
    """
    import json as _json
    cell = _sink_cell(tmp_path, [
        _json.dumps({"_event": "log", "step": 4112, "data": {"Door/total_loss": 1.5}}),
        _json.dumps({"_event": "log", "data": {"Door/ep_return_200": 3.0, "Door/step": 4112}}),
        _json.dumps({"_event": "log", "data": {"Door/ep_return_all": 2.0, "Door/step": 4112}}),
    ])
    rows = NORMALIZE.read_wandb_sink(cell, {"baseline": "ctrl", "family": "ctrl", "seed": "1",
                                            "cell": "ctrl-s1"})
    assert len(rows) == 1, f"one iteration must be one record, got {len(rows)}"
    native = rows[0]["native"]
    for key in ("Door/total_loss", "Door/ep_return_200", "Door/ep_return_all"):
        assert key in native, f"{key} missing; the data-field step was not used to merge"
    assert rows[0]["frame"] == 4112, "the data-field step must also become the record's frame"


# --- the conditions our evaluators' correctness rests on ---------------------------------------
# EVAL-DECOMPOSITION terms 3 and 5: our offline evaluators do not toggle module train/eval state
# for most families, and that is only safe because no train/eval-sensitive layer sits on any
# action path, and because nothing normalises OBSERVATIONS at eval. Both were verified by reading
# on 2026-09-04 across all twelve. Neither is guaranteed by anything -- each is one default flag
# away from being false, and the failure would be silent: BatchNorm at batch size 1 in train mode
# normalises a sample by its own statistics and still returns an action.

def test_batchnorm_stays_off_the_action_path_in_ppg_and_ibac_sni():
    """Both ship BatchNorm behind a default-off flag. If a default flips, our evaluators break."""
    impala = (ROOT / "runnable" / "ppg" / "phasic_policy_gradient" / "impala_cnn.py")
    if impala.exists():
        assert "batch_norm=False" in impala.read_text(encoding="utf-8"), (
            "ppg's ImpalaCNN no longer defaults batch_norm to False; its BatchNorm2d layers would "
            "be constructed and our evaluator does not put the model in eval mode")
    train = (ROOT / "runnable" / "ibac_sni" / "torch_rl" / "scripts" / "train.py")
    if train.exists():
        body = train.read_text(encoding="utf-8")
        assert 'default=False' in body and "use_bn" in body, (
            "ibac_sni's --use_bn no longer defaults to False; model_type 'default2' would build "
            "nn.BatchNorm2d on the acting CNN")


def test_no_baseline_normalises_observations_at_eval():
    """`ob=False` is why a checkpoint's saved `ob_rms` can be ignored by our evaluators.

    idaac's checkpoint literally stores `[actor_critic, envs.ob_rms]`. Restoring the weights and
    silently dropping the observation statistics would be a textbook silent eval bug -- it is
    harmless here only because `VecNormalize` is constructed with `ob=False`, so the statistics
    were never applied. That is the fact this pins.
    """
    for rel in (("runnable", "idaac", "ppo_daac_idaac", "envs.py"),
                ("runnable", "ctrl", "vec_env.py")):
        path = ROOT.joinpath(*rel)
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8")
        if "VecNormalize(" not in body:
            continue
        assert "ob=False" in body, (
            f"{path.name} constructs VecNormalize without ob=False; observations would be "
            "normalised during training and our offline evaluator restores no statistics")
