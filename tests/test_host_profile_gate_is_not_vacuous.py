"""The production-host gate must FAIL when the refusal it certifies is absent.

Every instrument this project has audited was found wrong, three of them written to enforce the
rule they then broke. A gate whose PASS does not depend on the thing it claims is worse than no
gate, because it is quoted. So this drives the gate's own predicate over a runner with the guard
removed and requires a FAIL.

Also pins the alignment of the two host_profile stamps: `effective_config.json` and the record must
report the same default, or one run yields two artifacts disagreeing about the machine it ran on.
"""
import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"


def _gates():
    spec = importlib.util.spec_from_file_location("_pg", ROOT / "scripts" / "production_gates.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_pg"] = m
    spec.loader.exec_module(m)
    return m


def test_the_gate_passes_on_the_real_runner():
    verdict, _ = _gates().gate_production_names_its_host()
    assert verdict == _gates().PASS


def test_the_gate_would_fail_without_the_guard(monkeypatch):
    """Remove the refusal from what the gate reads; the gate must notice."""
    gates = _gates()
    stripped = re.sub(r'if \[\[ "\$\{FRAMES:-10000\}" -ge 600000.*?\n  fi\n', "",
                      RUNNER.read_text(), flags=re.DOTALL)
    assert "-ge 600000" not in stripped, "the fixture failed to remove the guard; test is inert"
    monkeypatch.setattr(gates, "_read", lambda path: stripped)
    verdict, reason = gates.gate_production_names_its_host()
    assert verdict == gates.FAIL and "inherit" in reason


def test_the_guard_triggers_at_production_scale_only():
    text = RUNNER.read_text()
    assert "-ge 600000" in text, "600000 is the protocol budget; a probe at 10000 must not be blocked"


def test_both_host_profile_stamps_share_one_default():
    stamps = re.findall(r'"host_profile":\s*os\.environ\.get\((.*?)\)', RUNNER.read_text())
    assert len(stamps) >= 2, "expected the effective-config and record stamps"
    assert len(set(stamps)) == 1, (
        f"the host_profile stamps disagree: {stamps}. One run would produce two artifacts naming "
        f"different machines, and a reader could not tell that from a real profile change")
