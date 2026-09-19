"""The waiter's streak rule must require CONTIGUOUS samples, not just individually-clear ones.

Found live 2026-09-20: the host crashed at 21:25 on 2026-09-19, `gpu-occupancy-log.sh` restarted at
01:02 on 2026-09-20, and three minutes later a DRYRUN replay printed "streak 10/10" built from seven
pre-crash lines (21:16-21:22) plus three fresh ones. The only staleness guard, `LOG_MAX_AGE`, checks
only the age of the LAST line, which a fresh restart always satisfies -- so after any logger outage
the "ten CONSECUTIVE one-minute samples" rule silently became "any ten samples, however far apart".

This drives `clear_streak()` through `DECIDE_ONLY=1`/`AS_OF=...`, the replay mode the script's own
header names for exactly this kind of validation ("replay one past moment and exit"), so nothing
here spawns a container, touches the real occupancy log, or launches anything.
"""
from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WAITER = ROOT / "datasphere" / "native" / "host-scripts" / "wait-and-train-v4.sh"

# `date -Is` is GNU; the streak fix also needs `date -d <ISO-8601> +%s`, which GNU date on the
# real host (Ubuntu) parses natively, offset and all. BSD `date -j -f` needs the offset without a
# colon, so this strips it before delegating -- the same shape of accommodation the existing
# `date -Is` stub already makes for this Mac, extended to the one new invocation this fix adds.
DATE_STUB = """#!/bin/sh
if [ "$1" = "-Is" ]; then exec /bin/date -Iseconds; fi
if [ "$1" = "-d" ]; then
  ts=$(printf '%s' "$2" | sed -E 's/([+-][0-9]{2}):([0-9]{2})$/\\1\\2/')
  shift 2
  exec /bin/date -j -f "%Y-%m-%dT%H:%M:%S%z" "$ts" "$@"
fi
exec /bin/date "$@"
"""


def _sandbox(tmp_path: pathlib.Path, lines: list[str]) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    date_path = bin_dir / "date"
    date_path.write_text(DATE_STUB)
    date_path.chmod(0o755)

    occ = tmp_path / "gpu-occupancy.log"
    occ.write_text("".join(line + "\n" for line in lines))

    env = dict(os.environ)
    env.update({
        "PATH": f"{bin_dir}:{env['PATH']}",
        "HOME": str(tmp_path),
        "CARD": "1", "FAMILY": "stub", "BASELINE": "stub", "SEED": "1",
        "OCC": str(occ),
        "WAITER_LOG": str(tmp_path / "waiter.log"),
        "NEED": "100", "HOLD": "10",
    })
    return env


def _decide(env: dict, as_of: str | None) -> str:
    env = dict(env)
    env["DECIDE_ONLY"] = "1"
    if as_of is None:
        env.pop("AS_OF", None)
    else:
        env["AS_OF"] = as_of
    result = subprocess.run(["bash", str(WAITER)],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"rc={result.returncode} stderr={result.stderr}"
    return result.stdout.strip()


def _clear(ts: str) -> str:
    return f"{ts} card=1 mem=0 util=0 procs=0 holders=-"


@pytest.mark.skipif(not WAITER.exists(), reason="waiter script missing")
def test_a_gap_across_a_logger_outage_is_not_a_sustained_vacancy(tmp_path):
    """7 pre-crash + 3 post-restart samples, all individually clear, is NOT a 10-sample streak."""
    lines = [_clear(f"2026-09-19T21:{16 + i:02d}:00+03:00") for i in range(7)]   # 21:16 .. 21:22
    lines += [_clear(f"2026-09-20T01:{3 + i:02d}:00+03:00") for i in range(3)]   # 01:03 .. 01:05
    env = _sandbox(tmp_path, lines)
    out = _decide(env, "2026-09-20T01:05")
    assert "10/10" not in out, out
    assert out.endswith("wait"), out


@pytest.mark.skipif(not WAITER.exists(), reason="waiter script missing")
def test_ten_truly_contiguous_samples_are_still_accepted(tmp_path):
    """The control: a real ten-minute vacancy must still read as launchable."""
    lines = [_clear(f"2026-09-20T01:{i:02d}:00+03:00") for i in range(10)]       # 01:00 .. 01:09
    env = _sandbox(tmp_path, lines)
    out = _decide(env, "2026-09-20T01:09")
    assert "10/10" in out, out
    assert out.endswith("LAUNCHABLE"), out


@pytest.mark.skipif(not WAITER.exists(), reason="waiter script missing")
def test_an_unparseable_timestamp_refuses_rather_than_launching_blind(tmp_path):
    """`date -d` failing on every sample must fail CLOSED, not silently skip the time check.

    Each line below is individually clear (no holder, plenty of memory) but none of the ten
    timestamps can be placed in time -- a stand-in for a logger format change or a `date` that
    behaves differently on some host. Before this fix, an unparsable epoch just skipped the gap
    comparison, so all ten still counted as clear and the waiter would have launched blind.
    """
    lines = [f"NOT-A-TIMESTAMP-{i} card=1 mem=0 util=0 procs=0 holders=-" for i in range(10)]
    env = _sandbox(tmp_path, lines)
    out = _decide(env, None)
    assert "0/10" in out, out
    assert out.endswith("wait"), out
    log = (tmp_path / "waiter.log").read_text()
    assert "cannot parse the timestamp" in log, log


@pytest.mark.skipif(not WAITER.exists(), reason="waiter script missing")
def test_a_gap_exactly_at_the_limit_is_accepted_one_second_more_is_not(tmp_path):
    """The boundary: MAX_SAMPLE_GAP itself is still one streak; MAX_SAMPLE_GAP + 1 is not."""
    base = "2026-09-20T01:00:00+03:00"
    at_limit = "2026-09-20T01:02:00+03:00"    # 120s after base
    over_limit = "2026-09-20T01:02:01+03:00"  # 121s after base

    env = _sandbox(tmp_path / "at-limit", [_clear(base), _clear(at_limit)])
    env.update({"HOLD": "2", "MAX_SAMPLE_GAP": "120"})
    out = _decide(env, None)
    assert "2/2" in out, out
    assert out.endswith("LAUNCHABLE"), out

    env2 = _sandbox(tmp_path / "over-limit", [_clear(base), _clear(over_limit)])
    env2.update({"HOLD": "2", "MAX_SAMPLE_GAP": "120"})
    out2 = _decide(env2, None)
    assert "1/2" in out2, out2
    assert out2.endswith("wait"), out2
