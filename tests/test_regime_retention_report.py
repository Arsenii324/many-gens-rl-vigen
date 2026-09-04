"""What `regime_retention_report.py` must refuse to say.

The flattering failure for this instrument is a confident retention ratio computed from a
denominator that is at chance. drqv2/Door at 50k frames returns ~2.0 on the training scene; a
uniform random policy on the same scene returns ~1.5. `2.4 / 2.0 = 1.2` reads as "120%
retention, it generalizes" when both numbers are chance.

`test_at_chance_denominator_is_refused` is the load-bearing test, and it is written against
those measured values rather than against a convenient fixture, because the first version of
this guard passed on exactly them: it asked whether the denominator was small relative to the
spread of the returns, and 2.0 with sd 0.8 is not small. A guard aimed at the wrong quantity
passes its own test suite. This one is aimed at the floor.
"""
from __future__ import annotations

import importlib
import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture()
def mod(tmp_path, monkeypatch):
    m = importlib.import_module("regime_retention_report")
    importlib.reload(m)
    monkeypatch.setattr(m, "RESULTS", tmp_path)
    monkeypatch.setattr(m, "BOOT", 400)
    return m


def dump(d, tag, per_scene, control=None, n_success=0):
    (d / f"{tag}.json").write_text(json.dumps({
        "snapshot": "x.pt", "task": "Door", "mode": tag.split("__")[1],
        "trained_step": 50_000, "frames": 50_000, "action_repeat": 1,
        "episodes": 20, "seed": 0, "control_seed": 1,
        "scenes": {str(k): {"returns": list(map(float, v)), "n_success": n_success,
                            "n_episodes": len(v)} for k, v in per_scene.items()},
        "control": control}))


def ctl(returns):
    return {"scene": 0, "returns": list(map(float, returns)), "n_success": 0, "n_episodes": 20}


def chance(rng, n=20, loc=1.5):
    return rng.normal(loc, 0.8, n)


def solved(rng, n=20, loc=250.0):
    return rng.normal(loc, 30.0, n)


def write_floor(d, rng, loc=1.5, scenes=3):
    dump(d, "random-floor__train", {s: chance(rng, loc=loc) for s in range(scenes)})


def test_at_chance_denominator_is_refused(mod, tmp_path, capsys):
    rng = np.random.default_rng(0)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {s: chance(rng, loc=1.5) for s in range(3)},
         control=ctl(chance(rng, loc=1.5)))
    dump(tmp_path, "ck__eval-easy", {s: chance(rng, loc=1.6) for s in range(3)},
         control=ctl(chance(rng, loc=1.6)))
    mod.main([])
    out = capsys.readouterr().out
    assert "AT-CHANCE" in out, "a chance-level denominator produced a retention number"
    assert "POOLED" not in out


def test_above_chance_but_never_successful_is_not_pooled(mod, tmp_path, capsys):
    """The load-bearing one, written against the real measured numbers.

    drqv2/Door at 50k: train 2.02, random floor 1.52, zero successes. Twenty episodes is enough
    to separate 2.02 from 1.52 statistically, so a floor check ALONE clears this row and prints
    a confident ratio. What the ratio describes is retention of reward shaping by an agent that
    never once opened the door."""
    rng = np.random.default_rng(10)
    write_floor(tmp_path, rng, loc=1.52)
    dump(tmp_path, "ck__train", {s: chance(rng, loc=2.02) for s in range(3)},
         control=ctl(chance(rng, loc=2.0)), n_success=0)
    dump(tmp_path, "ck__eval-easy", {s: chance(rng, loc=2.4) for s in range(3)},
         control=ctl(chance(rng, loc=2.4)), n_success=0)
    mod.main([])
    out = capsys.readouterr().out
    assert "UNSOLVED-DENOM" in out
    assert "POOLED" not in out, "a shaping ratio was pooled as if it were task retention"
    assert "0/3" in out and "above chance but never successful" in out


