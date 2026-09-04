"""Protocol, env seam, replay buffer, agents, registry, generated files.

Every test here names the defect it exists to catch. Tests whose failure mode is subtle are
red-green verified in `mutants/catalogue.py` -- the mutation runner reverts the guard in the
production code and requires this suite to go red.
"""
from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from rlgen import registry, tags  # noqa: E402
from rlgen.agents import RandomAgent, assert_respects_deterministic, policy_for  # noqa: E402
from rlgen.envs import ContractError, EnvSpec, make_env  # noqa: E402
from rlgen.protocol import MODES, Protocol  # noqa: E402
from rlgen.replay import FrameReplay  # noqa: E402


# ============================================================================ protocol
def test_hash_ignores_labels_and_provenance_but_nothing_else():
    p = Protocol(task="Door")
    assert p.hash() == p.replace(name="other", seed=99, weights_source="x",
                                 code_commit="y").hash()
    for field, value in [("episodes_per_scene", 5), ("action_repeat", 2), ("horizon", 250),
                         ("eval_mode", "eval-hard"), ("policy_mode", "stochastic"),
                         ("aggregation", "iqm"), ("image_size", 64), ("frame_stack", 1),
                         ("total_frames", 1), ("eval_scene_ids", (0,))]:
        assert p.hash() != p.replace(**{field: value}).hash(), \
            f"{field} does not affect the protocol hash, so two runs differing in it would be " \
            f"treated as comparable"


def test_differences_names_exactly_what_broke_comparability():
    a = Protocol(task="Door")
    b = a.replace(episodes_per_scene=5, action_repeat=2)
    assert set(a.differences(b)) == {"episodes_per_scene", "action_repeat"}
    assert not a.comparable_to(b) and a.comparable_to(a.replace(seed=7))


def test_protocol_rejects_impossible_values():
    for kw in [dict(task="Nope"), dict(eval_mode="eval-extreme"), dict(policy_mode="argmax"),
               dict(episodes_per_scene=0), dict(eval_scene_ids=()),
               dict(horizon=501, action_repeat=2)]:
        with pytest.raises(ValueError):
            Protocol(**kw)


def test_card_states_every_field_that_moves_a_number():
    """The previous card omitted action_repeat, frame_stack and the episode count entirely."""
    card = Protocol(task="Lift").card()
    for k in ("action_repeat", "frame_stack", "image_size", "horizon", "episodes_per_scene",
              "eval_scene_ids", "aggregation", "policy_mode", "total_frames", "code_commit",
              "weights_source", "hash"):
        assert k in card, f"protocol card does not state {k!r}"


def test_no_protocol_value_is_hardcoded_outside_this_module():
    """Numbers that define the protocol may not be literals elsewhere in first-party code."""
    import ast
    from tests.test_eval_identity import first_party_sources, is_vendored
    telltale = {84: "image_size", 500: "horizon"}
    offenders = []
    for path in first_party_sources():
        rel = os.path.relpath(path, ROOT)
        # `rlgen/algos/` is vendored reference code -- see VENDORED_DIRS in test_eval_identity.py
        if rel.startswith(("rlgen/protocol.py", "tests/", "mutants/")) or is_vendored(path):
            continue
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in telltale:
                offenders.append(f"{rel}:{node.lineno} ({telltale[node.value]}={node.value})")
    assert not offenders, ("protocol-determining literal(s) outside rlgen/protocol.py: "
                           + ", ".join(offenders))


# ============================================================================ env seam
def spec(**kw):
    d = dict(task="Door", mode="train", scene_id=0, seed=0, backend="synthetic", horizon=20)
    d.update(kw)
    return EnvSpec(**d)


def test_env_spec_is_actually_immutable():
    """`EnvSpec` is `@dataclass(frozen=True)` -- this pins that the decorator is doing real work,
    not just declaring an intent nothing checks. Found by mutation testing (Stage 3 of the
    comparability-contract meta-plan): flipping `frozen=True` to `False` survived the whole suite,
    meaning nothing previously distinguished a genuinely-immutable EnvSpec from a mutable one that
    just happens not to be mutated by current code paths. A shared, derived-from-Protocol spec
    (`spec_from_protocol`) that a caller COULD mutate after construction is exactly the kind of
    silent cross-run contamination this project's `frozen=True` is meant to rule out by
    construction, not by convention."""
    import dataclasses
    e = spec()
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.task = "Lift"


def test_obs_shape_is_derived_from_the_factory_not_declared():
    """The previous harness hand-declared (3,84,84) while the pipeline produced (9,84,84)."""
    e = make_env(spec())
    obs = e.reset()
    assert obs.shape == e.obs_shape == e.spec.obs_shape
    assert obs.shape[0] == 3 * e.spec.frame_stack
    assert obs.dtype == np.uint8


