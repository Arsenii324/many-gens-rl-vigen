#!/usr/bin/env python3
"""Is the fleet launchable? Recomputed from the tree, not remembered from a document.

[Claude 2026-09-05] Two external reviews independently returned "no-go", and both said the same
thing about *why the question was hard to answer*: the launch decision is currently assembled by
reading several Markdown files that contain mutually inconsistent historical states. The second
review's gate #14 asks for "one machine-readable frozen production manifest" instead of asking the
run operator to interpret history. This is that.

It follows the pattern this project already trusts -- `requirements.py`, `open_decisions.py`,
`audit_implementations.py` -- where the instrument recomputes rather than restates. Prose goes
stale silently; a check that reads the tree fails loudly.

Three statuses, and the distinction is the point:

    PASS            verified in the tree right now
    FAIL            verified broken right now -- this is work, and it is ours
    OWNER           not broken; waiting on a decision only the owner can make

A gate that cannot be decided mechanically says so rather than guessing. `OWNER` is never counted
as progress and never as a defect: conflating "nobody has decided" with "something is wrong" is how
this project's status documents drifted in the first place.

    python scripts/production_gates.py
    python scripts/production_gates.py --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
from pathlib import Path

# Resolve the repository from this file, not from the caller's cwd, before importing local
# packages.  Direct absolute-path execution does not otherwise put the repository root on sys.path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datasphere.native.evaluator_identity import (
    canonical_evaluation_scope,
    evaluator_family_code_revision,
    evaluator_family_config_revision,
    evaluator_family_revision,
    measurement_revision,
    scope_revision,
)

IBAC_PROCS_SMOKE_EVIDENCE = ROOT / "results" / "validation" / "ibac_sni-procs16-v125.json"

PASS, FAIL, OWNER = "PASS", "FAIL", "OWNER"


def _read(relative: str) -> str:
    path = ROOT / relative
    return path.read_text(errors="replace") if path.is_file() else ""


def _grep(relative: str, pattern: str) -> bool:
    return re.search(pattern, _read(relative)) is not None


# --- the gates -----------------------------------------------------------------------------------
# Each returns (status, detail). Ordered as the second review ordered them: the ones that make the
# numbers wrong come before the ones that make them hard to interpret.


def gate_evaluation_pairing():
    """Review 2 gate #1. The claim that one eval seed gives every baseline identical door
    placements is false while one evaluator probes with reset()+step() and the other does not."""
    probes = _grep("scripts/eval_across_scenes.py", r"env\.step\(np\.zeros")
    per_episode = _grep("scripts/eval_grid.py", r"episode_index|condition_seed|per_episode_seed")
    if per_episode:
        return PASS, "per-episode condition seeding present in the grid evaluator"
    if probes:
        return FAIL, ("eval_across_scenes still probes with reset()+step(), consuming C69 global "
                      "draws the grid evaluator does not -- so the two families see different "
                      "placements for the same seed. Fix is per-episode condition seeds, not a "
                      "single reseed after the probe")
    return FAIL, "no per-episode condition seeding; pairing rests on a single initial seed"


def gate_regime_verification_fail_closed():
    """Review 2 gate #2 / review 1 #20. A cell whose intervention cannot be established must not
    emit a row -- the failure it hides produces retention near 1.0, which reads as invariance."""
    source = _read("scripts/eval_grid.py")
    if not source:
        return FAIL, "eval_grid.py absent"
    if "strict" in source and re.search(r"strict\s*=\s*True", source):
        return PASS, "strict verification present on production call sites"
    return FAIL, "verification abstains and still records the cell (fail-open)"


def gate_train_eval_rng_isolation():
    """Review 2 gate #3. Online evaluation resets consume the same global NumPy stream that sets
    training door placements, so the evaluation cadence is part of the training experiment."""
    try:
        descriptors = json.loads(_read("datasphere/native/families.json"))
        periodic = [name for name, entry in descriptors.items()
                    if not name.startswith("_") and entry.get("production", {}).get("eval_every") is not None]
        unisolated = [name for name, entry in descriptors.items()
                      if not name.startswith("_") and entry.get("production", {}).get(
                          "online_eval_rng_isolated") is True
                      and name == "ctrl" and "np.random.get_state()" not in _read("runnable/ctrl/train_ppo.py")]
    except Exception as error:
        return FAIL, f"could not read production evaluation settings: {type(error).__name__}"
    if not periodic and not unisolated:
        return PASS, ("online evaluation is disabled, or its PLACEMENT stream is isolated. Narrower "
                      "than it used to read: for ctrl the guard restores NumPy only, while "
                      "select_action rebinds the JAX key that update_ppo/update_cluster then "
                      "consume. That advance is upstream's own (ctrl_public train_ppo.py:193,202 "
                      "is byte-identical in this respect), so splitting the key would be OUR "
                      "deviation, not a repair -- it is deliberately not patched")
    if unisolated:
        return FAIL, f"RNG-isolation is declared but not implemented for: {', '.join(unisolated)}"
    return FAIL, ("online evaluation still runs during production training. Upstream's own "
                  "utils.Every returns False when `every is None`, so `eval_every_frames: null` "
                  "switches it off with no code change -- and offline checkpoint evaluation is "
                  "already the measurement (EVAL-PROTOCOL 0)")


def gate_online_eval_disable_is_executed():
    """The DESCRIPTOR saying `eval_every: null` is not evidence that no evaluation runs.

    External review 21, P0, and it was right: the runner implemented "disabled" by passing
    2147483647 as the cadence, and every one of these loops gates on `step % cadence == 0`, which
    is TRUE at step 0 for any cadence. So drqv2, svea, drq, sgqn, curl, rad, soda and alda each ran
    an unrequested initial evaluation -- consuming the process-global NumPy stream Door's placement
    draws from, by a different amount per family -- while `gate_train_eval_rng_isolation` passed by
    reading the descriptor rather than the executed path. A gate that cannot see the mechanism it
    certifies is the failure mode this file exists to prevent, so this one reads the mechanism.

    Two acceptable mechanisms, both checked here:
      * an upstream disable path -- RL-ViGen's `utils.Every` returns False for a None cadence, so
        `eval_every_frames=null` needs no source change; or
      * an explicit `NATIVE_DISABLE_ONLINE_EVAL` guard at the call site, for loops whose cadence is
        an int by construction (argparse, a typed spec).
    """
    try:
        descriptors = json.loads(_read("datasphere/native/families.json"))
    except Exception as error:
        return FAIL, f"could not read families.json: {type(error).__name__}"
    guarded_sources = {
        "dmc_gb": "runnable/dmc_gb/src/train.py",
        "alda": "runnable/alda/trainers/alda_trainer.py",
    }
    bad = []
    for family, entry in descriptors.items():
        if family.startswith("_") or not isinstance(entry, dict):
            continue
        production = entry.get("production") or {}
        has_option = any("{eval_every}" in str(option) for option in entry.get("options", []))
        if production.get("eval_every") is not None or not has_option:
            continue
        spelling = str(production.get("online_eval_disabled_spelling", "2147483647"))
        if spelling == "null":
            if "if self._every is None" not in _read("RL-ViGen-upstream/utils.py"):
                bad.append(f"{family}: spelled null, but utils.Every no longer honours a None cadence")
            continue
        source = guarded_sources.get(family)
        if source is None:
            bad.append(f"{family}: numeric cadence {spelling} and no known guarded call site")
            continue
        if "NATIVE_DISABLE_ONLINE_EVAL" not in _read(source):
            bad.append(f"{family}: numeric cadence {spelling} and {source} has no disable guard, "
                       "so step 0 still evaluates")
    if "NATIVE_ONLINE_EVAL_DISABLED_SPELLING" not in _read("datasphere/native/run_probe.sh"):
        bad.append("run_probe.sh still hardcodes the cadence instead of taking the family's spelling")
    if bad:
        return FAIL, "; ".join(bad)
    return PASS, ("disabling online evaluation is executed, not just declared: rlvigen through "
                  "upstream's own None-cadence path, dmc_gb and alda through an explicit guard "
                  "at the call site. A numeric sentinel alone evaluates at step 0")


def gate_idaac_level_seed():
    """Review 2 gate #4. A worker slot cannot be the same-instance identity when every episode
    resets to an independent physical instance."""
    envs = _read("runnable/idaac/ppo_daac_idaac/envs.py")
    if not envs:
        return FAIL, "idaac clone absent"
    if re.search(r"episode|reset_count|instance_id", envs) and "_LevelSeed" in envs:
        return PASS, "level identity appears episode-scoped"
    return FAIL, ("_LevelSeed is a constant per worker, so before_update pairs observations across "
                  "episode boundaries and labels their order from nsteps, which resets each "
                  "episode. Demonstrated in tests/test_port_semantics_defects.py")


def gate_ppg_auxiliary_kl():
    """Review 2 gate #5. The reduction that was right for a Categorical became wrong when the port
    gave the distribution an action dimension."""
    source = _read("runnable/ppg/phasic_policy_gradient/ppg.py")
    if not source:
        return FAIL, "ppg clone absent"
    if re.search(r"kl_divergence\([^)]*\).*?\.sum\(-1\)", source, re.S):
        return PASS, "auxiliary KL sums over the action dimension before averaging"
    return FAIL, ("kl_divergence(...).mean() averages over 7 action dims where the PPO losses sum, "
                  "so beta_clone is ~7x too weak. Ratio verified exactly 7.0 in "
                  "tests/test_port_semantics_defects.py")


def gate_ibac_sni_competence():
    """Review 2 gate #6. Historical entropy evidence does not establish final-config competence."""
    return OWNER, ("entropy_coef=0 removed runaway in a 25k historical procs=1 cell, but that "
                   "artifact does not bind --beta 1e-4 or the current payload. No exact-final "
                   "procs=16 V100 competence evidence exists. Needs a pilot at intended settings "
                   "long enough to show learning, not merely absence of explosion")