def test_learned_agent_clears_the_floor_and_gets_a_number(mod, tmp_path, capsys):
    """The guard must not mute the real case, or it is not a guard."""
    rng = np.random.default_rng(1)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {s: solved(rng) for s in range(3)},
         control=ctl(solved(rng)), n_success=15)
    dump(tmp_path, "ck__eval-easy", {s: solved(rng, loc=180.0) for s in range(3)},
         control=ctl(solved(rng, loc=178.0)), n_success=9)
    mod.main([])
    out = capsys.readouterr().out
    assert "POOLED regime retention" in out
    assert "AT-CHANCE" not in out


def test_no_floor_file_reports_nothing_at_all(mod, tmp_path, capsys):
    """Without a measured floor there is no denominator check, so there is no report."""
    rng = np.random.default_rng(2)
    dump(tmp_path, "ck__train", {0: solved(rng)}, control=ctl(solved(rng)), n_success=12)
    dump(tmp_path, "ck__eval-easy", {0: solved(rng, loc=200.0)}, control=ctl(solved(rng)),
         n_success=8)
    mod.main([])
    out = capsys.readouterr().out
    assert "NO RANDOM-POLICY FLOOR MEASURED" in out
    assert "POOLED" not in out and "RETAINS" not in out


def test_gap_inside_the_seed_floor_is_unresolved_not_null(mod, tmp_path, capsys):
    rng = np.random.default_rng(3)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {s: solved(rng, loc=250.0) for s in range(2)},
         control=ctl(solved(rng, loc=290.0)), n_success=15)   # seed alone moves the mean ~15%
    dump(tmp_path, "ck__eval-easy", {s: solved(rng, loc=248.0) for s in range(2)},
         control=ctl(solved(rng, loc=248.0)), n_success=15)
    mod.main([])
    out = capsys.readouterr().out
    assert "UNRESOLVED" in out and "RESOLUTION FLOOR" in out
    assert "no effect" not in out.lower()


def test_missing_control_downgrades_every_gap(mod, tmp_path, capsys):
    rng = np.random.default_rng(4)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {s: solved(rng) for s in range(2)}, control=None, n_success=15)
    dump(tmp_path, "ck__eval-easy", {s: solved(rng, loc=100.0) for s in range(2)}, control=None,
         n_success=6)
    mod.main([])
    out = capsys.readouterr().out
    assert "no control ran" in out and "UNINTERPRETABLE" in out


def test_incomplete_pair_reports_nothing(mod, tmp_path, capsys):
    rng = np.random.default_rng(5)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {0: solved(rng)})
    mod.main([])
    out = capsys.readouterr().out
    assert "incomplete pair" in out and "POOLED" not in out


def test_success_rate_comes_from_counts_and_is_not_merged(mod, tmp_path, capsys):
    """`run_scene` returns a success COUNT. Treating it as a per-episode list raises only after
    every scene has run -- i.e. it discards the whole evaluation at the last line."""
    rng = np.random.default_rng(6)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {0: solved(rng)}, control=ctl(solved(rng)), n_success=14)
    dump(tmp_path, "ck__eval-easy", {0: solved(rng, loc=200.0)},
         control=ctl(solved(rng, loc=200.0)), n_success=7)
    mod.main([])
    out = capsys.readouterr().out
    assert "14/20" in out and "7/20" in out
    assert "SR retention 0.500" in out
    assert "not averaged with it" in out


def test_pooled_number_states_it_is_not_the_protocol(mod, tmp_path, capsys):
    rng = np.random.default_rng(7)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {0: solved(rng), 1: chance(rng, loc=1.5)},
         control=ctl(solved(rng)), n_success=13)
    dump(tmp_path, "ck__eval-easy", {0: solved(rng, loc=200.0), 1: chance(rng, loc=1.5)},
         control=ctl(solved(rng, loc=200.0)), n_success=7)
    mod.main([])
    out = capsys.readouterr().out
    assert "NOT RL-ViGen's protocol" in out
    assert "1/2" in out