def test_contract_violation_raises_rather_than_warns():
    with pytest.raises(ContractError):
        from rlgen.envs import _assert_contract
        _assert_contract(spec(), np.zeros((9, 84, 84), dtype=np.float32), 7)
    with pytest.raises(ContractError):
        from rlgen.envs import _assert_contract
        _assert_contract(spec(), np.zeros((3, 84, 84), dtype=np.uint8), 7)


def test_act_dim_boundary_is_pinned_at_exactly_one():
    """`_assert_contract` raises on `act_dim < 1` -- i.e. `act_dim == 1` is accepted, `act_dim == 0`
    is not. Every real baseline in this project uses act_dim=7, so this exact boundary was never
    exercised by any other test -- found surviving mutation testing (Stage 3), both the `<` -> `<=`
    and the `1` -> `2` mutants, meaning act_dim==1 being valid was an unpinned assumption, not a
    checked one."""
    from rlgen.envs import _assert_contract
    ok_obs = np.zeros((9, 84, 84), dtype=np.uint8)
    _assert_contract(spec(), ok_obs, 1)  # must NOT raise
    with pytest.raises(ContractError):
        _assert_contract(spec(), ok_obs, 0)


def test_truncation_lands_exactly_on_the_horizon():
    """Door/Lift never terminate early, so every end is a time limit at a known step."""
    e = make_env(spec(horizon=13, action_repeat=1))
    e.reset()
    for t in range(1, 14):
        _o, _r, term, trunc, info = e.step(np.zeros(e.act_dim, dtype=np.float32))
        assert not term
        assert trunc == (t == 13), f"step {t}: truncated={trunc}"
    assert info["episode"]["l"] == 13


def test_action_repeat_shortens_the_episode():
    """`steps_per_episode` is horizon // action_repeat, and the episode really ends there.

    Added because mutant M4 (`return self.horizon`, dropping the division) SURVIVED the suite:
    every other episode-length test ran at action_repeat=1, where the two are equal and the
    defect is invisible. Frames-vs-agent-steps conflation is the single most common source of
    factor-of-N errors in RL tables, so it gets its own test at a repeat that can see it.
    """
    for repeat, expected in ((1, 12), (2, 6), (3, 4)):
        sp = spec(horizon=12, action_repeat=repeat)
        assert sp.steps_per_episode == expected
        e = make_env(sp)
        e.reset()
        for t in range(1, expected + 1):
            _o, _r, _term, trunc, info = e.step(np.zeros(e.act_dim, dtype=np.float32))
            assert trunc == (t == expected), \
                f"action_repeat={repeat}: truncated={trunc} at step {t}, expected end at {expected}"
        assert info["episode"]["l"] == expected

    p = Protocol(task="Door", horizon=12, action_repeat=3)
    assert p.steps_per_episode == 4, "Protocol and EnvSpec disagree about episode length"


def test_scene_and_mode_travel_with_every_step():
    e = make_env(spec(mode="eval-easy", scene_id=7))
    e.reset()
    _o, _r, _t, _tr, info = e.step(np.zeros(e.act_dim, dtype=np.float32))
    assert info["scene_id"] == 7 and info["mode"] == "eval-easy"


# ================================================================ choke-point instrumentation
# Meta-plan (comparability contract): rlgen/envs.py is the one environment-construction choke
# point every baseline must go through, training and eval alike. These tests pin the ground-truth
# instrumentation (step_calls, action_clip_events, max_abs_action_seen) a per-baseline pipeline's
# own reported frame count and action scale get cross-checked against, per that plan's Stage 2/3.
def test_step_calls_counts_every_real_step_and_survives_reset():
    """step_calls is lifetime, unlike `_t` -- a baseline's own frame counter has no excuse to
    disagree with it just because an episode ended and `_t` reset to 0."""
    e = make_env(spec(horizon=4, action_repeat=1))
    e.reset()
    assert e.step_calls == 0
    for expected in range(1, 9):
        e.step(np.zeros(e.act_dim, dtype=np.float32))
        assert e.step_calls == expected
        if expected % 4 == 0:
            e.reset()
    assert e.step_calls == 8, "step_calls must not reset with the episode"