def gate_ctrl_config_binding():
    """Review 2 gate #7. Flax from_bytes needs a target structure, so the checkpoint alone does not
    establish which model it is."""
    source = _read("scripts/eval_grid.py")
    if re.search(r"CTRL_DEFAULTS|num_clusters\s*=\s*200|n_att_heads\s*=\s*2", source):
        return FAIL, ("eval_grid holds a second copy of ctrl's hyperparameters (CTRL_DEFAULTS). It "
                      "matches today, but families.json passes cluster_len as a template, so "
                      "nothing prevents the evaluator reconstructing a different model")
    return PASS, "no duplicated ctrl configuration in the evaluator"


def gate_idaac_evaluator_device():
    """Review 2 gate #8."""
    source = _read("scripts/eval_grid.py")
    block = re.search(r"def run_scene_idaac.*?(?=\ndef )", source, re.S)
    if not block:
        return FAIL, "run_scene_idaac not found"
    if re.search(r"device\s*=\s*torch\.device\(\s*[\"']cpu", block.group(0)):
        return FAIL, "run_scene_idaac hardcodes cpu and discards the requested --device"
    return PASS, "idaac evaluator honours the requested device"


#: All seven evaluator families a real fleet cell executes. Distinct from the twelve BASELINES:
#: rlvigen covers five (drqv2/svea/drq/sgqn/curl) and dmc_gb covers two (rad/soda) through one path.
EVALUATOR_FAMILIES = ("rlvigen", "dmc_gb", "idaac", "alda", "ppg", "ibac_sni", "ctrl")


