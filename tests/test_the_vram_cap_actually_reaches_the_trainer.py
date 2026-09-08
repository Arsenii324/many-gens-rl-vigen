"""The VRAM cap must survive every later PYTHONPATH assignment, or it never applies at all.

[Claude 2026-09-09] It did not, and had not on any run. `run_probe.sh` installs `vram_cap.py` as a
`sitecustomize` module and prepends its directory to `PYTHONPATH`; five lines later another
`export PYTHONPATH=...` overwrote the variable without `${PYTHONPATH:+:$PYTHONPATH}`, discarding it.

**Why it survived so long.** Every run printed `NATIVE_VRAM_CAP_REQUESTED 2048 MiB`, and a solo
`idaac` cell sat at ~2019 MiB — just under the declared cap, because that is what idaac uses. The
cap looked enforced on the one family whose natural footprint resembles it. The first PACKED cell
exposed it immediately: two processes at **2019 MiB and 8207 MiB** against a 2048 MiB cap.

A safety mechanism on a shared GPU that had never once functioned while reporting that it had. This
file executes the real assignments rather than reading them, because the defect was invisible to
reading — both lines are individually correct.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"


def _pythonpath_assignments() -> list[str]:
    return [l.strip() for l in PROBE.read_text().splitlines()
            if re.match(r"\s*export PYTHONPATH=", l)]


def test_there_is_something_to_check():
    assert len(_pythonpath_assignments()) >= 2, _pythonpath_assignments()


def test_every_later_assignment_preserves_what_came_before():
    """Executed, not read: each line is individually valid; the defect is in their sequence."""
    lines = _pythonpath_assignments()
    script = "\n".join(["set -u", "work=/w", "vram_cap_dir=/w/.vram-cap",
                        "PYTHONPATH=/pre-existing", *lines,
                        'printf "%s\\n" "$PYTHONPATH"'])
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "/w/.vram-cap" in out.stdout, (
        "a later PYTHONPATH assignment discards the VRAM cap directory, so the cap never loads and "
        f"the cell runs uncapped on a shared card:\n{out.stdout}")
    assert "/pre-existing" in out.stdout, (
        f"an inherited PYTHONPATH is also discarded:\n{out.stdout}")


def test_the_cap_directory_is_prepended_where_it_is_installed():
    text = PROBE.read_text()
    assert 'export PYTHONPATH="$vram_cap_dir${PYTHONPATH:+:$PYTHONPATH}"' in text, (
        "the cap install no longer preserves an inherited PYTHONPATH")


def test_the_final_assignment_appends_rather_than_replaces():
    """Named explicitly so a future edit that drops the suffix fails here, not on a shared GPU."""
    lines = _pythonpath_assignments()
    final = lines[-1]
    assert "${PYTHONPATH:+:$PYTHONPATH}" in final, (
        f"the last PYTHONPATH assignment replaces instead of appending: {final}")


def test_the_cap_module_is_still_a_payload_member():
    """A cap that is not shipped cannot be installed, however correct the PYTHONPATH is."""
    contract = (ROOT / "datasphere" / "native" / "contract.py").read_text()
    assert "datasphere/native/vram_cap.py" in contract