def test_action_clip_events_and_max_abs_action_seen_reflect_what_actually_arrived():
    """Clipping has always happened silently in step(); this only makes it observable. An
    in-bounds action must not be counted, and an out-of-bounds one must be, at its true magnitude
    -- not the clipped one, or the whole point (detecting mis-scaled actions) is lost."""
    e = make_env(spec())
    e.reset()
    e.step(np.full(e.act_dim, 0.5, dtype=np.float32))
    assert e.action_clip_events == 0
    assert e.max_abs_action_seen == pytest.approx(0.5)

    e.step(np.full(e.act_dim, 3.0, dtype=np.float32))
    assert e.action_clip_events == 1
    assert e.max_abs_action_seen == pytest.approx(3.0), \
        "must record the PRE-clip magnitude, not 1.0 -- the clipped value carries no signal"

    e.step(np.full(e.act_dim, 0.1, dtype=np.float32))
    assert e.action_clip_events == 1, "an in-range action afterwards must not add another event"
    assert e.max_abs_action_seen == pytest.approx(3.0), "the running max must not fall back down"

    # Exact boundary, mag == 1.0 precisely. Found missing by mutation testing (Stage 3): the two
    # values tested above (0.5, 3.0) cannot distinguish `mag > 1.0` from `mag >= 1.0` -- both
    # thresholds agree at 0.5 (no event) and at 3.0 (event). `>` is the semantically correct
    # choice: np.clip(a, -1, 1) does not alter a value already exactly at the bound, so "clipped"
    # must mean "changed by clipping", and a value exactly at 1.0 is not changed.
    before = e.action_clip_events
    e.step(np.full(e.act_dim, 1.0, dtype=np.float32))
    assert e.action_clip_events == before, (
        "an action exactly at the clip bound (1.0) is not altered by clipping and must not count "
        "as a clip event")


def test_action_contract_violation_raises_rather_than_warns():
    """Mirrors test_contract_violation_raises_rather_than_warns above, for the action half of the
    seam: a wrong-shape action is a defect to raise on, not something numpy silently reshapes."""
    with pytest.raises(ContractError):
        from rlgen.envs import _assert_action_contract
        _assert_action_contract(np.zeros(3, dtype=np.float32), 7)
    with pytest.raises(ContractError):
        e = make_env(spec())
        e.reset()
        e.step(np.zeros(e.act_dim + 1, dtype=np.float32))


@pytest.mark.parametrize("name", registry.BRIEF_BASELINES)
def test_every_baseline_step_calls_matches_ground_truth(name):
    """Closes the gap docs/COMPARABILITY_CONTRACT.md §4/§5 recorded as open: only 3 of the 12
    baselines (one per family) had been empirically smoke-tested against the choke-point
    instrumentation, by hand, outside the suite. This is that check, permanent, for all 12 --
    build through the real registry path (what rlgen/trainer.py / trainer_onpolicy.py actually
    call), step a real policy a known number of times, and require step_calls to match exactly.
    Not zeros: a policy that ignores its input is a weaker test than one that doesn't (the same
    reasoning SyntheticEnv's own reward design already applies -- see this file's
    test_synthetic_env_is_sensitive_to_the_things_tests_rely_on below)."""
    from rlgen.agents import policy_for
    from rlgen.protocol import Protocol

    p = Protocol(task="Door", total_frames=0, horizon=12, action_repeat=1)
    agent = registry.get(name).build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    pol = policy_for(agent, True)
    e = make_env(spec(horizon=12, action_repeat=1))
    obs = e.reset()
    n = 6
    for _ in range(n):
        obs, _r, _term, _trunc, _info = e.step(pol(obs))
    assert e.step_calls == n, (
        f"{name}: step_calls={e.step_calls} after {n} real steps through the actual registry "
        f"build path -- ground truth and the environment's own count disagree")


def test_synthetic_env_is_sensitive_to_the_things_tests_rely_on():
    """Stated sensitivity: an instrument that cannot register a change cannot detect a mutation.

    Its first version paid `0.05 * a.mean()`, which a constant action maximises -- so it could not
    have detected a policy that ignores its observation.
    """
    def rollout(sp, pol):
        e = make_env(sp)
        o = e.reset()
        tot = 0.0
        for _ in range(sp.steps_per_episode):
            o, r, _t, tr, _i = e.step(pol(o))
            tot += r
            if tr:
                break
        return tot

    blind = lambda o: np.full(7, 0.5, np.float32)                                  # noqa: E731
    sighted = lambda o: make_env(spec()).__class__._target(make_env(spec()), o)     # noqa: E731
    assert rollout(spec(scene_id=0), blind) != rollout(spec(scene_id=3), blind), \
        "return does not depend on scene id"
    assert rollout(spec(seed=0), blind) != rollout(spec(seed=1), blind), \
        "return does not depend on the seed"
    assert rollout(spec(), sighted) > rollout(spec(), blind), \
        "an observation-reading policy does not beat an observation-blind one"


