"""Red-green for the two C20 probes -- `scripts/probe_seed_effect.py`, `scripts/probe_determinism.py`.

Both probes exist to answer a question whose *wrong* answer is a confident null: "the seed does
nothing", "the runs agree". A null is only a measurement if the design could have produced the
opposite answer, so both carry a positive control and both must report UNINTERPRETABLE when that
control fails to fire. That branch is the thing worth testing, because it is the branch that
never runs on a good day and so is never exercised by ordinary use.

The verdict functions are pure, so this file needs neither MuJoCo nor a GPU.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import probe_determinism as D  # noqa: E402
import probe_seed_effect as S  # noqa: E402


def rows(train: dict, easy: dict | None = None) -> list[dict]:
    """`train`/`easy` map (env_seed, global_seed) -> fingerprint."""
    out = []
    for mode, table in (("train", train), ("eval-easy", easy)):
        if table is None:
            continue
        for (es, gs), fp in table.items():
            out.append({"mode": mode, "env_seed": es, "global_seed": gs, "fp": fp})
    return out


INERT = {(0, 0): "A", (1, 0): "A", (0, 1): "B", (1, 1): "B"}   # fp tracks global seed only
LIVE = {(0, 0): "A", (1, 0): "B", (0, 1): "C", (1, 1): "D"}    # every condition distinct


class TestSeedEffectProbe:
    def test_the_measured_shape_reads_as_inert(self):
        v = S.summarise(rows(INERT, LIVE))["verdict"]
        assert v.startswith("ENV_SEED_INERT_IN_TRAIN"), v

    def test_a_control_that_does_not_fire_is_uninterpretable_not_a_null(self):
        """The whole point. If the env seed moves nothing even in eval-easy, the probe is blind,
        and 'inert in train' would be a statement about the probe rather than the env."""
        v = S.summarise(rows(INERT, INERT))["verdict"]
        assert v.startswith("UNINTERPRETABLE"), (
            f"got {v!r} -- a blind probe must not be allowed to report a null")

    def test_a_moving_train_arm_overturns_the_reading(self):
        v = S.summarise(rows(LIVE, LIVE))["verdict"]
        assert v.startswith("ENV_SEED_CONTROLS_TRAIN"), v

    def test_omitting_the_control_arm_is_reported_not_ignored(self):
        v = S.summarise(rows(INERT))["verdict"]
        assert v.startswith("NO_CONTROL_RUN"), v


def t(fp: str, n: int = 40, seed: int | None = 1, rc: int = 0, crashed: bool = False) -> dict:
    return {"fp": fp, "n_values": n, "seed": seed, "rc": rc, "crashed": crashed}


class TestDeterminismProbe:
    def test_agreement_with_a_live_control_is_determinism(self):
        v, _ = D.verdict(t("A"), t("A"), t("B"))
        assert v == "DETERMINISTIC"

    def test_disagreement_with_a_live_control_is_nondeterminism(self):
        v, _ = D.verdict(t("A"), t("B"), t("C"))
        assert v == "NONDETERMINISTIC"

    def test_a_control_that_matches_makes_agreement_meaningless(self):
        """Different seeds producing the same fingerprint means the probe cannot resolve runs --
        a truncated log or a fingerprint over constant columns would look exactly like this."""
        v, _ = D.verdict(t("A"), t("A"), t("A"))
        assert v == "UNINTERPRETABLE"

    def test_an_empty_run_establishes_nothing(self):
        v, _ = D.verdict(t("A", 0), t("A", 0), t("B"))
        assert v == "NO_SIGNAL"


class TestTheUnseededCaseGetsItsOwnVocabulary:
    """`ppg` has no seed knob, so its third trial is a third IDENTICAL invocation.

    Reporting "the cross-seed control fired" there would be a false statement about the design:
    nothing was varied. This was a real defect in the probe, found by reading it while it ran.
    """

    def test_identical_invocations_that_agree_are_not_called_seed_controlled(self):
        v, why = D.verdict(t("A", seed=None), t("A", seed=None), t("A", seed=None))
        assert v == "UNSEEDED_BUT_REPRODUCIBLE"
        assert "seed" in why

    def test_identical_invocations_that_disagree_name_the_real_problem(self):
        v, why = D.verdict(t("A", seed=None), t("B", seed=None), t("C", seed=None))
        assert v == "UNSEEDED_AND_NONDETERMINISTIC"
        assert "5-seed" in why or "reproducible" in why

    def test_the_seeded_path_is_unaffected(self):
        assert D.verdict(t("A"), t("A"), t("B"))[0] == "DETERMINISTIC"


class TestATimeoutIsNotAMeasurement:
    """A wall-clock-capped run did a different amount of WORK than its twin.

    `ppg` is the live case: `interacts_total=100_000_000` is a train_fn default with no CLI flag,
    so nothing can bound it by steps and every trial is cut off by the clock instead. Under
    varying machine load the trials cover different numbers of interactions, so their fingerprints
    differ for reasons that have nothing to do with RNG. Reporting NONDETERMINISTIC there would
    present a scheduler artefact as a finding.
    """

    def test_a_timed_out_trial_refuses_a_verdict(self):
        to = {"fp": "A", "n_values": 40, "seed": 1, "rc": -9}
        ok = {"fp": "B", "n_values": 40, "seed": 1, "rc": 0}
        assert D.verdict(to, ok, ok)[0] == "UNBOUNDED_RUN"
        assert D.verdict(ok, to, ok)[0] == "UNBOUNDED_RUN"
        assert D.verdict(ok, ok, to)[0] == "UNBOUNDED_RUN"

    def test_clean_runs_still_get_a_real_verdict(self):
        ok = lambda fp: {"fp": fp, "n_values": 40, "seed": 1, "rc": 0}
        assert D.verdict(ok("A"), ok("A"), ok("B"))[0] == "DETERMINISTIC"


class TestWallClockIsDroppedFromFingerprints:
    """Without this the probe reports every clone as nondeterministic, which is the false
    positive that looks like rigour and would have been believed."""

    def test_two_runs_differing_only_in_timing_agree(self, tmp_path):
        head = "episode,episode_reward,frame,fps,total_time\n"
        (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
        (tmp_path / "a" / "eval.csv").write_text(head + "0,0.846,0,3.71,0.84\n")
        (tmp_path / "b" / "eval.csv").write_text(head + "0,0.846,0,15.02,477.9\n")
        fa, na = D.fingerprint_csv(tmp_path / "a")
        fb, nb = D.fingerprint_csv(tmp_path / "b")
        assert na == nb == 1
        assert fa == fb, "fps/total_time must not enter the fingerprint"

    def test_but_a_real_metric_difference_still_shows(self, tmp_path):
        head = "episode,episode_reward,frame,fps,total_time\n"
        (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
        (tmp_path / "a" / "eval.csv").write_text(head + "0,0.846,0,3.71,0.84\n")
        (tmp_path / "b" / "eval.csv").write_text(head + "0,0.847,0,3.71,0.84\n")
        assert D.fingerprint_csv(tmp_path / "a")[0] != D.fingerprint_csv(tmp_path / "b")[0], (
            "a one-in-a-thousand change in episode_reward must change the fingerprint, or the "
            "probe cannot see divergence at all")

class TestTimingIsStrippedPerFieldNotPerLine:
    """Real defect, 2026-08-19: the filter dropped any line mentioning fps.

    `ibac_sni` prints `FPS 0071` in the same line as H, V, pL, vL, kl and SR, so a line-level
    filter discarded 21 updates of genuine signal and left a one-value fingerprint that could not
    resolve runs. The probe correctly reported UNINTERPRETABLE instead of a false verdict, but the
    measurement was lost and had to be re-run.
    """

    IBAC = ("U 18 | F 001152 | FPS 0071 | D 15 | rR 3.79 | H 10.030 | V 0.043 | "
            "pL -0.005 | vL 0.000 | kl 0.025 | SR 0.000")

    def test_metrics_survive_a_line_that_also_carries_fps(self):
        _, n = D.fingerprint_stdout(self.IBAC)
        assert n >= 5, f"only {n} values kept from a line with six metric floats on it"

    def test_the_timing_field_itself_is_excluded(self):
        _, n = D.fingerprint_stdout("total_time 477.912 fps 15.021 elapsed 3.500")
        assert n == 0, "wall-clock fields must never enter the fingerprint"

    def test_a_timing_field_does_not_swallow_the_metric_after_it(self):
        a, _ = D.fingerprint_stdout("fps 15.021 kl 0.025")
        b, _ = D.fingerprint_stdout("fps 99.999 kl 0.025")
        assert a == b, "changing only fps must not change the fingerprint"
        c, _ = D.fingerprint_stdout("fps 15.021 kl 0.026")
        assert a != c, "changing a real metric must change the fingerprint"

class TestTheFingerprintReadsShortNumbersToo:
    """The retraction of 2026-08-19, pinned.

    The extractor required three or more decimal places. `idaac` logs
    `test/mean_episode_reward` as `1.27`, so two runs that differed *there* agreed on everything
    the filter kept, and the probe called it DETERMINISTIC. That verdict was published.

    A fingerprint over a subset of output can only produce FALSE AGREEMENTS -- never false
    disagreements -- so the whole error class points at "reproducible", which is the direction
    that gets believed.
    """

    def test_a_two_decimal_metric_is_not_invisible(self):
        a, na = D.fingerprint_stdout("| test/mean_episode_reward | 1.27 |")
        b, nb = D.fingerprint_stdout("| test/mean_episode_reward | 1.60 |")
        assert na == nb == 1, "a two-decimal metric must contribute to the fingerprint"
        assert a != b, "two runs differing only in a short metric must not hash alike"

    def test_timing_is_still_excluded_at_any_precision(self):
        _, n = D.fingerprint_stdout("fps 15.02 total_time 477.9 elapsed 3.5")
        assert n == 0


class TestACrashIsNotAMeasurement:
    """Two crashed runs still print numbers, and comparing them measures nothing.

    Real case, 2026-08-19: `alda` forced onto CPU died inside its replay sampler on an
    unconditional `.cuda()`, and both trials produced 224 "values" of traceback. Without this
    guard the probe would have compared two stack traces and reported NONDETERMINISTIC.

    The exit code cannot discriminate: `ctrl` exits **1 on success** (absl calls `sys.exit` on a
    tuple return), so a nonzero rc is normal for one clone and fatal for another. The traceback
    works for both.
    """

    def test_a_crashed_trial_refuses_a_verdict(self):
        assert D.verdict(t("X", crashed=True), t("A"), t("B"))[0] == "RUN_FAILED"
        assert D.verdict(t("A"), t("X", crashed=True), t("B"))[0] == "RUN_FAILED"

    def test_a_nonzero_exit_without_a_traceback_still_gets_a_verdict(self):
        """ctrl's rc=1 is success; refusing on rc alone would discard a real result."""
        assert D.verdict(t("A", rc=1), t("B", rc=1), t("C", rc=1))[0] == "NONDETERMINISTIC"


