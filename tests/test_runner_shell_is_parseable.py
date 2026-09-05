"""`run_probe.sh` must parse as shell, and its embedded Python must parse as Python.

Caught live 2026-09-05: I added a comment containing the word `run's` inside a
`python3 -c '...'` block. The apostrophe CLOSED the single-quoted shell string, so every following
Python line became shell. Nothing in the suite would have noticed; the runner would have failed on
the remote host, on every family, after provisioning -- and the error would have pointed at a
Python line, not at the comment three lines above that actually broke it.

`bash -n` catches the quoting. It cannot see inside the quoted blocks, so the Python is extracted
and parsed separately. The extraction deliberately ends each block at the first standalone quote,
which means a stray apostrophe shows up here as a Python SyntaxError -- the same defect caught twice
by two different mechanisms, which is what you want for a file every remote job depends on.
"""
import ast
import pathlib
import re
import subprocess

import pytest

RUNNER = pathlib.Path(__file__).resolve().parents[1] / "datasphere" / "native" / "run_probe.sh"


def test_the_runner_parses_as_shell():
    done = subprocess.run(["bash", "-n", str(RUNNER)], capture_output=True, text=True)
    assert done.returncode == 0, f"run_probe.sh is not valid shell:\n{done.stderr}"


def _quoted_c_blocks():
    """`python3 -c '...'` -- the apostrophe-sensitive form, and the one that broke."""
    return re.findall(r"python3 -c '(.*?)'\s", RUNNER.read_text(), flags=re.DOTALL)


def _heredoc_blocks():
    """`python3 - <<'PY' ... PY` -- quoted heredocs, safe from apostrophes but still Python."""
    return re.findall(r"python3 - <<'(\w+)'[^\n]*\n(.*?)\n\1\b", RUNNER.read_text(), flags=re.DOTALL)


def _all_blocks():
    return _quoted_c_blocks() + [body for _, body in _heredoc_blocks()]


def test_extraction_still_finds_the_blocks():
    """Guards the test itself: a changed invocation style must not silently check nothing.

    This assertion has already earned its place -- the first version of this file matched only the
    `-c` form and quietly checked one block out of six.
    """
    assert len(_quoted_c_blocks()) >= 1, "the -c form vanished; update the pattern"
    assert len(_heredoc_blocks()) >= 4, "the heredoc form vanished; update the pattern"


def test_each_embedded_python_block_parses():
    for index, block in enumerate(_all_blocks()):
        try:
            ast.parse(block)
        except SyntaxError as exc:
            head = "\n".join(block.splitlines()[:3])
            pytest.fail(f"embedded python block {index} does not parse ({exc});\n"
                        f"a stray apostrophe in a comment is the usual cause.\nStarts:\n{head}")


def test_no_apostrophe_inside_a_single_quoted_block():
    """The specific trap, scoped to the form where it bites, so a future reader need not rediscover it."""
    for index, block in enumerate(_quoted_c_blocks()):
        assert "'" not in block, (
            f"-c block {index} contains an apostrophe, which closes the shell string and turns "
            f"every following Python line into shell")


def test_no_condition_tests_emptiness_of_an_already_defaulted_variable():
    """CORRECTIONS #45: a guard that could never fire, and two checks that passed on it.

    `run_probe.sh` defaults `NATIVE_HOST_PROFILE` near the top. A production guard several hundred
    lines later tested `-z "${NATIVE_HOST_PROFILE:-}"` -- unsatisfiable, so the refusal protecting
    the entire T4->V100 migration was dead code. Whether the CALLER supplied a value must be
    captured before the default is applied.
    """
    text = RUNNER.read_text()
    defaulted = sorted(set(re.findall(
        r'^\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)="\$\{\1:-[^}]*\}"', text, flags=re.MULTILINE)))
    assert defaulted, "the extraction found no defaulted variables; the pattern is stale"
    dead = []
    for var in defaulted:
        for pattern in (r'-z\s+"\$\{' + re.escape(var) + r'(:-)?\}?"',
                        r'-z\s+"\$' + re.escape(var) + r'"'):
            for found in re.finditer(pattern, text):
                dead.append(f"{var} at line {text[:found.start()].count(chr(10)) + 1}")
    assert not dead, (
        "these conditions can never be true, because the variable is defaulted earlier: "
        + "; ".join(dead) + ". Capture whether the caller set it, before the default runs.")