# ============================================================================ replay
def test_stacked_frames_never_cross_an_episode_boundary_after_wrap():
    """The ring-wrap hazard: index i-1 may belong to an older, unrelated episode.

    Frames are tagged with a per-episode marker in the pixel data itself so a spliced stack is
    detectable directly rather than inferred.
    """
    fs, cap = 3, 40
    rb = FrameReplay(capacity=cap, frame_shape=(3, 8, 8), act_dim=2, frame_stack=fs, nstep=2)
    ep_len = 7
    for ep in range(12):                      # 84 frames into a 40-slot ring: wraps twice
        rb.start_episode()
        for t in range(ep_len):
            f = np.full((3, 8, 8), ep % 250, dtype=np.uint8)
            rb.add(f, np.zeros(2, np.float32), 1.0, done=(t == ep_len - 1))
    obs, _a, _r, _d, nxt = rb.sample(64)
    for batch in (obs, nxt):
        for o in batch:
            markers = {int(o[3 * k].flat[0]) for k in range(fs)}
            assert len(markers) == 1, (
                f"a sampled stack spliced frames from episodes {sorted(markers)} -- the ring "
                f"wrapped across an episode boundary")


def test_replay_refuses_to_sample_when_it_cannot():
    rb = FrameReplay(capacity=100, frame_shape=(3, 8, 8), act_dim=2, frame_stack=3, nstep=3)
    with pytest.raises(RuntimeError, match="no sampleable transition"):
        rb.sample(4)


def test_replay_rejects_wrong_dtype_and_shape():
    rb = FrameReplay(capacity=10, frame_shape=(3, 8, 8), act_dim=2, frame_stack=2, nstep=1)
    with pytest.raises(TypeError):
        rb.add(np.zeros((3, 8, 8), np.float32), np.zeros(2), 0.0, False)
    with pytest.raises(ValueError):
        rb.add(np.zeros((9, 8, 8), np.uint8), np.zeros(2), 0.0, False)


# ============================================================================ agents
def test_random_agent_is_declared_not_deterministic():
    a = RandomAgent(act_dim=7, seed=0)
    assert a.respects_deterministic is False
    assert_respects_deterministic(a, (9, 84, 84))          # exempted, must not raise


def test_every_runnable_baseline_respects_the_deterministic_flag():
    p = Protocol(task="Door", total_frames=0)
    for name in registry.runnable():
        s = registry.get(name)
        if s.build is None:
            continue
        agent = s.build(p, p.obs_shape, 7, "cpu", {"seed": 0})
        assert_respects_deterministic(agent, p.obs_shape)


def test_policy_output_shape_and_bounds():
    p = Protocol(task="Door", total_frames=0)
    obs = np.random.default_rng(0).integers(0, 256, size=p.obs_shape, dtype=np.uint8)
    for name in registry.runnable():
        s = registry.get(name)
        if s.build is None:
            continue
        a = policy_for(s.build(p, p.obs_shape, 7, "cpu", {"seed": 0}), True)(obs)
        assert a.shape == (7,), f"{name}: action shape {a.shape}"
        assert a.dtype == np.float32, f"{name}: action dtype {a.dtype}"
        assert np.all(np.abs(a) <= 1.0 + 1e-6), f"{name}: action out of [-1,1]: {a}"


# ============================================================================ registry
def test_every_baseline_in_the_brief_has_an_entry():
    for n in registry.BRIEF_BASELINES:
        s = registry.get(n)
        assert s.status in ("implemented", "alias", "eval_only", "absent")
        assert s.notes or s.status == "implemented", f"{n}: no explanation for status {s.status}"


def test_aliases_are_declared_and_labelled():
    for n, s in registry.BASELINES.items():
        if s.status == "alias":
            assert s.alias_of in registry.BASELINES, f"{n}: alias_of {s.alias_of!r} unknown"
            assert s.alias_of in s.label, f"{n}: label {s.label!r} hides the aliasing"


def test_absent_baselines_are_not_runnable_and_say_why():
    for n, s in registry.BASELINES.items():
        if s.status == "absent":
            assert s.build is None and not s.trainable
            assert len(s.notes) > 40, f"{n}: 'absent' without a real explanation"


def test_upstream_algo_import_does_not_drag_in_pieg():
    """Loading one algorithm must not import hydra/torchvision via algos/__init__.py."""
    mod = registry.load_upstream_module("drqv2")
    assert hasattr(mod, "DrQV2Agent")
    assert "algos" not in sys.modules or not hasattr(sys.modules.get("algos"), "pieg")


# ============================================================================ generated files
def test_generated_baseline_files_are_current():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_baselines.py"),
                        "--check"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_baseline_has_a_launch_script_and_a_readme():
    for n in registry.BRIEF_BASELINES:
        for f in ("train.sh", "README.md"):
            p = os.path.join(ROOT, "baselines", n, f)
            assert os.path.exists(p), f"missing {p}"
        assert os.access(os.path.join(ROOT, "baselines", n, "train.sh"), os.X_OK)