def _validation_entry_problem(root: Path, family: str, entry: dict,
                              code_revision: str, config_revision: str,
                              static_revision: str) -> str | None:
    """Return a fail-closed explanation for one scope-attested validation entry.

    This binds the ledger claim to retained evaluator rows.  It cannot establish that the job or
    environment was honest; those remain review obligations, as does the dynamic import manifest.
    """
    required = (
        "validation_kind", "evaluator_revision", "evaluator_scope",
        "evaluator_scope_revision", "evaluator_measurement_revision",
        "evaluation_records_path", "evaluation_records_sha256",
    )
    missing = [key for key in required if key not in entry or entry[key] in (None, "")]
    if missing:
        return "missing scope attestation fields: " + ", ".join(missing)
    if entry["validation_kind"] != "functional_endpoint":
        return "validation_kind is not functional_endpoint"

    scope = entry["evaluator_scope"]
    try:
        canonical = canonical_evaluation_scope(scope)
    except (TypeError, ValueError) as error:
        return f"invalid evaluator_scope: {error}"
    if canonical != scope:
        return "evaluator_scope is not canonical"
    if canonical["family"] != family:
        return f"evaluator_scope family is {canonical['family']!r}, expected {family!r}"
    if canonical["eval_scope"] != "endpoint":
        return "evaluator_scope is not an endpoint scope"
    if entry["evaluator_revision"] != static_revision:
        return "evaluator_revision does not match the current family revision"
    expected_scope_revision = scope_revision(canonical)
    if entry["evaluator_scope_revision"] != expected_scope_revision:
        return "evaluator_scope_revision does not match evaluator_scope"
    expected_measurement_revision = measurement_revision(static_revision, expected_scope_revision)
    if entry["evaluator_measurement_revision"] != expected_measurement_revision:
        return "evaluator_measurement_revision does not match static revision and scope"

    relative = entry["evaluation_records_path"]
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        return "evaluation_records_path must be a relative repository path"
    root = root.resolve()
    artifact = (root / relative).resolve()
    try:
        artifact.relative_to(root)
    except ValueError:
        return "evaluation_records_path escapes the repository"
    try:
        mode = artifact.lstat().st_mode
    except OSError as error:
        return f"evaluation evidence is unreadable: {error}"
    if not stat.S_ISREG(mode):
        return "evaluation evidence is not a regular file"
    try:
        raw = artifact.read_bytes()
    except OSError as error:
        return f"evaluation evidence is unreadable: {error}"
    digest = hashlib.sha256(raw).hexdigest()
    if entry["evaluation_records_sha256"] != digest:
        return "evaluation evidence SHA256 does not match"

    rows = []
    try:
        text = raw.decode("utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                return f"evaluation JSONL line {line_number} is not an object"
            rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return f"evaluation evidence is malformed JSONL: {error}"
    applicable = [row for row in rows if row.get("phase") == "offline-eval"]
    if not applicable:
        return "evaluation evidence has no offline-eval rows"
    expected_row_values = {
        "family": family,
        "baseline": canonical["baseline"],
        "evaluator_revision": static_revision,
        "evaluator_code_revision": code_revision,
        "evaluator_config_revision": config_revision,
        "evaluator_scope": canonical,
        "evaluator_scope_revision": expected_scope_revision,
        "evaluator_measurement_revision": expected_measurement_revision,
    }
    for index, row in enumerate(applicable):
        mismatched = [key for key, expected in expected_row_values.items()
                      if row.get(key) != expected]
        if mismatched:
            return (f"offline-eval row {index} disagrees with ledger identity: "
                    + ", ".join(mismatched))
    return None


def gate_shared_evaluator_validated():
    """Review 2 gate #9 / review 1 #9.

    [Corrected 2026-09-05, twice. First: this said "drqv2 remains discharged" while suspending
    idaac, on reasons that were family-agnostic -- exempted by inattention, not argument. Second:
    it then hardcoded "ZERO of twelve" as the answer FOREVER, which is the identical mechanism --
    an instrument whose verdict does not track the world it claims to check. A gate that always
    returns the same string regardless of what has actually run is not a gate, it is a comment with
    extra steps.

    Now reads `validated_evaluator_families.json`, a ledger written when a human-reviewed artifact
    proves the functional endpoint path (complete diagnostics, physical pairing, 0 unpaired).
    Each entry must bind a shallow-but-explicit endpoint scope and its measurement revision to the
    current family closure.  A common evaluator hash cannot make this claim: it missed CTRL's
    vec_env and overreacted to IBAC's training-only checkpoint driver.
    """
    ledger_path = ROOT / "datasphere" / "native" / "validated_evaluator_families.json"
    try:
        ledger = json.loads(ledger_path.read_text())
    except (OSError, ValueError) as error:
        return OWNER, f"could not read the validation ledger: {type(error).__name__}"
    sys.path.insert(0, str(ROOT))

    current_hits, stale, missing, invalid = [], [], [], []
    for family in EVALUATOR_FAMILIES:
        entry = ledger.get(family)
        if not entry:
            missing.append(family)
            continue
        if not isinstance(entry, dict):
            invalid.append(f"{family} (ledger entry is not an object)")
            continue
        try:
            code_revision = evaluator_family_code_revision(ROOT, family)
            config_revision = evaluator_family_config_revision(ROOT, family)
            static_revision = evaluator_family_revision(ROOT, family)
        except Exception as error:
            return OWNER, f"could not compute {family} evaluator identity: {error}"
        if (entry.get("family_code_revision") != code_revision or
                entry.get("family_config_revision") != config_revision or
                entry.get("evaluator_revision") != static_revision):
            stale.append(family)
            continue
        problem = _validation_entry_problem(ROOT, family, entry, code_revision,
                                            config_revision, static_revision)
        if problem:
            invalid.append(f"{family} ({problem})")
        elif not (entry.get("paired") and entry.get("diagnostics_complete") and
                  entry.get("runtime_imports_checked")):
            missing.append(f"{family} (recorded but not paired+complete)")
        else:
            current_hits.append(family)

    if not missing and not stale and not invalid:
        return PASS, (f"all {len(EVALUATOR_FAMILIES)} evaluator families validated on their current "
                      f"family closures: {', '.join(current_hits)}")
    return OWNER, (
        f"{len(current_hits)}/{len(EVALUATOR_FAMILIES)} evaluator families validated on their CURRENT "
        f"family closures: {', '.join(current_hits) or 'none'}. "
        + (f"On a SUPERSEDED revision, needs re-run: {', '.join(stale)}. " if stale else "")
        + (f"Never validated: {', '.join(missing)}. " if missing else "")
        + (f"Invalid attestation: {', '.join(invalid)}." if invalid else ""))


def gate_estimands_frozen():
    """Review 2 gates #10, #11. Time-limit semantics and the retention estimand.

    [Corrected 2026-09-05.] C1 ("the largest comparability defect found") is folded into this row
    and was under-described here: its FALSE-CERTIFICATION half is already fixed
    (`rlgen/protocol.py`'s `TIME_LIMIT_HANDLING`, per-baseline, no longer hashes drq and rad
    alike), and its substantive half already has a reasoned recommendation ("declare and quantify,
    don't equalise" -- RESEARCH-FRAME.md, since equalising would stop these being the authors' own
    settings). Still correctly OWNER: a reasoned recommendation is not a ratification, and this
    project's own governance model keeps that distinction regardless of how settled the analysis
    looks (docs/CONSTRUCTION.md#c1).
    """
    return OWNER, ("P-C76 open; time-limit split is 3 bootstrap / 9 terminal (C1) -- the false-"
                   "certification half is already fixed and the substantive half already has a "
                   "reasoned recommendation (declare and quantify, don't equalise); formal "
                   "ratification of that recommendation is what remains. Retention as a raw "
                   "return ratio is not invariant to reward offsets and Door's reward is shaped "
                   "with a non-zero floor. Separate appearance from scene generalisation")


def gate_seed_policy_frozen():
    """Review 2 gate #12. Outcome-dependent seed allocation is post-selection bias.

    [Corrected 2026-09-05, external review 14 section 23: found this message describing the OLD
    adaptive-allocation problem as if it were still the live plan, when `EVAL-PROTOCOL.md` already
    states the operational default that replaced it. The message must describe the CURRENT state
    needing ratification, not a decision already made -- an OWNER row whose text argues against a
    superseded default reads as more unresolved science than actually remains.]
    """
    protocol = _read("docs/EVAL-PROTOCOL.md")
    if re.search(r"fixed 3 for every reported row", protocol, re.IGNORECASE):
        return OWNER, ("operational default is fixed n=3 for every reported row, no outcome-"
                       "dependent allocation (EVAL-PROTOCOL.md); awaiting formal owner ratification, "
                       "not a still-open design question")
    return OWNER, ("adaptive allocation ('one seed everywhere, then concentrate where live') is "
                   "outcome-dependent sampling and must be replaced by a fixed minimum for every "
                   "reported row, or a predeclared stopping rule")


def gate_source_tree_frozen():
    """Review 2 gate #13 / review 1 #3. Provenance ambiguity becomes experimental ambiguity the
    moment runs start."""
    # [Corrected 2026-09-05, found by the fourth external review: this read `.stdout` and never
    # checked `returncode`. Where git FAILS -- no repository, as in a packaged review artifact --
    # stdout is empty, the line count is zero, and the gate returned PASS. It converted
    # failure-to-check into a clean bill of health, which is the precise failure this file exists
    # to prevent and which its own docstring warns about. Fails closed now.]
    try:
        proc = subprocess.run(["git", "-C", str(ROOT), "status", "--short"],
                              capture_output=True, text=True, timeout=30)
    except Exception as error:
        return FAIL, f"could not read git state: {type(error).__name__}"
    if proc.returncode != 0:
        return FAIL, ("git could not report the tree state "
                      f"(exit {proc.returncode}: {proc.stderr.strip()[:120] or 'no stderr'}). "
                      "A tree whose provenance cannot be established is not a frozen tree; this "
                      "gate fails closed rather than reading silence as cleanliness")
    dirty = proc.stdout.strip()
    count = len([line for line in dirty.splitlines() if line.strip()])
    if count == 0:
        return PASS, "working tree clean; the commit identifies the code exactly"
    return FAIL, (f"{count} uncommitted paths. No commit currently means 'the code whose results "
                  "we report', and two agents' changes are interleaved in this tree")


def gate_environment_manifest():
    """Review 2 gate #13 (second half) / review 1 #40 / C29."""
    lock = _read("datasphere/native/source-lock.json")
    if re.search(r"container|image_digest|dependenc|resolved_packages", lock):
        return PASS, "source lock records the environment as well as the source"
    return FAIL, ("source-lock.json pins source and assets but no dependency versions or container "
                  "digest. The job already captures resolved_packages.json / environment.json / "
                  "egl.json -- they are simply not bound to the records or the protocol hash")


def gate_production_canary():
    """Review 2 gate #15. The full shape, once, per runtime family."""
    return OWNER, ("train -> checkpoint -> clean reload -> full offline grid -> records -> "
                   "statistics has never run end to end at production length for any family. The "
                   "longest real cell is 5.1 h; a 6e5 soda cell is projected at 45 h")


def gate_placement_provenance():
    """Review 3's addition. Pairing should be auditable from the records, not inferred from RNG
    theory -- this project has already had one stream asymmetry, and an episode-level witness is
    what would have caught it the same day."""
    source = _read("scripts/eval_grid.py")
    has_hash = re.search(r"placement_hash|placement_state|initial_state_hash|placement_witness", source)
    # [Corrected 2026-09-05, external review 7 §4] This used to accept a bare `episode_index`
    # anywhere in the file -- which matched a LOOP VARIABLE, so the gate reported that records
    # carry an episode id when no identifier reached a record at all. Match the emitted dict KEY
    # instead: a quoted key with a colon only appears where a record is being built.
    has_id = re.search(r'"eval_episode_ids?"\s*:', source)
    if has_hash and has_id:
        return PASS, "records carry an episode id and a realized-placement witness"
    if has_id:
        return FAIL, ("episode index is recorded but the realized Door placement is not, so pairing "
                      "remains inferred rather than provable")
    return FAIL, "neither an episode id nor a placement witness reaches the records"


def gate_release_suite_green():
    """No check is currently red, and none is red-but-tolerated.

    [Corrected 2026-09-05, found by the fifth external review.] This inspected exactly one file --
    `tests/test_docs_integrity.py` -- and grepped it for `xfail` ANYWHERE, so an unrelated xfail
    satisfied it and any other audit could be red while it reported PASS. It was named for the
    release suite and checked a corner of it.

    It still does not run the full suite (minutes, not gate-time). What it does now is run the fast
    audits that have actually been red, and say plainly what it did not check -- which is the
    distinction the old version elided.

    [Added 2026-09-05, CORRECTIONS #47/#61.] `test_descriptor_values_are_converted.py` joined the
    list after a NEW, different unconverted `d["cluster_len"]` use (`_ctrl_train_state`, added
    after the scanner already existed) reached a real remote job and burned it
    (`bt1s3hm3166ge2kgg93c`) before any test ran against the code that grew it. The scanner itself
    was fine -- it is a whole-file AST scan, not a one-line patch -- the gap was that nothing
    forced it to run between writing new evaluator code and submitting a job. It is 0.4s and
    string-only; it belongs here, not only in the full suite.
    """
    checked, red = [], []
    for label, cmd in (
            ("docs links", ["pytest", "-q",
                            "tests/test_docs_integrity.py::test_internal_links_resolve"]),
            ("eval cadence anchors", [sys.executable, "scripts/audit_eval_cadence.py", "--check"]),
            ("descriptor values converted", ["pytest", "-q",
                            "tests/test_descriptor_values_are_converted.py"])):
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180)
        except Exception as error:
            red.append(f"{label} (could not run: {type(error).__name__})")
            continue
        checked.append(label)
        if proc.returncode != 0:
            red.append(label)
    if red:
        return FAIL, ("red or unrunnable: " + ", ".join(red) +
                      ". NOTE this gate runs only the fast audits, not the full suite -- a green "
                      "here is not a release-suite pass")
    return PASS, ("fast audits green (" + ", ".join(checked) +
                  "). NOT the full suite: run `pytest tests/ -q` for that")

