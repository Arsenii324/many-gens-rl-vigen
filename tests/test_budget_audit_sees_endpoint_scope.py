"""The budget auditor must cost BOTH evaluation scopes and the training phase.

It greped only `OFFLINE_EVAL_EPISODES`. Configs on the `ENDPOINT_EVAL_*` scope -- which is every
validation config written after I split the scopes -- returned None and were `continue`d, printing
nothing. A skipped config is indistinguishable from a passing one, which is the exact failure this
auditor was built to catch, committed by the auditor.

Also pins the false-alarm direction: an offline config's FRAMES names its snapshot's budget, not
work to do, so it must NOT be charged for training.
"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _audit():
    spec = importlib.util.spec_from_file_location("_jb", ROOT / "scripts" / "audit_job_budgets.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_jb"] = m
    spec.loader.exec_module(m)
    return m


ENDPOINT = ("timeout --foreground 7200s env CELLS=alda:1 FRAMES=10000 ENDPOINT_EVAL=1 "
            "ENDPOINT_EVAL_REGIMES=train,eval-easy ENDPOINT_EVAL_SCENES=0 ENDPOINT_EVAL_EPISODES=5")
OFFLINE = ("timeout --foreground 9000s env CELLS=drqv2:1 FRAMES=60000 OFFLINE_EVAL_SNAPSHOT=s.pt "
           "OFFLINE_EVAL_EPISODES=20 OFFLINE_EVAL_REGIMES=train,eval-easy")


def test_endpoint_scope_configs_are_costed_not_skipped():
    assert _audit().episodes_of(ENDPOINT) == 10, "5 episodes x 2 regimes x 1 scene"


def test_offline_scope_still_works():
    assert _audit().episodes_of(OFFLINE) == 40


def test_a_training_phase_is_charged_for():
    seconds, family = _audit().training_seconds(ENDPOINT)
    assert family == "alda" and seconds > 0


def test_an_offline_config_is_not_charged_for_training():
    assert _audit().training_seconds(OFFLINE) == (0, None), "vestigial FRAMES must not bill"


def test_every_live_validation_config_is_visible_to_the_auditor():
    """The regression that matters: no config on disk asking for an eval may go uncosted."""
    configs = ROOT / "datasphere" / "native"
    audit = _audit()
    for path in sorted(configs.glob("cfg-*functional-v11*.yaml")):
        text = path.read_text()
        assert audit.episodes_of(text), f"{path.name} asks for an evaluation the auditor cannot see"
