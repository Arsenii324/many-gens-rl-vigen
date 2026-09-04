# Original-implementation locations

A lookup table, not an analysis. For each of the 12 baselines: where the original-authors' own
code actually sits on this disk, verified by `git remote -v` where a `.git` exists (not assumed
from a folder name), plus any continuous-action port sitting alongside it. `FAITHFULNESS.md` has
the per-algorithm hyperparameter/divergence analysis; this file answers "where is the ground
truth, and is it discrete or continuous" — and, since 2026-08-16, a related but separate question:
"what does that ground truth actually come WITH" — a train loop, an eval loop, both, or (for two
baselines, checked directly, not assumed) neither.

**Original-authors-fidelity is yes/no, not a spectrum.** Yes means: this is the paper's own
authors' own released code, unmodified, with a verifiable origin. A port, a fork with edits, or a
third party's reimplementation is fidelity = NO regardless of how faithful it tries to be, and is
listed separately.

Checked 2026-08-14. Paths are relative to `/Users/a2mogus/build-projs/ccm-intro/` unless stated.

**Commit-level provenance, added 2026-08-14** (`porting-directive.md` §3: identity alone isn't
enough — behavior is settled by the diff, not the remote). None of the 10 checkable clones have a
git tag at all (`git describe --tags` fails on every one — checked directly, not assumed), so
"the commit the paper's results correspond to" cannot be confirmed by tag proximity for any of
them. What follows per baseline is the actual `HEAD` commit and date, plus a coarse drift read from
the gap between that date and the paper's own publication date — not a substitute for reading each
paper's own stated commit/release note, which was not done this pass.

---

## The DrQ-v2 family

### `drqv2` — Yarats et al., ICLR 2022, arXiv:2107.09645
- **Original, fidelity YES, continuous (DMC)**:
  `projects/many-gens-rl-vigen/ext/drqv2` — origin `facebookresearch/drqv2.git`, verified.
  `HEAD c0c650b`, 2022-03-21 — ~1 month after ICLR 2022 acceptance (~late Jan 2022). No tag. Low
  drift risk on date grounds; not diffed against a paper-stated commit (none found stated).
- Also present, fidelity NO (RL-ViGen's own copy, executed unmodified at runtime by this repo,
  not diffed against the line above): `projects/many-gens-rl-vigen/RL-ViGen-upstream/algos/drqv2.py`
  — carries the original Facebook copyright header but has not been independently diffed against
  the `ext/drqv2` clone above; treat as "probably identical, not confirmed."

### `svea` — Hansen et al., NeurIPS 2021, arXiv:2107.00644
- **Original, fidelity YES, continuous (DMC)**:
  `projects/many-gens-rl-vigen/ext/dmcontrol-generalization-benchmark/src/algorithms/svea.py` —
  origin `nicklashansen/dmcontrol-generalization-benchmark.git`, verified. Hansen is SVEA's own
  lead author, so this is the genuine original despite living inside a multi-method benchmark repo
  rather than a repo named `svea`.
  `HEAD ff9c0aa`, **2024-01-03 — ~2 years 2 months after NeurIPS 2021 (~Dec 2021).** Real drift risk:
  this is a living multi-method benchmark repo, not a paper-release snapshot, and the same clone is
  cited below for `soda` too. Not diffed against a paper-stated commit.
