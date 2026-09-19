"""The waiter fires exactly once, and that cost a window.

`wait-and-train-v4.sh` exits after its first launch attempt, success or failure. On 2026-09-17 a
cell died 24 s in (`EGL_NOT_INITIALIZED`); the card stayed clear afterwards and nothing used it,
because the waiter was already gone. This exercises the opt-in retry branch that covers that case,
and -- equally -- pins the default, which must still be launch-once.

These are the first tests of a host script in this repo, so the ground rules are worth stating.
Everything Linux-only is stubbed on PATH (`flock`, `pgrep`, `docker`, `nvidia-smi`, `df`, `stat`,
`free`) and `HOME` points at a temp directory, so nothing here touches the production host, the real
occupancy log, or the real lock. What is NOT stubbed is the decision under test: the streak rule,
the launch, and the retry arithmetic all run as written.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WAITER = ROOT / "datasphere" / "native" / "host-scripts" / "wait-and-train-v4.sh"

STUBS = {
    # `date -Is` is GNU; BSD date wants the long form. `date -d <ISO-8601> +%s` is what
    # clear_streak() (2026-09-20) uses to detect a gap between samples, on or off this Mac -- GNU
    # date on the real host parses that natively, with or without a UTC offset, so both shapes are
    # mirrored here via BSD's `-j -f` rather than letting an unsupported `-d` fail outright, which
    # would make every sample in this file's un-offset fixtures "unparsable" and turn the
    # gap-contiguity fix's fail-closed behaviour into an infinite wait for streaks that used to
    # form immediately.
    "date": r"""#!/bin/sh
if [ "$1" = "-Is" ]; then exec /bin/date -Iseconds; fi
if [ "$1" = "-d" ]; then
  ts="$2"; shift 2
  case "$ts" in
    *[+-][0-9][0-9]:[0-9][0-9])
      norm=$(printf '%s' "$ts" | sed -E 's/([+-][0-9]{2}):([0-9]{2})$/\1\2/')
      exec /bin/date -j -f "%Y-%m-%dT%H:%M:%S%z" "$norm" "$@"
      ;;
    *)
      exec /bin/date -j -f "%Y-%m-%dT%H:%M:%S" "$ts" "$@"
      ;;
  esac
fi
exec /bin/date "$@"
""",
    "flock": "#!/bin/sh\nexit 0\n",
    "pgrep": "#!/bin/sh\nexit 1\n",
    "docker": "#!/bin/sh\nexit 0\n",          # `docker ps` prints nothing: no cell of ours is up
    "nvidia-smi": "#!/bin/sh\necho 32000\n",  # far above NEED
    "df": "#!/bin/sh\necho h\necho 'x 1 2 999999999 4'\n",   # NR==2 $4 -> ~953 GiB free
    "stat": '#!/bin/sh\nexec /bin/date +%s\n',               # the occupancy log is always fresh
    "free": "#!/bin/sh\necho h\necho 'Mem: 1 2 3 4 5 120'\n",
}


def _sandbox(tmp_path: pathlib.Path, wrapper_body: str) -> tuple[dict, pathlib.Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in STUBS.items():
        path = bin_dir / name
        path.write_text(body)
        path.chmod(0o755)

    work = tmp_path / "rlvigen-work"
    work.mkdir()
    wrapper = work / "stub-wrapper.sh"
    wrapper.write_text(wrapper_body)
    wrapper.chmod(0o755)

    runs = tmp_path / "rlvigen-runs"
    runs.mkdir()
    occ = runs / "gpu-occupancy.log"
    # Twelve samples with no foreign holder and the card nearly empty: a genuine window.
    occ.write_text("".join(
        f"2026-09-18T12:{m:02d}:00 card=1 mem=100 holders=-\n" for m in range(12)))

    env = dict(os.environ)
    env.update({
        "PATH": f"{bin_dir}:{env['PATH']}",
        "HOME": str(tmp_path),
        "CARD": "1", "FAMILY": "idaac", "BASELINE": "stub", "SEED": "999",
        "POLL": "1", "MAXWAIT": "45", "HOLD": "10", "HEARTBEAT": "1000",
        # MAX_SAMPLE_GAP (2026-09-20) defaults to POLL*3, which is right when POLL tracks the
        # log's own write cadence -- it does not here: POLL=1 above is a TEST speed knob for the
        # waiter's own re-poll loop, unrelated to this fixture's log, which is one 60-second-apart
        # sample per line regardless. Left at the default, every real 60s gap between this file's
        # own samples would exceed a 3s tolerance and reset the streak on every single sample.
        "MAX_SAMPLE_GAP": "120",
        "WRAPPER": "stub-wrapper.sh",
        # The real wait for a cell container is 60 x 5 s. No container ever appears here, so
        # without this every test would idle for five minutes per launch attempt.
        "CELL_WAIT_TRIES": "1",
        "WAITER_LOCK": str(tmp_path / "waiter.lock"),
        "OCC": str(occ),
        "MIN_RAM_GIB": "0",
    })
    return env, tmp_path / "rlvigen-runs" / "prod-v214" / "stub-s999-prod-waiter-v4.log"


def _run(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([shutil.which("bash") or "bash", str(WAITER)],
                          env=env, capture_output=True, text=True, timeout=180)


@pytest.mark.skipif(not WAITER.exists(), reason="waiter script missing")
def test_the_default_is_still_launch_once():
    """Nothing about tonight's armed waiter may change. Off by default, and off means one launch."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        env, log = _sandbox(pathlib.Path(tmp), "#!/bin/sh\nexit 7\n")
        _run(env)
        body = log.read_text()
        assert body.count("WINDOW HELD") == 1, body
        assert "retry" not in body, body
        assert "this waiter is done" in body, body


@pytest.mark.skipif(not WAITER.exists(), reason="waiter script missing")
def test_a_fast_failure_is_retried_only_when_the_flag_is_set():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        env, log = _sandbox(pathlib.Path(tmp), "#!/bin/sh\nexit 7\n")
        env.update({"RETRY_FAST_FAILURES": "1", "MAX_RETRIES": "1",
                    "FAST_FAILURE_SECONDS": "600"})
        _run(env)
        body = log.read_text()
        assert body.count("WINDOW HELD") == 2, body
        assert "retry 1/1" in body, body
        assert "this waiter is done" in body, body


@pytest.mark.skipif(not WAITER.exists(), reason="waiter script missing")
def test_a_cell_that_ran_a_while_is_never_retried():
    """The branch exists for a launch that dies in its first minutes, not for a crash at hour nine.

    Rerunning a long cell would relaunch training from zero over its own partial run, and it would
    do it unattended.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        env, log = _sandbox(pathlib.Path(tmp), "#!/bin/sh\nsleep 4\nexit 7\n")
        env.update({"RETRY_FAST_FAILURES": "1", "MAX_RETRIES": "2",
                    "FAST_FAILURE_SECONDS": "2"})
        _run(env)
        body = log.read_text()
        assert body.count("WINDOW HELD") == 1, body
        assert "ran 4s" in body or "not a fast failure" in body, body


@pytest.mark.skipif(not WAITER.exists(), reason="waiter script missing")
def test_a_successful_launch_is_never_retried():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        env, log = _sandbox(pathlib.Path(tmp), "#!/bin/sh\nexit 0\n")
        env.update({"RETRY_FAST_FAILURES": "1", "MAX_RETRIES": "2",
                    "FAST_FAILURE_SECONDS": "600"})
        _run(env)
        body = log.read_text()
        assert body.count("WINDOW HELD") == 1, body
