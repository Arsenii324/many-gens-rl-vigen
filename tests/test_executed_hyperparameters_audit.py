"""The instrument that would have caught the beta bug must itself be non-vacuous.

`scripts/audit_executed_hyperparameters.py` compares what FAITHFULNESS claims against what the
launcher, the descriptor, or the clone's argparse default actually supplies.  It exists because
every other audit in this tree asks whether a MECHANISM is present, and none asked whether a
claimed VALUE reaches the process -- which is how ibac_sni ran at beta=1.0 for the project's whole
life while the table recorded 1e-4.
"""
import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _audit():
    spec = importlib.util.spec_from_file_location(
        "_hp_audit", ROOT / "scripts" / "audit_executed_hyperparameters.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_hp_audit"] = module
    spec.loader.exec_module(module)
    return module


def test_the_comparison_distinguishes_the_beta_case():
    """1.0 vs 1e-4 must not compare equal, or the whole audit is decorative."""
    audit = _audit()
    assert audit.same("1e-4", "1e-4")
    assert audit.same("0.0001", "1e-4")
    assert not audit.same("1.", "1e-4")
    assert not audit.same("1.0", "1e-4")


def test_it_reads_the_launcher_and_the_clone_default_separately():
    audit = _audit()
    flags = audit.launcher_flags("ibac_sni")
    assert flags.get("beta") == "1e-4", (
        "the ibac_sni launcher no longer passes --beta 1e-4; the clone default of 1.0 would apply"
    )
    assert audit.same(audit.argparse_default("ibac_sni", "beta"), "1.0"), (
        "the clone's --beta default changed; re-derive whether the explicit launcher value is "
        "still the right one instead of assuming this audit still guards the same thing"
    )


def test_faithfulness_claims_are_actually_being_parsed():
    """A parser that silently finds nothing would make every verdict vacuously clean."""
    audit = _audit()
    parsed = audit.claims()
    assert parsed, "no per-baseline claims were parsed out of FAITHFULNESS.md at all"
    assert ("vib_beta", "1e-4") in parsed.get("ibac_sni", []), (
        "the ibac_sni beta claim is no longer being read out of FAITHFULNESS.md"
    )


def test_the_tree_currently_honours_every_claim_it_can_locate():
    audit = _audit()
    assert audit.audit() == 0, (
        "a hyperparameter FAITHFULNESS claims is contradicted by the process; run "
        "scripts/audit_executed_hyperparameters.py for the offending rows"
    )


def test_hydra_style_overrides_are_read_from_the_launcher():
    """The RL-ViGen five are launched with `key=value`, not `--flag`, and that decides what runs.

    `runnable/_launch/rlvigen.sh:78` passes `action_repeat=1` over the config's 2, and line 61 calls
    that "this project's declared protocol". Parsing only `--flags` made this audit blind to every
    value those five actually run -- which is how a wrong correction got published, computed from
    the config default instead of the override (CORRECTIONS #35/#36).
    """
    audit = _audit()
    flags = audit.launcher_flags("drqv2")
    assert flags, "no launcher resolved for drqv2; the RL-ViGen five share runnable/_launch/rlvigen.sh"
    assert flags.get("action_repeat") == "1", (
        f"the launcher's hydra overrides are not being read: {sorted(flags)[:8]}"
    )


def test_launcher_overrides_take_precedence_over_the_config_file():
    """Hydra resolves a command-line override above the yaml; this audit must agree with hydra."""
    audit = _audit()
    source = (ROOT / "scripts" / "audit_executed_hyperparameters.py").read_text()
    launcher_at = source.index("def launcher_flags")
    config_at = source.index("def rlvigen_config_value")
    resolve_at = source.index("if seconds_per_episode is not None") if "if seconds_per_episode is not None" in source else len(source)
    # the resolution order in `audit()` must consult the launcher before the config file
    body = source[source.index("def audit("):]
    assert body.index("launcher_flags") < body.index("rlvigen_config_value"), (
        "the config file is consulted before the launcher, so an override would be invisible"
    )


def test_every_rlvigen_baseline_resolves_to_the_shared_launcher():
    audit = _audit()
    for baseline in ("drqv2", "svea", "drq", "sgqn", "curl"):
        assert audit.launcher_flags(baseline).get("action_repeat") == "1", (
            f"{baseline} does not resolve to rlvigen.sh; its executed values would be invisible"
        )


def test_sgqn_released_profile_is_traceable_from_hydra_config_to_loss():
    """The selected SGQN profile is the released code, not the retired adapter or Table 6.

    C64 was a documentation defect with a dangerous shape: all three value sets existed in the
    repository, so a plausible-looking claim could identify the wrong executable path.  Pin the
    composed Hydra config and the only non-configurable discrepancy (the loss literal) together.
    A paper profile, if ever explicitly requested, must create a different named configuration;
    it cannot make this test silently describe a new main run.
    """
    audit = _audit()
    assert audit.rlvigen_config_value("sgqn", "aux_lr") == ("1e-4", "sgqn_config.yaml aux_lr")
    assert audit.rlvigen_config_value("sgqn", "aux_beta") == ("0.99", "sgqn_config.yaml aux_beta")
    assert audit.rlvigen_config_value("sgqn", "sgqn_quantile") == ("0.93", "sgqn_config.yaml sgqn_quantile")

    launcher = (ROOT / "runnable" / "_launch" / "rlvigen.sh").read_text()
    assert 'CFG="${AGENT}_config"' in launcher and '--config-name "$CFG"' in launcher

    source = (ROOT / "RL-ViGen-upstream" / "algos" / "sgqn.py").read_text()
    assert re.search(r"critic_loss\s*\+=\s*0\.9\s*\*", source), (
        "SGQN's released-code consistency coefficient moved or became configurable; re-derive "
        "the profile label and source/paper qualification instead of carrying .9 by memory")


def test_nonproduction_claims_are_explicitly_classified_not_silently_dropped():
    audit = _audit()
    audit.EXCLUDED.clear()
    audit.claims()
    excluded = set(audit.EXCLUDED)
    expected = {
        ("alda", "num_steps", "2048"),
        ("ctrl", "ctrl_clusters", "32"),
        ("ctrl", "ctrl_window", "8"),
        ("ctrl", "ctrl_coef", "0.1"),
        ("ctrl", "nstep", "1"),
        ("ctrl", "nstep", "3"),
        ("ibac_sni", "sni_lambda", "0.5"),
        ("sgqn", "aux_update_freq", "2"),
    }
    assert expected <= excluded, (
        "historical/reference-only claims must be excluded with an auditable reason; otherwise "
        f"the gate confuses them with unresolved production claims: missing={expected - excluded}"
    )


def test_ppg_python_callable_defaults_are_reached():
    audit = _audit()
    assert audit.python_callable_default("ppg", "n_aux_epochs") == "6"
    assert audit.python_callable_default("ppg", "beta_clone") == "1.0"
