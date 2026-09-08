"""The wheel cache must be on when a mount exists and off when it does not.

[Claude 2026-09-08] Written after a live cell was still in `pip` 51 minutes in, nowhere near the
GPU.
`--no-cache-dir` was added deliberately -- an in-container cache costs 3.0 GB in a layer that
`docker run --rm` throws away -- but that reasoning silently assumed the layer was the only place a
cache could live, so the alternative it was really choosing was re-downloading ~2.5 GB of torch CUDA
wheels at 162-835 kB/s on a shared uplink, once per cell, forever.

The failure this file guards is the places365 one repeated: forwarding an env var that promises a
path the container does not have. `NATIVE_PIP_CACHE=1` without the `-v` would make run_probe.sh
drop `--no-cache-dir` and write 3.0 GB into the writable layer of a host that is 99% full -- the
exact cost the flag existed to avoid, now paid with none of the benefit. So the mount and the flag
are required to be established together, and the branch is EXECUTED rather than pattern-matched:
a conditional can read correctly and still resolve the wrong way under `set -u` on bash 3.2.
"""
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"
HOST = ROOT / "datasphere" / "native" / "run_on_production_host.sh"


def _branch_source() -> str:
    """The real bytes of the decision, lifted out of run_probe.sh."""
    text = PROBE.read_text()
    start = text.index("PIP_CACHE_FLAGS=(--no-cache-dir)")
    end = text.index("python3 -m pip install ${PIP_CACHE_FLAGS", start)
    return text[start:end]


def _resolve(pip_cache_env: str, writable: bool, tmp_path) -> str:
    """Run the actual branch and report the flags it produces."""
    fake_root = tmp_path / "root"
    (fake_root / ".cache").mkdir(parents=True)
    if not writable:
        # A cache directory that exists but cannot be written is the interesting case: the branch
        # must fall BACK, not proceed as though the mount were there.
        (fake_root / ".cache" / "pip").mkdir()
        (fake_root / ".cache" / "pip").chmod(0o500)
    body = _branch_source().replace("/root/.cache/pip", f"{fake_root}/.cache/pip")
    script = f"set -u\nexport NATIVE_PIP_CACHE={pip_cache_env}\n{body}\n" \
             'printf "FLAGS[%s]\\n" "${PIP_CACHE_FLAGS[*]-}"\n'
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_without_the_mount_the_flag_stays(tmp_path):
    out = _resolve("0", writable=True, tmp_path=tmp_path)
    assert "FLAGS[--no-cache-dir]" in out, out
    assert "NATIVE_PIP_CACHE_DISCIPLINE off" in out, out


def test_with_the_mount_the_cache_dir_is_passed_explicitly(tmp_path):
    """Dropping --no-cache-dir is NOT enough: pip in this image has caching disabled outright.

    [Claude 2026-09-09] Two full installs ran with the mount in place and left the host cache at
    4.0K while the discipline line printed "wheels persist across cells". `pip cache dir` in the
    image says "cache is disabled"; passing --cache-dir explicitly overrides it.
    """
    out = _resolve("1", writable=True, tmp_path=tmp_path)
    assert "--cache-dir" in out, (
        "only the absence of --no-cache-dir, which this image ignores: " + out)
    assert "FLAGS[]" not in out, out
    assert "NATIVE_PIP_CACHE_DISCIPLINE on" in out, out


def test_requested_but_unwritable_falls_back_loudly(tmp_path):
    out = _resolve("1", writable=False, tmp_path=tmp_path)
    assert "FLAGS[--no-cache-dir]" in out, out
    assert "REQUESTED but" in out, out


def test_the_env_var_is_only_set_where_the_mount_is_established():
    """The places365 defect: an env var promising a path no mount provides."""
    text = HOST.read_text()
    guard = text.index('if [[ -n "${NATIVE_PIP_CACHE_HOST:-}" ]]; then')
    end = text.index("\nfi\n", guard)
    block = text[guard:end]
    assert 'NATIVE_PIP_CACHE=1' in block, "the flag is set outside the block that mounts the cache"
    assert 'PIP_CACHE_ARGS=(-v ' in block
    assert text.count('NATIVE_PIP_CACHE=1') == 1, "set in more than one place"


def test_the_mount_is_actually_passed_to_docker():
    """PIP_CACHE_ARGS existing is not the same as docker receiving it."""
    text = HOST.read_text()
    mounts = text[text.index("DOCKER_MOUNT_ARGS=(-v"):]
    mounts = mounts[:mounts.index(")\n")]
    assert 'PIP_CACHE_ARGS[@]' in mounts, mounts


def test_a_cache_outside_home_is_refused():
    text = HOST.read_text()
    guard = text.index('if [[ -n "${NATIVE_PIP_CACHE_HOST:-}" ]]; then')
    block = text[guard:text.index("\nfi\n", guard)]
    assert re.search(r'"\$HOME"/\*\)', block), "no $HOME containment check"
    assert "exit 2" in block
