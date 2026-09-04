"""The citation content-checker must be right about cases whose answer is known in advance.

`scripts/check_citations.py --content` reports ~97 defects across the document set. That number
is worth nothing on its own: an instrument tuned until its output looks reasonable will always
produce a reasonable-looking number. So the verdicts are pinned here against planted citations
whose correct answer is fixed by construction — a citation to a line that says what it claims
MUST come back CONFIRMED, and one to a line that moved MUST come back DRIFT.

Both false directions are tested, because they cost differently and both were live during
development:

- a **false ABSENT** makes the checker cry wolf, and a checker that cries wolf stops being read.
  Four separate classes of it were found and fixed (see the script's docstring): citations
  reading each other as anchors, prose fragments captured between two code spans, path-shaped
  anchors tested inside the file they point away from, and the author's own notation
  (`Adam(lr=3e-4, B1=0.9)` with Greek letters) matched as if it were source.
- a **false CONFIRMED** is worse and quieter: it certifies a stale citation, which is the exact
  failure the instrument exists to catch.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_citations import (  # noqa: E402
    CITE, TIGHT, anchors_of, content_verdict, enclosing_symbols, mask_fences, usable_anchor,
)

SOURCE = '''"""A module docstring."""
import numpy as np


class DrQV2Adapter:
    def act(self, obs, step):
        a = self.policy(obs)
        return np.clip(a, -1.0, 1.0)


def helper(x):
    return x / 255.0
'''
# line 1 docstring, 2 import, 5 class, 6 def act, 7 a=, 8 return np.clip, 11 def helper, 12 /255


@pytest.fixture()
def src(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "agents.py"
    p.write_text(SOURCE)
    return p


def verdict(src, first, anchor, last=None):
    return content_verdict(src, first, last or first, anchor)[0]


class TestVerdictsAreCorrectWhereTheAnswerIsKnown:
    def test_exact_quote_at_the_right_line_is_confirmed(self, src):
        assert verdict(src, 8, "return np.clip(a, -1.0, 1.0)") == "CONFIRMED"

    def test_the_same_quote_at_the_wrong_line_is_drift_not_confirmed(self, src):
        """The whole point. Line 2 exists, so the existence check passes it; only content
        can tell that the citation no longer lands on what it claims."""
        assert verdict(src, 2, "return np.clip(a, -1.0, 1.0)") == "DRIFT"

    def test_a_quote_absent_from_the_file_is_absent(self, src):
        assert verdict(src, 8, "torch.nn.Linear(50, 1)") == "ABSENT"

    def test_a_qualified_symbol_is_checked_by_scope_not_by_text(self, src):
        """`DrQV2Adapter.act` appears nowhere as text; it names the scope line 8 sits in."""
        assert "DrQV2Adapter.act" not in SOURCE
        assert verdict(src, 8, "DrQV2Adapter.act") == "CONFIRMED"

    def test_scope_check_still_rejects_the_wrong_scope(self, src):
        """Guards the scope path against becoming a rubber stamp: line 12 is in `helper`."""
        assert verdict(src, 12, "DrQV2Adapter.act") in ("ABSENT", "DRIFT")

    def test_slack_allows_citing_a_def_for_a_line_in_its_body(self, src):
        assert verdict(src, 6, "return np.clip(a, -1.0, 1.0)") == "CONFIRMED"

    def test_slack_does_not_stretch_to_an_unrelated_line(self, src):
        assert verdict(src, 1, "return np.clip(a, -1.0, 1.0)") == "DRIFT"


class TestParaphraseIsNotSilentlyCountedAsEither:
    def test_identifier_level_agreement_is_reported_as_paraphrase(self, src):
        """Docs quote code as a sentence needs it. That is neither a pass nor a defect."""
        assert verdict(src, 8, "a = np.clip(policy(obs))") == "PARAPHRASE"

    def test_paraphrase_requires_the_identifiers_to_actually_be_there(self, src):
        assert verdict(src, 8, "b = torch.clamp(critic(state))") == "ABSENT"


class TestAnchorSelectionRejectsWhatIsNotAQuote:
    @pytest.mark.parametrize("span", [
        "), and ",                              # prose captured between two code spans
        ". As released, ",                      # ditto
        "rlgen/agents.py:218",                  # another citation
        "nets.py",                              # a filename: points away from the cited file
        "rlgen/envs.py::_assert_contract",      # a pointer elsewhere
        "Adam(lr=3e-4, β1=0.9)",           # the author's notation, not source
        "nn.Linear(2048, ·)",              # placeholder dot
        "abc",                                  # too short to identify anything
        "the quick brown fox",                  # plain prose
    ])
    def test_rejected(self, span):
        assert not usable_anchor(span), f"{span!r} would produce a false verdict"

    @pytest.mark.parametrize("span", [
        "return np.clip(a, -1.0, 1.0)",
        "action_repeat: 2",
        "global_frame = global_step * action_repeat",
        "DrQV2Adapter.act",
        "if self.consistency:",
    ])
    def test_accepted(self, span):
        assert usable_anchor(span)


class TestPairingAcrossTheDocument:
    def test_a_citation_does_not_read_its_own_span_as_its_anchor(self):
        line = "see `rlgen/agents.py:83` for this"
        m = CITE.search(line)
        assert all("agents.py" not in a for _, a in anchors_of(line, m))

    def test_an_anchor_on_the_previous_wrapped_line_is_found(self):
        """Prose here wraps at ~100 columns, so the anchor is routinely a line away."""
        text = ("configs set `action_repeat: 2`\n(`cfgs/svea_config.yaml:9`) and nothing "
                "overrides it")
        m = CITE.search(text)
        assert "action_repeat: 2" in [a for _, a in anchors_of(text, m)]

    def test_the_wrong_quote_in_the_same_sentence_does_not_decide_it(self):
        """The case that broke the first version: the nearest span after the citation was
        *our* value, while the cited file holds upstream's. Both must be offered."""
        text = ("upstream sets `action_repeat: 2` (`cfgs/svea_config.yaml:9`); we run "
                "`action_repeat=1`")
        m = CITE.search(text)
        got = [a for _, a in anchors_of(text, m)]
        assert "action_repeat: 2" in got and "action_repeat=1" in got

    def test_a_blank_line_ends_the_thought(self):
        text = "`x = compute(y)`\n\nunrelated paragraph citing `rlgen/agents.py:83` here"
        m = CITE.search(text)
        assert all("compute" not in a for _, a in anchors_of(text, m))

    def test_distances_come_back_sorted_so_tight_binding_is_knowable(self):
        text = "`return np.clip(a, -1.0, 1.0)` at `rlgen/agents.py:83`, unlike `helper(x)`"
        m = CITE.search(text)
        got = anchors_of(text, m)
        assert got == sorted(got, key=lambda t: t[0])
        assert got[0][0] <= TIGHT


