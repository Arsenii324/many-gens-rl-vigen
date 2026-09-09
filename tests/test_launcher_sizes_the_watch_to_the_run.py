"""The watch budget must be derived from the run, not typed next to it.

[Claude 2026-09-08] The launch this file replaces armed both card watches for 4500s against an
assumed ~10 minute bootstrap. 51 minutes in it was still downloading, so the watches would expire
before the cell ever reached the GPU, and both would have exited 0 reporting a clean run.

Three separate things had to be right and all three were hand-typed: the card index (three times --
`--gpus`, and `--device` on each watcher, with nothing checking they agreed), the watch budget, and
the relationship between that budget and the cell timeout. This pins all three.

The arithmetic is EXECUTED out of the real file rather than restated here. A test that recomputes
the formula independently passes whenever the two copies agree, including when they are both wrong.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "datasphere" / "native" / "launch-card-cell.sh"


def _derive(cell_timeout: str, extra_env: dict | None = None) -> dict[str, int]:
    """Run the launcher's own arithmetic, lifted verbatim, and report what it produced."""
    text = LAUNCHER.read_text()
    head = 'if [[ -n "${NATIVE_VENV_HOST:-}" ]]; then'
    tail = "WATCH_SECONDS=$(( MUST_COVER + SLACK ))"
    # Said explicitly, because losing the anchor means the derivation itself has been replaced --
    # most likely by a constant, which is exactly the defect this file exists to catch.
    assert head in text, (
        "the launcher no longer derives a bootstrap allowance from which path the cell takes; "
        "the watch budget is not being computed from the run any more")
    assert 'BOOTSTRAP_ALLOWANCE="${NATIVE_BOOTSTRAP_ALLOWANCE_SECONDS' in text
    assert tail in text, (
        "the launcher no longer derives WATCH_SECONDS from MUST_COVER + SLACK; a hardcoded budget "
        "is what caused the 2026-09-08 near-miss")
    body = text[text.index(head):text.index(tail) + len(tail)]
    env = {"CELL_TIMEOUT_SECONDS": cell_timeout, **(extra_env or {})}
    exports = "".join(f"export {k}={v}\n" for k, v in env.items())
    script = (f"set -u\n{exports}{body}\n"
              'printf "cover=%s watch=%s boot=%s\\n" "$MUST_COVER" "$WATCH_SECONDS" "$BOOTSTRAP_ALLOWANCE"\n')
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", out.stdout)}


def test_the_watch_outlasts_the_cell_and_its_bootstrap():
    got = _derive("3600")
    assert got["cover"] > 3600, "the cover does not even include the bootstrap"
    assert got["watch"] > got["cover"], "no slack: the watch ends exactly as the work does"
    # The specific failure: a 3600s cell whose watch was 4500s.
    assert got["watch"] > 4500, f"still short enough to reproduce the near-miss: {got}"


def test_a_longer_cell_gets_a_longer_watch():
    """The budget must track the cell, or it is a constant wearing a formula's clothes."""
    short, long = _derive("3600"), _derive("162000")   # 45h, production scale
    # x2, because the budget now covers training AND the evaluation that follows it, and the eval
    # allowance defaults to the cell timeout (2026-09-09: eval measured ~1.6x its training).
    assert long["watch"] - short["watch"] == 2 * (162000 - 3600), (short, long)


def test_the_bootstrap_allowance_is_pessimistic_by_default():
    """Measured ~2h without a wheel cache. A default below that re-creates the near-miss."""
    assert _derive("3600")["boot"] >= 7200


def _code() -> str:
    """The executable body. Prose mentioning a flag is not the same as passing it."""
    return "\n".join(l for l in LAUNCHER.read_text().splitlines()
                      if not l.lstrip().startswith("#"))


# --must-cover-seconds applies to all three watches (exclusivity, yield, disk); the cell-active
# flags apply only to the two that watch the CARD, since a disk does not become "ours".
@pytest.mark.parametrize("flag, expected", [("--must-cover-seconds", 3),
                                            ("--stop-when-inactive", 2),
                                            ("--active-file", 2)])
def test_the_watchers_receive_their_flags(flag, expected):
    code = _code()
    assert code.count(flag) == expected, (
        f"{flag} reaches {code.count(flag)} watcher(s) in the executable body, expected {expected}")


def test_the_card_index_is_derived_once():
    code = _code()
    for literal in ("--device 0", "--device 1", 'device=0"', 'device=1"'):
        assert literal not in code, f"card index hardcoded as {literal!r}"
    # preflight, exclusivity watch, yield watch -- all three from the same variable.
    assert code.count('--device "$CARD"') == 3, code.count('--device "$CARD"')
    # preflight's --gpus and the cell's DOCKER_GPUS; the watchers use --gpus all deliberately,
    # because nvidia-smi in a container restricted to our card cannot see a neighbour on another.
    assert code.count("device=${CARD}") == 2, "the --gpus flags must come from CARD too"


