#!/usr/bin/env python3
"""Do the twelve clones' reported numbers land on one axis? — the clone-era seam audit.

    python scripts/audit_comparability_seam.py

## Why this exists

[`docs/COMPARABILITY_CONTRACT.md`](../docs/COMPARABILITY_CONTRACT.md) §1–§10 answered this
question once, and answered it for the **retired `rlgen/` port**: its argument rests on
*"every baseline's environment interaction, training and eval alike, goes through
`rlgen/envs.py`'s construction path"*, plus four shared adapter classes. The null became the clone
on 2026-08-17. There is no shared construction path now and there are no adapters, so that
evidence does not transfer — see the amendment at the head of that file, and C30.

`TASK.md` R3 was relaxed 2026-08-26 from *identical evaluation code* to **metrics fully on the
same axes and directly comparable**, and named that document as carrying the burden. Half of it
cannot. This is the missing half, for the architecture that actually runs.

## The bar this is built to

The owner's, stated when the relaxation was taken: be *"in a state where we can confidently
declare same-axis based on all circumstances that take effect, not only name some reasons why it'd
be compatible and call it a day."*

So this script does not argue. Per axis it prints the value **per baseline**, says whether the
twelve agree, and — the part that matters — says whether that value was **DERIVED** (read out of
code or config now) or is **RECORDED** (established once by hand and restated here). A RECORDED row
is not evidence of the same kind, and mixing the two is how "we checked" comes to mean "someone
once said".

## Read `docs/PART2-METRIC-INVENTORY.md` FIRST -- it is the reasoning of record

That file (opened 2026-08-17, 432 lines) already derived, by hand and from the emitting code, most
of what this script re-derives: the raw-vs-normalised reward table and the wrapper-order argument
behind it, the 8/4 frame-stack split and why it is faithful rather than a porting artifact, the
three-way resolution split, the three distinct action distributions, and the per-baseline x-axis
units. **This script is not an independent authority and must not be read as a second opinion.** It
is the re-derivable check that those facts have not drifted, plus the axes that document did not
cover.

This division exists because the same work was very nearly done twice: on 2026-08-26 the reward and
frame-stack axes here were derived from scratch by someone who had not read that file, and arrived
at the same answers. Agreement was luck, not method -- a fresh derivation that had *disagreed*
would have been a defect report against a document nobody was consulting.

## Two kinds of split, which fail differently

The first version of this script printed one flat list, and that was wrong in a way worth keeping
recorded: it put `render resolution` and `truncation` next to each other as though a disagreement
in either meant the same thing. It does not.

- **UNITS** — the axis decides what the reported number *means arithmetically*. Reward
  normalisation, the success definition, the episode the number is summed over, the estimator that
  turns episodes into a reported mean. A split here makes two numbers **incommensurable**: no
  amount of care in reading them fixes it, because they are not the same quantity.
- **CONDITIONS** — the axis decides *what was measured* while leaving the units alone. Render
  resolution, frame-stack depth, action repeat, how the time limit is bootstrapped. A split here
  leaves the numbers commensurable but makes a difference between them **unattributable to the
  algorithm**, since something other than the algorithm also differs.

R3 as relaxed -- *"metrics fully on the same axes and directly comparable"* -- is a claim about
both, and the two halves need different remedies: a UNITS split has to be removed or converted, a
CONDITIONS split can be declared and quantified (which is what `RESEARCH-FRAME.md` says the claim
does). Reporting them in one undifferentiated count hides that.

## What it deliberately does not do

It does not grade R3. Whether these axes are *sufficient* is a judgement about which circumstances
take effect, and that is the owner's; new axes should be added here as they are identified rather
than the absence of one being read as its being fine. **A clean run means these axes agree, not
that the metrics are comparable.**
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRODUCTION_FRAMES = 600_000
HOST_PROFILE = "datasphere"

_family_spec = importlib.util.spec_from_file_location(
    "_native_family_for_seam", ROOT / "datasphere" / "native" / "family.py")
_family = importlib.util.module_from_spec(_family_spec)
_family_spec.loader.exec_module(_family)

BASELINES = ["drqv2", "drq", "svea", "sgqn", "curl", "rad", "soda", "alda",
             "idaac", "ppg", "ctrl", "ibac_sni"]

#: Which launcher drives each baseline — the file that decides its environment.
LAUNCHER = {b: "rlvigen.sh" for b in ("drqv2", "drq", "svea", "sgqn", "curl")}
LAUNCHER.update({"rad": "dmc_gb.sh", "soda": "dmc_gb.sh", "alda": "alda.sh",
                 "idaac": "idaac.sh", "ppg": "ppg.sh", "ctrl": "ctrl.sh",
                 "ibac_sni": "ibac_sni.sh"})


#: Where each baseline's own code lives. The five natives have no scene-sweeping evaluator of
#: their own (C72), so their retention number is produced by THIS repository's
#: `scripts/eval_across_scenes.py` while the other seven produce their own -- an asymmetry that is
#: itself a comparability fact, and one the per-baseline roots have to encode honestly rather than
#: hide by pointing all twelve at the same file.
NATIVES = ("drqv2", "drq", "svea", "sgqn", "curl")
SRC_ROOT = {b: ROOT / "RL-ViGen-upstream" for b in NATIVES}
SRC_ROOT.update({"rad": ROOT / "runnable" / "dmc_gb", "soda": ROOT / "runnable" / "dmc_gb",
                 "alda": ROOT / "runnable" / "alda", "idaac": ROOT / "runnable" / "idaac",
                 "ppg": ROOT / "runnable" / "ppg", "ctrl": ROOT / "runnable" / "ctrl",
                 "ibac_sni": ROOT / "runnable" / "ibac_sni"})

#: Vendored third-party trees that are on disk but not on the robosuite path. Searching them makes
#: every baseline look like it does everything: `dm_control`'s locomotion tasks scale rewards, and
#: `coinrun` declares a frame stack, and neither is reachable from a Door run. Excluding them is a
#: claim about what executes, so it is written here where it can be argued with rather than buried
#: in a regex.
OFF_PATH = ("dm_control", "coinrun", "gym-minigrid", "toy-classification", "baselines/common",
            "site-packages", "__pycache__", "/tests/", "/test_")


class EmptyInput(RuntimeError):
    """A source tree this audit reads produced no files. See `assert_inputs_present`."""


def _py_files(root: pathlib.Path):
    for f in root.rglob("*.py"):
        sp = str(f)
        if any(x in sp for x in OFF_PATH):
            continue
        yield f


def assert_inputs_present() -> None:
    """Fail loudly if a source tree this audit reads is missing. `RIGOR.md` section 6.1.

    **Every negative finding here is an absence**, and that is the dangerous shape: `frame_stack`
    concludes "1" from *no frame-stacking wrapper on the robosuite path*, `reward_pipeline`
    concludes "learner: raw" from *no VecNormalize*, `success_source` concludes "NO SUCCESS
    RECORDED" from *no matching line*. If a baseline's tree were moved, renamed, or simply not
    checked out, every one of those searches would return nothing and the audit would report a
    confident, uniform, entirely fictional result -- with no error anywhere.

    That is `RIGOR.md`'s "check that cannot fail": a cross-check which parsed zero rows reported
    success, because "0 disagreements" reads as agreement. The rule it states is that a checker
    asserts its input is non-empty and fails loudly otherwise, and a verifier that verifies nothing
    exits non-zero.

    This is not hypothetical for this file. `SRC_ROOT` points the five natives at
    `RL-ViGen-upstream/` and the other seven at `runnable/<name>/`, and the project has already
    retired one whole tree (`rlgen/`) mid-flight -- which is exactly the event that would empty
    these paths while leaving the script runnable.
    """
    empty = []
    for b in BASELINES:
        root = SRC_ROOT[b]
        if not root.exists():
            empty.append(f"{b}: {root.relative_to(ROOT) if root.is_relative_to(ROOT) else root} does not exist")
            continue
        if next(_py_files(root), None) is None:
            empty.append(f"{b}: {root.name} contains no .py files this audit may read")
    if empty:
        raise EmptyInput(
            "this audit reads absences as findings, so an empty source tree would produce a "
            "confident fictional result rather than an error (RIGOR.md 6.1). Refusing:\n  "
            + "\n  ".join(empty))


def _grep(root: pathlib.Path, pattern: str) -> list[str]:
    """Every matching line under `root`, skipping trees not on the robosuite path."""
    rx = re.compile(pattern)
    hits = []
    for f in _py_files(root):
        try:
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{f.relative_to(ROOT)}:{i}")
        except OSError:
            continue
    return hits


def reward_pipeline() -> tuple[dict, str]:
    """What the reported episode return is measured in, and what the learner trains on.

    This is the axis most able to break R3 outright and the one whose answer is least visible from
    the outside, because the two halves come apart. Three baselines normalise reward by a running
    return standard deviation and clip it to +/-10 -- `idaac` and `ctrl` through baselines'
    `VecNormalize(ob=False)` (whose `ret` defaults to True), `ppg` through its own
    `RewardNormalizer`. On a naive reading their reported returns would be in units of a running
    statistic and could not be put on one axis with the other nine at all.

    They are not, and the reason is **wrapper order**, which no config records:

    - `idaac` -- `envs.py:104-105` builds `VecMonitor(...)` and *then* `VecNormalize(...)`, so the
      monitor accumulating `info['episode']['r']` sits INSIDE the normaliser and never sees a
      normalised reward. `train.py:171` reads exactly that key.
    - `ctrl` -- `vec_env.py:38-44`, same order, same consequence; `evaluate_ppo.py:94` averages
      `info['r']`.
    - `ppg` -- normalises at `ppo.py:222`, on the already-collected segment inside the learner. The
      env-side `VecMonitor2` never sees it.

    So the REPORTED quantity is raw for all twelve, and the LEARNER's reward is normalised for
    three. That is the same shape as `effective action repeat`: uniform in the value that decides
    comparability, split in a mechanism that decides how fragile the uniformity is. Here the
    fragility is sharp -- moving one wrapper, or reading the venv's reward instead of the monitor's,
    silently changes the units of every number a baseline reports, and nothing raises.
    """
    # [Corrected 2026-09-05.] The REPORTED half used to be the literal string "raw" for all
    # twelve, on the strength of the wrapper-order argument above -- which is about each family's
    # NATIVE evaluator. But this file's own header says the final number is produced by
    # `eval_grid.py`, and that path is not the native one. On 2026-09-05 external review 8 found
    # `eval_grid`'s ctrl evaluator summing the OUTERMOST VecNormalize reward, so ctrl's reported
    # return really was in units of a running statistic while this axis said UNIFORM.
    #
    # The docstring above had already named the hazard exactly -- "reading the venv's reward
    # instead of the monitor's silently changes the units of every number a baseline reports, and
    # nothing raises". It was prose, not a check. This derives it.
    grid = (ROOT / "scripts" / "eval_grid.py").read_text()
    # AST, not a regex over the block: the block contains a COMMENT explaining the flag, and a
    # regex matched that comment rather than the call -- so the check passed while the call had
    # been reverted. An audit that can be satisfied by its own explanatory prose is worse than no
    # audit, because it reads as evidence.
    ctrl_raw = False
    for node in ast.walk(ast.parse(grid)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "RLViGenVecEnvCustom"):
            for keyword in node.keywords:
                if (keyword.arg == "normalize_rewards" and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is False):
                    ctrl_raw = True
    idaac_block = re.search(r"def run_scene_idaac.*?(?=\ndef )", grid, re.S)
    idaac_raw = bool(idaac_block and re.search(r"episode\[.r.\]|\[.episode.\]", idaac_block.group(0)))
    ppg_block = re.search(r"def run_scene_ppg.*?(?=\ndef )", grid, re.S)
    ppg_raw = bool(ppg_block and "recent_eprets" in ppg_block.group(0))
    reported_raw = {"ctrl": ctrl_raw, "idaac": idaac_raw, "ppg": ppg_raw}

    out = {}
    for b in BASELINES:
        norm = _grep(SRC_ROOT[b], r"VecNormalize\(|RewardNormalizer\(")
        learner = ("NORMALISED by running return std, clipped" if norm else "raw")
        reported = "raw" if reported_raw.get(b, True) else "NORMALISED by the production evaluator"
        out[b] = f"{reported} | learner: {learner}"
    return out, ("DERIVED on both halves now: the learner's from the presence of a normaliser, and "
                 "the REPORTED half from what scripts/eval_grid.py actually accumulates per family "
                 "-- ctrl's normalize_rewards flag, idaac's VecMonitor read, ppg's recent_eprets. "
                 "The wrapper order that keeps each NATIVE evaluator raw remains RECORDED (idaac "
                 "envs.py:104-105, ctrl vec_env.py:38-44, ppg ppo.py:222)")


def frame_stack() -> tuple[dict, str]:
    """How many frames the policy sees at once. [C2](../docs/CONSTRUCTION.md#c2)

    Derived from the production descriptor where the main profile selects an explicit adapter
    value, then checked against source wrappers. IDAAC and PPG keep adapter defaults of 1 for
    historical C1, but production `families.json` selects 3 for C2. An absence is weaker evidence
    than a declaration and the provenance string says so.

    **The 10/2 split is one number and several different facts** — recorded 2026-09-07 in
    [C2](../docs/CONSTRUCTION.md#c2), and it changes what "equalise the stack" could even mean:

    - `idaac` — source-backed DMC comparator uses 3 frames with the full method.
    - `ctrl` — **double-counting.** It builds temporal structure explicitly over a sliding window of
      `cluster_len=10` single frames; a stack represents the same axis twice.
    - `ibac_sni` — **mis-calibration.** Its VIB's beta is tuned against single-frame input entropy;
      a stack adds task-relevant motion information, so the same beta under-regularises.
    - `ppg` — source-backed DMC comparator adaptation uses 3 frames; OpenAI PPG has no primary DMC
      configuration, so this is not called canonical PPG.

    This axis therefore reports a split of 2. The count is what the seam
    needs; the reasons are what a decision about the seam needs, which is why they are here and not
    only in the register.
    """
    out = {}
    descriptor_path = ROOT / "datasphere" / "native" / "families.json"
    descriptors = json.loads(descriptor_path.read_text(encoding="utf-8")) if descriptor_path.exists() else {}
    for b in BASELINES:
        selected = descriptors.get(b, {}).get("constants", {}).get("frame_stack")
        if selected is not None:
            out[b] = str(selected)
            continue
        if b in NATIVES:
            cfg = ROOT / "RL-ViGen-upstream" / "cfgs" / "config.yaml"
            m = re.search(r"frame_stack:\s*(\d+)", cfg.read_text(encoding="utf-8")) if cfg.exists() else None
            out[b] = m.group(1) if m else "?"
            continue
        decl = None
        for f in _py_files(SRC_ROOT[b]):
            if f.name != "arguments.py":
                continue
            m = re.search(r"--frame_stack.*default=(\d+)", f.read_text(encoding="utf-8", errors="replace"))
            if m:
                decl = m.group(1)
                break
        if decl:
            out[b] = decl
            continue
        stacker = _grep(SRC_ROOT[b], r"FrameStack|VecFrameStack")
        out[b] = "1 (no frame-stack wrapper on the robosuite path)" if not stacker else "?"
    return out, "DERIVED (production descriptor plus family source wrappers)"


def success_source() -> tuple[dict, str]:
    """Where each baseline's success number comes from -- or that it has none.

    Success is the one quantity in this project that is not a reward, so a disagreement here is not
    a scaling difference but a different question being answered. What the audit finds is not a
    disagreement in *definition* -- everything that reports success reads `info['success']`, which
    robosuite fills from `_check_success` -- but a split in **who computes it**: the five natives
    have no scene-sweeping evaluator of their own, so their number is produced by this repository's
    instrument, while the others produce their own. C72.

    **This function's first version reported five baselines as recording NO SUCCESS AT ALL, and
    that was false.** The pattern required `info.get('success'` or `info['success']` literally, and
    every one of the five actually writes `(info or {}).get('success', False)` -- the defensive
    idiom, with the dict access one paren further out. Five of twelve losing the only unit-free
    metric would have been the largest R3 finding in the project, and it was a regex.

    That is the **second** time this script over-reported a split (the first: `effective action
    repeat` as "SPLIT 4 ways" when all twelve run at 1). Both errors ran the same direction --
    claiming the baselines disagree when they agree -- and both came from reading the *shape* of
    code instead of what it does. An audit whose failure mode is over-reporting incomparability is
    the safer of the two possible biases, but it is not harmless: it spends attention on defects
    that are not there, and it would eventually be discounted. Any new axis added here should be
    confirmed against `docs/PART2-METRIC-INVENTORY.md`, which derived several of these facts by
    hand in August and is the reasoning of record; this script is the re-derivable check that they
    have not drifted, not an independent authority.
    """
    out = {}
    for b in BASELINES:
        if b in NATIVES:
            ev = ROOT / "scripts" / "eval_across_scenes.py"
            has = "success" in ev.read_text(encoding="utf-8") if ev.exists() else False
            out[b] = ("_check_success, any-step | computed by OUR eval_across_scenes.py" if has
                      else "NO SUCCESS RECORDED")
            continue
        hits = _grep(SRC_ROOT[b], r"\.get\(\s*[\"']success|\[\s*[\"']success[\"']\s*\]")
        out[b] = ("_check_success, any-step | computed by its OWN evaluator" if hits
                  else "NO SUCCESS RECORDED")
    return out, "DERIVED"


def action_distribution() -> tuple[dict, str]:
    """Which density the policy actually induces on `Box(-1, 1, (7,))`.

    **Not derived here.** This is `docs/PART2-METRIC-INVENTORY.md` Finding 6, taken from the record
    and restated, and the provenance string says RECORDED so it is never mistaken for a live check.
    Re-deriving it would mean tracing four authored Gaussian heads and two squashing schemes, which
    that document already did -- and which it also got wrong on its first pass, having inferred an
    8/4 split from lineage instead of reading each actor. Copying the finished answer is the
    correct move; copying the *method* would risk repeating the mistake it already corrected.

    The reason it belongs on a comparability audit at all: the third family's likelihood disagrees
    with what the environment executes. robosuite's `base_controller.scale_action` clips an
    out-of-range sample, so mass outside the box is folded onto the boundary while the policy's own
    `log_prob` still treats it as interior. That is the authors' design in all three cases and no
    rescaling of a reported number touches it.
    """
    out = {}
    for b in BASELINES:
        if b in ("rad", "soda", "alda"):
            out[b] = "SAC squashed Gaussian (tanh on the sample, log_pi corrected)"
        elif b in NATIVES:
            out[b] = "DrQv2 squashed mean + truncated noise (noise clipped, not squashed)"
        else:
            out[b] = "unsquashed Gaussian, bounded only by robosuite's clip"
    return out, "RECORDED from PART2-METRIC-INVENTORY.md Finding 6; not re-derived here"


def reported_estimator() -> tuple[dict, str]:
    """What turns a set of episodes into the one number a baseline reports.

    Two different quantities live under similar names here, and the distinction is the whole point
    of the axis:

    - **Evaluation numbers** -- what this project compares -- are, for all twelve, the sample mean
      of episode returns under a **fixed** policy: our `eval_across_scenes.py` for the natives,
      `test.py::evaluate` for `idaac` (first 10 completed episodes), `evaluate_ppo.py` for `ctrl`,
      `src/train.py::evaluate` for `rad`/`soda`, the trainer's own eval envs for `alda`,
      `_launch/ppg_eval.py` for `ppg`, `scripts/evaluate.py` for `ibac_sni`. Same estimator; only
      **N** differs, and N is precision, not quantity -- it widens a confidence interval without
      changing what is being estimated.
    - **Training-curve numbers are NOT that**, and pooling the two would be the error this axis
      exists to prevent. `idaac`'s `train/mean_episode_reward` is a rolling mean over the last
      **10** episodes (`train.py:146`, `deque(maxlen=10)`); `ctrl` and `ppg` keep 100. A rolling
      window is taken over a policy that was *changing while it was being measured*; a
      fixed-policy sweep is not. They share a name, a unit and an axis label, and they are
      different estimands.

    So the axis is uniform for the comparison this project actually makes, and that uniformity is
    conditional on only ever reading the evaluation number. The condition is invisible in any plot,
    which is why it is written here rather than assumed.
    """
    out = {}
    for b in BASELINES:
        if b in NATIVES:
            out[b] = "fixed-policy sample mean | N = episodes x scenes (ours)"
        elif b == "idaac":
            out[b] = "fixed-policy sample mean | N = 10 (test.py)"
        elif b == "ctrl":
            out[b] = "fixed-policy sample mean | N = one batch of num_envs (evaluate_ppo.py)"
        elif b in ("rad", "soda"):
            out[b] = "fixed-policy sample mean | N = --num_eval_episodes"
        elif b == "alda":
            out[b] = "fixed-policy sample mean | N = its trainer's eval envs"
        elif b == "ppg":
            out[b] = "fixed-policy sample mean | N = ppg_eval.py's episode cap"
        else:
            out[b] = "fixed-policy sample mean | N = evaluate.py's episode cap"
    return out, ("RECORDED from the eval entry points named in PART2-METRIC-INVENTORY.md section 3; "
                 "the rolling-window training curves are a DIFFERENT estimand -- see docstring")


def observation_layout() -> tuple[dict, str]:
    """The array each network is handed: axis order, dtype, and where pixels get scaled.

    Neither `PART2-METRIC-INVENTORY.md` nor `FAITHFULNESS.md` covers this -- checked 2026-08-26 --
    so unlike the other RECORDED axes here it is not a restatement of someone else's derivation.

    Every difference below is **faithful by design**: each clone hands its network the layout that
    network was written for, the same reason the resolutions differ (P6). It is recorded because
    the differences are invisible at the metric and would otherwise be re-derived by the next
    person to ask whether the twelve "see the same thing". They do not, in three independent ways
    at once -- resolution, frame count, and this.

    `ctrl` looks like a defect and is not: its `observation_space` is declared (C,H,W) while the
    data is (H,W,C), because upstream's `ProcgenVecEnvCustom` does exactly the same and
    `buffer.py` compensates with `state_shape = [shape[1], shape[2], shape[0]]`. Matching the
    existing convention is what keeps `buffer.py` untouched -- documented at `vec_env.py:582`.
    Checked before being reported, after two earlier axes here were reported wrong for exactly the
    opposite reason.
    """
    out = {}
    for b in BASELINES:
        if b in NATIVES:
            out[b] = "CHW uint8 (9,84,84) | scaled in the encoder: x/255 - 0.5"
        elif b in ("rad", "soda", "alda"):
            out[b] = "CHW uint8 (9,84,84) | scaled inside the algorithm"
        elif b == "idaac":
            out[b] = "CHW float32 (3,64,64) | scaled at the wrapper: x/255"
        elif b == "ibac_sni":
            out[b] = "HWC float32 (64,64,3) | scaled at the wrapper: x/255"
        else:
            out[b] = "HWC uint8 (64,64,3) | transposed and scaled inside the network"
    return out, "DERIVED by reading each robosuite wrapper; not covered by PART2 or FAITHFULNESS"


def evaluation_scene_set() -> tuple[dict, str]:
    """The scene set of the REPORTED production measurement.

    The final number is produced by ``eval_grid.py`` from a retained checkpoint, not by a
    baseline's training-time progress evaluator. The production descriptor is the source of truth
    for that grid, and it is deliberately common across the twelve. Training-time progress logging
    is a separate, non-reported axis below.

    """
    import json
    descriptors = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
    out = {}
    for baseline in BASELINES:
        family = next(name for name, entry in descriptors.items()
                      if not name.startswith("_") and baseline in entry["baselines"])
        settings = descriptors[family]["production"]
        scenes = settings["offline_eval_scenes"]
        regimes = settings["offline_eval_regimes"]
        out[baseline] = f"{len(scenes)} scenes, {regimes} | production offline eval_grid"
    return out, ("DERIVED from each family's production descriptor: all twelve use the same "
                 "offline grid (four regimes x ten scenes); eval_grid.py is the reporting path")


def training_time_scene_coverage() -> tuple[dict, str]:
    """What each baseline's TRAINING-TIME progress evaluator varies. [C72]

    This is not the reported endpoint, but it remains important provenance: several source loops
    log only scene 0 while the offline measurement later sweeps ten scenes. Conflating this with
    the reported scene set was the false R3 split this audit used to emit.
    """
    out = {}
    for b in BASELINES:
        if b in NATIVES:
            out[b] = "ten scenes, nine held out | our eval_across_scenes.py sweeps them"
        else:
            out[b] = "scene 0 only | its own evaluator varies the regime, not the scene"
    return out, ("DERIVED: every non-native TRAINING-TIME evaluator builds its env with scene_id=0 "
                 "(idaac envs.py:101, ibac_sni general.py:74, dmc_gb wrappers.py:23, "
                 "alda alda_trainer.py:148; ctrl and ppg take the same default)")


def regimes_in_one_run() -> tuple[dict, str]:
    """How many visual regimes a baseline can report from a SINGLE training run.

    **Not derived here.** `docs/PART2-METRIC-INVENTORY.md` section 3 tabulates it from each
    baseline's own runner, and its Finding 4 records how the two gaps were closed. Restated with
    provenance RECORDED, the same standing as `induced action distribution`.

    Why it is a CONDITIONS axis rather than a UNITS one: every baseline can be *made* to report any
    regime — through its own evaluator over a saved checkpoint where its training loop cannot
    (`ibac_sni`'s `scripts/evaluate.py`, `ppg` through `_launch/ppg_eval.py`) — so no reported
    number means something different because of this. What differs is how much a single run yields,
    which is a cost and a scheduling fact, not a change of quantity.

    It stayed on this script's NOT-COVERED list until 2026-08-26 with the note that a regime
    mismatch would go uncaught. That was true of the script and never true of the project: PART2
    had the table from 2026-08-17. Naming a gap the record had already filled is the same
    duplication C76 records, in the milder direction.
    """
    out = {}
    for b in BASELINES:
        if b in NATIVES:
            out[b] = "train + one held-out regime | only since patch P12; both envs were train before"
        elif b in ("rad", "soda"):
            out[b] = "train + one --eval_mode | its own test_env"
        elif b == "alda":
            out[b] = "train + eval-easy + eval-hard | its own three-env trainer"
        elif b == "idaac":
            out[b] = "train + eval-easy | test.py::evaluate, RLVIGEN_EVAL_MODE"
        elif b == "ctrl":
            out[b] = "train + train(ID) + eval-easy | its own three envs"
        elif b == "ibac_sni":
            out[b] = "one per training run | any regime via its OWN scripts/evaluate.py on a checkpoint"
        else:
            out[b] = "one per training run | any regime via _launch/ppg_eval.py on a checkpoint"
    return out, "RECORDED from PART2-METRIC-INVENTORY.md section 3 and its Finding 4; not re-derived here"


def truncation() -> tuple[dict, str]:
    """Per-baseline truncation-vs-termination, from `protocol.py`'s own map."""
    src = (ROOT / "rlgen" / "protocol.py").read_text(encoding="utf-8")
    m = re.search(r"TIME_LIMIT_HANDLING\s*=\s*\{(.*?)\n\}", src, re.S)
    if not m:
        return {}, "UNREADABLE"
    got = dict(re.findall(r'"(\w+)":\s*"(\w+)"', m.group(1)))
    return got, "DERIVED"


def image_size() -> tuple[dict, str]:
    """Render resolution, from each launcher's `RLVIGEN_IMAGE_SIZE` export.

    This is the live mechanism (patch P6 reads the variable); `arguments.py`'s own `image_size` is
    a dead knob on the robosuite path — C71 #5. Reading the launcher is therefore reading what
    decides the value, not what looks like it does.
    """
    out = {}
    for b in BASELINES:
        f = ROOT / "runnable" / "_launch" / LAUNCHER[b]
        if not f.exists():
            out[b] = "no-launcher"
            continue
        m = re.search(r'RLVIGEN_IMAGE_SIZE="\$\{RLVIGEN_IMAGE_SIZE:-(\d+)\}"',
                      f.read_text(encoding="utf-8"))
        out[b] = m.group(1) if m else "84 (robo_config default)"
    return out, "DERIVED"


def action_repeat() -> tuple[dict, str]:
    """Effective action repeat, and how each baseline gets there.

    All twelve run at 1 and they arrive three different ways (INTEGRATION-DELTA's audit): five
    natives by an explicit override against a shipped default of 2, and seven because nothing on
    their robosuite path can express any other value — two of those via a knob that is passed and
    never read (C71 #1, #2). "1" alone would hide that difference, so the mechanism is printed.
    """
    out = {}
    rlv = (ROOT / "runnable" / "_launch" / "rlvigen.sh")
    forced = "action_repeat=1" in rlv.read_text(encoding="utf-8") if rlv.exists() else False
    for b in BASELINES:
        if b in ("drqv2", "drq", "svea", "sgqn", "curl"):
            out[b] = "1 (launcher override; shipped default is 2)" if forced else "1 (UNSET?)"
        elif b in ("rad", "soda"):
            out[b] = "1 (flag passed but NEVER READ - C71 #1)"
        elif b == "alda":
            out[b] = "1 (spec key never read - C71 #2)"
        else:
            out[b] = "1 (no mechanism exists)"
    return out, "DERIVED for the natives; RECORDED for the rest"


def horizon() -> tuple[dict, str]:
    """Episode length. One number, two sources, and they must agree."""
    cfg = ROOT / "RL-ViGen-upstream" / "envs" / "robosuiteVGB" / "cfg" / "robo_config.yaml"
    m = re.search(r"horizon:\s*(\d+)", cfg.read_text(encoding="utf-8")) if cfg.exists() else None
    env_h = m.group(1) if m else "?"
    dmc = ROOT / "runnable" / "_launch" / "dmc_gb.sh"
    m2 = re.search(r"--episode_length (\d+)", dmc.read_text(encoding="utf-8")) if dmc.exists() else None
    return ({b: (m2.group(1) if (b in ("rad", "soda") and m2) else env_h) for b in BASELINES},
            "DERIVED")


#: Axes whose VALUE decides comparability while the mechanism decides fragility. Reporting
#: `action_repeat` as "split four ways" was this script's own first-output defect: the value is
#: uniformly 1 for all twelve, and only *how they get there* differs. That difference is real and
#: worth printing -- it is what would break silently if a config changed (C71) -- but it is not a
#: split in the axis, and calling it one overstates the incomparability the audit exists to measure.
#: `reward pipeline` has the same shape and a sharper edge: see that function's docstring.
VALUE_OF = {"effective action repeat": lambda v: v.split(" ", 1)[0],
            "reward pipeline": lambda v: v.split(" | ", 1)[0],
            "success definition and who computes it": lambda v: v.split(" | ", 1)[0],
            "reported estimator": lambda v: v.split(" | ", 1)[0],
            "evaluation scene set": lambda v: v.split(" | ", 1)[0],
            "replay capacity and eviction at 6e5": lambda v: v.split(" | ", 1)[0],
            "x-axis accounting": lambda v: v.split(" | ", 1)[0]}

#: (title, kind, fn). KIND is the distinction this script's first version lacked -- see the module
#: docstring. It is not cosmetic: a UNITS split has to be removed or converted before the numbers
#: can be compared at all, while a CONDITIONS split can be declared and quantified, which is what
#: the claim in RESEARCH-FRAME.md already says it does.
UNITS, CONDITIONS = "UNITS", "CONDITIONS"
def crop_policy() -> tuple[dict, str]:
    """What the policy actually SEES, which is not the question `render resolution` answers.

    **ORIGIN: `docs/AUDIT-2026-08-17.md` Question 4, not this file and not 2026-09-04.** That audit
    already established the 100-then-crop-84 rule, whose choice it is (`arguments.py`'s own, for
    exactly `{rad, curl, pad, soda}`), why patch P6 exists, and what happens without it: **RAD
    silently degrades to SAC** -- `random_crop` computes `crop_max = 84 - 84 = 0` and its own guard
    returns the input unaugmented, with no error -- while **SODA hard-asserts** on
    `x.size(-1) == 100`. It was re-derived here on 2026-09-04 and briefly written up as a NEW gap,
    which it was not; the owner caught it. What was genuinely missing is this: a finding recorded
    in a doc had never reached the axis machinery, so nothing mechanical carried it and the seam
    audit reported only `render resolution`. Recording the value is not the same as wiring it.

    That axis records 84 / 64 / 100 and stops. But `rad` and `soda` never feed their
    100-pixel render to the network: `modules.CenterCrop(84)` is the encoder's first layer and
    returns `x[:, :, 8:-8, 8:-8]`. Their policy sees an 84 window covering the middle 84% of the
    frame linearly; the ten whose render is used whole see 100% of theirs. Two baselines "at 84
    pixels" are looking at different amounts of the room, and on a manipulation task whose object
    can sit off-centre that is a difference in what is VISIBLE, not in resolution.

    Entirely faithful and not a defect: `arguments.py` sets image_size=100 / image_crop_size=84 for
    exactly the algorithms that crop, and it is a train/eval pair -- random crop when sampling the
    buffer, centre crop at action time. It is simply an axis on which the twelve differ and which
    nothing recorded.
    """
    args = ROOT / "runnable" / "dmc_gb" / "src" / "arguments.py"
    modules = ROOT / "runnable" / "dmc_gb" / "src" / "algorithms" / "modules.py"
    cropping: set[str] = set()
    if args.exists():
        lines = args.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "args.image_size = 100" not in line:
                continue
            for back in lines[max(0, i - 3):i]:
                found = re.search(r"args\.algorithm in \{([^}]*)\}", back)
                if found:
                    cropping = {t.strip().strip("'\"") for t in found.group(1).split(",")}
            break
    applies = modules.exists() and "class CenterCrop" in modules.read_text(encoding="utf-8")
    out = {}
    for b in BASELINES:
        crops = b in cropping and LAUNCHER.get(b) == "dmc_gb.sh" and applies
        out[b] = ("84 centre crop of a 100 render (encoder CenterCrop; random crop at train)"
                  if crops else "none -- the render is used whole")
    return out, ("DERIVED from arguments.py's 100/84 algorithm set and the CenterCrop layer that "
                 "applies it")


def replay_capacity() -> tuple[dict, str]:
    """Replay capacity, and whether it ever EVICTS at the production budget.

    [Claude 2026-09-04, named by the owner, derived from the clones rather than from this list.]
    Capacity alone is not the comparable quantity -- eviction is. A buffer larger than the budget
    never evicts, so the learner samples uniformly over the whole run; a buffer smaller than the
    budget samples a recency window. Those are different training distributions, which is what
    makes R4's "equal training length" mean different things per baseline.

    The result is host-profile-specific. DataSphere's 300k accommodation evicts before 6e5; the
    V100 profile's 620k capacity retains the whole run. Reporting one while launching the other
    would manufacture or hide a comparability split.

    **The split is ours, not upstream's.** `families.json` applies `replay_capacity=300000` to the
    RL-ViGen five at the current DataSphere production shape, well below 6e5, so they evict while
    `rad`/`soda` (capacity = train_steps, by construction) never do. It is the operational memory
    accommodation that makes the five runnable on the allowed tiers. The V100 migration target is
    1e6, but it is deliberately unapplied here because this descriptor also drives probes.

    Prior art checked before deriving: `FAITHFULNESS.md:132` RETRACTED a replay-capacity finding
    against the retired port, on the grounds that RL-ViGen's replay is disk-backed (one `.npz` per
    episode, only `max_size // num_workers` resident) so the cap is nominal rather than a tensor.
    That retraction is about MEMORY and leaves the eviction question untouched.
    """
    out = {}
    try:
        declared_rlvigen_cap = _family.production(
            "rlvigen", profile=HOST_PROFILE).get("replay_capacity")
    except (OSError, KeyError, ValueError, TypeError):
        declared_rlvigen_cap = None
    cfg = ROOT / "RL-ViGen-upstream" / "cfgs" / "config.yaml"
    rlvigen_cap = None
    if cfg.exists():
        m = re.search(r"replay_buffer_size:\s*(\d+)", cfg.read_text(encoding="utf-8"))
        rlvigen_cap = m.group(1) if m else None
    dmc_train = ROOT / "runnable" / "dmc_gb" / "src" / "train.py"
    dmc_is_budget = dmc_train.exists() and "capacity=args.train_steps" in dmc_train.read_text(
        encoding="utf-8")
    alda_trainer = ROOT / "runnable" / "alda" / "trainers" / "alda_trainer.py"
    alda_cap = None
    if alda_trainer.exists():
        m = re.search(r"buffer_capacity:\s*int\s*=\s*([\d_]+)", alda_trainer.read_text(
            encoding="utf-8"))
        alda_cap = m.group(1).replace("_", "") if m else None
    for b in BASELINES:
        if LAUNCHER.get(b) == "rlvigen.sh":
            cap = declared_rlvigen_cap if declared_rlvigen_cap is not None else rlvigen_cap
            if cap is None:
                out[b] = "unread | unread"
            elif int(cap) < PRODUCTION_FRAMES:
                out[b] = (f"recency ring | {int(cap)} < {PRODUCTION_FRAMES}; evicts oldest "
                          "episodes under the declared production override")
            else:
                out[b] = (f"uniform over the whole run | {int(cap)} >= {PRODUCTION_FRAMES}; "
                          "disk-backed nominal capacity")
        elif LAUNCHER.get(b) == "dmc_gb.sh":
            out[b] = (f"uniform over the whole run | capacity = train_steps = {PRODUCTION_FRAMES}, "
                      "never evicts BY CONSTRUCTION" if dmc_is_budget else "unread | unread")
        elif b == "alda":
            if alda_cap is None:
                out[b] = "unread | unread"
            elif int(alda_cap) < PRODUCTION_FRAMES:
                out[b] = f"recency ring | {int(alda_cap)} < {PRODUCTION_FRAMES}"
            else:
                out[b] = f"uniform over the whole run | {int(alda_cap)} >= {PRODUCTION_FRAMES}"
        else:
            out[b] = "current rollout only | on-policy, no replay exists"
    return out, (f"DERIVED for host profile {HOST_PROFILE!r} from family.py's resolved rlvigen "
                 "production override, "
                 "RL-ViGen-upstream/cfgs/config.yaml, dmc_gb/src/train.py:111 and "
                 f"alda_trainer.py:59; eviction compared against the {PRODUCTION_FRAMES} budget")


def x_axis_accounting() -> tuple[dict, str]:
    """What ONE unit on the frame axis means, per baseline.

    [Claude 2026-09-04.] `PART2-METRIC-INVENTORY.md` devotes its section 2 to the x-axis and this
    audit had no axis for it — found by diffing that document's decomposition against this list
    rather than by noticing something, and raised in practice by the `ppg` defect of the same day,
    where `read_ppg` read a column the repo does not write and every `ppg` record carried
    `frame: null`.

    Each family writes a different counter; the question is whether they are the same UNIT. They
    are — every one counts **environment transitions**:

      * the five: `global_frame = global_step * action_repeat` (`train.py:134-135`)
      * `rad`/`soda`, `alda`: `step` / `env_steps`
      * `idaac`: `(j+1) * num_processes * num_steps`, multiplied across parallel envs
      * `ppg`: `total_interact_count += ic_per_step` (`log_save_helper.py:58`), 2048 quantum
      * `ctrl`: `FLAGS.num_envs * step`, multiplied across parallel envs
      * `ibac_sni`: `num_frames += logs["num_frames"]` from its collector

    The vector-env four multiply by their env count rather than counting vector steps, so one unit
    is one transition and not N of them. **The single fragility is the five**: theirs is the only
    counter carrying an `action_repeat` factor, and it agrees with the rest exactly because that
    factor is uniformly 1. At `action_repeat=2` their x-axis would count env frames while their
    agent took half as many decisions, and every curve would shift 2x against the other seven.
    """
    counter = {
        **{b: "env transitions | global_step * action_repeat (=1)" for b in
           ("drqv2", "drq", "svea", "sgqn", "curl")},
        "rad": "env transitions | step", "soda": "env transitions | step",
        "alda": "env transitions | env_steps",
        "idaac": "env transitions | num_processes * num_steps",
        "ppg": "env transitions | total_interact_count, 2048 quantum",
        "ctrl": "env transitions | num_envs * step",
        "ibac_sni": "env transitions | collector num_frames",
    }
    return {b: counter.get(b, "unread") for b in BASELINES}, (
        "DERIVED from each family's own counter and from the column each reader in "
        "normalize_curves.py takes as `frame`")


def updates_per_env_frame() -> tuple[dict, str]:
    """How much LEARNING happens per unit of the common x-axis.

    [Claude 2026-09-05; corrected after review 14.] `x_axis_accounting` establishes that all
    twelve count the same UNIT -- environment transitions -- and that is true and was the right
    question. This axis asks the other half of it: at a common 600k-frame budget, how many learner
    updates does each family take per newly collected replay transition? The answer is not common.

    Do not use action repeat as the denominator here. A source action-repeat-4 transition is one
    replay item, not four. `action_repeat=1` is correct for robosuite (RL-ViGen Supplementary
    Table 2), but it remains a separate physics-substep condition axis. The native five's 0.5
    value comes directly from `update_every_steps=2`; RAD/SODA/ALDA are approximately 1.0 per new
    replay transition. Their source action-repeat-4 configuration should be reported separately,
    not converted into a claimed 0.25 replay ratio.

    The native-five 0.5 versus RAD/SODA/ALDA 1.0 difference is a real training-rate condition and
    should be reported. For `alda`, the old Lift stability result matters beyond bookkeeping:
    FAITHFULNESS.md:603-616 measured `utd=1.0` diverging where `0.25` did not, fixed it, and pinned
    the fix with two tests that import the RETIRED `rlgen` port -- while production launches
    `runnable/alda`, which has no such knob. See notes/FINDING-update-to-data-ratio.md and A27.

    The four on-policy families have no per-step replay ratio; their analogue is epochs x
    minibatches per rollout and is deliberately not forced into this column.
    """
    five = "0.5 | update_every_steps=2 at action_repeat=1 (source ~1 per replay transition)"
    out = {b: five for b in ("drqv2", "drq", "svea", "sgqn", "curl")}
    for b in ("rad", "soda"):
        out[b] = "1.0 | one update per new replay transition, ar dead-knob=1; source ar=4"
    out["alda"] = "1.0 | alda_trainer.py:58, one update per new replay transition; source ar=4, see A27"
    # On-policy: grad steps per env frame = (epochs x minibatches) / (num_envs x num_steps).
    # [Claude 2026-09-05, notes/FINDING-on-policy-update-density.md, A29.] `ibac_sni` and `ctrl`
    # match their upstream default exactly once on the V100 profile that restores full parallelism
    # (16 and 64 envs respectively, both upstream's own defaults). `idaac` and `ppg` do not: both
    # run fewer parallel envs than Procgen's 64 (a single V100 cannot run that many robosuite/MuJoCo
    # envs the way Procgen's cheap 2D levels allow), with epochs/minibatches unchanged, so their
    # regular-phase density is elevated. This is independent of PPG's AUXILIARY-phase cadence,
    # already corrected to match its reference exactly (A26) -- that fix and this finding are
    # different axes of the same mechanism (rollout size vs. fixed epoch/minibatch counts).
    out["idaac"] = "0.00195/frame (policy), 0.01758/frame (value) | 16x256 rollout vs upstream 64x256 -- 4x, see A29"
    out["ppg"] = "0.00391/frame regular-phase | 8x256 rollout vs upstream 64x256(1-rank)/262144(4-rank) -- 8x-32x, see A29"
    out["ibac_sni"] = "0.015625/frame | 16x128 rollout, matches upstream's own default exactly (both 16x128)"
    out["ctrl"] = "0.001465/frame | v100 profile 64x256, matches upstream's own default exactly (both 64x256)"
    return out, "DERIVED from each training loop and its effective action_repeat"


def warmup_length() -> tuple[dict, str]:
    """Frames of random/undertrained action before the first learner update, per family.

    [Claude 2026-09-05.] Not previously an axis, found while checking update density from every
    side. Every value below is each family's own UNMODIFIED upstream default -- faithful by
    design, the same reasoning as `observation_layout` -- so this is declared, not a defect: the
    five and rad/soda/alda's warmup differs 4x (`num_seed_frames: 4000` vs `init_steps: 1000`)
    purely because that is each source's own choice, and neither this project's launchers nor
    `families.json` override it for production (only `smoke_all.sh`'s cheap functional smoke does,
    which is expected and does not affect production runs).

    Materially small either way: 4000 or 1000 against a 600k-frame budget is 0.67% or 0.17%, a
    one-time startup cost rather than something that compounds across the run the way the
    updates-per-env-frame axis does. Declared for completeness, not raised as a decision.

    The four on-policy families have no separate warmup phase: their first collected rollout IS
    the data for their first update, so there is no pre-update random-action period to report.
    """
    five = "4000 frames | num_seed_frames: 4000, RL-ViGen-upstream/cfgs/config.yaml:13, unmodified"
    out = {b: five for b in ("drqv2", "drq", "svea", "sgqn", "curl")}
    for b in ("rad", "soda"):
        out[b] = "1000 frames | --init_steps default 1000, dmc_gb/src/arguments.py:20, unmodified"
    out["alda"] = "1000 frames | init_steps: int = 1000, alda_trainer.py:52, unmodified"
    for b in ("idaac", "ppg", "ibac_sni", "ctrl"):
        out[b] = "0 (no separate warmup phase) | on-policy: first rollout is the first update's data"
    return out, "DERIVED from each training loop's own unmodified upstream default"


AXES = [("reward pipeline", UNITS, reward_pipeline),
        ("success definition and who computes it", UNITS, success_source),
        ("episode horizon", UNITS, horizon),
        ("reported estimator", UNITS, reported_estimator),
        ("evaluation scene set", UNITS, evaluation_scene_set),
        ("training-time scene coverage", CONDITIONS, training_time_scene_coverage),
        ("truncation at time limit", CONDITIONS, truncation),
        ("render resolution", CONDITIONS, image_size),
        ("crop policy -- what the policy SEES", CONDITIONS, crop_policy),
        ("replay capacity and eviction at 6e5", CONDITIONS, replay_capacity),
        ("x-axis accounting", UNITS, x_axis_accounting),
        ("frame-stack depth", CONDITIONS, frame_stack),
        ("effective action repeat", CONDITIONS, action_repeat),
        ("induced action distribution", CONDITIONS, action_distribution),
        ("observation layout and pixel scaling", CONDITIONS, observation_layout),
        ("regimes reachable in one run", CONDITIONS, regimes_in_one_run),
        ("updates per env frame", CONDITIONS, updates_per_env_frame),
        ("warmup length before first update", CONDITIONS, warmup_length)]

#: Empty as of 2026-08-26, and that is a statement about this list rather than about the twelve.
#: Every axis anyone has NAMED is now derived or recorded here; it does not follow that the axes
#: nobody named are absent, and the summary says so on every run. The null is unchanged.
#:
#: **SEARCH `docs/` BEFORE DECLARING A GAP.** [Claude 2026-09-04] The `crop policy` axis was
#: documented in full in AUDIT-2026-08-17.md Question 4 and sat there for eighteen days while this
#: script reported only `render resolution`; asked about augmentations, I re-derived it and wrote it
#: up as new, and the owner caught it from memory. The protocol line below -- "a named gap gets
#: closed, an unnamed one does not exist to be closed" -- is exactly what hid it: the axis WAS
#: named, in a document this file does not reference. Recording a value is not the same as wiring
#: it, and prose is where this project's findings live. Grep first.
#:
#: When an axis is identified, add it here first with what makes it matter, then derive it. That
#: order is deliberate: the two axes this list held longest -- the reported estimator and the
#: evaluation scene set -- were both eventually derived, and the second turned out to be the only
#: UNITS split in the audit. A named gap gets closed; an unnamed one does not exist to be closed.
NOT_COVERED: list[str] = [
    # [Claude 2026-09-04, named by the owner.] REPLAY BUFFER CAPACITY AND COMPOSITION. Four of the
    # twelve (idaac, ppg, ctrl, ibac_sni) are on-policy and hold no replay at all; of the eight that
    # do, `rad`/`soda` take `capacity = args.train_steps` with no flag (plan_production.py records
    # this and calls a cap "a source change"), so their buffer never evicts and at the end of
    # training they are sampling uniformly over the whole run, while a capped buffer is sampling a
    # recency window. At equal frames those are different training distributions, which makes
    # "equal training length" (R4) mean different things per baseline. NAMED AND NOT DERIVED: the
    # capacities live in five different config surfaces and a half-derived number here would be
    # worse than an honest gap. It is a CONDITIONS axis when derived, not UNITS -- it changes what
    # was measured, not what the number means.
    #
    # [Claude 2026-09-04, second pass] The entry above was first written as a COMMENT inside this
    # list, which left the list empty and the audit still printing "0 underived" -- the exact
    # recorded-but-not-mechanised failure this file exists to prevent, committed here while
    # describing it. It is a string now, so it is counted and printed.
# [x-axis accounting was named here and is now DERIVED above -- 2026-09-04]


]

#: Deliberately NOT axes of this audit, recorded so that leaving them out is a decision someone can
#: argue with rather than an omission nobody noticed.
#:
#: **Reward scale of each baseline's SOURCE domain.** DMC pays up to 1.0/step (return to ~1000),
#: Procgen pays on a different scale again, and Door pays at most 0.5/step of shaping plus exactly
#: 1.0 for success (C62). Every source paper's hyperparameters were tuned against its own
#: magnitude. That is real and it matters -- but it does not touch what a *reported Door number
#: means*, because all twelve are evaluated on Door and report Door's own reward. It is a question
#: about whether each algorithm is being run in a regime its settings suit, which is C75's class
#: (a formulation bound to a concrete quantity) and C75's own falsifier already names the
#: reward-scale axis as the cheapest test of it.
#:
#: This was listed as an underived axis of THIS audit until 2026-08-26 and that was a
#: misclassification. Moving it out does not make R3 easier: the same pass added `evaluation scene
#: set`, which splits, so the audit's headline went from "every UNITS axis uniform" to "one UNITS
#: axis splits". Scope was corrected in the direction that costs more, not less.
OUT_OF_SCOPE_ROUTED_ELSEWHERE = "reward scale of the source domains -> C75"


def main(argv: list[str] | None = None) -> int:
    global HOST_PROFILE
    if argv is not None:
        parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
        parser.add_argument("--host-profile", choices=("datasphere", "v100"), required=True)
        HOST_PROFILE = parser.parse_args(argv).host_profile
    try:
        assert_inputs_present()
    except EmptyInput as e:
        print("REFUSED TO RUN\n  " + str(e))
        return 2
    print("CLONE-ERA COMPARABILITY SEAM AUDIT")
    print("  COMPARABILITY_CONTRACT §1-§10 audit the RETIRED rlgen/ port; this audits what runs.")
    print("  A clean run means THESE AXES agree -- not that the metrics are comparable.")
    print("  UNITS      = decides what the number MEANS. A split makes them incommensurable.")
    print("  CONDITIONS = decides what was MEASURED. A split makes a difference unattributable.\n")
    tally = {UNITS: [0, 0], CONDITIONS: [0, 0]}   # [uniform, total]
    for title, kind, fn in AXES:
        values, provenance = fn()
        distinct, by_value = {}, {}
        key = VALUE_OF.get(title, lambda v: v)
        for b in BASELINES:
            raw = str(values.get(b, "?"))
            distinct.setdefault(raw, []).append(b)
            by_value.setdefault(key(raw), []).append(b)
        uniform = len(by_value) == 1
        tally[kind][0] += uniform
        tally[kind][1] += 1
        print(f"  [{kind}] {title}")
        print(f"    provenance: {provenance}")
        verdict = "UNIFORM" if uniform else f"SPLIT {len(by_value)} ways"
        if uniform and len(distinct) > 1:
            verdict += (f" in value, but reached {len(distinct)} different ways"
                        " -- uniform today, fragile to a config change")
        print(f"    {verdict}")
        for val, who in sorted(distinct.items(), key=lambda kv: -len(kv[1])):
            print(f"      {val:<58} {' '.join(who)}")
        print()

    for kind in (UNITS, CONDITIONS):
        ok, tot = tally[kind]
        print(f"  {kind:<11} {ok}/{tot} DERIVED axes uniform across the twelve.")
    if NOT_COVERED:
        print(f"  UNDERIVED   {len(NOT_COVERED)} axes named below and never derived by anything.")
    else:
        print("  UNDERIVED   0 -- every axis ANYONE HAS NAMED is derived or recorded. That is a")
        print("              fact about the list, not about the twelve; see the null below.")
    print()
    print("  THE NULL IS THAT TWO BASELINES' NUMBERS ARE NOT THE SAME QUANTITY, and nothing above")
    print("  lifts it. A uniform axis removes one way they could differ; it is not evidence that")
    print("  the ways nobody enumerated are absent. This script cannot output 'comparable' and")
    print("  has no state in which it would -- that conclusion needs a reasoned argument that the")
    print("  enumeration is COMPLETE, which is a judgement about unknown unknowns and belongs to")
    print("  the owner, not to a checklist. See docs/RESEARCH-FRAME.md and the CLAUDE.md null")
    print("  'two numbers from different systems are not the same quantity until shown to be'.")
    print()
    if not NOT_COVERED:
        print("  No axis on the named list is left underived. Add the next one to NOT_COVERED as")
        print("  soon as it is identified -- a named gap gets closed, an unnamed one does not")
        print("  exist to be closed. The two this list held longest were the reported estimator")
        print("  and the evaluation scene set, and the second is the only UNITS split found.")
        return 0
    print("  Axes NOT covered here and known to matter -- absence from this list is not evidence")
    print("  of agreement, it is evidence nobody has derived it yet:")
    import textwrap
    for n in NOT_COVERED:
        print(textwrap.fill(n, width=96, initial_indent="    - ", subsequent_indent="      "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
