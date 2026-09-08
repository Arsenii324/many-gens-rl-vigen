"""A completed cell must not report failure because its own outputs are unreadable.

[Claude 2026-09-09] The first cell to complete on the production host printed
`native probe completed successfully`, then:

    cp: cannot open '.../out/records.jsonl' for reading: Permission denied
    === CELL EXIT=1

The container runs as root (the images declare no USER and apt-get needs it), so bind-mounted
outputs are root-owned and some are 0600 -- `records.jsonl` and `run_manifest.json`. `result.tgz` is
0644 and copied fine, which is what made this partial rather than obvious: an expensive run reported
as a failure, with the records silently left behind.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "datasphere" / "native" / "run_on_production_host.sh"


def test_the_outputs_are_chowned_before_they_are_copied():
    text = WRAPPER.read_text()
    assert "chown -R" in text, "nothing hands the root-owned outputs back to the host user"
    chown_at = text.index('chown -R "$(id -u):$(id -g)" /out')
    copy_at = text.index('cp "$WORKDIR/out/result.tgz" "$RESULT"')
    assert chown_at < copy_at, "the chown runs after the copy it exists to enable"


def test_the_chown_happens_in_a_container_not_on_the_host():
    """A non-root host user cannot chown root-owned files, and the host may not be changed."""
    text = WRAPPER.read_text()
    block = text[text.index('if [[ -d "$WORKDIR/out" ]]; then'):]
    block = block[:block.index("cp \"$WORKDIR/out/result.tgz\"")]
    assert "docker run --rm" in block, (
        "the chown is attempted on the host, where it cannot work and must not be attempted")
    assert '-v "$WORKDIR/out:/out"' in block, "mounts something other than our own output directory"


def test_it_does_not_abort_the_run_when_the_chown_fails():
    """The copies may still succeed; failing here would discard a completed cell."""
    text = WRAPPER.read_text()
    block = text[text.index('if [[ -d "$WORKDIR/out" ]]; then'):]
    block = block[:block.index("cp \"$WORKDIR/out/result.tgz\"")]
    assert "||" in block and "warning" in block, (
        "a failed chown must warn and continue, not abort a cell that has already finished")