def test_it_refuses_without_a_cell_timeout(tmp_path):
    """The budget is derived from it, so a missing timeout must stop the launch, not default it."""
    out = subprocess.run(
        ["bash", str(LAUNCHER), str(tmp_path / "p.tgz"), str(tmp_path / "r.tgz")],
        capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "CARD": "0", "CELLS": "idaac:101"})
    assert out.returncode != 0
    assert "CELL_TIMEOUT_SECONDS" in out.stderr, out.stderr + out.stdout


def test_the_stand_down_runs_even_on_an_early_exit():
    """A refused preflight must still stop watchers this script started."""
    text = LAUNCHER.read_text()
    trap_at = text.index("trap stand_down EXIT")
    assert trap_at < text.index("STEP 0"), "the trap is installed after work has already begun"


# --- the container needs a bound too, not just the cell inside it -------------------------------
# [Claude 2026-09-08] CELL_TIMEOUT_SECONDS starts when TRAINING starts. Nothing bounded the phase
# before it, and on 2026-09-08 that phase was the long one. A hung `pip` would leave a container
# running indefinitely on a shared machine, and the outer `timeout` on the SSH connection is not a
# substitute: it kills the client while dockerd keeps the container alive.


def test_the_container_is_reaped_at_the_declared_budget():
    code = _code()
    assert "REAPING" in code, "nothing bounds the container itself"
    assert 'sleep "$WATCH_SECONDS"' in code, (
        "the reaper must use the same derived budget as the watches, not its own constant")
    assert 'docker stop "$CELL_NAME"' in code


def test_the_cell_container_has_a_name_the_reaper_can_find():
    code = _code()
    assert 'NATIVE_CONTAINER_NAME="$CELL_NAME"' in code, (
        "run_on_production_host.sh would name the container by timestamp and the reaper could not "
        "address it")
    # Anchored, or `docker stop` could match a substring of somebody else's container name.
    assert '"name=^${CELL_NAME}$"' in code, "the reaper's filter is not anchored"


def test_the_reaper_does_not_outlive_the_run():
    """A detached `sleep 12600` left behind by every launch is litter on a shared host."""
    code = _code()
    kill_at = code.index('kill "$reaper_pid"')
    assert code.index("stand_down() {") < kill_at < code.index("docker stop \"$EXCL\""), (
        "the reaper is not killed during stand-down")


def test_how_many_processes_are_ours_is_not_a_bare_literal():
    """A false breach reads exactly like a real one, so the assumption must be nameable.

    Verified 2026-09-08: no family under runnable/ spawns CUDA subprocesses -- the only
    torch.multiprocessing reference is commented out -- so 1 is right today for all twelve. It is a
    variable so that a family which later grows a worker pool can say so.
    """
    code = _code()
    assert '--expect-ours "$EXPECT_OURS"' in code, "process count hardcoded at the call site"
    # [Claude 2026-09-09] Was `:-1`. The default is now DERIVED from the cell list, because a
    # packed run puts one process on the card per CELL and a literal 1 made the daemon yield to
    # its own second cell.
    assert 'EXPECT_OURS="${NATIVE_EXPECT_OURS:-$_cell_count}"' in code


def test_a_prebuilt_environment_collapses_the_bootstrap_allowance():
    """The allowance must track WHICH path the cell takes, not be remembered by the operator.

    With no prebuilt env the cell runs pip, measured past two hours on 2026-09-08. With one, only
    `apt` runs, measured at 71 seconds. An allowance sized for the slow path silently over-covers;
    one sized for the fast path silently under-covers, and under-covering is what leaves a GPU
    phase unwatched.
    """
    slow = _derive("3600")
    fast = _derive("3600", {"NATIVE_VENV_HOST": "/home/x/rlvigen-env/torch-abc"})
    assert fast["boot"] < slow["boot"], (slow, fast)
    assert fast["watch"] < slow["watch"]
    # Still has to cover the cell itself plus a real bootstrap, or we have traded one bug for another.
    assert fast["cover"] > 3600 and fast["boot"] >= 300, fast


def test_the_budget_covers_evaluation_not_only_training():
    """CELL_TIMEOUT_SECONDS wraps TRAINING only; eval runs after it and is comparable in size.

    [Claude 2026-09-09] run_probe.sh applies the cell timeout at its line ~500 and then calls
    run_curve_eval / run_endpoint_eval afterwards, outside it. Measured on the idaac 600k cell:
    ~5h training, ~4.5h curve eval (11 checkpoints x 1478s), ~3.3h endpoint grid (80 regime-scene
    passes at 2 per 5 min). A reaper budget derived from the cell timeout alone covers about half
    the container's life, and the failure it permits is the worst-timed one available: killing a
    cell DURING EVALUATION, after every hour of training is already paid for.
    """
    got = _derive("43200")
    assert got["cover"] >= 2 * 43200, (
        f"the watch budget still assumes the cell timeout bounds the whole container: {got}")
