"""The horizon a return is summed over, and the attribute the truncation seam reads to find it.

Episode return is a sum over an episode, so it is comparable only if every baseline sums over the
same horizon. Two things hold that, and neither was checked.

**The declared horizon must equal the one the environment is actually built with.**
`Protocol.horizon` says 500 and `robo_config.yaml`'s `task_def.horizon` says 500. If those ever
part, the protocol certifies a horizon no run uses — the shape of [C45], which is this project's
most expensive defect to date, and statically checkable here.

**The truncation seam must read the horizon, not restate it.** Three seams turn episode-end into a
bootstrap decision, all of the form

    done_bool = 0 if episode_step + 1 == env._max_episode_steps else float(done)

reading an *attribute*. A literal in that position would work until the horizon changed and then
fail silently, because a bootstrap that never fires looks exactly like a terminal that always
does.

**And the same attribute name means two different things across the clones.** In `alda` and
`dmc_gb` it is live and comes from the env. In `ctrl` it is assigned `10_000` — twice — against a
real horizon of 500, and never read ([C14](../docs/CONSTRUCTION.md#c14): *"Dead on this path;
wrong if ever read"*). If `ctrl` ever adopted the seam its DMC-lineage siblings use,
`episode_step + 1 == 10_000` would never fire at a 500-step horizon and every truncation would be
recorded as a real terminal — which is [C1](../docs/CONSTRUCTION.md#c1)'s defect, arrived at by
copying a line that looks correct.

This pins the mechanism. It takes no position on C1's 3/9 split, which is an open decision.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SEAMS = [
    "runnable/alda/dmcontrol_generalization_benchmark/src/train.py",
    "runnable/alda/trainers/alda_trainer.py",
    "runnable/dmc_gb/src/train.py",
]
ROBO_CONFIG = "RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml"


def code_lines(path: pathlib.Path):
    """(lineno, line) for lines that are actually code: no comments, no docstring bodies.

    Both exclusions were forced by false positives, and they are one failure in two dialects.
    A shell comment in `rlvigen.sh` restating "action_repeat=1" satisfied a textual search for
    the setting; a Python docstring in `ctrl/vec_env.py` listing `_max_episode_steps` as part of
    an interface satisfied a search for a *read* of it. **Prose documenting a mechanism is
    indistinguishable, to a text matcher, from the mechanism** -- and the better documented the
    file, the worse it is as a target.

    Handles the triple-double-quote form only, which is what every file here uses.
    """
    out, in_doc = [], False
    for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        s = line.strip()
        if in_doc:
            if '"""' in s:
                in_doc = False
            continue
        if s.startswith('"""'):
            if not (len(s) > 5 and s.endswith('"""')):
                in_doc = True
            continue
        if not s or s.startswith("#"):
            continue
        out.append((n, line))
    return out


def read(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} absent")
    return p.read_text(errors="replace")


def test_the_declared_horizon_matches_the_environment_config():
    """Same shape as C45, and unlike C45 this one can be caught without running anything."""
    from rlgen.protocol import DEFAULT_HORIZON, Protocol
    m = re.search(r"^\s*horizon:\s*(\d+)", read(ROBO_CONFIG), re.M)
    assert m, f"{ROBO_CONFIG} no longer declares a horizon"
    assert int(m.group(1)) == DEFAULT_HORIZON == Protocol().horizon == 500, (
        f"protocol says {DEFAULT_HORIZON}, robo_config says {m.group(1)}. A protocol certifying a "
        "horizon no run uses is the C45 failure, and every episode return is a sum over it.")


@pytest.mark.parametrize("rel", SEAMS, ids=lambda p: "/".join(p.split("/")[-2:]))
def test_the_seam_reads_the_horizon_rather_than_restating_it(rel):
    text = read(rel)
    seams = re.findall(r"done_bool\s*=\s*0\s*if\s*episode_step\s*\+\s*1\s*==\s*([^\s]+)", text)
    assert seams, f"{rel}: the truncation seam is gone or reshaped -- C1's split is measured here"
    for target in seams:
        assert not target.strip().isdigit(), (
            f"{rel}: the seam compares against the literal {target!r}. It must read the horizon "
            "from the env; a literal survives a horizon change and then never fires, which is "
            "indistinguishable from a terminal that always does.")
        assert "_max_episode_steps" in target, (
            f"{rel}: the seam now reads {target!r} rather than _max_episode_steps -- if the source "
            "of the horizon changed, C1's accounting changed with it.")


def test_ctrls_invented_horizon_is_still_never_read():
    """C14 is MONITORED on the grounds that the value is dead. This checks it stays dead."""
    reads = []
    for p in (ROOT / "runnable" / "ctrl").rglob("*.py"):
        for n, line in code_lines(p):
            if "_max_episode_steps" not in line:
                continue
            # An assignment is the declaration C14 tolerates; anything else is a read.
            if not re.search(r"_max_episode_steps\s*=", line):
                reads.append(f"{p.relative_to(ROOT)}:{n}: {line.strip()[:60]}")
    assert not reads, (
        f"ctrl now READS _max_episode_steps: {reads}. It is assigned 10_000 against a real horizon "
        "of 500, so any read is wrong by 20x, and C14's MONITORED status rested on it being dead.")


def test_ctrls_value_is_still_the_one_c14_describes():
    """If someone fixes it to 500 this test fails, and C14 should then be closed rather than left
    describing a value that no longer exists."""
    vals = set(re.findall(r"_max_episode_steps\s*=\s*(\d[\d_]*)", read("runnable/ctrl/vec_env.py")))
    assert vals == {"10_000"}, (
        f"ctrl's _max_episode_steps is now {vals}. If it was corrected to 500, close C14 and "
        "delete this test; if it changed to something else, C14 needs re-reading.")
