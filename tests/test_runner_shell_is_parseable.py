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


# --- the same guarantees, for every shell script in datasphere/native/ ---------------------------
# [Claude 2026-09-08] `test_no_apostrophe_inside_a_single_quoted_block` above already encoded this
# trap -- and did not catch it twice on 2026-09-08, because it was scoped to run_probe.sh alone
# while the apostrophes went into `build-env.sh`. Once in `${PAYLOAD:?...the payload's own tree}`,
# where an apostrophe is a quote even inside DOUBLE quotes; once in a comment inside a `bash -c '`
# block, where a comment is not a comment because the outer shell has not tokenised it yet.
#
# A guard that names the right defect and looks in one file is not a guard for the codebase. These
# widen it to every script, so a new one is covered the day it is written rather than the day it
# breaks.
#
# `bash -n` is the load-bearing one: BOTH 2026-09-08 apostrophes were outright syntax errors, so a
# per-script parse catches them without needing to reason about where quotes open and close. A
# first attempt here also tried to extract every `-c` block across all scripts and count quotes;
# it failed on four scripts that `bash -n` accepts, because that extraction cannot tell a
# deliberate close-reopen toggle from a stray quote. The naive version was deleted rather than
# tuned -- a lint that cries wolf on correct code gets suppressed, and then it guards nothing.

NATIVE_DIR = pathlib.Path(__file__).resolve().parents[1] / "datasphere" / "native"
SHELL_SCRIPTS = sorted(NATIVE_DIR.glob("*.sh"))


def test_there_are_shell_scripts_to_check():
    """A glob that silently matches nothing passes every test below."""
    assert len(SHELL_SCRIPTS) >= 4, [p.name for p in SHELL_SCRIPTS]


@pytest.mark.parametrize("script", SHELL_SCRIPTS, ids=lambda p: p.name)
def test_every_native_shell_script_parses(script):
    done = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert done.returncode == 0, f"{script.name} is not valid shell:\n{done.stderr}"


@pytest.mark.parametrize("script", SHELL_SCRIPTS, ids=lambda p: p.name)
def test_no_apostrophe_inside_a_parameter_expansion_message(script):
    """`${VAR:?the payload's own tree}` is a syntax error even inside double quotes.

    Bash tokenises the expansion body before quote removal, so the apostrophe is a quote character
    there regardless of the surrounding double quotes. This one cost a whole file parse.
    """
    import re
    for match in re.finditer(r"\$\{[A-Za-z_][A-Za-z0-9_]*:[?=-]([^}]*)\}", script.read_text()):
        assert "'" not in match.group(1), (
            f"{script.name}: apostrophe inside ${{VAR:?...}} message {match.group(1)!r} -- this is "
            f"a syntax error even within double quotes")