class TestFenceMaskingKeepsOffsetsHonest:
    def test_masking_preserves_length_so_line_numbers_stay_right(self):
        text = "before\n```python\ncode = 1\n```\nafter `x.y` and `a.py:3`\n"
        assert len(mask_fences(text)) == len(text)
        assert mask_fences(text).count("\n") == text.count("\n")

    def test_fenced_content_cannot_be_used_as_an_anchor(self):
        text = "```\nsecret = 1\n```\nsee `rlgen/agents.py:83`"
        masked = mask_fences(text)
        assert "secret" not in masked


class TestScopeDetection:
    def test_finds_both_method_and_class(self, src):
        assert {"DrQV2Adapter", "act"} <= enclosing_symbols(SOURCE.splitlines(), 8)

    def test_module_level_line_has_no_enclosing_def(self, src):
        assert enclosing_symbols(SOURCE.splitlines(), 2) == set()

    def test_out_of_range_line_is_empty_not_an_error(self, src):
        assert enclosing_symbols(SOURCE.splitlines(), 9999) == set()


def test_the_checker_finds_the_defect_it_was_built_to_find(tmp_path):
    """End-to-end on the failure SYSTEM.md predicted: a reference re-cloned, lines shifted.

    Without this the suite could pass on primitives while the assembled tool reported nothing.
    """
    p = tmp_path / "mod.py"
    p.write_text(SOURCE)
    assert verdict(p, 8, "return np.clip(a, -1.0, 1.0)") == "CONFIRMED"
    # simulate an upstream re-clone that inserted 40 lines above the cited code
    p.write_text("\n" * 40 + SOURCE)
    assert verdict(p, 8, "return np.clip(a, -1.0, 1.0)") == "DRIFT", (
        "a citation whose target moved 40 lines must not still read as confirmed -- this is "
        "the exact silent failure the instrument exists to catch")

class TestTableCellsAreAnchorBoundaries:
    """A `|` between a citation and a code span means they are in different cells.

    Real defect, 2026-08-19: a per-baseline wiring table cites one file per row, and the span
    nearest row N's citation was row N+1's code. The checker anchored across the boundary and
    reported two correct citations as drifted. Scoped to table rows, so a shell pipe in prose is
    unaffected -- which the last test here pins.
    """

    def test_a_span_in_the_next_cell_is_not_an_anchor(self):
        line = ("| `ppg` | `runnable/ppg/ppo.py:91` — `logratio = newlogp - logp` | "
                "`logger.logkv` / its own module |")
        m = re.search(r"`runnable/ppg/ppo\.py:91`", line)
        anchors = [a for _, a in anchors_of(line, m)]
        assert "logger.logkv" not in anchors, (
            "an anchor from the next table cell describes a different claim")

    def test_a_span_in_the_same_cell_still_anchors(self):
        line = "| `ppg` | `runnable/ppg/ppo.py:91` — `logratio = newlogp - logp` | notes |"
        m = re.search(r"`runnable/ppg/ppo\.py:91`", line)
        assert "logratio = newlogp - logp" in [a for _, a in anchors_of(line, m)]

    def test_prose_containing_a_pipe_is_unaffected(self):
        """The rule must not fire outside tables, or a shell pipe silently kills real anchors."""
        line = "Run `grep x | head` and see `foo.py:12` which sets `alpha = 0.1` today."
        m = re.search(r"`foo\.py:12`", line)
        assert "alpha = 0.1" in [a for _, a in anchors_of(line, m)]