def gate_external_anchor():
    """Review 1 #30 / review 2 / review 3 all raise it: no published RL-ViGen number has been
    reproduced under matched conditions, and the original plan made a production cell double as the
    anchor -- which inverts the dependency.

    [Corrected 2026-09-06: this message was stale against DECISION-SHEET.md's own A9 revision
    (2026-09-05), which closed the "reproduce it as a separate run" question and left only
    ratification. A dedicated anchor-reproduction cell is no longer the plan -- a free
    acceptance test is. Do not re-read the old message as still describing what's missing.]
    """
    return OWNER, ("C48's ordering concern is answered without a dedicated cell, not left open: "
                   "RL-ViGen's own published Robosuite table gives drqv2 Door eval-easy 3.6 across "
                   "seeds {3,7,4,3,1} (range 1-7), read from the units-certified sheet "
                   "(notes/rlvigen-published-door-anchor.md; RETURNS, not success rates -- C33/Q2). "
                   "The stated criterion, fixed BEFORE the fleet runs as the reviews asked: the "
                   "fleet's own drqv2 seeds should fall inside that published range -- not "
                   "reproduce 3.6 itself, which two of their own three comparison methods "
                   "(CURL 6.6, DrQ 14.0) don't either, and which a random policy alone can produce "
                   "(our floor's max reaches 6.93). This makes the anchor a free check against "
                   "results the fleet produces anyway (DECISION-SHEET.md A9), not a prerequisite "
                   "job. OWNER only for ratifying that this counts as the anchor the reviews asked "
                   "for, and for the check itself once production drqv2 seeds exist")


def gate_scheduler_ram_invariant():
    """Review 3's class-level fix for the alda SIGKILL: a tier that cannot fit a family should fail
    at submission, not after burning the cell."""
    # [Corrected 2026-09-05: the first version of this gate searched plan_production.py and passed,
    # because a feasibility comparison does exist there (`ram <= tier["usable_ram_gib"]`, :225).
    # That PASS was not earned. alda was still submitted to a tier it cannot fit, because the cfg
    # was hand-written with `cloud-instance-type: gt4.1` and never went through the planner. The
    # surface that matters is the SUBMISSION path, not the cost model -- which is exactly the
    # reviewer's point about not relying on a human to notice the two disagree.]
    # [Corrected 2026-09-05, owner: production runs on DIFFERENT infrastructure — a plain Docker
    # container, not DataSphere, and not yet accessible. So this gate is scoped to PREPRODUCTION:
    # it protects the probe/pilot cells we are still running here. The production analogue is
    # `gate_production_renderer_verified` below, because what actually transfers to the new machine
    # is the memory FOOTPRINT and the C95 renderer requirement, not the tier table.]
    submit = _read("datasphere/native/job.sh")
    family = _read("datasphere/native/family.py")
    if "check-memory" in submit and re.search(r"def check_memory\(", family):
        return PASS, "submission validates the requested tier against the family's memory envelope"
    return FAIL, ("the planner compares RAM to the tier (plan_production.py:225) but the SUBMIT "
                  "path does not, so a hand-written cfg bypasses it -- which is how alda reached "
                  "gt4.1 and was SIGKILLed. Measured peak 14.73 GiB (bt1s7mph7hp31qcr1ilb) against "
                  "14.5 usable; the cost model already knew and nothing enforced it. Wanted: "
                  "requested RAM >= measured fixed peak + margin, checked at submit")


def gate_selected_scene_path_disabled():
    """Review 1 #37. A headline must not be computable from a performance-selected scene set."""
    source = _read("scripts/results_table.py")
    if not source:
        return PASS, "no legacy reporting path present"
    if re.search(r"for k in usable\b", source):
        return FAIL, "results_table still pools over performance-selected `usable` scenes"
    return PASS, "reporting pools a fixed scene set, not a selected one"


def gate_result_metadata_truthful():
    """Review 1 #7 -- the highest-priority defect either review found, because it is silent and it
    travels with every row. The conventions block stamps an `eval_policy_mode` onto results; for
    three families it disagreed with what the evaluator actually does."""
    conventions = _read("datasphere/native/normalize_curves.py")
    evaluator = _read("scripts/eval_grid.py")
    if not conventions:
        return FAIL, "normalize_curves.py absent"
    claimed_static = re.findall(r'"(\w+)":\s*\{[^}]*?"eval_policy_mode":\s*"([a-z-]+)"',
                                conventions, re.S)
    samples = {name for name in ("idaac", "ppg", "ibac_sni", "ctrl")
               if re.search(rf"run_scene_{name}.*?It SAMPLES", evaluator, re.S)}
    wrong = [(n, v) for n, v in claimed_static if n in samples and v != "sample"]
    if wrong:
        return FAIL, ("result metadata contradicts the evaluator for " +
                      ", ".join(f"{n} (says {v!r}, evaluator samples)" for n, v in wrong))
    return PASS, "eval_policy_mode agrees with what the evaluator does"


def gate_statistical_protocol_frozen():
    """Review 3 gate #7. The corrected protocol exists as a proposal; a proposal is not a freeze."""
    protocol = _read("docs/EVAL-PROTOCOL.md")
    if re.search(r"outer unit|training seed is the (only )?outer", protocol):
        return PASS, "the inference protocol is merged into the evaluation protocol"
    return OWNER, ("the corrected inference plan lives in "
                   "notes/proposal-inference-and-checkpoint-selection.md and is not merged: outer "
                   "unit = training seed (n=3, not 600 episodes), fixed-vs-random scene estimand, "
                   "a numeric competence threshold, and a missing-run policy all need freezing")


def gate_checkpoint_rule_frozen():
    """Review 3 gate #8 / review 1 #29."""
    protocol = _read("docs/EVAL-PROTOCOL.md")
    # [Corrected 2026-09-05, twice, same session -- self-caught before it stood.] First found: the
    # regex was case-sensitive against a doc that capitalises sentence starts ("Endpoint is the
    # headline"), so PASS was structurally unreachable. Made it case-insensitive, which immediately
    # produced a live false PASS -- the exact line it now matched sits under EVAL-PROTOCOL.md's own
    # "Current operational defaults ... awaiting owner settlement" heading. A recommendation being
    # WRITTEN DOWN is not the same as being RATIFIED, and this gate must not conflate the two: the
    # two-layer model this project runs on keeps every operational default open at the ratification
    # surface regardless of how well-argued it is. Matches `gate_seed_policy_frozen`'s fix: always
    # OWNER, describe the current default accurately rather than a superseded one, never auto-PASS
    # from doc text alone.
    if re.search(r"endpoint is the headline|Headline = (the )?exact endpoint", protocol, re.IGNORECASE):
        return OWNER, ("operational default is endpoint-as-headline, trajectory descriptive, no "
                       "selected-best column (EVAL-PROTOCOL.md); awaiting formal owner ratification. "
                       "Any future selected-best column additionally needs reserved validation "
                       "episodes, equal candidate opportunity across methods, and a per-seed vs "
                       "per-method choice decided in advance")
    return OWNER, ("endpoint-as-headline is recommended but not frozen. Any selected-best column "
                   "additionally needs reserved validation episodes, equal candidate opportunity "
                   "across methods, and a per-seed vs per-method choice -- decided in advance")


def gate_production_renderer_verified():
    """[C95](../docs/CONSTRUCTION.md#c95) on the machine that will actually produce the numbers.

    The owner states production runs on separate infrastructure — a plain Docker container we do not
    yet have access to. C95's *rule* survives that move unchanged; its *measurement* does not. The
    same checkpoint read 131.5 under EGL in the container and 13.85 locally under glfw, so "which
    renderer, on which machine" is part of the measurement rather than a detail of it.

    This cannot be satisfied from here: it requires the production host. It is a gate rather than a
    note because a fleet measured under an unverified renderer cannot be repaired afterwards -- the
    checkpoints would be fine and every number computed from them would be suspect.
    """
    return OWNER, ("production is another V100 with Docker and a Linux environment of OUR CHOICE "
                   "(owner, 2026-09-05). That makes C95 tractable by construction rather than a "
                   "hazard to discover: build the image to match the renderer we validated here "
                   "(MUJOCO_GL=egl), pin its digest into source-lock, and reproduce one known cell "
                   "to show the new platform reads the same. NOT against the archived drqv2 100k "
                   "480.6: RESULTS-VALIDITY records that this number predates per-episode condition "
                   "seeding, deterministic kernels and strict regime verification, so a mismatch "
                   "against it would confound renderer with evaluator revision -- the one thing the "
                   "probe exists to separate. The probe is a THREE-step comparison: (a) re-measure "
                   "that checkpoint here on the CURRENT evaluator to get R_A, (b) measure the same "
                   "checkpoint, evaluator and container on the production host to get R_B, (c) "
                   "compare R_A with R_B, where the platform is then the only changed factor. Do it "
                   "BEFORE the fleet; the checkpoints would survive a mismatch but every number "
                   "computed from them would not")