class TestWallClockInEitherWordOrder:
    """The `ctrl` retraction of 2026-08-19, pinned.

    `TIMING_FIELD` matches keyword-then-number (`fps 15.02`). `ctrl` prints
    `PPO took 1.134254 seconds` -- number first -- and absl line prefixes carry
    `07:27:14.912374`. Neither matched, both entered the fingerprint, and `ctrl` was reported
    NONDETERMINISTIC twice for a baseline that reproduces.

    **This is the opposite error to the `idaac` one and they bracket the instrument.** Reading too
    LITTLE of the output produces false agreement (idaac); reading wall-clock produces false
    disagreement (ctrl). A fingerprint is wrong in both directions unless it reads all of the
    metrics and none of the clock.
    """

    def test_number_first_timing_is_excluded(self):
        _, n = D.fingerprint_stdout("PPO took 1.134254 seconds")
        assert n == 0

    def test_log_timestamps_are_excluded(self):
        _, n = D.fingerprint_stdout("I0819 07:27:14.912374 84043 xla_bridge.py:906] loss 1.5")
        assert n == 0, "an absl-prefixed line is a clock reading, not a measurement"

    def test_ordinary_metrics_survive_both_filters(self):
        _, n = D.fingerprint_stdout("| H 10.030 | V 0.043 | kl 0.025 |")
        assert n == 3
