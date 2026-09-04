"""`probe_regimes` must enumerate the regimes the environment actually implements.

C19 rests on this probe, and C46 compares the scene axis against its result. Its regime list is a
hardcoded tuple; `make_env` decides what regimes exist. If upstream renames or adds one, the
probe does not fail — it silently measures a smaller set, and the missing regime never appears in
any table. That is the quiet direction, so it is asserted here rather than trusted.

No environment is built: this compares a tuple against source text and stays runnable anywhere.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "RL-ViGen-upstream"
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.skipif(not UPSTREAM.exists(), reason="upstream clone absent")

MAKE_ENV = UPSTREAM / "envs" / "robosuiteVGB" / "robosuitevgb" / "utils.py"


def implemented_regimes() -> set[str]:
    """Regimes `make_env` branches on, read from its own source."""
    t = MAKE_ENV.read_text(errors="replace")
    return set(re.findall(r"cfg_dict\['mode'\]\s*==\s*'([\w-]+)'", t))


def test_the_probe_covers_every_regime_it_could_measure():
    from scripts.probe_regimes import REGIMES
    impl = implemented_regimes()
    assert impl, "no regime branches found in make_env -- this checker went blind"
    missing = impl - set(REGIMES) - {"cam-easy", "cam-hard"}   # camera regimes are a separate axis
    assert not missing, (
        f"make_env implements regimes the probe never measures: {sorted(missing)}. C19's "
        "separation result would silently exclude them.")


def test_every_regime_the_probe_names_actually_exists():
    """The other direction: a probe naming a regime that was removed reports it as unbuildable
    and the run reads as a partial failure rather than a stale list."""
    from scripts.probe_regimes import REGIMES
    impl = implemented_regimes()
    assert set(REGIMES) <= impl, (
        f"probe names regimes make_env does not implement: {sorted(set(REGIMES) - impl)}")


def test_train_is_among_them_because_it_is_the_reference():
    from scripts.probe_regimes import REGIMES
    assert REGIMES[0] == "train", (
        "every between-regime distance is measured against train; if it is not first, or not "
        "present, the probe has no reference point")