def gate_production_scope_frozen():
    """The owner notes the deliverable may cover Door **and possibly Lift**. That is scope, and it
    changes constants rather than merely adding rows."""
    return OWNER, ("Door is the scoped task and every constant is Door's -- the C55 random floor of "
                   "1.842 (C55, re-measured over 200 paired episodes), the certified ten scenes, "
                   "the 500-step horizon, the published anchor "
                   "table. Adding Lift means re-deriving each of those for Lift: its own floor "
                   "exists (6.562) but only at 25 episodes against Door's 200, and its own "
                   "published-value/floor relationship is flagged elsewhere as an unexplained "
                   "anomaly Door does not share (faithfulness-reconciliation.md). Reading "
                   "(DECISION-SHEET.md A33): Door alone for this production run, Lift as a stated "
                   "follow-on rather than co-equal scope now. OWNER for ratifying that reading or "
                   "stating an override")


def gate_record_completeness():
    """The only gate whose omission cannot be repaired after the fleet finishes.

    Owner, 2026-09-05: the run must yield *the actual data*, not only verdicts on pre-set
    hypotheses, so a question held privately is still answerable without a rerun. Every other open
    item can be fixed by re-analysing; this one fixes the set of answerable questions permanently at
    the moment the last cell completes. Spec: notes/record-completeness-spec.md.
    """
    source = _read("scripts/eval_grid.py") + _read("scripts/eval_provenance.py")
    if not source:
        return FAIL, "eval_grid.py absent"
    required = {
        "episode_length": r"episode_length",
        "termination reason": r"termination|time_limit_hit|truncated",
        "realized placement parameters": r"initial_placement|placement_params",
        "policy scale": r"log_std",
        "vector-level clip rate": r"clip_rate|clipped_fraction|action_clip",
    }
    missing = [label for label, pat in required.items() if not re.search(pat, source)]
    if not missing:
        return PASS, "episode rows carry outcome, condition and policy diagnostics"
    return FAIL, ("episode rows are missing: " + ", ".join(missing) +
                  ". A hash proves pairing but cannot answer 'did performance depend on where the "
                  "door was' -- record the parameters and derive the hash from them. One row is "
                  "~1 KB; the fleet is hundreds of job-hours, so the burden of proof is on "
                  "EXCLUDING a field")


def gate_schedule_matches_protocol():
    """Review 4 A1: the schedule must describe the experiment we intend to run.

    A stale schedule produces perfectly valid runs of the wrong experiment, which is the most
    expensive kind of defect available here."""
    import json as _json
    try:
        data = _json.loads(_read("datasphere/native/production-schedule.json") or "{}")
    except ValueError as error:
        return FAIL, f"schedule is not valid JSON: {error}"
    rows = [r for r in data.get("rows", []) if isinstance(r, dict)]
    budgets = sorted({r["frames"] for r in rows if "frames" in r})
    settings = data.get("recommended_settings", {}) or {}
    eval_every = (settings.get("EVAL_EVERY_FRAMES") or {}).get("value")
    problems = []
    if budgets and 600_000 not in budgets:
        problems.append(f"rows carry {budgets}, none at the intended 600,000")
    if eval_every:
        problems.append(f"still recommends EVAL_EVERY_FRAMES={eval_every} after online evaluation "
                        "was disabled for production")
    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "schedule budgets and evaluation settings match the intended protocol"


def gate_replay_audit_is_honest():
    """Review 4 A6: `audit_comparability_seam.py` asserts the replay buffer covers the whole run
    without comparing the cap to the budget. At the production cap of 300k in a 600k run it is a
    recency ring that evicts the first half of experience, for five baselines at once."""
    audit = _read("scripts/audit_comparability_seam.py")
    if not audit:
        return FAIL, "audit_comparability_seam.py absent"
    hardcoded = re.search(r'nominal, disk-backed, "\s*\n?\s*"exceeds 6e5', audit) or \
                ("exceeds 6e5" in audit and not re.search(r"(cap|capacity)\s*[<>]=?\s*", audit))
    if hardcoded:
        return FAIL, ("the seam audit states 'uniform over the whole run ... exceeds 6e5' whenever a "
                      "capacity exists, without comparing it to the budget. families.json caps "
                      "replay at 300,000 in a 600,000-frame run, so both clauses are false for the "
                      "RL-ViGen five")
    return PASS, "replay capacity is compared against the budget rather than asserted"


def gate_ibac_evaluator_honours_device():
    """Review 5: `utils/agent.py` computes `self.device` and never uses it, so IBAC evaluation runs
    on CPU whatever `--device` says. Same class as the idaac hardcoded-CPU defect."""
    agent = _read("runnable/ibac_sni/torch_rl/utils/agent.py")
    if not agent:
        return FAIL, "ibac_sni clone absent"
    if re.search(r"\.to\(\s*self\.device\s*\)", agent):
        return PASS, "the IBAC agent moves its model to the requested device"
    return FAIL, ("agent.py sets self.device (:15) and never applies it -- the CPU-saved model is "
                  "never moved, and preprocess_obss takes no device, so --device cuda silently "
                  "evaluates on CPU. Latent alongside it: the argmax branch uses dist.probs, which "
                  "is categorical-only and would raise on the continuous Normal")


def gate_container_pinned_by_digest():
    """Review 4 M / review 5 / C29. A tag is mutable; the renderer is load-bearing (C95)."""
    import json as _json
    try:
        lock = _json.loads(_read("datasphere/native/source-lock.json") or "{}")
    except ValueError as error:
        return FAIL, f"source-lock is not valid JSON: {error}"
    image = str(lock.get("container_image", ""))
    if "sha256:" not in image:
        return FAIL, (f"container recorded as a MUTABLE TAG ({image or 'absent'}). C95 showed the same "
                      "checkpoint reads 131.5 vs 13.85 under a different renderer, so 'same code and "
                      "checkpoint' does not imply the same observations unless the image is pinned by "
                      "digest. NOTE this is a MIGRATION-TIME item: production runs on our own V100 with "
                      "an image of our choice, so the digest to pin is that image's, which does not "
                      "exist yet. Pin it when built -- see MIGRATION-T4-TO-V100.md step 2")
    submitter = _read("datasphere/native/job.sh")
    if "verify_container_image" not in submitter or 'verify_container_image "$cfg"' not in submitter:
        return FAIL, ("source-lock records a digest but job.sh does not enforce it before submission; "
                      "a hand-written config can still select a mutable image")
    return PASS, f"container pinned by digest and enforced on submit ({image[:40]}...)"


def gate_no_episode_level_inference():
    """Review 5 P1. The corrected plan makes the TRAINING SEED the outer unit; a bootstrap over
    pooled episodes treats 600 correlated rows as replicates and would understate uncertainty
    badly. The concern is not that the function exists but that it could silently become the
    publication path."""
    source = _read("scripts/results_table.py")
    if not source:
        return PASS, "no legacy reporting path present"
    if re.search(r"def boot_ci", source):
        required = ("--legacy-exploratory", "if not a.legacy_exploratory", "return 2")
        if not all(marker in source for marker in required):
            return FAIL, ("results_table.py still bootstraps the ratio of POOLED MEANS over episodes "
                          "(:116) with no explicit early refusal. The outer replicate is the training "
                          "seed (n=3), not the episode (n=600). Either cluster by seed or make this "
                          "path unusable for headline numbers")
        return PASS, "legacy episode-resampling table requires explicit opt-in and is non-headline"
    return PASS, "no episode-level reporting path present"


def gate_claimed_hyperparameters_are_executed():
    """The beta class: a value researched, sourced, written into FAITHFULNESS -- and never passed.

    ibac_sni ran at beta=1.0 while the table recorded 1e-4, because the launcher passed no --beta
    and nothing compared the two. Five external reviews, an audit reporting "12/12 genuine" and a
    fidelity ledger citing the value all missed it, because every existing instrument asks whether
    a MECHANISM is present, not whether a claimed VALUE reaches the process.
    """
    import subprocess
    try:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_executed_hyperparameters.py")],
                              capture_output=True, text=True, timeout=180)
    except Exception as error:
        return FAIL, f"the executed-hyperparameter audit could not run: {type(error).__name__}"
    if proc.returncode == 0:
        # The auditor prints an explanatory UNLOCATED legend even when every live row resolves.
        # Count only table rows; otherwise the gate fails forever on its own documentation.
        unresolved = [line.strip() for line in proc.stdout.splitlines()
                      if "UNLOCATED" in line and not line.lstrip().startswith("UNLOCATED")]
        unlocated = len(unresolved)
        defaulted = proc.stdout.count(" DEFAULTED ")
        if unlocated:
            return FAIL, (f"{unlocated} claimed hyperparameter value(s) are not located in the "
                          "audited production sources; they are not certified: "
                          + "; ".join(unresolved[:6]))[:700]
        return PASS, (f"no claimed hyperparameter is contradicted by the process "
                      f"({defaulted} hold only by the clone's own default, {unlocated} could not be "
                      f"located in a launcher, descriptor or argparse and are NOT certified)")
    offending = [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith("!!")]
    return FAIL, ("FAITHFULNESS claims values the process does not use: "
                  + "; ".join(offending)[:400] if offending else
                  "the executed-hyperparameter audit reported a mismatch")


