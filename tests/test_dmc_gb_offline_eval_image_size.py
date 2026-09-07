"""dmc_gb's robosuite render is native 84x84; RAD/SODA need the raw 100x100 render to crop from.

`runnable/_launch/dmc_gb.sh` exports `RLVIGEN_IMAGE_SIZE=100` before TRAINING, but
`run_probe.sh`'s three offline/endpoint/curve evaluation paths (`run_endpoint_eval`,
`run_curve_eval`, `run_offline_eval`) call `scripts/eval_grid.py` directly, in `run_probe.sh`'s
own shell, which never inherited that export. Left unset, `robosuitevgb/utils.py` renders
natively at 84, RAD's own `random_crop` silently degrades to the identity (`crop_max <= 0`), and
SODA hard-asserts `x.size(-1) == 100` and cannot run at all.

Found via the v194 wave's dmc_gb cell: `verify_runtime_observation_geometry` failed correctly on
a real mismatch ("expected 9 channels ... at 100x100, observed (9, 84, 84)"), not a false
positive -- confirming the eval subprocess actually ran at the wrong render size. This test pins
the fix (each call site sets `RLVIGEN_IMAGE_SIZE=100` for family `dmc_gb`) as source text, the
same style `test_observation_geometry.py` already uses for the launcher scripts.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN_PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"


def _function_body(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}\(\) \{{\n(.*?)\n\}}", text, re.DOTALL | re.MULTILINE)
    assert match, f"could not find function {name}() in {RUN_PROBE}"
    return match.group(1)


def test_endpoint_and_curve_eval_guard_dmc_gb_image_size():
    text = RUN_PROBE.read_text()
    for func in ("run_endpoint_eval", "run_curve_eval"):
        body = _function_body(text, func)
        assert '"$family" == "dmc_gb"' in body, (
            f"{func} no longer guards dmc_gb's render size -- rad/soda's crop would silently "
            "degrade to the identity again")
        assert 'RLVIGEN_IMAGE_SIZE=' in body
        assert re.search(r'env "\$\{image_size_env\[@\]\}" python3 scripts/eval_grid\.py', body), (
            f"{func} must pass image_size_env into the eval_grid.py invocation it guards")


def test_offline_eval_guards_dmc_gb_image_size():
    text = RUN_PROBE.read_text()
    body = _function_body(text, "run_offline_eval")
    assert '"${OFFLINE_EVAL_FAMILY:-rlvigen}" == "dmc_gb"' in body
    assert 'RLVIGEN_IMAGE_SIZE=' in body
    assert re.search(r'env "\$\{image_size_env\[@\]\}" python3 scripts/eval_grid\.py', body)
