"""A mounted environment that cannot be verified must stop the cell, never fall back to pip.

[Claude 2026-09-08] The prebuilt-venv path exists because `pip` costs over two hours per cell and
`apt` costs 71 seconds -- the environment and the run are different lifecycles
(notes/production-host/19-environment-lifecycle-vs-run-lifecycle.md).

The dangerous failure is not a crash. It is a FALLBACK. If a broken mount, a stale image or a
mismatched requirement set quietly sent the cell back to `pip install`, the run would still succeed,
still produce a record, and still be reported as clean -- while silently costing two hours and,
worse, executing an environment nobody verified. The symptom would be the bandwidth bill.

So every branch below must exit non-zero, and none may reach the pip path. The branch is EXECUTED
out of run_probe.sh rather than pattern-matched: a refusal that reads correctly and resolves the
wrong way under `set -u` is exactly what this project keeps finding.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"

HEAD = 'NATIVE_VENV_DISCIPLINE="off: this cell builds its own environment with pip"'
TAIL = 'echo "NATIVE_VENV_DISCIPLINE $NATIVE_VENV_DISCIPLINE"'


def _branch() -> str:
    text = PROBE.read_text()
    assert HEAD in text, "the prebuilt-venv branch is gone from run_probe.sh"
    assert TAIL in text
    return text[text.index(HEAD):text.index(TAIL) + len(TAIL)]


def _venv(tmp_path, *, manifest: dict | None, interpreter: bool = True) -> pathlib.Path:
    d = tmp_path / "env"
    (d / "bin").mkdir(parents=True)
    if interpreter:
        # ABSOLUTE path on purpose. Activation puts this directory first on PATH, so a shim that
        # called bare `python3` would exec itself forever -- which is what happened the first time.
        shim = d / "bin" / "python3"
        shim.write_text(f"#!/bin/sh\nexec {sys.executable} \"$@\"\n")
        shim.chmod(0o755)
    if manifest is not None:
        (d / "ENVIRONMENT.json").write_text(json.dumps(manifest))
    return d


def _run(tmp_path, venv: pathlib.Path | None, digest: str | None, want_reqs="alpha\nbeta"):
    """Execute the real branch with a stubbed family.py and a Linux-style sha256sum."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    # The container has GNU coreutils; macOS does not. Supply what run_probe.sh legitimately expects.
    sha = bindir / "sha256sum"
    sha.write_text("#!/bin/sh\nexec shasum -a 256 \"$@\"\n")
    sha.chmod(0o755)
    tool = tmp_path / "family_stub.py"
    tool.write_text("import sys\nprint('''%s''')\n" % want_reqs)

    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    script = ["set -u", f'cells=idaac:1', f'FAMILY_TOOL={tool}']
    if venv is not None:
        script.append(f'export NATIVE_VENV={venv}')
    if digest is not None:
        script.append(f'export NATIVE_IMAGE_DIGEST={digest}')
    script.append(_branch())
    script.append('echo "REACHED_PIP_PATH"')     # stands in for the bootstrap that follows
    return subprocess.run(["bash", "-c", "\n".join(script)],
                          capture_output=True, text=True, timeout=120, env=env,
                          cwd=str(tmp_path))


def _reqhash(text="alpha\nbeta") -> str:
    import hashlib
    return hashlib.sha256(("\n".join(sorted(text.splitlines())) + "\n").encode()).hexdigest()[:8]


@pytest.mark.parametrize("case", ["no-manifest", "no-interpreter", "no-digest", "wrong-image",
                                  "wrong-requirements"])
def test_every_unverifiable_environment_refuses_and_never_reaches_pip(tmp_path, case):
    good = {"base_image": "nvidia/cuda@sha256:94c1577b2cd9dd6c0312dc04",
            "requirements_sha256_8": _reqhash()}
    digest = "94c1577b2cd9"
    if case == "no-manifest":
        venv, out = _venv(tmp_path, manifest=None), None
        out = _run(tmp_path, venv, digest)
    elif case == "no-interpreter":
        out = _run(tmp_path, _venv(tmp_path, manifest=good, interpreter=False), digest)
    elif case == "no-digest":
        out = _run(tmp_path, _venv(tmp_path, manifest=good), None)
    elif case == "wrong-image":
        out = _run(tmp_path, _venv(tmp_path, manifest=good), "deadbeefdead")
    else:
        bad = dict(good, requirements_sha256_8="00000000")
        out = _run(tmp_path, _venv(tmp_path, manifest=bad), digest)

    both = out.stdout + out.stderr
    assert out.returncode == 3, f"{case}: expected refusal, got {out.returncode}\n{both}"
    assert "REACHED_PIP_PATH" not in out.stdout, (
        f"{case}: FELL BACK TO PIP. A silent fallback costs two hours and executes an environment "
        f"nobody verified.\n{both}")


def test_a_verified_environment_activates_and_skips_pip(tmp_path):
    good = {"base_image": "nvidia/cuda@sha256:94c1577b2cd9dd6c0312dc04",
            "requirements_sha256_8": _reqhash()}
    venv = _venv(tmp_path, manifest=good)
    out = _run(tmp_path, venv, "94c1577b2cd9")
    both = out.stdout + out.stderr
    assert out.returncode == 0, both
    assert "NATIVE_VENV_DISCIPLINE on:" in both, both
    assert "pip is not run" in both, both


def test_without_a_venv_nothing_changes(tmp_path):
    """The whole mechanism must be inert when unused, or it breaks every existing caller."""
    out = _run(tmp_path, None, None)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "REACHED_PIP_PATH" in out.stdout
    assert "NATIVE_VENV_DISCIPLINE off:" in out.stdout


def test_the_pip_bootstrap_is_actually_inside_the_guard():
    """The branch printing 'on' means nothing if pip runs regardless."""
    text = PROBE.read_text()
    guard = text.index('if [[ -z "${NATIVE_VENV:-}" ]]; then\npython3 -m pip install --upgrade pip')
    close = text.index("fi   # end: skip the whole pip bootstrap when NATIVE_VENV supplied one")
    body = text[guard:close]
    assert "-r /tmp/requirements-for-this-job.txt" in body, (
        "the requirement install is outside the guard, so a prebuilt venv would be ignored")


def test_the_host_mounts_it_read_only():
    """Read-only is the mechanism, not caution: it is what freezes the environment by construction."""
    host = (ROOT / "datasphere" / "native" / "run_on_production_host.sh").read_text()
    assert '-v "${NATIVE_VENV_HOST}:/opt/rlvigen-env:ro"' in host, (
        "a writable environment mount is not frozen, and gate_environment_manifest stays OWNER")
    assert 'NATIVE_IMAGE_DIGEST=' in host