def gate_job_budgets_fit():
    """A job killed by its own timeout is indistinguishable from a code fault, and has already paid.

    bt14het9mvpvvu8vatgo died that way: 3729s wall against `timeout --foreground 3600s`, no stdout
    to download, exit 5. Seven sibling configs carried the identical budget. Reported at the
    MEASURED healthy throughput (22 s/episode, bt1ip5f8c6mqqm7fd2bn) rather than the regressed one,
    so this gate flags genuinely unfittable configs instead of re-reporting the throughput
    regression, which has its own note.
    """
    try:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_job_budgets.py")],
                              capture_output=True, text=True, timeout=120)
    except Exception as error:
        return FAIL, f"the job-budget audit could not run: {type(error).__name__}"
    offending = [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith("!!")]
    if proc.returncode == 0:
        return PASS, "every job config's timeout fits its own episode count at measured throughput"
    return FAIL, ("job configs cannot fit their own workload: " + "; ".join(offending))[:400]



def _audit_exit_code(script: str, *args: str) -> tuple[int, str]:
    """Run a standalone audit and return its verdict, so a gate can carry it."""
    try:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args],
                              capture_output=True, text=True, timeout=300)
    except Exception as error:  # noqa: BLE001 - a gate must never crash the report
        return -1, f"{type(error).__name__}"
    return proc.returncode, proc.stdout


def gate_no_row_pools_two_closures():
    """A24/A25: seeds from different closures are different revisions and must not be pooled.

    This audit existed and NOTHING ran it before a release -- and until 2026-09-07 it could not
    have failed anyway: it compared each row's `execution_kind` against the literal "production",
    which is not in `contract.py`'s vocabulary, so its findings branch was unreachable. Both halves
    are fixed; wiring it here is what makes it evidence rather than a script somebody might run.
    """
    code, out = _audit_exit_code("audit_row_closure.py", "--strict")
    if code == -1:
        return OWNER, f"the row-closure audit could not run: {out}"
    if code == 0:
        return PASS, ("no production row pools two scientific closures "
                      "(exploratory rows may, and that is not a finding)")
    findings = [line.strip() for line in out.splitlines() if "MIXED-CLOSURE finding" in line]
    return FAIL, ("a reported row pools seeds from different closures: "
                  + ("; ".join(findings) or "see scripts/audit_row_closure.py --strict"))[:300]


def gate_observation_geometry_is_not_contradicted():
    """No record may disagree with `OBSERVATION_GEOMETRY` about what it ran at.

    Frame stack and render size are the values this project has most often stated wrongly, and the
    errors were all found by hand-tracing. `--strict` fails when a baseline has records and none
    carries its declared pair; the audit also NAMES the baselines that have produced no record at
    all, which is a gap rather than a failure and is reported as such below.
    """
    code, out = _audit_exit_code("audit_observation_geometry.py", "--strict")
    if code == -1:
        return OWNER, f"the geometry audit could not run: {out}"
    if code != 0:
        contradicted = [line.strip() for line in out.splitlines() if "CONTRADICTED" in line]
        return FAIL, ("a record contradicts the declared observation geometry: "
                      + ("; ".join(contradicted) or "run scripts/audit_observation_geometry.py"))[:300]
    never = [line.strip() for line in out.splitlines() if "never run for them" in line]
    if never:
        detail = never[0].split(":", 1)[-1].strip().rstrip(".")
        return PASS, ("no record contradicts the declared geometry; the runtime assertion has "
                      f"never run for {detail} -- declared and would-be-checked, not verified")
    return PASS, "every baseline has a record carrying its declared observation geometry"



#: Audits that are pass/fail checks and must therefore be CONSULTED by a gate, not merely present.
#: Keyed to the question each answers, so a reader of the gate output knows what went unchecked if
#: one starts failing. `tests/test_every_audit_is_classified.py` fails if a new audit appears in
#: scripts/ and lands in neither this set nor DESCRIPTIVE_AUDITS below.
GATING_AUDITS = {
    "audit_shared_evaluator.py": "has the shared evaluator earned the right to report each number",
    "audit_static_classes.py": "three defect classes that were findable by reading and were not",
    "audit_checkpoint_semantics.py": "what each checkpoint contains, and what it does NOT permit",
    "audit_instruments.py": "which instruments are themselves checked, and which are on trust",
}

#: Inventories. They describe rather than decide, and several are already consumed by the gates
#: above (`audit_comparability_seam` feeds three of them). Listed so the classification is total.
DESCRIPTIVE_AUDITS = {
    "audit_comparability_seam.py", "audit_dead_knobs.py", "audit_eval_axis.py",
    "audit_eval_state.py", "audit_seed_control.py", "audit_executed_hyperparameters.py",
    "audit_implementations.py", "audit_job_budgets.py", "audit_pairing_evidence.py",
    "audit_row_closure.py", "audit_submission_configs.py", "audit_observation_geometry.py",
    "audit_eval_cadence.py",
}


def gate_failing_capable_audits_are_consulted():
    """An audit that can fail and that nothing runs is not evidence, it is an unread opinion.

    Seventeen audits exist. Ten were standalone, and two of those -- `audit_row_closure` and
    `audit_observation_geometry` -- turned out to be exactly the checks a release needed, one of
    which could not fail at all until it was repaired. The remaining four below can fail, carry a
    production question each, and were consulted by nothing. Running them HERE means a reviewer's
    one command covers them, and a regression in any of them surfaces on the same line as
    everything else.
    """
    failures = []
    for script, question in sorted(GATING_AUDITS.items()):
        code, out = _audit_exit_code(script)
        if code == -1:
            return OWNER, f"{script} could not run: {out}"
        if code != 0:
            failures.append(f"{script} ({question})")
    if failures:
        return FAIL, "audit(s) failing and previously unconsulted: " + "; ".join(failures)
    return PASS, (f"{len(GATING_AUDITS)} pass/fail audits consulted here rather than left "
                  "standalone: shared evaluator, static defect classes, checkpoint semantics, "
                  "instrument trust")


def gate_clone_patches_reproduce():
    """RECOVERY-HANDOFF says the clones are reproducible from ext/ plus runnable/_patches/*.patch.

    Nothing checked it. `setup/apply_patches.py` does not apply those files -- it patches the
    vendored RL-ViGen tree -- so they are provenance snapshots, and a snapshot nobody re-derives
    drifts the first time a clone is edited. Five of six had drifted by 2026-09-05, including two
    edits that unblocked families which could not be evaluated at all.
    """
    try:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "refresh_clone_patches.py"),
                               "--check"], capture_output=True, text=True, timeout=180)
    except Exception as error:
        return FAIL, f"the clone-patch check could not run: {type(error).__name__}"
    if "MISSING SOURCE" in proc.stdout:
        return OWNER, ("some ext/ sources are absent here, so their snapshots could not be checked. "
                       "That is not a pass; re-run where ext/ holds the real clones")
    if proc.returncode == 0:
        return PASS, "every clone patch still reproduces its clone from ext/"
    stale = [line.strip() for line in proc.stdout.splitlines() if "STALE" in line]
    return FAIL, ("clone patches no longer reproduce their clones, so the stated recovery path is "
                  "broken: " + "; ".join(stale))[:300]