def test_denominator_flag_swaps_which_regime_is_the_claim(mod, tmp_path, capsys):
    """Naming the denominator names which regime you claim the policy trained on.

    C54 is the reason this is a flag and not a constant: for the archived checkpoints the
    stored training pixels match eval-easy, so reading their retention with `train` underneath
    asserts the opposite of the evidence. The two directions are reciprocals and the report
    must say which one it printed.
    """
    rng = np.random.default_rng(20)
    dump(tmp_path, "random-floor__train", {s: chance(rng) for s in range(2)})
    dump(tmp_path, "random-floor__eval-easy", {s: chance(rng) for s in range(2)})
    dump(tmp_path, "ck__train", {0: solved(rng, loc=100.0)},
         control=ctl(solved(rng, loc=100.0)), n_success=10)
    dump(tmp_path, "ck__eval-easy", {0: solved(rng, loc=200.0)},
         control=ctl(solved(rng, loc=200.0)), n_success=18)

    mod.main([])
    fwd = capsys.readouterr().out
    assert "denominator 'train'" in fwd
    mod.main(["--denominator", "eval-easy"])
    rev = capsys.readouterr().out
    assert "denominator 'eval-easy'" in rev

    def pooled(text):
        line = [l for l in text.splitlines() if "POOLED regime retention" in l][0]
        return float(line.split(":")[1].split()[0])

    a, b = pooled(fwd), pooled(rev)
    assert a > 1.0 > b, f"expected reciprocal directions, got {a} and {b}"
    assert abs(a * b - 1.0) < 0.02, f"{a} and {b} are not reciprocals"


def test_column_headers_name_the_actual_regimes(mod, tmp_path, capsys):
    """A results column labelled with the wrong regime is the error most likely to be believed.

    The header was written literally at first, so `--denominator eval-easy` printed eval-easy's
    numbers under a "train ret" heading while the ratio underneath was computed correctly. Every
    number on the page was right and the table said the opposite of what it meant.
    """
    rng = np.random.default_rng(30)
    dump(tmp_path, "random-floor__train", {0: chance(rng)})
    dump(tmp_path, "random-floor__eval-easy", {0: chance(rng)})
    dump(tmp_path, "ck__train", {0: solved(rng, loc=100.0)},
         control=ctl(solved(rng, loc=100.0)), n_success=10)
    dump(tmp_path, "ck__eval-easy", {0: solved(rng, loc=200.0)},
         control=ctl(solved(rng, loc=200.0)), n_success=18)

    mod.main(["--denominator", "eval-easy"])
    out = capsys.readouterr().out
    header = [l for l in out.splitlines() if "verdict" in l and "scene" in l][0]
    assert header.index("eval-easy ret") < header.index("train ret"), \
        f"denominator column is not labelled first: {header!r}"

    mod.main(["--denominator", "train"])
    header = [l for l in capsys.readouterr().out.splitlines()
              if "verdict" in l and "scene" in l][0]
    assert header.index("train ret") < header.index("eval-easy ret"), \
        f"columns did not swap with the denominator: {header!r}"


def test_a_denominator_that_rarely_succeeds_is_not_pooled(mod, tmp_path, capsys):
    """The hole an adversarial re-check found, and the reason MIN_DENOM_SUCCESS exists.

    The guard originally fired only at EXACTLY zero successes. A real checkpoint (svea seed 1)
    scored 1/20 on every scene it succeeded on at all -- never more -- sailed through, and was
    pooled into a retention of 0.947. That read as robustness. It was a shaped-reward plateau
    from a policy that essentially never opens the door, and the number went into a headline
    before the re-check killed it.

    One success in twenty is the case to pin, not zero.
    """
    rng = np.random.default_rng(40)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {s: solved(rng, loc=100.0) for s in range(3)},
         control=ctl(solved(rng, loc=100.0)), n_success=1)      # 1/20 = 5%
    dump(tmp_path, "ck__eval-easy", {s: solved(rng, loc=95.0) for s in range(3)},
         control=ctl(solved(rng, loc=95.0)), n_success=1)
    mod.main([])
    out = capsys.readouterr().out
    assert "WEAK-DENOM(1/20)" in out, "a 5%-success denominator was treated as competent"
    assert "POOLED" not in out, "a shaping plateau was pooled as if it were task retention"