def test_upstream_patches_are_applied():
    """A run against unpatched upstream measures the training distribution and calls it eval."""
    if not os.path.isdir(os.path.join(ROOT, "RL-ViGen-upstream")):
        pytest.skip("RL-ViGen-upstream not present")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "setup", "apply_patches.py"),
                        "--check"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_runnable_baseline_has_a_config_entry():
    """A baseline with no config entry is invisible until someone runs it.

    This was not hypothetical: `rad`, `soda`, `alda`, `ppg`, `ibac_sni` and `idaac` were
    registered, tested, and had generated launch scripts -- and their `configs/vigen.yaml`
    entries were lost in an edit. Every unit test still passed, because every test builds agents
    through the registry directly. It surfaced only when `baselines/rad/train.sh` was run against
    the real simulator and exited with "no config 'rad'".

    The launch path and the registry must agree, so the agreement is asserted.
    """
    import yaml
    with open(os.path.join(ROOT, "configs", "vigen.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for name in registry.runnable():
        assert name in cfg, (
            f"baseline {name!r} is runnable but has no entry in configs/vigen.yaml, so "
            f"`bash baselines/{name}/train.sh` exits with 'no config'")
        assert cfg[name].get("baseline", name) == name, \
            f"config {name!r} points at baseline {cfg[name].get('baseline')!r}"


def test_volatile_counts_stay_out_of_prose_docs():
    """Test counts and mutant scores belong in docs/VALIDATION.md, which is dated -- nowhere else.

    Five documents drifted out of date in one session because each restated a number that moves
    every commit. A dated log that is stale reads as history; a prose claim that is stale reads as
    a fact. So the numbers live in one dated place and everything else names the command.
    """
    import re
    allowed = {"docs/VALIDATION.md", "HANDOFF.md"}   # dated records, staleness is honest there
    pat = re.compile(r"\b\d{2,3}\s+tests\b|\b\d{2,3},\s+all passing\b|curated\s+\d+/\d+")
    offenders = []
    for rel in ("README.md", "instruction.md", "docs/TASK.md", "docs/RIGOR.md",
                "docs/PROJECT-INDEX.md", "docs/compute.md", "setup/VENDORED.md"):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path) or rel in allowed:
            continue
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            if pat.search(line):
                offenders.append(f"{rel}:{i}: {line.strip()[:70]}")
    assert not offenders, (
        "volatile counts outside docs/VALIDATION.md:\n  " + "\n  ".join(offenders))


#: Baselines whose constructed learning rate does NOT equal the configured `lr`, with the reason.
#: This is a record of a known defect, not an endorsement -- see docs/PREMISES.md P8. Each entry
#: says which rate is actually used and why the configured one never arrives.
KNOWN_LR_DROPS = {
    "rad":  (1e-3, "`lr` is not a key in SAC_DEFAULTS (which names actor_lr/critic_lr/alpha_lr), "
                   "so _sac_family's `if k in SAC_DEFAULTS` filter drops it"),
    "soda": (1e-3, "same as rad"),
    "alda": (1e-3, "`AldaConfig` has no `lr` field, so _alda_build's `if hasattr(cfg, k)` drops it"),
}


def test_constructed_learning_rates_match_the_configured_one():
    """The config shows ONE learning rate; three baselines silently run at ten times it.

    `configs/vigen.yaml:base` sets `lr: 1.0e-4` and no entry overrides it. But each builder filters
    `hyper` differently -- `hyper.get("lr")`, `if k in SAC_DEFAULTS`, `if hasattr(cfg, k)` -- and a
    key the filter does not recognise is dropped without a word. So rad/soda/alda construct at
    1e-3 while everything else constructs at 1e-4.

    This test does not assert that the current state is correct. It **pins** it: the exception list
    above is the complete set of baselines where configured and constructed disagree, so a NEW
    silent drop fails the build, and fixing an existing one requires deleting its entry -- a
    deliberate act with a diff, rather than a discovery in the next audit.

    The measurement itself is `tools/dump_constructed_hyperparams.py`, which exists so the claim in
    docs/PREMISES.md P8 has a reproducible artifact behind it.
    """
    import sys
    sys.path.insert(0, ROOT)
    from tools.dump_constructed_hyperparams import collect

    data = collect()
    offenders = []
    for name, rec in sorted(data.items()):
        opts = rec.get("optimizers") or {}
        primary = {k: v for k, v in opts.items()
                   if isinstance(v, float) and ("actor" in k or "policy" in k)}
        if not primary:
            continue                       # `random` has no optimizer; nothing to check
        want = rec.get("config_lr")
        if want is None:
            continue
        got = sorted(set(primary.values()))
        if name in KNOWN_LR_DROPS:
            expected, why = KNOWN_LR_DROPS[name]
            if got != [expected]:
                offenders.append(
                    f"{name}: recorded as dropping to {expected:g} ({why}) but constructed {got}")
            continue
        if got != [float(want)]:
            offenders.append(
                f"{name}: config says lr={want:g}, constructed {got} -- a builder is silently "
                f"dropping the key. Add it to KNOWN_LR_DROPS with a reason, or fix the builder.")
    assert not offenders, "constructed learning rates disagree with the config:\n  " + \
                          "\n  ".join(offenders)


def test_the_unbiased_sweep_can_reach_every_production_module():
    """The sweep's coverage must follow `rlgen/`, not a list someone remembered to update.

    `mutants/sweep.py` carried a hand-written TARGETS list that omitted `trainer_onpolicy.py` from
    the day that module was created. Every sweep kill rate reported before this test was therefore
    measured over a codebase missing the on-policy budget stop, the GAE bootstrap and the shared
    eval cadence -- while being described as a sweep over `rlgen/`. The number was not wrong; its
    stated scope was. That is the more dangerous of the two.

    Reaching a module is not the same as sampling it in any given run (`-n` is a random draw), so
    this asserts the *pool* -- what the sweep is able to mutate at all.
    """
    import sys
    sys.path.insert(0, ROOT)
    from mutants import sweep

    production = {fn for fn in os.listdir(os.path.join(ROOT, "rlgen"))
                  if fn.endswith(".py") and fn != "__init__.py"}
    assert set(sweep.TARGETS) == production, (
        f"sweep targets and rlgen/ disagree; unmutated: {sorted(production - set(sweep.TARGETS))}")

    # And the pool must actually contain sites from each -- a module of pure constants would be
    # "targeted" while contributing nothing to mutate, which is invisible from TARGETS alone.
    pooled = {fn for fn, _kind, _lineno, _node in _sweep_pool(sweep)}
    barren = production - pooled
    assert not barren, f"targeted but contributes no mutation sites: {sorted(barren)}"


def _sweep_pool(sweep):
    """The sweep's candidate sites, without paying for the sampling/compile pass."""
    import ast
    pool = []
    for fn in sweep.TARGETS:
        tree = ast.parse(open(os.path.join(ROOT, "rlgen", fn), encoding="utf-8").read())
        c = sweep.Collector()
        c.visit(tree)
        pool.extend((fn, kind, getattr(node, "lineno", 0), node) for kind, node in c.sites)
    return pool


def test_env_patches_matches_the_patch_script():
    """`Protocol.env_patches` is inside the hash, so a stale value certifies the wrong tree.

    It listed three patches while four were applied, and its comment claimed
    `setup/apply_patches.py` set it -- grep showed nothing ever wrote it. A provenance field that
    drifts is worse than an absent one, because the hash makes it look authoritative.

    This pins the two together by patch FAMILY (P1..P4), which is the granularity the protocol
    records; `apply_patches.py` splits some families into lettered steps (P3a/P3b, P4a/P4b/P4c)
    that are implementation detail, not protocol.
    """
    import re
    import sys
    sys.path.insert(0, ROOT)
    from setup.apply_patches import PATCHES

    from rlgen.protocol import Protocol

    script_families = {re.match(r"(P\d+)", name).group(1) for name, *_ in PATCHES}
    proto_families = {re.match(r"(P\d+)", p).group(1) for p in Protocol().env_patches}
    assert proto_families == script_families, (
        f"Protocol.env_patches names {sorted(proto_families)} but setup/apply_patches.py applies "
        f"{sorted(script_families)}. The protocol hash would certify the wrong tree.")


# ================================================================================================
# FOUND 2026-08-14 by a differential test written for nd_ln_style_train.py: two agents built with
# the IDENTICAL declared seed, in the same process, produced DIFFERENT actions from identical
# observations. Traced to the root cause: neither `rlgen/trainer.py::train` nor
# `rlgen/trainer_onpolicy.py::train_onpolicy` ever called `torch.manual_seed` -- `protocol.seed`
# was threaded through to every agent's `hyper["seed"]`, but nothing in the shared trainer actually
# used it to seed weight initialisation. A seeding utility
# (`rlgen/algos/soda_utils.py::set_seed_everywhere`) has existed the whole time with ZERO callers
# anywhere in the repo -- vendored from SODA's own script, never wired into this repo's trainer.
#
# FIXED: both `train()` and `train_onpolicy()` now seed torch/numpy/random from `protocol.seed`
# before constructing the agent. These tests exercise the REAL, PRODUCTION entry points end to
# end (not an isolated construction helper) for one representative baseline per trainer, so a
# regression in the actual fix -- not a re-implementation of it -- is what gets caught.

def _checkpoints_equal(a, b) -> bool:
    """A checkpoint's `state_dict()` is NOT a flat tensor dict -- module entries
    (encoder/actor/critic/...) are flat, but optimizer entries (encoder_opt/actor_opt/...) are
    `{"state": {...}, "param_groups": [...]}`, and `param_groups` holds plain floats (lr, betas),
    not tensors. `torch.equal` on a dict raises TypeError, which is what a naive flat double-loop
    hits. Recurse through whatever shape is actually there instead of assuming one."""
    import torch
    if isinstance(a, torch.Tensor):
        return isinstance(b, torch.Tensor) and torch.equal(a, b)
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(
            _checkpoints_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return (isinstance(b, (list, tuple)) and len(a) == len(b)
               and all(_checkpoints_equal(x, y) for x, y in zip(a, b)))
    return a == b
def test_off_policy_training_is_reproducible_from_a_declared_seed():
    """rlgen.trainer.train, called twice with the identical protocol/seed on the synthetic
    backend, must produce BYTE-IDENTICAL checkpoints. total_frames=0 so this is fast (agent
    construction + the mandatory frame-0 eval + a save, no actual training) -- weight
    initialisation is exactly what the found bug affected, and it happens before frame 0."""
    import tempfile
    import torch
    from rlgen.protocol import Protocol
    from rlgen.trainer import TrainConfig, train

    def run(tmp, name):
        p = Protocol(task="Door", total_frames=0, seed=5, episodes_per_scene=1,
                    eval_scene_ids=(0,), horizon=8)
        c = TrainConfig(device="cpu", backend="synthetic")
        logdir = train(p, "drqv2", c, {}, os.path.join(tmp, name), verbose=False)
        ckpt = torch.load(os.path.join(logdir, "checkpoint.pt"), map_location="cpu",
                          weights_only=False)
        return ckpt["agent"]

    with tempfile.TemporaryDirectory() as tmp:
        sd1 = run(tmp, "a")
        sd2 = run(tmp, "b")

    assert sd1.keys() == sd2.keys(), f"checkpoint key sets differ: {sd1.keys()} vs {sd2.keys()}"
    assert _checkpoints_equal(sd1, sd2), (
        "checkpoint differs between two runs with the identical declared seed -- weight "
        "initialisation is not reproducible from the seed")


def test_on_policy_training_is_reproducible_from_a_declared_seed():
    """Same property, through rlgen.trainer_onpolicy.train_onpolicy -- a SEPARATE fix, in a
    separate file, for the four PPO-family baselines."""
    import tempfile
    import torch
    from rlgen.protocol import Protocol
    from rlgen.trainer import TrainConfig
    from rlgen.trainer_onpolicy import train_onpolicy

    def run(tmp, name):
        p = Protocol(task="Door", total_frames=0, seed=5, episodes_per_scene=1,
                    eval_scene_ids=(0,), horizon=8)
        c = TrainConfig(device="cpu", backend="synthetic")
        logdir = train_onpolicy(p, "idaac", c, {"num_steps": 8}, os.path.join(tmp, name),
                                verbose=False)
        ckpt = torch.load(os.path.join(logdir, "checkpoint.pt"), map_location="cpu",
                          weights_only=False)
        return ckpt["agent"]

    with tempfile.TemporaryDirectory() as tmp:
        sd1 = run(tmp, "a")
        sd2 = run(tmp, "b")

    assert sd1.keys() == sd2.keys()
    assert _checkpoints_equal(sd1, sd2), (
        "checkpoint differs between two on-policy runs with the identical declared seed")


def test_different_seeds_still_produce_different_weights():
    """The other half of the property: the fix above must not have accidentally made EVERY run
    identical regardless of seed (e.g. by seeding with a constant). Two DIFFERENT declared seeds
    must diverge."""
    import tempfile
    import torch
    from rlgen.protocol import Protocol
    from rlgen.trainer import TrainConfig, train

    def run(tmp, name, seed):
        p = Protocol(task="Door", total_frames=0, seed=seed, episodes_per_scene=1,
                    eval_scene_ids=(0,), horizon=8)
        c = TrainConfig(device="cpu", backend="synthetic")
        logdir = train(p, "drqv2", c, {}, os.path.join(tmp, name), verbose=False)
        ckpt = torch.load(os.path.join(logdir, "checkpoint.pt"), map_location="cpu",
                          weights_only=False)
        return ckpt["agent"]

    with tempfile.TemporaryDirectory() as tmp:
        sd1 = run(tmp, "a", seed=1)
        sd2 = run(tmp, "b", seed=2)

    assert not _checkpoints_equal(sd1, sd2), (
        "seeds 1 and 2 produced BYTE-IDENTICAL checkpoints -- the reproducibility fix has "
        "collapsed all seeds to one, which is a worse bug than the one it fixed")


def test_hermetic_on_policy_baselines_use_their_own_storage_class_not_idaacs():
    """FOUND 2026-08-14 (docs/REGISTER.md): `trainer_onpolicy.py` hardcoded
    `idaac.storage.RolloutStorage` for every on-policy baseline regardless of which Learner was
    actually built -- `ibac_sni`/`ppg`'s own hermetic storage classes were never reached by the
    real trainer, only by their own unit tests. Silent: no crash, just the wrong minibatch count.
    Fixed by having each hermetic Learner declare its own `storage_cls`, read by the trainer off
    the constructed agent. This test is what makes that guarantee self-renewing rather than a
    one-time fix -- a future baseline that forgets to set `storage_cls` explicitly, or that
    accidentally shares it with a sibling, fails here rather than silently training with the
    wrong buffer.
    """
    import torch

    from rlgen.algos.ibac_sni.storage import RolloutStorage as IbacSniStorage
    from rlgen.algos.idaac.storage import RolloutStorage as IdaacStorage
    from rlgen.algos.ppg.storage import RolloutStorage as PpgStorage

    expected = {"idaac": IdaacStorage, "ppg": PpgStorage, "ibac_sni": IbacSniStorage}
    p = Protocol(task="Door", total_frames=0)
    for name, want in expected.items():
        agent = registry.get(name).build(p, p.obs_shape, 7, "cpu", {"seed": 0})
        got = agent.learner.storage_cls
        assert got is want, (
            f"{name}: storage_cls is {got.__module__}.{got.__qualname__}, "
            f"expected {want.__module__}.{want.__qualname__}")


def test_every_patch_declares_what_kind_of_change_it_is():
    """A patch with no class is a change nobody has decided the character of.

    `Protocol.env_patches` hashes WHICH patches were present, so any number can be traced to its
    patch set. That is not the same as knowing whether the number is attributable to RL-ViGen or
    to us, and the difference is what `PATCH_CLASS` records: PLATFORM (this stack only, changes
    nothing measured), RESTORES (makes their own declared intent reachable), ENABLES (adds or
    changes what is measured -- the number is ours).

    Asserted rather than trusted because the failure is silent in the direction that matters: a
    new patch added without a class would default to nothing, and a constructed number would be
    indistinguishable from a fidelity one.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "apply_patches", os.path.join(ROOT, "setup", "apply_patches.py"))
    ap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ap)

    families = {ap.patch_family(name) for name, *_ in ap.PATCHES}
    unclassified = sorted(families - set(ap.PATCH_CLASS), key=lambda f: int(f[1:]))
    assert not unclassified, (
        f"patch families with no class: {unclassified}. Add one to PATCH_CLASS in "
        "setup/apply_patches.py -- PLATFORM, RESTORES or ENABLES -- deciding whether a number "
        "produced with it is still theirs.")

    stale = sorted(set(ap.PATCH_CLASS) - families, key=lambda f: int(f[1:]))
    assert not stale, f"PATCH_CLASS names families the registry no longer has: {stale}"

    assert set(ap.PATCH_CLASS.values()) <= {"PLATFORM", "RESTORES", "ENABLES"}, \
        f"unknown class in PATCH_CLASS: {set(ap.PATCH_CLASS.values())}"


def test_the_enables_set_is_what_makes_a_number_ours():
    """Pins the current ENABLES set, so growing it is a deliberate act with a diff.

    P6 (render size settable -- RAD and SODA are specified at 100, their config fixes 84), P10 and
    P11 (success emitted and accumulated -- upstream emits none on this path). The fidelity line
    was therefore crossed well before any scene or regime patch was proposed, which is worth
    knowing before treating existing numbers as pure reproductions.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "apply_patches", os.path.join(ROOT, "setup", "apply_patches.py"))
    ap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ap)
    # P14 joined on 2026-08-19 (C45 + C43). It is different in kind from the other three: P6,
    # P10 and P11 change what is RECORDED about a run, P14 changes WHICH DISTRIBUTION is
    # evaluated -- ten certified scenes instead of one, plus a train-regime denominator. Every
    # number produced before it therefore sits on a different footing, not merely a different
    # patch list, and C47's retention is the case in point.
    # P15 and P18 joined on 2026-09-02, and both are smaller in kind than P14. P15 evaluates and
    # snapshots at the exact declared endpoint instead of the last cadence boundary before it;
    # P18 keeps intermediate snapshots the loop already wrote and discarded. Neither changes which
    # distribution is evaluated, and neither changes training -- P18's is byte-identical. They are
    # ENABLES rather than PLATFORM because each ADDS a measurement that did not exist, and the
    # class is about whether a number is ours, not about how large the change is.
    #
    # Both were applied to the tree before this pin was updated, which is how `Protocol.env_patches`
    # came to certify a P1-P14 tree while a P1-P18 tree ran. The pin did its job late rather than
    # not at all; see the register entry of 2026-09-02.
    assert ap.classify_patches().get("ENABLES") == ["P6", "P10", "P11", "P14", "P15", "P18"], (
        "the ENABLES set changed. That is allowed and must be deliberate: it is the set of "
        "patches that make a number ours rather than RL-ViGen's, so every result produced before "
        "and after the change sits on a different footing.")