def gate_ibac_procs_is_runnable():
    """A configured process count that cannot start is worse than a small one that can.

    Before the Door-specific repair, `bt1q6jd096m3re2n7jp2` measured an EOFError at procs=2:
    constructed MuJoCo/EGL environments were sent through the upstream fork path.  The repaired
    Door path keeps that upstream default for non-Door use, but passes picklable factories through
    an explicit spawn context.  This gate checks both source invariants and the later procs=16
    functional smoke; it must not re-certify the historical fork failure as current state.
    """
    try:
        descriptors = json.loads(_read("datasphere/native/families.json"))
    except Exception as error:
        return FAIL, f"could not read families.json: {type(error).__name__}"
    entry = descriptors.get("ibac_sni", {}) or {}
    train = _read("runnable/ibac_sni/torch_rl/scripts/train.py")
    # Spawn unpickles the factory before the driver can resolve bare `utils`, so its implementation
    # deliberately lives under an IBAC-specific module.  Read that module, not the compatibility
    # re-export in utils/general.py: treating a relocation as "no factory" made this gate fall
    # through to its procs=1 PASS while the v100 descriptor still requested 16.
    runtime = _read("runnable/ibac_sni/torch_rl/ibac_sni_runtime.py")
    penv = _read("runnable/ibac_sni/torch_rl/torch_rl/torch_rl/utils/penv.py")
    forced_fork = "set_start_method(\"fork\")" in train
    # The original defect was passing constructed Door environments to that fork.  The repaired
    # path keeps the upstream top-level setting for non-Door usage, but sends Door factories to an
    # explicit spawn context and seeds global NumPy in the factory before the first reset.  A gate
    # that only searches for the old fork token would reject the repaired path; a gate that only
    # checks for spawn would miss the independent-RNG requirement.
    factory_path = (
        "callable(env_or_factory)" in penv
        and 'start_method = "spawn"' in penv
        and "get_context(start_method)" in penv
        and "make_rlvigen_env_process" in train
    )
    factory_reseeds = bool(re.search(
        r"def make_rlvigen_env_process\(.*?:", runtime, flags=re.DOTALL)) and all(
            token in runtime for token in ("random.seed(env_seed)", "numpy.random.seed(env_seed)"))
    # Scoped to the worker BODY, not the file: a bare token search across the whole module would
    # match a comment or an unrelated helper and flip this gate green -- the dangerous direction,
    # since a green here certifies that 16 workers draw independent placements.
    body = re.search(r"\ndef worker\(.*?\n(?=\S)", penv, flags=re.DOTALL)
    worker_reseeds = bool(body) and any(
        token in body.group(0) for token in
        ("np.random.seed(", "random.seed(", ".seed(", "set_seed(", "default_rng("))
    unsafe = not (factory_path and factory_reseeds) and (forced_fork or not worker_reseeds)
    offenders = []
    base = str((entry.get("constants", {}) or {}).get("procs", "1"))
    if base not in ("1", "None") and unsafe:
        offenders.append(f"base procs={base}")
    for profile, override in (entry.get("host_profiles") or {}).items():
        value = str(((override.get("constants") or {}) if isinstance(override, dict) else {})
                    .get("procs", "1"))
        if value not in ("1", "None") and unsafe:
            offenders.append(f"{profile} procs={value}")
    if not factory_path and not forced_fork and not worker_reseeds and offenders:
        return FAIL, ("the fork start method is gone, but penv.worker() still re-seeds nothing, so "
                      "every worker draws the SAME Door placement sequence from the global numpy "
                      f"RNG (C69). Configured anyway: {', '.join(offenders)}. Fixing the start "
                      "method alone does not make procs>1 correct -- it makes the damage silent")
    if not factory_path and not forced_fork:
        return OWNER, ("ibac_sni no longer forces the fork start method, so the measured procs=2 "
                       "EOFError may no longer apply. Re-measure before raising procs")
    if offenders and not factory_path:
        return FAIL, ("ibac_sni forces multiprocessing fork (train.py:110) and MuJoCo/EGL contexts "
                      "do not survive one -- procs>1 dies at parallel env setup, measured in "
                      f"bt1q6jd096m3re2n7jp2. Configured anyway: {', '.join(offenders)}"
                      + ("" if worker_reseeds else
                         ". SECOND, independent defect: penv.worker() re-seeds nothing, so all "
                         "workers would share one placement stream even once the crash is fixed"))
    if factory_path and factory_reseeds:
        try:
            evidence = json.loads(IBAC_PROCS_SMOKE_EVIDENCE.read_text())
        except (OSError, ValueError) as error:
            return OWNER, ("ibac_sni's Door path constructs environments in spawned workers and "
                           "seeds their NumPy streams independently, but the real procs=16 smoke "
                           f"has no readable evidence ({type(error).__name__})")
        required = {
            "family": "ibac_sni",
            "tier": "gt4i.1",
            "procs": 16,
            "status": "SUCCESS",
            "exit_status": 0,
        }
        mismatches = [f"{key}={evidence.get(key)!r} (expected {value!r})"
                      for key, value in required.items() if evidence.get(key) != value]
        markers = evidence.get("markers", {})
        if markers.get("import_gate") != "NATIVE_IMPORT_GATE_PASSED ibac_sni":
            mismatches.append("missing successful import-gate marker")
        if not str(markers.get("final_evaluation", "")).startswith(
                "NATIVE_FINAL_EVALUATION_COMPLETED frame="):
            mismatches.append("missing final-evaluation marker")
        if not str(markers.get("cell_completed", "")).startswith("NATIVE_CELL_COMPLETED ibac_sni"):
            mismatches.append("missing cell-completed marker")
        if int(evidence.get("observed_process_count", 0)) < 18:
            mismatches.append("observed process count is below parent + 16 workers")
        if float(evidence.get("max_sum_hwm_gib", float("inf"))) >= 27.0:
            mismatches.append("observed high-water memory does not fit gt4i.1")
        if mismatches:
            return OWNER, ("ibac_sni has a procs=16 smoke record, but it is not sufficient: "
                           + "; ".join(mismatches))
        return PASS, ("ibac_sni procs=16 completed a spawn/EGL functional smoke on gt4i.1; "
                      "this proves the configured process path is runnable, not V100 throughput "
                      "or competence")
    return PASS, ("ibac_sni procs stays at 1 everywhere, matching the measured fork/EGL constraint")


def gate_pairing_proven_physically():
    """Retention compares regimes, so the physical condition must be shown equal across them.

    External review 10: "An image hash is not evidence that physical placement is the same." Correct
    -- `placement_witnesses` are observation hashes, and a matched physical placement under two
    visual regimes SHOULD hash differently. The physical evidence is P20's realized
    `initial_placement`, and this checks it rather than the hash.
    """
    try:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_pairing_evidence.py")],
                              cwd=ROOT, capture_output=True, text=True, timeout=180)
    except Exception as error:
        return FAIL, f"the pairing-evidence audit could not run: {type(error).__name__}"
    summary = [l.strip() for l in proc.stdout.splitlines() if "cross-regime comparisons" in l]
    if proc.returncode != 0:
        bad = [l.strip() for l in proc.stdout.splitlines() if "NOT PAIRED" in l]
        return FAIL, ("records show regimes that are NOT physically paired, so any retention number "
                      "from them is confounded by placement: " + "; ".join(bad))[:300]
    if not summary:
        return OWNER, ("no records contain two regimes for one (baseline, seed, scene), so pairing "
                       "has not been demonstrated from data. That is not a pass")
    eligible = re.search(r"(\d+) (?:eligible )?cross-regime comparisons", summary[0])
    if not eligible or not int(eligible.group(1)):
        return OWNER, ("no current, provenanced cross-regime record has a physical pairing "
                       "comparison, so legacy records cannot establish this gate")
    missing = re.search(r"(\d+) lacking physical evidence", summary[0])
    if missing and int(missing.group(1)):
        return FAIL, ("physical pairing is incomplete: " + summary[0] + "; records without a "
                      "realized-placement witness cannot support a paired retention claim")
    return PASS, f"physical placements match across regimes in every comparable record ({summary[0]})"


def gate_v100_schedule_matches_descriptor(schedule_path=None):
    """The production-host artifact must be the current explicit-profile planner output."""
    schedule = Path(schedule_path) if schedule_path is not None else (
        ROOT / "datasphere" / "native" / "production-schedule-v100.json")
    if not schedule.is_file():
        return FAIL, f"V100 schedule is absent: {schedule}"
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "datasphere" / "native" / "plan_production.py"),
             "--host-profile", "v100"],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
    except Exception as error:
        return FAIL, f"V100 schedule generator could not run: {type(error).__name__}"
    if proc.returncode != 0:
        return FAIL, f"V100 schedule generator failed: {proc.stderr.strip()[:180]}"
    if schedule.read_text() != proc.stdout:
        return FAIL, ("V100 schedule is stale or does not match the resolved v100 descriptor; "
                      "regenerate with plan_production.py --host-profile v100 --sync-schedule")
    try:
        data = json.loads(proc.stdout)
    except ValueError as error:
        return FAIL, f"V100 schedule generator emitted invalid JSON: {error}"
    if data.get("host_profile") != "v100" or len(data.get("rows", [])) != 12:
        return FAIL, "V100 schedule does not identify the v100 profile and all twelve baselines"
    return PASS, ("V100 schedule matches family.py's resolved descriptor; throughput remains "
                  "explicitly unmeasured on V100")