- Also present, fidelity NO: `RL-ViGen-upstream/algos/svea.py` (RL-ViGen's own DrQ-v2-based port —
  registry.py's own note: "Original SVEA is DrQ-based; this is the DrQ-v2 port RL-ViGen ships").

### `sgqn` — Bertoin et al., NeurIPS 2022, arXiv:2209.09203
- **Original, fidelity YES, continuous (DMC)**:
  `projects/many-gens-rl-vigen/ext/SGQN/DMC/` — origin `SuReLI/SGQN.git`, verified. (The repo also
  ships a `robot_env/` variant; DMC is the one this project's own `svea`-backbone entry compares
  against.)
  `HEAD f383fc0`, **2024-06-30 — ~1 year 8 months after NeurIPS 2022 (~Nov 2022).** Real drift risk,
  same shape of concern as `svea`/`soda`'s repo above. Not diffed against a paper-stated commit.
  Backbone SGQN's own paper builds on (DrQ-v2-style vs. something else) not confirmed this pass —
  needed before the classification below can be upgraded past "unconfirmed."

### `curl` — Laskin, Srinivas, Abbeel, ICML 2020, arXiv:2004.04136
- **Original, fidelity YES, continuous (DMC)**:
  `projects/many-gens-rl-vigen/ext/curl` — origin `MishaLaskin/curl.git`, verified. Confirmed
  continuous directly: `train.py` imports `dmc2gym` and calls `dmc2gym.make(...)`.
  `HEAD 8416d6e`, 2020-10-28 — ~3-4 months after ICML 2020 (~July 2020). Moderate drift risk. Not
  diffed against a paper-stated commit.

---

## The SAC family

### `drq` — Yarats/Kostrikov/Fergus, ICLR 2021, arXiv:2004.13649
- **Original, fidelity YES, continuous (DMC)**:
  `projects/many-gens-rl-vigen/ext/drq` — origin `denisyarats/drq.git`, verified. Confirmed
  continuous: `train.py` imports `dmc2gym`, builds a `dm_control` environment.
  `HEAD dd040f1`, 2021-11-18 — ~10 months after ICLR 2021 acceptance (~Jan 2021). Moderate drift
  risk. Not diffed against a paper-stated commit.

### `rad` — Laskin et al., NeurIPS 2020, arXiv:2004.14990
- **Original, fidelity YES, continuous (DMC) — CLONED 2026-08-16, closing the one gap in this
  file.** `projects/many-gens-rl-vigen/ext/rad` — origin `MishaLaskin/rad.git`, verified.
  `HEAD 18d079e`, 2021-03-28 — ~4 months after NeurIPS 2020 (~Dec 2020). No tag. Ships
  `data_augs.py`, `curl_sac.py`, `train.py`, `utils.py`.
  **There was never a reason for its absence** — it clones in seconds; the earlier "only paper
  resources exist" state below was an unexamined gap, not a constraint, and it survived three
  separate passes over this file because each one re-read the note instead of testing it.
  **The augmentation-parameter diff, open since 2026-08-14 as "cheap to close, not yet done", is
  now closed from primary source**: `data_augs.py:8` is `def random_crop(imgs, out=84)`, and
  `train.py:27,29` default `--pre_transform_image_size=100` / `--image_size=84`, with
  `--data_augs default='crop'` (`:76`) and `pre_transform_image_size` applied only when `'crop' in
  data_augs` (`:189`). So RAD's own default pipeline renders at **100×100 and random-crops to
  84×84** — a real ±16px spatial jitter. This project renders natively at 84×84 (RL-ViGen/robosuite
  mandate), where `random_crop(out=84)` is **exactly the identity — zero jitter, augmentation
  silently absent**. That is precisely why `random_shift` (DrQ-v2's pad-and-crop translation) was
  substituted, and the substitution is now **verified against the reference rather than inferred
  from its README**. The branch point stands as already declared in `rlgen/algos/rad.py`.
- Superseded note (kept for the record — this was the state before the clone):
  `ext/baseline_resources/06_rad/` (PDF, OpenReview thread, `paper_source_2004.14990.tar.gz` —
  LaTeX source, not code). `repo_link.txt` in that folder names the canonical repo as
  `https://github.com/MishaLaskin/rad`.
  The locally-vendored stand-in, `ext/dmcontrol-generalization-benchmark/src/algorithms/rad.py`,
  is a 13-line empty subclass of `SAC` with zero method overrides — RAD's actual contribution
  (data augmentation) evidently lives outside this file, applied generically before observations
  reach the algorithm.
  **Checked directly 2026-08-14** (fetched `MishaLaskin/rad`'s own README via `WebFetch`, not
  trusted from the old resource-bundle note): the official repo uses the SAME pattern —
  `--agent rad_sac` selects a base SAC agent, `--data_augs crop-rotate-flip` selects augmentation
  independently via flags, applied as a generic preprocessing layer. Structural match confirmed,
  from a primary source, not assumed. **Not yet done**: a byte-level diff of the actual
  augmentation code (`data_augs.py` in the official repo vs. whatever `utils.py`/`factory.py`
  applies in the vendored DMC-GB copy) — the architecture matches, the exact crop/pad parameters
  haven't been compared. That's the remaining gap if RAD's specific numbers ever matter.

### `soda` — Hansen & Wang, ICRA 2021, arXiv:2011.13389
- **Original, fidelity YES, continuous (DMC)**:
  `projects/many-gens-rl-vigen/ext/dmcontrol-generalization-benchmark/src/algorithms/soda.py` —
  same repo and same reasoning as `svea` above (Hansen is SODA's own lead author too).
  Same `HEAD ff9c0aa`, 2024-01-03 — ~3 years after ICRA 2021 (~2020-2021). Same real drift risk as
  `svea`, more pronounced given the longer gap. Not diffed against a paper-stated commit.

### `alda` — Batra & Sukhatme, ICML 2025, arXiv:2410.07441
- **Original, fidelity YES, continuous**:
  `projects/many-gens-rl-vigen/ext/ALDA_Official` — origin `SumeetBatra/ALDA_Official.git`,
  verified. This is the "unedited cloned version" — genuinely the authors' own release, untouched.
  Confirmed continuous: it bundles its own `dmcontrol_generalization_benchmark/` with `dmc2gym`.
  `HEAD 8dcc968`, 2025-05-27 — predates the ICML 2025 venue by ~1-2 months, consistent with an
  arXiv-preprint-era release ahead of the camera-ready. Low drift risk given the recency. Not
  diffed against a paper-stated commit.
- Also present, fidelity NO (gen-rebuttal's edited port, continuous, adapted to robosuite rather
  than DMC): `rlgen/algos/alda/{agent.py,nets.py,config.py}` — per that file's own header, "COPIED,
  NOT IMPORTED" from `../gen-rebuttal/vigen-idaac/vigen_alda/`, which is itself gen-rebuttal's own
  from-scratch port, not a copy of the line above. So there are two hops between what's in `rlgen/`
  and the original: `ALDA_Official` (yes) -> gen-rebuttal's port (no) -> `rlgen/algos/alda` (no,
  copied from the port, not from the original).

---

## The PPO family

### `idaac` — Raileanu & Fergus, ICML 2021, arXiv:2102.10330
- **Original, fidelity YES, discrete (Procgen) only**:
  `projects/gen-rebuttal/ext/idaac` — origin `rraileanu/idaac.git`, verified. No continuous version
  was ever officially released — confirmed by an exhaustive fork audit (all 13 forks of this repo
  checked via the GitHub API; none add continuous support) and a literature search, both run this
  session via `agy`, independently spot-checked.
  `HEAD 2fe3020`, 2021-06-11 — ~1 month before ICML 2021 (~July 2021), consistent with a
  pre-camera-ready arXiv-era release. Low drift risk. Not diffed against a paper-stated commit.
- Continuous port, fidelity NO (ours, one hop from the original, robosuite not DMC):
  `projects/gen-rebuttal/vigen-idaac/vigen_idaac/` — gen-rebuttal's own from-scratch port.

### `ppg` — Cobbe et al., ICML 2021, arXiv:2009.04416
- **Original, fidelity YES, discrete (Procgen) only**:
  `projects/many-gens-rl-vigen/ext/phasic-policy-gradient` — origin
  `openai/phasic-policy-gradient.git`, verified.
  `HEAD 7295473`, 2020-12-11 — predates ICML 2021 by several months, consistent with the paper's
  original arXiv timeline (Cobbe et al. posted late 2020). Low drift risk. Not diffed against a
  paper-stated commit.
- Continuous ports exist, but **not vendored locally** — found on GitHub this session via `agy`,
  independently spot-checked (both files fetched and read directly, code confirmed real, not
  hallucinated): `jjccero/pbrl` (`pbrl/algorithms/ppg/ppg.py`) and `agi-brain/xuance`
  (`xuance/torch/learners/policy_gradient/ppg_learner.py`). Both are third-party community
  frameworks, fidelity NO — nobody, including the original authors, has released a continuous PPG.

### `ibac_sni` — Igl et al., NeurIPS 2019, arXiv:1901.10902
- **Original, fidelity YES**: `projects/many-gens-rl-vigen/ext/IBAC-SNI` — origin
  `microsoft/IBAC-SNI.git`, verified. `HEAD 6b3a58b`, 2020-06-28 — ~6 months after NeurIPS 2019
  (~Dec 2019). Moderate drift risk. Not diffed against a paper-stated commit.
  **Corrected 2026-08-16 — this was described as "discrete (TF 1.x CoinRun) only", which is wrong
  in the way that mattered most.** The repo ships *two* implementations: the TF 1.x CoinRun path
  (`coinrun/coinrun/{policies,ppo2,config}.py`, the paper's headline experiments) **and the
  authors' own PyTorch path** (`torch_rl/bottleneck.py`, `torch_rl/model.py`, MiniGrid). The
  consequence is direct: the framework-boundary argument that would license treating a third
  party's PyTorch re-derivation as the best available base for this baseline **does not apply
  here**, because a first-party PyTorch bottleneck exists on this disk.
- Third-party port, fidelity NO, still discrete (Procgen, not continuous):
  `~/Downloads/IBAC_SNI_torch` — DZ's independent PyTorch port. No continuous version of IBAC-SNI
  exists anywhere, confirmed by the same `agy` search as IDAAC/CTRL above.
  **Class established 2026-08-16, having previously been left unstated:** its two IBAC-specific
  files (`agents/ppo_ibac.py`, `common/policy_ibac.py`) are a **Construction** — a re-derivation
  from the paper, not a transcription of the authors' code. Evidence: their headers cite the paper
  by title and venue and describe the mechanism in prose; `ppo_ibac.py::evaluate()` is a
  translated copy of the *dirty* `train-procgen-pytorch_example/agents/ppo.py::evaluate()`, so this
  port post-dates and partly derives from that tree rather than being its sibling. Usable as
  **wiring** (how IBAC bolts into a PPO host), never as the **authority on IBAC-SNI's semantics** —
  that authority is `ext/IBAC-SNI` above.

### `ctrl` — Mazoure et al., ICLR 2022, arXiv:2106.02193
- **Original, fidelity YES, discrete (Procgen) only, JAX/Flax**:
  `projects/many-gens-rl-vigen/ext/ctrl_public` — origin `bmazoure/ctrl_public.git`, verified.
  `HEAD 7a118c8`, 2022-03-15 — ~1-2 months after ICLR 2022 acceptance (~Jan 2022). Low-moderate
  drift risk. Not diffed against a paper-stated commit.
  Its own PPO update (`algo.py`: `update_ppo`, `update_daac`) is a from-scratch JAX implementation,
  independent of every other baseline's PyTorch code — there was never a code-sharing relationship
  between CTRL's own reference and any other baseline here, discrete or continuous.
  No continuous CTRL exists anywhere (confirmed: the repo's one fork has zero modifications,
  Mazoure's full GitHub profile checked, citing literature checked, all via `agy` this session).
  **No PyTorch reimplementation of CTRL exists anywhere either**, confirmed 2026-08-14 by a second,
  differently-angled `agy` search (GitHub code search, PapersWithCode, OpenReview's ICLR 2022
  thread, and all 30 papers citing arXiv:2106.02193 via the Semantic Scholar API — every citation
  is a conceptual "related work" mention; none ran CTRL as an actual experimental baseline,
  continuous or otherwise). One plausible-looking false lead was checked and ruled out: Mazoure's
  own `DRIML` repo (NeurIPS 2020, PyTorch) implements a *different* method — consecutive-state
  mutual information, not CTRL's cross-trajectory clustering. So there is currently no PyTorch
  ground truth for CTRL at all, discrete or continuous — any PyTorch port has to be derived
  directly from the paper's math and checked against the JAX source line-by-line, with no
  reference implementation anywhere to shortcut against or diff toward.

---

## Classification — Transcription / Adaptation / Construction

Per `porting-directive.md` §0. **Most of this work is transcription; if a piece of it is not, that
is the finding.** Below, per baseline, with the file:line evidence, not asserted from memory.

| Baseline | What's actually in this repo | Class | Why |
|---|---|---|---|
| `drqv2` | `RL-ViGen-upstream/algos/drqv2.py`, executed unmodified | **Transcription** | Facebook copyright header intact; not independently diffed against `ext/drqv2` (open gap, noted above) |
| `svea` | `RL-ViGen-upstream/algos/svea.py` | **Adaptation** | Registry's own note: "Original SVEA is DrQ-based; this is the DrQ-v2 port RL-ViGen ships" — RL-ViGen's own backbone-port, not SVEA's authors' own code. `drq.py` in the same repo carries the same Facebook-copyright/hydra/`RandomShiftsAug` structure, confirming the DrQ-v2-style pattern directly rather than assuming it from the note alone |
| `sgqn` | `RL-ViGen-upstream/algos/sgqn.py` | **Adaptation** | **Resolved 2026-08-14**, was "unconfirmed": `RL-ViGen-upstream/algos/sgqn.py` imports `from drqv2 import DrQV2Agent, Actor, Critic` directly. SGQN's own official repo (`ext/SGQN/DMC/src/algorithms/sgsac.py`, its actual method) builds on its own local `sac.py` instead — same file-structure lineage as Hansen's DMC-GB (`curl.py`/`drq.py`/`rad.py`/`sac.py`/`svea.py`/`soda.py` all present, `sgsac.py` added on top), not DrQ-v2's. Same shape as `svea`/`curl`/`drq`: RL-ViGen's own backbone-port, not a transcription of the method's own official approach |
| `curl` | `RL-ViGen-upstream/algos/curl.py` | **Adaptation** | CURL (2020) predates DrQ-v2 (2022) by over a year; CURL's own official repo (`ext/curl`) is standalone SAC+contrastive, not DrQ-v2-based. `_drqv2_family` construction path strongly implies the same backbone-port RL-ViGen did for `svea` |
| `drq` | `RL-ViGen-upstream/algos/drq.py`, despite `backbone="sac"` label | **Adaptation** | Confirmed directly: this file carries the Facebook-copyright/hydra/`RandomShiftsAug` DrQ-v2-style structure, not the SAC-based structure of DrQ's own official repo (`ext/drq`) — the `backbone="sac"` registry label does not match what the file actually is |
| `rad` | `rlgen/algos/rad.py` (`SAC` + augmentation), `sac.py` base | **Adaptation, already well-declared** | **Corrected 2026-08-14** — first-pass classification (Construction) was wrong: read from `_sac_family`'s caller-side docstring, not from `rad.py` itself. `rad.py`'s own docstring cites the paper directly and names the branch point precisely (render-resolution mismatch: RAD's own `random_crop` at 100→84 is the identity at this protocol's native 84×84, so `random_shift` — RL-ViGen's own DrQ-v2 translation, matched exactly so the augmentation isn't confounded by two different implementations — is substituted, declared, and cross-referenced in the registry notes). This is close to the directive's §4 model shape already. `sac.py` base: see next row |
| `soda` | `rlgen/algos/soda.py`, `sac.py` | **Transcription** (was Construction; corrected 2026-08-14) | First-pass classification was wrong the same way as `rad`'s. Diffed directly against `ext/dmcontrol-generalization-benchmark/src/algorithms/{sac,soda}.py`: near line-for-line match, differing only in `.cuda()` → `.to(self.device)` (device-agnosticism) and import paths. `soda.py` even inherits the original's own latent bug (`train()` guarding on `hasattr(self, 'soda_predictor')`, a name never set — `__init__` sets `self.predictor`) — found and fixed here, still present in the vendored original. Both files were missing the citation that would have made this obvious; added 2026-08-14 (`rlgen/algos/sac.py`, `soda.py` docstrings) |
| `alda` | `rlgen/algos/alda/{agent.py,nets.py,config.py}` | **Transcription of an Adaptation** | Two hops: `ALDA_Official` (yes) → gen-rebuttal's own from-scratch port to robosuite (Adaptation, not by ALDA's authors) → `rlgen/algos/alda` (per its own header, "COPIED, NOT IMPORTED" from gen-rebuttal's port — a faithful transcription of that adaptation, not of the original) |
| `idaac` | `rlgen/algos/idaac/algo.py` (`Learner`) | **Adaptation** | This project's own continuous-control adaptation of IDAAC (no official continuous IDAAC exists anywhere — confirmed exhaustively), informed by but not copied from gen-rebuttal's independent adaptation of the same paper |
| `ppg` | `rlgen/algos/ppg/{model,algo,storage,config}.py` | **Reclassified 2026-08-16, Adaptation** (was Construction) | **Superseded 2026-08-14**: `ppg` was rebuilt hermetic (`porting-directive.md` §1), no longer inheriting `idaac/algo.py:Learner` at all — `onpolicy_ext.py` (which held the old inheriting `PPGLearner`) was deleted 2026-08-14 once every on-policy baseline had its own module. The Construction problem this row previously named ("no reference settles PPG's mechanism running on IDAAC's specific PPO variant") no longer applies, because that combination no longer exists in the code — `ppg/algo.py` is built from PPG's own reference (`ext/phasic-policy-gradient/`) alone. Remaining open gap, found 2026-08-16 by external review: the hermetic module was never itself numerically verified against that reference (no T1/T2 check exists for it, only internal self-consistency tests) — see `docs/REGISTER.md`, `docs/INTERIM-REPORT-2026-08-16.md` §9 |
| `ibac_sni` | `rlgen/algos/ibac_sni/{model,algo,storage,config}.py` | **Reclassified 2026-08-16, Adaptation** (was Construction) | Same correction as `ppg`, same date: hermetic since 2026-08-14, `onpolicy_ext.py::IBACSNILearner` deleted. Built from DZ's own reference alone. Same open verification gap as `ppg` — never numerically checked against the reference, internal self-consistency only |
| `ctrl` | `rlgen/algos/ctrl/{model,algo,storage,config}.py` | **Construction** (reclassified 2026-08-16, same verdict for a DIFFERENT reason than before) | Hermetic since 2026-08-14, `onpolicy_ext.py::CTRLLearner` deleted — the *old* reason for Construction ("zero precedent for the PPO-core combination") no longer applies. Still correctly Construction, because CTRL's own reference is JAX/Flax and this project is PyTorch throughout: `porting-directive.md` §1 names crossing that boundary as what "converts a faithful-transcription artifact into a constructed one." Partially closed 2026-08-16: `model.py::Impala` (the CNN encoder) now has a real, passing T1 weight-transplant check against the actual JAX reference (`tests/test_ctrl_parity.py`) — found and fixed two real bugs to get a genuine pass (flatten order, maxpool padding value), not merely claimed. The rest of `CTRLPolicy` and all of `algo.py`'s training-loop math remain T4 (structural accounting), not yet given an equivalent numerical check — see `docs/REGISTER.md`'s 2026-08-16 entries |

**Read-off, corrected 2026-08-14, superseded again 2026-08-16** (first pass over-called
Construction on `rad`/`soda` by reading the caller's docstring instead of the files themselves,
and left `sgqn` unconfirmed rather than checking its actual import — both closed same-day; then
`ppg`/`ibac_sni` moved from Construction to Adaptation once they went hermetic later the same
day, `ctrl` stayed Construction but for a new reason — see the three rows above, corrected
2026-08-16): 2 clean Transcriptions (`drqv2`, `soda`), 1 Transcription-of-an-Adaptation (`alda`),
8 Adaptations (`svea`, `curl`, `drq`, `sgqn`, `idaac`, `rad`, `ppg`, `ibac_sni`), 1 Construction
(`ctrl`) — `sac.py` as the shared base under both `rad` and `soda` is itself a Transcription, not
a separate construction. The "Constructions correlate with defects" observation this section
previously made at n=3 no longer has enough Constructions left to say much with (n=1) — worth
naming as a stopped clock, not silently dropping the claim: the correlation was real while it
held, the sample it held over shrank to where it can't be evaluated anymore, and that itself is
not evidence the underlying claim was wrong. `ctrl` is *also* the one Construction with a real,
passing T1 check on part of it now (`model.py::Impala`, 2026-08-16) — the one remaining
Construction is simultaneously the best-verified baseline on this specific axis, which is a
sharper, not weaker, version of "constructions need more scrutiny, not less."

---

## `~/Downloads` inventory — CLOSED 2026-08-16, one-time, not a standing practice

Prompted by discovering mid-session that `~/Downloads/train-procgen-pytorch_example/` had sat
unexamined for an entire session while being materially relevant. Swept exhaustively once
(every `.git` directory at depth ≤3, every `.py` modified since 2026-07-01, plus keyword search).
**Closed**: the user owns what lands here and will say when something does, so there is no
periodic re-check — this table is the record, not a checkpoint to re-run.

| Item | What it actually is | Bearing on the 12 |
|---|---|---|
| `IBAC_SNI_torch/train-procgen-pytorch/` | **DZ-provided.** DZ's own IBAC-SNI PyTorch port. No `.git`. | `ibac_sni`'s working reference |
| `train-procgen-pytorch_example/` | **DZ-provided, and NOT clean — corrected 2026-08-16 on first contact with the artifact.** The `.git` remote is genuinely verified (`git@github.com:joonleesky/train-procgen-pytorch.git`) and `HEAD` is a real upstream commit (`1678e4a9e2cb8ffc3772ecb3b589a3e0e06a2281`, 2020-09-10) — but the **working tree** carries ` M agents/ppo.py`, ` M train.py` and an untracked `experiments/`. This row previously said "Clean … the exact base DZ edited": *remote-verified* had been read as *working-tree-clean*, which are different properties, and only the first was ever checked. The modified `agents/ppo.py` is an unrelated third party's noise-injection experiment (SVD `find_principal_component`, a `noise_amplitude` knob, Russian comments) and **does not parse** — `ast.parse` raises `SyntaxError` on `self.find_principal_component( self.storage.  )` | **Not usable as a base as it sits.** The base term is the *commit*, not this tree: `git show 1678e4a:<path>` |
| `train-procgen-pytorch` @ `1678e4a` (via `git show`) | Pristine upstream `joonleesky/train-procgen-pytorch`. Parses, imports, genuinely unmodified | **`ibac_sni`'s actual base term — reachable.** DZ's delta against *this* is **4 files, not 5**: `hyperparams/procgen/config.yml` and `train.py` modified, `agents/ppo_ibac.py` and `common/policy_ibac.py` new (+ 5 non-code launch `.sh`). `agents/ppo.py` is byte-identical to upstream (`diff` exit 0) — it entered the old 5-file count only because the diff was taken against the dirty tree |
| `Nd_ln.py` | **DZ-provided.** DZ's own trainer. Duplicate of `gen-rebuttal/ext/alda/Nd_ln.py` | Terms/provenance only — trains a different algorithm (disentangled encoder + gradient reversal), never an architecture anchor |
| `faithful_nd_ln.py`, `faithful_nd_ln.VERIFIED.py` | Corrected reference produced by the user with another AI against `Nd_ln.py`'s defects (~25 tagged bugs) | Provenance/terms; imports the sibling's audited `vigen_alda` |
| `config.py`, `envs.py`, `model.py`, `storage.py`, `algo.py` (top level, 2026-07-29) | **Our own lineage, not an original.** An older snapshot of `gen-rebuttal/vigen-idaac/vigen_idaac/` — diffs 216–740 lines against that package's current state | Comparison point for `idaac` only. **Does not overturn "no official continuous IDAAC exists"** — IDAAC's own repo is Procgen-discrete; this is a third-party (our-lineage) continuous adaptation |
| `rlvigen_adapter.py` | Same lineage; self-labelled "THE ONLY SPECULATIVE FILE" | Carries RL-ViGen's `EVAL_SCENES=range(10)`, `EVAL_TRIALS_PER_SCENE=10` from the NeurIPS'23 supplementary |
| `files (5)/{audit_tools,protocol_variance,resolve_setting}.py` | Same lineage; analysis tooling | None on baseline fidelity |
| `solve-basic-training.py`, `sol_v2.py` | Unrelated (NMT assignment; competitive programming) | None |

**Verdict: no unaccounted-for first-party original exists in `~/Downloads`.** That still holds —
the sweep of that directory was real and its result stands. The materially new affordance is
`joonleesky/train-procgen-pytorch` @ `1678e4a` as `ibac_sni`'s literal base (**via `git show`, not
via the `_example` working tree** — see that row).

**Rewritten 2026-08-16, because the sentence that stood here was falsified by the very first task
it was supposed to make safe — and, checked afterwards, on the same day it was written**
(`git log -S 'the exact base DZ edited'` -> `24b5f300`, 2026-08-16). An earlier version of this
correction said "within four days", which invented a decay story for what was simply wrong on
arrival. The distinction is not pedantic: staleness would suggest a re-checking cadence, whereas a
same-day error points at a **missing step in the sweep itself** — it verified remotes and never
opened a working tree. See `docs/STEP-ZERO.md` gate 0. It read: *"The 'I did not realise a reachable original
existed' failure mode is closed by this table, not by a recurring check."* It is not, and could
not have been. The table's scope is one directory. `ibac_sni`'s actual first-party original —
including a **PyTorch** implementation by the authors themselves — was sitting in `ext/IBAC-SNI`
inside this very repo the whole time, was listed three sections above in this same file, and was
still not consulted before a third party's re-derivation was queued up as the reference. A
directory sweep closes *that directory*; it does not close the failure mode, because the failure
mode is **not looking at the reference you already know you have**. What actually closes it is the
per-baseline gate — state the base term as a fact, name the specific file the semantics come
from — run at the moment work on that baseline begins. `docs/STEP-ZERO.md` gate 1. A table is
evidence for such a check; it is not a substitute for one, and no completed sweep ever discharges
a future baseline's obligation to look.

## Summary: what's actually missing

- **12 of 12** have a verified, locally-vendored, fidelity-YES original, as of 2026-08-16.
  `rad` was the last gap and is now cloned (`ext/rad`, `MishaLaskin/rad.git`, `HEAD 18d079e`);
  its augmentation-parameter diff is closed from primary source (see §`rad` above — RAD's own
  default is render-100/crop-84, which is the identity at this project's native 84×84, confirming
  the already-declared `random_shift` substitution rather than merely assuming it).
  **All 12 paper bundles are also present** (`ext/baseline_resources/01_drqv2` … `12_ctrl`).
- **Continuous ground truth exists for 8 of 12** (`drqv2`, `svea`, `sgqn`, `curl`, `drq`, `soda`,
  `alda`, and now `ppg` via third-party ports). **`idaac`, `ibac_sni`, `ctrl` have no continuous
  reference anywhere on Earth, as far as an exhaustive search this session could establish** — our
  own ports are the first continuous versions of these three that exist. That is the real,
  irreducible fidelity risk for those three specifically, and no amount of further searching
  local disk or the web is going to close it — the only way to raise confidence on those three is
  scrutiny of the port itself against each paper's stated method, not a diff against a reference
  implementation that doesn't exist.

---

## What each reference actually supplies: train loop, eval loop, both, or neither

A different question from everything above, raised 2026-08-16 and checked
file-by-file rather than assumed. Every baseline's `rlgen/` code goes through this project's OWN
`trainer.py`/`trainer_onpolicy.py` and `evaluate()` regardless — per `porting-directive.md` §2 the
harness is deliberately never shared with any reference's own loop. What varies, and matters for a
different reason (how much precedent exists to check a claim against, and whether a baseline's own
paper ever measured anything resembling a train/eval generalization gap at all), is what each
*reference* itself came with.

| Baseline(s) | Own train loop | Own eval loop | What the eval loop actually does |
|---|---|---|---|
| `drqv2`, `svea`, `sgqn`, `curl`, `drq` | `RL-ViGen-upstream/train.py` (353-line `eval.py` is separate, not called from train) | `RL-ViGen-upstream/eval.py` (353 lines) | `robo_eval`/`habi_eval`/`carla_eval` — domain-specific, genuinely evaluates under RL-ViGen's own randomized visual settings. Rich and purpose-built for exactly this kind of generalization measurement. |
| `rad`, `soda`, `sac` | `ext/dmcontrol-generalization-benchmark/src/train.py` | `ext/dmcontrol-generalization-benchmark/src/eval.py` | `evaluate(env, agent, video, num_episodes, eval_mode, ...)`, `--eval_mode` (`distracting_cs`, `color_hard`, `video_hard`, etc.) — this benchmark's entire purpose is generalization under visual perturbation, so its eval machinery is the richest of any reference checked here. |
| `ctrl` | `ext/ctrl_public/train_ppo.py` | Two mechanisms, both in the reference: `train_ppo.py` itself constructs `env_test_ID` and `env_test_OOD` (in-distribution / out-of-distribution) *inside the training script*, evaluated every update alongside `env` (train); a separate `evaluate_ppo.py` also exists. Architecturally the closest of any reference here to what this project's own train-vs-eval-scene split is trying to measure. |
| `alda` | `ext/ALDA_Official/trainers/alda_trainer.py::train()` | Same class, `alda_trainer.py::evaluate(self, step, distracting_env=False, color_env=False)` | Built-in distribution-shift evaluation (`distracting_env`/`color_env` flags) — genuine precedent for a generalization-style measurement, in the same file as training, not bolted on separately. |
| `ppg` | `ext/phasic-policy-gradient/phasic_policy_gradient/train.py` | **None.** Checked directly: zero matches for `eval`/`test_env`/`held-out`/`generaliz` anywhere in `train.py` or `ppo.py`. | **Nothing.** PPG's own official code trains and logs training-distribution statistics only. There is no generalization-gap measurement anywhere in the reference to compare this project's own protocol against, corroborate it with, or diverge from — this project's `eval-easy`/`eval-hard` split for PPG has zero precedent in the paper's own code. (Procgen's own level-sampling convention, which PPG's training relies on, is a different, coarser mechanism — train-level-count vs. full-level-set — not a separate eval script.) |
| `ibac_sni` | `~/Downloads/IBAC_SNI_torch/train-procgen-pytorch/train.py` | **None.** Checked directly: `train.py` constructs exactly one `ProcgenEnv` (`grep`-confirmed, single construction site), no second env, no `eval.py` anywhere in the repo. | **Nothing**, same situation as `ppg` exactly — no built-in generalization measurement in DZ's own reference to check against. |
| `idaac` | N/A | N/A | No continuous reference exists at all (see the exhaustive-search finding above) — there is no code to have a train or eval loop in. The Procgen-discrete IDAAC download this project has access to is a different question (Appendix E's continuous DMC results were never released as code), already established, not re-litigated here. |

**Why this matters, concretely, not just as a taxonomy exercise.** For the 5 baselines with rich,
purpose-built eval machinery (RL-ViGen family, DMC-GB family, `ctrl`, `alda`), there is at least a
*structural* precedent to check this project's own train/eval split against — even though the
actual numbers will never be directly comparable (different task, different image size, different
protocol), the *shape* of the measurement (does the paper's own code treat "eval under
perturbation" as a first-class thing, distinct from training) is corroborated by the reference
itself. For `ppg` and `ibac_sni`, this project's own generalization-gap measurement is being
applied to a method whose own authors' code never attempted anything resembling it — not wrong, but
worth being honest about: **the "does this method generalize" question this whole project asks is,
for these two specifically, a question this project is imposing on the method, not one its own
authors' code ever posed to it.** That's not a defect in the port; it's a fact about what evidence
exists to lean on when interpreting whatever number these two baselines eventually produce.
