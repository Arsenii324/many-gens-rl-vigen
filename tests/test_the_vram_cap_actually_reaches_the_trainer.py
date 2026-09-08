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


def test_the_final_assignment_preserves_the_inherited_path():
    """Named explicitly so a future edit that drops it fails here, not on a shared GPU.

    [Claude 2026-09-09] It must preserve the inherited PYTHONPATH *and* put it FIRST -- appending
    was the second version of this bug, because runnable/_shim's sitecustomize then won the name.
    """
    final = _pythonpath_assignments()[-1]
    assert "${PYTHONPATH:+$PYTHONPATH:}" in final, (
        f"the last PYTHONPATH assignment drops or appends the inherited path: {final}")


def test_the_cap_module_is_still_a_payload_member():
    """A cap that is not shipped cannot be installed, however correct the PYTHONPATH is."""
    contract = (ROOT / "datasphere" / "native" / "contract.py").read_text()
    assert "datasphere/native/vram_cap.py" in contract


# --- "requested" and "in force" are different claims, and only one is checkable ------------------


def test_the_runner_verifies_the_cap_rather_than_announcing_it():
    """`NATIVE_VRAM_CAP_REQUESTED` printed for a day while the cap was discarded.

    A log line that says a safety property was *asked for* is not evidence it holds. The runner now
    imports the cap module through the same interpreter the trainer uses, after every PYTHONPATH
    assignment, and refuses when it is not importable.
    """
    text = PROBE.read_text()
    assert "NATIVE_VRAM_CAP_IN_FORCE" in text, "the cap is announced but never verified"
    assert "NATIVE_VRAM_CAP_NOT_IN_FORCE" in text
    verify_at = text.index("NATIVE_VRAM_CAP_IN_FORCE")
    last_pythonpath = text.rindex("export PYTHONPATH=")
    assert verify_at > last_pythonpath, (
        "the cap is verified BEFORE the last PYTHONPATH assignment, which is exactly where it was "
        "being discarded")


def test_an_unenforced_cap_stops_the_cell():
    text = PROBE.read_text()
    block = text[text.index("NATIVE_VRAM_CAP_NOT_IN_FORCE"):][:700]
    assert "exit 3" in block, (
        "an unenforced cap must stop the cell: it is quoted as a safety property on a shared card, "
        "and a declared absence is safer than a false presence")


def test_the_cap_module_carries_a_marker_the_check_can_see():
    cap = (ROOT / "datasphere" / "native" / "vram_cap.py").read_text()
    assert "_rlvigen_vram_cap" in cap, (
        "the verification would fall back to matching a filename, which a rename would silently "
        "defeat")


# --- two modules compete for the name `sitecustomize`, and Python takes the first ----------------
# [Claude 2026-09-09] `runnable/_shim/sitecustomize.py` (the Mac MPS-as-CUDA shim) is on the cell's
# PYTHONPATH ahead of the cap directory. Python imports the FIRST `sitecustomize` and stops, so the
# shim won and the cap never loaded -- even after the earlier fix stopped PYTHONPATH being
# overwritten. Appending was not enough; the cap has to come first, and must then chain to what it
# displaces so the shim is not silently suppressed in return.


def _shim_and_cap(tmp_path):
    import shutil
    cap, shim = tmp_path / "cap", tmp_path / "shim"
    cap.mkdir(); shim.mkdir()
    shutil.copy(ROOT / "datasphere" / "native" / "vram_cap.py", cap / "sitecustomize.py")
    shutil.copy(ROOT / "runnable" / "_shim" / "sitecustomize.py", shim / "sitecustomize.py")
    return cap, shim


def test_the_cap_wins_when_a_competing_sitecustomize_is_on_the_path(tmp_path):
    import os
    import subprocess
    import sys as _sys
    cap, shim = _shim_and_cap(tmp_path)
    env = dict(os.environ, PYTHONPATH=f"{cap}:{shim}")
    out = subprocess.run(
        [_sys.executable, "-c",
         "import sitecustomize; print(hasattr(sitecustomize,'_rlvigen_vram_cap'))"],
        capture_output=True, text=True, env=env, timeout=60)
    assert out.stdout.strip().endswith("True"), (
        "runnable/_shim's sitecustomize shadowed the VRAM cap:\n" + out.stdout + out.stderr)


def test_the_runner_puts_the_cap_directory_first():
    lines = _pythonpath_assignments()
    final = lines[-1]
    assert final.startswith('export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}'), (
        f"the inherited PYTHONPATH (which carries the cap) is appended, so runnable/_shim's "
        f"sitecustomize is imported instead: {final}")


def test_the_cap_chains_to_the_sitecustomize_it_displaces(tmp_path):
    """Winning the name must not silently disable the shim."""
    cap = (ROOT / "datasphere" / "native" / "vram_cap.py").read_text()
    assert "_chain_to_displaced_sitecustomize" in cap, (
        "the cap takes the sitecustomize name without running what it replaced")
    # Check for the real statement, not the docstring that explains why it was removed.
    code_lines = [l.strip() for l in cap.splitlines()
                  if l.strip().startswith("import sitecustomize")]
    assert not code_lines, (
        f"the old self-import is back: this module IS sitecustomize, so it chained to itself: "
        f"{code_lines}")

    import os
    import subprocess
    import sys as _sys
    capdir, shim = _shim_and_cap(tmp_path)
    # A marker the displaced module writes, so we can prove it actually executed.
    (shim / "sitecustomize.py").write_text(
        "import pathlib\npathlib.Path(%r).write_text('ran')\n" % str(tmp_path / "shim-ran"))
    env = dict(os.environ, PYTHONPATH=f"{capdir}:{shim}")
    subprocess.run([_sys.executable, "-c", "import sitecustomize"],
                   capture_output=True, text=True, env=env, timeout=60)
    assert (tmp_path / "shim-ran").exists(), (
        "the displaced sitecustomize never ran; the cap suppressed it")