def gate_production_names_its_host():
    """SYNTHESIS.md's "highest-risk thing remaining, which no gate covers" -- now covered.

    Nine of twelve baselines carry a DataSphere-shaped adaptation (num_envs, procs, the 300k replay
    cap) chosen for 4-8 cores and 27 GiB. Production is a 16-core, 113-GiB V100. `host_profile()`
    defaults to "datasphere" so every existing probe config keeps working, and that default is
    exactly the trap: running the SMALL configuration on the BIG machine succeeds quietly and
    produces valid-looking numbers of a rescaled experiment. Only the opposite error fails loudly.

    So at production scale the runner must REFUSE to infer the host.
    """
    runner = _read("datasphere/native/run_probe.sh")
    fires = re.search(r"FRAMES:-\d+\}\"?\s*-ge\s*600000", runner)
    # The guard must test whether the CALLER named a host, not whether the variable is set -- the
    # runner defaults it at line 6, so an emptiness test is dead code. This gate asserted the weaker
    # thing first and passed on a guard that could never fire.
    explicit = "NATIVE_HOST_PROFILE_EXPLICIT" in runner
    if fires and explicit:
        return PASS, ("a production-length run (>=600000 frames) refuses to start unless "
                      "NATIVE_HOST_PROFILE is set explicitly")
    return FAIL, ("nothing stops a production-scale run from inheriting the probe host profile, so "
                  "DataSphere-shaped values would execute on the V100 and SUCCEED, producing a "
                  "rescaled experiment that no downstream check can distinguish from the intended "
                  "one. Wanted: the runner refuses the default at production frames")


def gate_submission_configs_runnable():
    """Do the job configs themselves name real cells and tiers that can hold them?

    `gate_scheduler_ram_invariant` verifies that the SUBMIT SCRIPT contains a memory check. It does,
    and that gate passed while three jobs were submitted on 2026-09-05 that could not run: two on a
    tier below their family minimum (one SIGKILLed at 11.07 GiB) and one naming `rlvigen`, an
    evaluator family, as though it were a baseline. Hand-written configs go to
    `datasphere project job execute` and never touch the submit script -- which is written in that
    gate's own comment as the reason alda was SIGKILLed the FIRST time.

    Certifying that a mechanism exists is not certifying that the path in use invokes it.
    """
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_submission_configs.py")],
                          capture_output=True, text=True)
    if done.returncode == 0:
        return PASS, "every live job config names real cells and a tier its families fit"
    bad = [line.strip() for line in done.stdout.splitlines() if line.strip().startswith("!!")]
    return FAIL, f"{len(bad)} config(s) would die on submission: " + "; ".join(bad[:2])


def gate_ctrl_v100_profile_restored():
    """ctrl carries the same DataSphere-shaped adaptation as idaac/ibac_sni/ppg -- upstream defaults
    `num_envs=64` (`ext/ctrl_public/train_ppo.py:33`), ours runs 16, a 4x reduction -- and it is
    already named in that company in review-4-5-triage.md's own table ("ctrl 4x"). idaac, ibac_sni
    and ppg all got an explicit v100 host-profile override restoring their process count. ctrl did
    not: `families.json`'s ctrl entry has `"host_profiles": {}`. Found 2026-09-05 in a chat response
    and NOT written anywhere durable until this gate -- exactly the failure mode of a finding that
    only exists in a transcript. A gate cannot be lost that way: it reads the tree, not memory.
    """
    descriptors = json.loads(_read("datasphere/native/families.json"))
    ctrl = descriptors.get("ctrl", {})
    if (ctrl.get("host_profiles") or {}).get("v100", {}).get("constants", {}).get("num_envs"):
        return PASS, "ctrl has a v100 profile restoring num_envs toward upstream's 64"
    return OWNER, ("ctrl runs upstream's num_envs=64 at 16 (a 4x DataSphere-shaped reduction, same "
                  "class as idaac/ibac_sni/ppg) with NO v100 host profile to restore it on the "
                  "production host, unlike its three siblings. Restoring it would roughly "
                  "quadruple ctrl's measured 13.57 GiB peak toward ~54 GiB -- fits solo on 113 GiB, "
                  "check before packing. Mechanical, not a judgment call: same reasoning already "
                  "applied to the other three.")


def gate_checkpoint_cadence_matches_fleet():
    """Every family's intermediate-checkpoint cadence must match A20's 12-stamp/50k decision on the
    V100 profile, or the retained curve has a different resolution per family for no scientific
    reason -- same class of finding as ctrl's missing v100 num_envs profile.

    rlvigen's base 100000 was a DataSphere-container disk-space decision (20.2 GiB free in the
    container); a v100 profile already exists for this family (it overrides replay_capacity) but had
    never been extended to this setting, so it silently carried the DataSphere-era value onto a host
    where the reason for it (container disk limits) no longer applies. Found 2026-09-05, fixed here.
    """
    descriptors = json.loads(_read("datasphere/native/families.json"))
    bad = []
    for family, entry in descriptors.items():
        if family.startswith("_") or not isinstance(entry, dict):
            continue
        base = (entry.get("production") or {}).get("preserve_snapshots") or \
               (entry.get("production") or {}).get("save_every")
        if base is None:
            continue
        v100 = (entry.get("host_profiles") or {}).get("v100", {}).get("production", {})
        effective = v100.get("preserve_snapshots", v100.get("save_every", base))
        if effective != 50000:
            bad.append(f"{family}: v100 cadence is {effective}, not 50000")
    if bad:
        return FAIL, "; ".join(bad)
    return PASS, "every family's v100 checkpoint cadence matches the fleet's 12-stamp/50k decision"


GATES = [
    ("submission configs runnable", gate_submission_configs_runnable),
    ("checkpoint cadence matches fleet", gate_checkpoint_cadence_matches_fleet),
    ("ctrl v100 profile restored", gate_ctrl_v100_profile_restored),
    ("production names its host", gate_production_names_its_host),
    ("v100 schedule matches descriptor", gate_v100_schedule_matches_descriptor),
    ("pairing proven physically", gate_pairing_proven_physically),
    ("ibac_sni procs runnable", gate_ibac_procs_is_runnable),
    ("clone patches reproduce", gate_clone_patches_reproduce),
    ("job budgets fit", gate_job_budgets_fit),
    ("claimed hyperparameters executed", gate_claimed_hyperparameters_are_executed),
    ("evaluation pairing", gate_evaluation_pairing),
    ("regime verification fail-closed", gate_regime_verification_fail_closed),
    ("train/eval RNG isolation", gate_train_eval_rng_isolation),
    ("online eval disable executed", gate_online_eval_disable_is_executed),
    ("idaac level_seed semantics", gate_idaac_level_seed),
    ("ppg auxiliary KL scaling", gate_ppg_auxiliary_kl),
    ("ibac_sni competence", gate_ibac_sni_competence),
    ("ctrl config binding", gate_ctrl_config_binding),
    ("idaac evaluator device", gate_idaac_evaluator_device),
    ("shared evaluator validated", gate_shared_evaluator_validated),
    ("estimands frozen", gate_estimands_frozen),
    ("seed policy frozen", gate_seed_policy_frozen),
    ("source tree frozen", gate_source_tree_frozen),
    ("environment manifest", gate_environment_manifest),
    ("production canary", gate_production_canary),
    ("placement provenance", gate_placement_provenance),
    ("release suite green", gate_release_suite_green),
    ("external RL-ViGen anchor", gate_external_anchor),
    ("scheduler RAM invariant", gate_scheduler_ram_invariant),
    ("selected-scene path disabled", gate_selected_scene_path_disabled),
    ("result metadata truthful", gate_result_metadata_truthful),
    ("statistical protocol frozen", gate_statistical_protocol_frozen),
    ("checkpoint rule frozen", gate_checkpoint_rule_frozen),
    ("production renderer verified", gate_production_renderer_verified),
    ("production scope frozen (Door / +Lift)", gate_production_scope_frozen),
    ("record completeness", gate_record_completeness),
    ("schedule matches protocol", gate_schedule_matches_protocol),
    ("replay audit is honest", gate_replay_audit_is_honest),
    ("ibac evaluator honours device", gate_ibac_evaluator_honours_device),
    ("container pinned by digest", gate_container_pinned_by_digest),
    ("no episode-level inference", gate_no_episode_level_inference),
    ("no row pools two closures", gate_no_row_pools_two_closures),
    ("observation geometry uncontradicted", gate_observation_geometry_is_not_contradicted),
    ("failing-capable audits consulted", gate_failing_capable_audits_are_consulted),
]


def evaluate() -> list[dict]:
    rows = []
    for name, check in GATES:
        try:
            status, detail = check()
        except Exception as error:            # a broken check must not read as a passing gate
            status, detail = FAIL, f"check raised {type(error).__name__}: {error}"
        rows.append({"gate": name, "status": status, "detail": detail})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = evaluate()
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        width = max(len(r["gate"]) for r in rows)
        for row in rows:
            print(f"{row['status']:<6} {row['gate']:<{width}}  {row['detail']}")
        failed = [r for r in rows if r["status"] == FAIL]
        owner = [r for r in rows if r["status"] == OWNER]
        print(f"\n{len(rows) - len(failed) - len(owner)} pass, {len(failed)} fail, "
              f"{len(owner)} waiting on the owner.")
        if failed:
            print("\nNOT LAUNCHABLE. The failures above are work, and they are ours.")
        elif owner:
            print("\nNo mechanical failures remain. What is left is decisions, not repairs.")
    return 1 if any(r["status"] == FAIL for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
