"""A job killed by its own timeout has already spent the money and reports a generic error.

`bt14het9mvpvvu8vatgo` died that way -- 3729s wall against `timeout --foreground 3600s`, exit 5, no
stdout to download -- and seven sibling configs carried the identical budget. Nothing checked that a
config's timeout could fit the evaluation it asked for.

The rates are per-family and MEASURED, because a flat rate produced a false FAIL on
`cfg-offline-eval-s2-full-v50.yaml`, a config that had demonstrably succeeded. This test pins both
directions: the audit must accept a config that really ran, and reject one that cannot fit.
"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _audit():
    spec = importlib.util.spec_from_file_location(
        "_budget", ROOT / "scripts" / "audit_job_budgets.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_budget"] = module
    spec.loader.exec_module(module)
    return module


def test_episode_count_multiplies_regimes_and_scenes():
    """The grid runs episodes x regimes x scenes; costing only `episodes` understates it tenfold."""
    audit = _audit()
    text = ("OFFLINE_EVAL_EPISODES=20 OFFLINE_EVAL_REGIMES=train,eval-easy "
            "OFFLINE_EVAL_SCENES=0,1,2")
    assert audit.episodes_of(text) == 120


def test_the_config_that_really_succeeded_is_accepted():
    """cfg-offline-eval-s2-full-v50 ran 400 drqv2 episodes in 3593s under a 9000s timeout."""
    audit = _audit()
    path = ROOT / "datasphere" / "native" / "cfg-offline-eval-s2-full-v50.yaml"
    if not path.is_file():                                         # pragma: no cover
        import pytest
        pytest.skip("the reference config is not in this tree")
    text = path.read_text()
    episodes = audit.episodes_of(text)
    rate = audit.MEASURED_SECONDS_PER_EPISODE.get(audit.family_of(text), audit.UNMEASURED_DEFAULT)
    need = audit.BOOTSTRAP_SECONDS + episodes * rate * audit.SAFETY
    assert need <= 9000, (
        f"the audit would reject a config that demonstrably completed: needs {need:.0f}s of 9000s"
    )


def test_measured_rates_are_derived_from_named_jobs():
    """A rate with no job behind it is a guess wearing a measurement's clothes."""
    audit = _audit()
    source = (ROOT / "scripts" / "audit_job_budgets.py").read_text()
    for family in ("drqv2", "idaac"):
        assert family in audit.MEASURED_SECONDS_PER_EPISODE
    assert "bt1rr9hodosm5sn09t1a" in source and "bt1ip5f8c6mqqm7fd2bn" in source, (
        "the per-family rates must cite the job IDs they were measured from"
    )


def test_the_whole_config_directory_currently_fits():
    audit = _audit()
    assert audit.audit() == 0, (
        "a job config cannot fit its own workload; run scripts/audit_job_budgets.py"
    )