def test_a_competent_denominator_still_pools(mod, tmp_path, capsys):
    """The threshold must not mute the case it exists to protect."""
    rng = np.random.default_rng(41)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {s: solved(rng, loc=100.0) for s in range(3)},
         control=ctl(solved(rng, loc=100.0)), n_success=15)     # 15/20 = 75%
    dump(tmp_path, "ck__eval-easy", {s: solved(rng, loc=40.0) for s in range(3)},
         control=ctl(solved(rng, loc=40.0)), n_success=4)
    mod.main([])
    out = capsys.readouterr().out
    assert "POOLED regime retention" in out
    assert "WEAK-DENOM" not in out


def test_contamination_alarm_fires_when_eval_beats_train(mod, tmp_path, capsys):
    """A policy scoring higher on the held-out regime than on its declared training one is
    refused, not reported (C65).

    This is the case every archived `drqv2` checkpoint in this project actually exhibits — 1.89,
    2.51 and 2.79 across all ten scenes — and which C54 concludes means the run did not train on
    the distribution its config declares.
    """
    rng = np.random.default_rng(11)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {s: solved(rng, loc=60.0) for s in range(3)},
         control=ctl(solved(rng, loc=60.0)), n_success=8)
    dump(tmp_path, "ck__eval-easy", {s: solved(rng, loc=180.0) for s in range(3)},
         control=ctl(solved(rng, loc=180.0)), n_success=15)
    mod.main([])
    out = capsys.readouterr().out
    assert "CONTAMINATION ALARM" in out
    assert "DO NOT REPORT" in out


def test_contamination_alarm_is_silent_on_an_ordinary_result(mod, tmp_path, capsys):
    """The mirror of the test above: a normal cell, where eval is worse than train, must not
    trip it. Without this the alarm could fire unconditionally and still pass the test above.
    """
    rng = np.random.default_rng(12)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {s: solved(rng, loc=200.0) for s in range(3)},
         control=ctl(solved(rng, loc=200.0)), n_success=15)
    dump(tmp_path, "ck__eval-easy", {s: solved(rng, loc=90.0) for s in range(3)},
         control=ctl(solved(rng, loc=90.0)), n_success=6)
    mod.main([])
    out = capsys.readouterr().out
    assert "CONTAMINATION ALARM" not in out
    assert "all-scene pooled ratio" in out


def dump_per_scene(d, tag, per_scene, control=None):
    """Like `dump`, but `per_scene` maps scene -> (returns, n_success).

    `dump` applies a single `n_success` to every scene, which cannot express "scene 0 is solved
    and the rest are not" — and that is the only shape that distinguishes the all-scene screen
    from the guarded subset. Written after the first version of the test below passed against a
    deliberately reintroduced bug.
    """
    (d / f"{tag}.json").write_text(json.dumps({
        "snapshot": "x.pt", "task": "Door", "mode": tag.split("__")[1],
        "trained_step": 50_000, "frames": 50_000, "action_repeat": 1,
        "episodes": 20, "seed": 0, "control_seed": 1,
        "scenes": {str(k): {"returns": list(map(float, v)), "n_success": ns,
                            "n_episodes": len(v)} for k, (v, ns) in per_scene.items()},
        "control": control}))


