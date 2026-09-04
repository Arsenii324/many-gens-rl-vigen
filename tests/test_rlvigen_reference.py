"""The published numbers this project measures itself against must come from the file, not memory.

`scripts/rlvigen_reference.py` reads RL-ViGen's shipped `results/evaluation_score.xlsx`. Those
values are load-bearing three times over: C31 uses them as the ceiling, C32's claim that three of
twelve baselines are published as not learning rests on them, and C37's whole puzzle is the
distance between our `drqv2` and their **3.6** on door Easy.

Until now nothing checked any of it. `scripts/rlvigen_reference.py` was one of seven instruments
with no test at all (see `docs/SYSTEM.md`), which is the uncomfortable shape: the numbers we
compare ourselves against were read by code no one had verified reads correctly.

Two distinct jobs here, and they fail for different reasons:

- **the parser** is checked against a synthetic sheet whose correct answer is fixed by
  construction, including sheets shaped to break it;
- **the transcriptions in prose** are checked against the real file, which is the anti-drift
  check `rlvigen_reference.py`'s own docstring promises ("a number retyped into a document is a
  number that can drift from its source -- a failure this project has already caught three
  times") but did not enforce.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

openpyxl = pytest.importorskip("openpyxl")
from scripts.rlvigen_reference import XLSX, read  # noqa: E402

# The isolated candidate tree carries RL-ViGen slimmed to what robosuite Door needs -- 1,591 files
# lighter than the working copy, almost all of them meshes, textures and modules for robots and
# tasks Door never constructs. That slimming is load-bearing and proven: the base payload ships
# this vendored tree (robosuite is NOT pip-installed) and five RL-ViGen baselines have completed
# Door cells from it remotely. What it also removes is `results/evaluation_score.xlsx`, which no
# run reads and only these tests do. Absent asset, not absent evidence -- so skip rather than fail,
# because a red suite that means "this is the slim tree" trains the reader to ignore red.
pytestmark = pytest.mark.skipif(
    not XLSX.is_file(), reason=f"published reference workbook absent: {XLSX}")


def sheet(tmp_path, rows, name="Robosuite"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = name
    for r in rows:
        ws.append(list(r))
    p = tmp_path / "s.xlsx"
    wb.save(p)
    return p


@pytest.fixture()
def patched(monkeypatch):
    """Point `read` at a synthetic workbook."""
    def use(path):
        monkeypatch.setattr("scripts.rlvigen_reference.XLSX", path)
    return use


class TestParserOnKnownInput:
    def test_reads_labelled_rows_for_both_tasks(self, tmp_path, patched):
        patched(sheet(tmp_path, [
            ("DrQ-v2 (Easy)", None, None, None, None, None),
            ("door", 1.0, 2.0, 3.0, 4.0, 5.0),
            ("lift", 10.0, 20.0, 30.0, 40.0, 50.0),
        ]))
        got = read()
        assert got["door"] == [("DrQ-v2 (Easy)", [1.0, 2.0, 3.0, 4.0, 5.0])]
        assert got["lift"] == [("DrQ-v2 (Easy)", [10.0, 20.0, 30.0, 40.0, 50.0])]

    def test_label_comes_from_the_nearest_heading_above(self, tmp_path, patched):
        """Two blocks must not collapse onto one label -- that would silently merge methods."""
        patched(sheet(tmp_path, [
            ("SVEA (Easy)", None), ("door", 1.0),
            ("SGQN (Easy)", None), ("door", 400.0),
        ]))
        assert [lab for lab, _ in read()["door"]] == ["SVEA (Easy)", "SGQN (Easy)"]

    def test_rows_without_numbers_are_dropped_not_zero_filled(self, tmp_path, patched):
        """A blank row must not enter the mean as 0 and drag a published figure down."""
        patched(sheet(tmp_path, [("X (Easy)", None), ("door", None, None), ("lift", 5.0)]))
        got = read()
        assert "door" not in got
        assert got["lift"] == [("X (Easy)", [5.0])]

    def test_task_words_are_never_mistaken_for_a_label(self, tmp_path, patched):
        patched(sheet(tmp_path, [("door", 1.0), ("door", 2.0)]))
        assert all(lab == "" for lab, _ in read()["door"]), (
            "a data row was promoted to a heading; labels would shift by one block")

    def test_only_five_seed_columns_are_read(self, tmp_path, patched):
        """Columns past the fifth are not seeds; letting them in inflates n."""
        patched(sheet(tmp_path, [("M (Easy)", None), ("door", 1, 2, 3, 4, 5, 999, 888)]))
        assert read()["door"][0][1] == [1, 2, 3, 4, 5]


class TestTheRealFile:
    def test_the_workbook_is_present_and_parses(self):
        assert XLSX.exists(), f"{XLSX} is missing; C31's ceiling has no source"
        got = read()
        assert set(got) == {"door", "lift"}

    def test_shape_is_seven_methods_by_three_regimes(self):
        got = read()
        for task in ("door", "lift"):
            labels = [lab for lab, _ in got[task]]
            assert len(labels) == 21, f"{task}: expected 7 methods x 3 regimes, got {len(labels)}"
            assert all(len(v) == 5 for _, v in got[task]), "not every row has 5 seeds"

    def test_the_regimes_present_are_the_ones_documented(self):
        """Their sheet spells one of them 'Meidum'. Pinned as-is: silently correcting a typo in
        a source file is how a reader loses the ability to find the row again."""
        labels = " ".join(lab for lab, _ in read()["door"])
        assert "Meidum" in labels, "the sheet's own spelling changed; check the file, not this test"
        for regime in ("Easy", "Hard"):
            assert f"({regime})" in labels


class TestProseAgreesWithTheFile:
    """The check the module's docstring promises. These are the figures quoted in the register."""

    def value(self, task, label):
        for lab, vals in read()[task]:
            if lab == label:
                return sum(vals) / len(vals)
        raise AssertionError(f"{label!r} not found for {task}")

    def test_drqv2_door_easy_is_the_3_6_that_c37_is_built_on(self):
        assert round(self.value("door", "DrQ-v2 (Easy)"), 1) == 3.6

    def test_the_register_still_quotes_that_number(self):
        doc = (ROOT / "docs" / "CONSTRUCTION.md").read_text(errors="replace")
        assert re.search(r"`?DrQ-v2`?[^\n]{0,80}\b3\.6\b|\b3\.6\b[^\n]{0,80}DrQ-v2", doc), (
            "C37 no longer quotes 3.6 for DrQ-v2 door Easy. If the source changed, this test "
            "should have failed first; if the prose changed, say why in the register")

    @pytest.mark.parametrize("label,lo,hi", [
        ("SVEA (Easy)", 260, 275), ("SGQN (Easy)", 385, 396), ("PIEG (Easy)", 382, 392),
    ])
    def test_the_methods_that_do_learn_are_two_orders_above_drqv2(self, label, lo, hi):
        """C37's reframing depends on DrQ-v2 being an outlier inside their own table, not a
        typical result. If these move, that argument needs re-reading."""
        assert lo <= self.value("door", label) <= hi

    def test_published_drqv2_sits_at_our_measured_random_floor(self):
        """The basis for C32: 'published as not learning' is a comparison to a floor we measured
        ourselves (probe_floor, door mean 1.63), not an impression."""
        from scripts.rlvigen_reference import OUR_RANDOM
        floor_mean, floor_max = OUR_RANDOM["door"]
        assert floor_mean < self.value("door", "DrQ-v2 (Easy)") < floor_max, (
            "published DrQ-v2 is no longer between the random floor's mean and its best episode; "
            "C32's wording depends on that")
