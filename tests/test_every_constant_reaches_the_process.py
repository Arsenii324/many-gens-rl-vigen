"""A constant in `families.json` must reach the process, or be a verified provenance record.

`constants` are only emitted as argv where an `options`/`positional` template references them by
`{name}`. Nothing checked that, so a constant could be declared, recorded in the decision sheet,
carried into the production schedule and the payload manifest -- and never passed.

It happened, on 2026-09-08, to a change made that same day: A43 set `ibac_sni.lr = 0.0005` to move
the port off `torch_rl`'s MiniGrid-tuned `7e-4`, and `--lr` was not in the options template, so the
run would have used 7e-4 while every artifact said 5e-4. Found by asking the launcher what it
actually emits rather than reading the config.

Six others were unreferenced and are NOT defects: `ctrl`'s `num_clusters`, `n_att_heads`,
`embedding_type`, `lr`, `lr_ctrl` and `max_grad_norm` all equal the released code's own
`absl.flags` defaults, so they document what the run uses rather than override it. That claim is
not taken on trust here -- it is checked against `train_ppo.py`.

The distinction matters because the two look identical in the config: an unreferenced constant that
matches the default is documentation, and one that does not is a silent lie.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAMILIES = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())

#: Constants deliberately not passed, each because it equals the clone's own default. The value is
#: the source the default is read from, so the exemption is verified rather than asserted.
RECORDED_NOT_PASSED = {
    ("ctrl", "num_clusters"): "runnable/ctrl/train_ppo.py",
    ("ctrl", "n_att_heads"): "runnable/ctrl/train_ppo.py",
    ("ctrl", "embedding_type"): "runnable/ctrl/train_ppo.py",
    ("ctrl", "lr"): "runnable/ctrl/train_ppo.py",
    ("ctrl", "lr_ctrl"): "runnable/ctrl/train_ppo.py",
    ("ctrl", "max_grad_norm"): "runnable/ctrl/train_ppo.py",
}


def _unreferenced() -> set[tuple[str, str]]:
    out = set()
    for family, entry in FAMILIES.items():
        if not isinstance(entry, dict) or "constants" not in entry:
            continue
        template = json.dumps(entry.get("options", [])) + json.dumps(entry.get("positional", []))
        for name in entry["constants"]:
            if "{" + name + "}" not in template:
                out.add((family, name))
    return out


def test_no_constant_silently_fails_to_reach_the_process():
    unexpected = sorted(_unreferenced() - set(RECORDED_NOT_PASSED))
    assert not unexpected, (
        "these constants are declared but no options/positional template references them, so the "
        "value never reaches the process while every artifact reports it: "
        f"{unexpected}. Either add the flag, or add it to RECORDED_NOT_PASSED with the source "
        "showing it equals the clone's own default.")


def test_the_exemptions_really_do_equal_the_clones_defaults():
    """An exemption that is not checked is just a longer way of not checking."""
    for (family, name), source in sorted(RECORDED_NOT_PASSED.items()):
        text = (ROOT / source).read_text()
        match = re.search(r"flags\.DEFINE_\w+\(\s*['\"]" + re.escape(name) + r"['\"]\s*,\s*([^,]+),",
                          text)
        assert match, f"{source} defines no flag named {name}; the exemption cannot be verified"
        default = match.group(1).strip().strip("'\"")
        declared = str(FAMILIES[family]["constants"][name])
        try:
            same = abs(float(default) - float(declared)) < 1e-12
        except ValueError:
            same = default == declared
        assert same, (
            f"{family}.{name} is exempted from being passed on the grounds that it matches "
            f"{source}'s default, but the default is {default!r} and the config says {declared!r}. "
            "It is therefore an override that never happens.")


def test_the_ibac_sni_learning_rate_is_passed():
    """The specific regression: A43's value must appear in the emitted argv."""
    template = json.dumps(FAMILIES["ibac_sni"].get("options", []))
    assert "{lr}" in template, (
        "ibac_sni declares `lr` and does not pass it, so the run uses torch_rl's 7e-4 MiniGrid "
        "default while A43, the decision sheet and the production schedule all say 5e-4")