def test_the_screen_reads_all_scenes_not_the_guarded_subset(mod, tmp_path, capsys):
    """The alarm must be computed over every scene, not over those clearing the denominator
    guard — different estimands, and on the real data they disagree in *sign*.

    Built to the shape of the real failure. Scene 0 is solved under `train` and dead under
    `eval-easy`, and it is the ONLY scene whose `train` arm clears the 25%-success guard. So the
    guarded subset is scene 0 alone and reads far below 1, while all three scenes together read
    far above it. Keying the screen to the guarded subset therefore reports a tidy retention
    number for a contaminated checkpoint — which is the bug this test exists to kill, and which
    an earlier version of this test did not kill because the helper it used gave every scene the
    same success count.

    Mutation-verified: replacing `rows` with `usable` in the screen makes this fail.
    """
    rng = np.random.default_rng(13)
    write_floor(tmp_path, rng)
    dump_per_scene(tmp_path, "ck__train", {
        0: (solved(rng, loc=300.0), 18),
        1: (chance(rng, loc=3.0), 0),
        2: (chance(rng, loc=3.0), 0)}, control=ctl(solved(rng, loc=300.0)))
    dump_per_scene(tmp_path, "ck__eval-easy", {
        0: (chance(rng, loc=3.0), 0),
        1: (solved(rng, loc=400.0), 19),
        2: (solved(rng, loc=400.0), 19)}, control=ctl(chance(rng, loc=3.0)))
    mod.main([])
    out = capsys.readouterr().out
    assert "CONTAMINATION ALARM" in out, (
        "the screen read the guarded subset instead of all scenes: scene 0 alone looks like a "
        "collapse, while all three together show the policy preferring the held-out regime")


def dump_seeded(d, tag, per_scene, control=None, n_success=0):
    """`dump`, plus the `placement_seeded` marker a post-C69 grid carries."""
    dump(d, tag, per_scene, control=control, n_success=n_success)
    p = d / f"{tag}.json"
    obj = json.loads(p.read_text())
    obj["placement_seeded"] = True
    p.write_text(json.dumps(obj))


def test_pre_c69_grids_are_flagged_as_unseeded(mod, tmp_path, capsys):
    """A grid without `placement_seeded` is announced as not reproducible (C69).

    Those grids were measured while `run_scene` left global numpy unseeded, so
    `UniformRandomSampler` placed the door from whatever RNG state the process had — ~1.6 cm of
    movement between runs recording an identical seed. The archive will be a mix as grids are
    re-derived, so a reader comparing two numbers has to be told which side each one is on.
    """
    rng = np.random.default_rng(21)
    write_floor(tmp_path, rng)
    dump(tmp_path, "ck__train", {s: solved(rng) for s in range(3)},
         control=ctl(solved(rng)), n_success=15)
    dump(tmp_path, "ck__eval-easy", {s: solved(rng, loc=180.0) for s in range(3)},
         control=ctl(solved(rng, loc=178.0)), n_success=9)
    mod.main([])
    out = capsys.readouterr().out
    assert "NOT seeded" in out
    assert "pre-C69" in out


def test_seeded_grids_are_not_flagged(mod, tmp_path, capsys):
    """The mirror: a grid carrying the marker must stay silent.

    Without this the warning could fire unconditionally and still pass the test above — the
    vacuity failure this repo has hit repeatedly.
    """
    rng = np.random.default_rng(22)
    write_floor(tmp_path, rng)
    dump_seeded(tmp_path, "ck__train", {s: solved(rng) for s in range(3)},
                control=ctl(solved(rng)), n_success=15)
    dump_seeded(tmp_path, "ck__eval-easy", {s: solved(rng, loc=180.0) for s in range(3)},
                control=ctl(solved(rng, loc=178.0)), n_success=9)
    mod.main([])
    out = capsys.readouterr().out
    assert "NOT seeded" not in out, "a post-C69 grid must not be flagged"
    assert "POOLED regime retention" in out, "the report must still produce its number"
