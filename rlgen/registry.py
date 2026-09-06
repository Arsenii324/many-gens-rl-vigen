"""The one place baselines are named, and the one place their status is declared.

R6 IN THE BRIEF is that the twelve baselines are genuine. The failure mode is not that a baseline
is missing -- it is that a baseline is present in name only and gets a row in the results table
anyway. In this repo's previous state, `ctrl` was a zero-override subclass of CURL, `rad` added
nothing to SAC, and `ppg` was a DrQ-v2 actor with no update rule at all, while the real 480-line
PPG implementation sat unimported. All three would have appeared as independent rows.

So every baseline declares a STATUS, and the status is machine-readable:

    implemented  a real, distinct training rule for this method
    alias        deliberately identical to another baseline at inference; `alias_of` says which.
                 Aliases are NOT forbidden -- CTRL and CURL genuinely share an inference network;
                 UNDECLARED aliases are what corrupt a table.
    eval_only    the network and inference path exist and are faithful, but no training rule is
                 implemented here, so it can score a checkpoint and cannot produce one
    absent       named in the brief, not implemented. Present so the gap is countable.

`train.py` refuses to train anything that is not `implemented`, `plot.py` marks aliases on the
figure, and `tests/test_registry.py` asserts every baseline in the brief has an entry.

BACKBONE IS DECLARED SEPARATELY FROM METHOD. "SVEA" is a method; "SVEA on DrQ-v2" is a
measurement. At least two different SVEA numbers exist in the literature for overlapping settings
because the original is DrQ-based and a later re-implementation is DrQ-v2-based, with encoders of
different depth. Recording only the method name reproduces that confusion.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM = os.path.join(ROOT, "RL-ViGen-upstream")


def load_upstream_module(name: str):
    """Import `RL-ViGen-upstream/algos/<name>.py` WITHOUT executing the `algos` package __init__.

    Upstream's `algos/__init__.py` is one line -- `from algos import pieg` -- and `pieg.py`
    imports `hydra` and `torchvision`. So a plain `from algos.drqv2 import DrQV2Agent` drags in
    two heavy transitive dependencies of an algorithm this benchmark never runs, and dies with
    `ModuleNotFoundError: hydra` on any machine that lacks them. Five of the twelve baselines were
    unconstructible for this reason (docs/REVIEW.md F3).

    Loading the module file directly keeps the dependency set honest: a baseline pays only for
    what it actually imports.
    """
    algos = os.path.join(UPSTREAM, "algos")
    for p in (UPSTREAM, algos):
        if p not in sys.path:
            sys.path.insert(0, p)
    key = f"_rlvigen_algo_{name}"
    if key in sys.modules:
        return sys.modules[key]
    path = os.path.join(algos, f"{name}.py")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found; is RL-ViGen-upstream installed?")
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        # A half-executed module left in sys.modules turns the next attempt into a confusing
        # AttributeError ("module has no attribute SGQNAgent") instead of the real cause
        # ("No module named captum"). Purge it so the failure stays honest.
        sys.modules.pop(key, None)
        raise
    return mod


@dataclass(frozen=True)
class BaselineSpec:
    name: str
    method: str
    backbone: str
    status: str
    paper: str
    #: (protocol, obs_shape, act_dim, device, hyper) -> agent object exposing
    #: `.act(obs, deterministic: bool) -> np.ndarray`
    build: Callable | None = None
    alias_of: str | None = None
    notes: str = ""
    #: Packages this baseline needs on top of requirements.txt. The brief requires each baseline's
    #: README to name its environment; this is where that information lives, so the README and the
    #: code cannot disagree. Discovered by running, not by reading: SGQN's saliency path imports
    #: captum at module scope and nothing upstream declares it.
    extra_requirements: tuple = ()
    #: True when the baseline consumes ROLLOUTS rather than replay batches, i.e. it must be
    #: driven by rlgen/trainer_onpolicy.py. Declared on the spec so `train.py` picks the loop
    #: from the registry rather than from a branch someone has to remember to update.
    on_policy: bool = False
    #: External DATASETS this baseline needs *to train*. Same reasoning, one step worse: a missing
    #: dataset here surfaces at the first gradient step, which is AFTER the frame-0 evaluation has
    #: already written a protocol card, an episodes.csv and a tensorboard file. A run that cannot
    #: possibly finish must not leave artifacts that look like a run that can, so
    #: `check_data_requirements` is called before anything is written.
    data_requirements: tuple = ()


    @property
    def trainable(self) -> bool:
        return self.status == "implemented"

    @property
    def label(self) -> str:
        """What a figure legend shows. An alias never gets to look independent."""
        if self.status == "alias" and self.alias_of:
            return f"{self.name} (= {self.alias_of})"
        if self.status == "eval_only":
            return f"{self.name} (eval-only)"
        return self.name


#: name -> (human description, predicate returning True when the data is present)
def _places365_present() -> bool:
    """RL-ViGen resolves the overlay dataset through `cfgs/aug_config.cfg` -> `datasets`."""
    import json
    cfg = os.path.join(UPSTREAM, "cfgs", "aug_config.cfg")
    if not os.path.exists(cfg):
        return False
    try:
        for d in json.load(open(cfg, encoding="utf-8")).get("datasets", []):
            # Either partition will do -- the overlay images are nuisance, not labels, so `val`
            # (~2 GB) is a declared alternative to `train` (~24 GB); see
            # setup/fetch_overlay_dataset.sh. The check must name the partition: an earlier
            # version also accepted `os.path.isdir(d)`, which reported the dataset present
            # whenever the registered directory merely existed.
            for part in ("train", "val"):
                if os.path.isdir(os.path.join(d, "places365_standard", part)):
                    return True
    except Exception:
        return False
    return False


DATASETS = {
    "places365": (
        "Places365-standard (~24 GB), used by SVEA/SGQN's `random_overlay` augmentation at "
        "TRAINING time only. Path list: RL-ViGen-upstream/cfgs/aug_config.cfg -> \"datasets\".",
        _places365_present),
}


def check_data_requirements(name: str) -> list[str]:
    """-> list of human-readable problems; empty when the baseline can train here.

    Evaluation of an existing checkpoint does NOT need these -- the augmentation lives in
    `update()`, not in `act()` -- so the message says so rather than implying the baseline is
    unusable.
    """
    spec = get(name)
    out = []
    for d in spec.data_requirements:
        desc, present = DATASETS[d]
        if not present():
            out.append(f"{d}: {desc}")
    return out


# ---------------------------------------------------------------------------------------------
# Builders. Each returns an object with `.act(obs, deterministic) -> np.ndarray (act_dim,)`.
# ---------------------------------------------------------------------------------------------
def _drqv2_family(cls_name: str, module: str, defaults: dict | None = None):
    """`defaults` are the constructor arguments this particular agent REQUIRES.

    They live here, next to the class they belong to, rather than in the config -- a required
    argument that only appears in a yaml entry is a crash waiting for whoever calls the builder
    without that entry, which is exactly what the test suite does.
    """
    defaults = defaults or {}

    def build(protocol, obs_shape, act_dim, device, hyper):
        hyper = {**defaults, **hyper}
        mod = load_upstream_module(module)
        cls = getattr(mod, cls_name)
        kw = dict(obs_shape=obs_shape, action_shape=(act_dim,), device=device,
                  lr=hyper.get("lr", 1e-4), feature_dim=hyper.get("feature_dim", 50),
                  hidden_dim=hyper.get("hidden_dim", 1024),
                  critic_target_tau=hyper.get("critic_target_tau", 0.01),
                  num_expl_steps=hyper.get("num_expl_steps", 2000),
                  update_every_steps=hyper.get("update_every_steps", 2),
                  stddev_schedule=hyper.get("stddev_schedule", "linear(1.0,0.1,500000)"),
                  stddev_clip=hyper.get("stddev_clip", 0.3), use_tb=False)
        # sgqn_quantile added 2026-08-10: without it the config cannot reach SGQN's quantile and
        # the constructor default (0.95) stood, where both canonical SGQN's code and RL-ViGen's
        # Table 6 say 0.90. A knob the config cannot reach is not a knob.
        for extra in ("init_temperature", "log_std_bounds", "hidden_depth", "aux_lr", "aux_beta",
                      "sgqn_quantile"):
            if extra in hyper:
                kw[extra] = hyper[extra]
        from .agents import DrQV2Adapter
        return DrQV2Adapter(cls(**kw), act_dim=act_dim)
    return build


def _sac_family(cls_name: str, module: str, defaults: dict | None = None):
    """RAD and SODA. RL-ViGen does not ship them, so their SAC backbone lives in rlgen/algos/.

    Recovered from this repo's own history at `de879a0` rather than rewritten: `sac.py` is a full
    SAC, `soda.py` a genuine BYOL-style auxiliary, `augmentations.py` the DMC-GB augmentation set.
    """
    defaults = defaults or {}

    def build(protocol, obs_shape, act_dim, device, hyper):
        import importlib
        from .agents import SAC_DEFAULTS, SacAdapter, _Args
        mod = importlib.import_module(f"rlgen.algos.{module}")
        cls = getattr(mod, cls_name)
        args = _Args(device=device, **{**SAC_DEFAULTS, **defaults,
                                       **{k: v for k, v in hyper.items()
                                          if k in SAC_DEFAULTS or k.startswith("rad_")}})
        return SacAdapter(cls(obs_shape, (act_dim,), args), act_dim=act_dim, device=device)
    return build


def _alda_build(protocol, obs_shape, act_dim, device, hyper):
    """ALDA. Its reference package expects to be imported as top-level `autoencoders.*` /
    `models.*`, so third_party/alda goes on sys.path rather than its imports being rewritten --
    the same don't-edit-the-reference rule applied to RL-ViGen's own algorithms."""
    import torch
    vendored = os.path.join(ROOT, "third_party", "alda")
    if vendored not in sys.path:
        sys.path.insert(0, vendored)
    from .agents import AldaAdapter
    from .algos.alda.agent import AldaAgent
    from .algos.alda.config import AldaConfig
    cfg = AldaConfig()
    for k, v in hyper.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    dev = torch.device(device)
    return AldaAdapter(AldaAgent(cfg, obs_shape, act_dim, dev), act_dim=act_dim, device=dev)


def _ppo_family(algo: str):
    """IDAAC, DAAC and plain PPO share one `Learner`; `cfg.algo` selects which."""
    def build(protocol, obs_shape, act_dim, device, hyper):
        import torch
        from .agents import PPOFamilyAdapter
        from .algos.idaac.algo import Learner
        from .algos.idaac.config import Config
        cfg = Config()
        cfg.algo = algo
        for k, v in hyper.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        cfg.device = str(device)
        dev = torch.device(device)
        return PPOFamilyAdapter(Learner(cfg, obs_shape, act_dim, dev), act_dim=act_dim, device=dev)
    return build


def _ppg_hermetic_build(protocol, obs_shape, act_dim, device, hyper):
    """PPG's own hermetic module (`rlgen/algos/ppg/`) -- not built on `idaac/algo.py::Learner`,
    per `porting-directive.md` §1. See `docs/REGISTER.md` 2026-08-14 for the five divergences
    from the old shared core (`rlgen/algos/onpolicy_ext.py`, deleted 2026-08-14 once every
    on-policy baseline had its own hermetic module) this exists to fix."""
    import torch
    from .agents import PPOFamilyAdapter
    from .algos.ppg.algo import Learner
    from .algos.ppg.config import Config
    cfg = Config()
    for k, v in hyper.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    dev = torch.device(device)
    return PPOFamilyAdapter(Learner(cfg, obs_shape, act_dim, dev), act_dim=act_dim, device=dev)


def _ibac_sni_hermetic_build(protocol, obs_shape, act_dim, device, hyper):
    """IBAC-SNI's own hermetic module (`rlgen/algos/ibac_sni/`) -- not built on
    `idaac/algo.py::Learner`, per `porting-directive.md` §1. See `docs/REGISTER.md` 2026-08-14
    for the divergences from the old shared core this exists to fix."""
    import torch
    from .agents import PPOFamilyAdapter
    from .algos.ibac_sni.algo import Learner
    from .algos.ibac_sni.config import Config
    cfg = Config()
    for k, v in hyper.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    dev = torch.device(device)
    return PPOFamilyAdapter(Learner(cfg, obs_shape, act_dim, dev), act_dim=act_dim, device=dev)


def _ctrl_hermetic_build(protocol, obs_shape, act_dim, device, hyper):
    """CTRL's own hermetic module (`rlgen/algos/ctrl/`) -- not built on `idaac/algo.py::Learner`,
    per `porting-directive.md` §1. CTRL's own reference is JAX
    (`ext/ctrl_public/`), sharing no code lineage with IDAAC's PyTorch port at all -- the
    JAX-vs-PyTorch framework decision (`docs/REGISTER.md`, 2026-08-14) settled a from-scratch
    PyTorch port, independently T1/T2-verified. See `docs/REGISTER.md`'s dated entries for the
    full reference-reading trail this module was built from."""
    import torch
    from .agents import PPOFamilyAdapter
    from .algos.ctrl.algo import Learner
    from .algos.ctrl.config import Config
    cfg = Config()
    for k, v in hyper.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    dev = torch.device(device)
    return PPOFamilyAdapter(Learner(cfg, obs_shape, act_dim, dev), act_dim=act_dim, device=dev)


def _random_build(protocol, obs_shape, act_dim, device, hyper):
    from .agents import RandomAgent
    return RandomAgent(act_dim=act_dim, seed=hyper.get("seed", 0))


BASELINES: dict[str, BaselineSpec] = {}


def register(spec: BaselineSpec) -> BaselineSpec:
    BASELINES[spec.name] = spec
    return spec


# -- the negative control -----------------------------------------------------------------------
# Not in the brief, and the most important entry in this table. Every "improvement" is a
# comparison against this, and it must be MEASURED rather than assumed. On Lift the shaped reward
# pays 1 - tanh(10*d) at every one of 500 steps, so a random arm collects up to 60.06 return
# without ever lifting the block; a 2-episode probe put that floor at 0.47 and 100 episodes put it
# at 7.80 +/- 11.38. Any ratio computed against the small number was wrong by 16x and looked fine.
register(BaselineSpec(
    name="random", method="uniform random policy", backbone="none", status="implemented",
    paper="-", build=_random_build,
    notes="Negative control. Run it first, on every task, and gate every ratio on it."))

# -- DrQ-v2 family (RL-ViGen's own reference implementations) -------------------------------------
register(BaselineSpec(
    name="drqv2", method="DrQ-v2", backbone="drqv2", status="implemented",
    paper="Yarats et al. 2021, arXiv:2107.09645", build=_drqv2_family("DrQV2Agent", "drqv2"),
    notes="RL-ViGen's reference backbone; every other DrQ-v2-family entry is measured against it."))
register(BaselineSpec(
    name="svea", method="SVEA", backbone="drqv2", status="implemented",
    paper="Hansen et al. 2021, arXiv:2107.00644", build=_drqv2_family("SVEAAgent", "svea"),
    data_requirements=("places365",),
    notes="Original SVEA is DrQ-based; this is the DrQ-v2 port RL-ViGen ships. Two different "
          "'SVEA' numbers exist in the literature for this reason -- hence backbone in the label. "
          "Its overlay augmentation needs the Places365 dataset AT TRAINING TIME; evaluating an "
          "existing checkpoint does not."))
register(BaselineSpec(
    name="sgqn", method="SGQN", backbone="drqv2", status="implemented",
    paper="Bertoin et al. 2022, arXiv:2209.09203", build=_drqv2_family("SGQNAgent", "sgqn"),
    extra_requirements=("captum",), data_requirements=("places365",),
    notes="Its saliency machinery imports captum at module scope; nothing upstream declares that."))
register(BaselineSpec(
    name="curl", method="CURL", backbone="drqv2", status="implemented",
    paper="Laskin et al. 2020, arXiv:2004.04136",
    build=_drqv2_family("CURLAgent", "curl", defaults={"aux_lr": 1e-4, "aux_beta": 0.99}),
    notes="RL-ViGen's CURLAgent subclasses DrQV2Agent with its own CNNEncoder; it does NOT use "
          "the SAC stack, contrary to the previous handover doc's normalisation table. VERIFIED "
          "2026-08-14: the original CURL paper's defining mechanism -- a separate, "
          "momentum(EMA)-updated KEY encoder producing anchors for the contrastive loss, distinct "
          "from the query encoder -- is not present. `CURLAgent` (algos/curl.py:54-60) builds "
          "exactly ONE `self.encoder`, shared by `curl_head` and `actor`; the only EMA update "
          "anywhere is `soft_update_params(critic, critic_target, ...)`, the ordinary DrQ-v2/SAC "
          "target-critic update every family member has, not a CURL-specific key encoder. So this "
          "port trains the InfoNCE-style contrastive head against features from the SAME encoder "
          "being contrastively pulled, rather than a slowly-moving target -- inherited faithfully "
          "from RL-ViGen's own code, not a defect introduced here, but worth knowing if a reviewer "
          "asks why CURL's contrastive loss here does not behave the way the original paper's "
          "does."))
register(BaselineSpec(
    name="drq", method="DrQ", backbone="sac", status="implemented",
    paper="Kostrikov et al. 2020, arXiv:2004.13649",
    build=_drqv2_family("DrQAgent", "drq", defaults={
        # DrQAgent's __init__ has no defaults for these three; they are SAC-era arguments that
        # DrQ-v2 dropped. The values are the 2020 paper's.
        "init_temperature": 0.1, "log_std_bounds": [-5, 2], "hidden_depth": 2}),
    notes="The 2020 SAC-based DrQ, not DrQ-v2. Its 40.1M-parameter Linear(39200,1024) trunk is "
          "faithful to the paper, not a bug: the 50-dim bottleneck arrived with DrQ-v2."))

# -- declared aliases ---------------------------------------------------------------------------
register(BaselineSpec(
    name="ctrl", method="CTRL (Cross-Trajectory Representation Learning)", backbone="impala",
    status="implemented", paper="Mazoure et al., ICLR 2022, arXiv:2106.02193",
    build=_ctrl_hermetic_build, on_policy=True,
    notes="PPO plus a self-supervised objective over PAIRS OF TRAJECTORIES, partitioned online "
          "via a real Sinkhorn-Knopp assignment (rlgen/algos/ctrl/, hermetic per "
          "porting-directive.md §1 -- the old shared onpolicy_ext.py core is gone, "
          "docs/REGISTER.md). MYOW positive pairs sampled from the SAME partition, not "
          "neighbouring ones: the reference's own neighbour-selection mechanism is unrunnable as "
          "shipped (an undefined-variable bug, verified directly against ext/ctrl_public/algo.py), "
          "so same-partition sampling is the only evidenced-runnable option, not an invented "
          "simplification."))

register(BaselineSpec(
    name="rad", method="RAD", backbone="sac", status="implemented",
    paper="Laskin et al. 2020, arXiv:2004.14990",
    build=_sac_family("RAD", "rad"),
    notes="SAC plus an augmentation applied to the replay batch -- the augmentation IS the method, "
          "and the previous `class RAD(SAC): pass` had none of it. PROTOCOL DEVIATION: the paper's "
          "random_crop renders at 100x100 and crops to 84; RL-ViGen renders 84 directly, so RAD "
          "uses random_shift (pad 4, crop back) -- the same kind of augmentation at the "
          "resolution the shared protocol fixes. On the SAC backbone, not DrQ-v2: DrQ-v2 already "
          "applies RandomShiftsAug, so RAD-on-DrQ-v2 would be a near-alias of it."))
register(BaselineSpec(
    name="soda", method="SODA", backbone="sac", status="implemented",
    paper="Hansen & Wang 2020, arXiv:2011.13389",
    build=_sac_family("SODA", "soda"), data_requirements=("places365",),
    notes="SAC plus a BYOL-style predictor trained to match augmented and un-augmented views. Its "
          "overlay augmentation needs Places365 AT TRAINING TIME. Same 100->84 resolution "
          "deviation as RAD, declared for the same reason."))

register(BaselineSpec(
    name="alda", method="ALDA", backbone="sac", status="implemented",
    paper="Batra & Sukhatme, ICML 2025, arXiv:2410.07441 "
          "(the brief cites 2001.01046 -- see docs/TASK.md section 6 Q2)",
    build=_alda_build,
    notes="VQ-VAE latent alignment on a SAC backbone, so it uses the same off-policy loop as "
          "everything else here. Algorithm files copied from ../gen-rebuttal/vigen-idaac rather "
          "than imported -- the sibling's own entry points say `from vigen_idaac.envs import ...` "
          "and fail at import in any other tree. Its training and evaluation now go through this "
          "repo's shared trainer and shared evaluator, which is what makes its numbers comparable "
          "with the other baselines'."))

register(BaselineSpec(
    name="idaac", method="IDAAC", backbone="impala", status="implemented",
    paper="Raileanu & Fergus 2021, arXiv:2102.10330", build=_ppo_family("idaac"),
    on_policy=True,
    notes="On-policy: driven by rlgen/trainer_onpolicy.py, which shares this repo's evaluator, "
          "logger, protocol and eval cadence with the off-policy baselines -- only experience "
          "COLLECTION differs, which is the one thing the brief allows to differ. Algorithm files "
          "copied from ../gen-rebuttal/vigen-idaac, where the discrete->continuous and "
          "64->84 adaptations were already made and marked."))

register(BaselineSpec(
    name="ppg", method="Phasic Policy Gradient", backbone="impala", status="implemented",
    paper="Cobbe et al. 2020, arXiv:2009.04416", build=_ppg_hermetic_build, on_policy=True,
    notes="Hermetic module (rlgen/algos/ppg/), not the shared onpolicy_ext.py core, per porting-directive.md SS1 -- switched 2026-08-14 (docs/REGISTER.md). Genuinely separate policy/value encoders (arch=dual, the reference's own confirmed default), a three-term aux-phase loss (policy-KL clone, aux-head distillation, AND continued value-network training) on its own optimizer, one SGD epoch per rollout (not ten), no gradient clipping, no LR decay, unclipped MSE value loss -- five real divergences from the old shared core, all found and fixed this session. DEVIATION: the paper's categorical clone-KL becomes the closed-form Gaussian KL, because this benchmark's policy is a diagonal Gaussian. Not verified against published returns -- nobody has published PPG on RL-ViGen robosuite."))

register(BaselineSpec(
    name="ibac_sni", method="IBAC-SNI", backbone="impala", status="implemented",
    paper="Igl et al. 2019, arXiv:1910.12911", build=_ibac_sni_hermetic_build, on_policy=True,
    notes="Hermetic module (rlgen/algos/ibac_sni/), rebuilt base-first 2026-08-16 from joonleesky/train-procgen-pytorch @ 1678e4a (vendored verbatim at rlgen/algos/ibac_sni/_upstream_1678e4a/), with IBAC-SNI's semantics taken from the AUTHORS' OWN release, ext/IBAC-SNI (microsoft/IBAC-SNI @ 6b3a58b). PPO plus a variational information bottleneck and selective noise injection: SNI averages TWO complete clipped PPO surrogates -- one from the noisy pass, one from the deterministic pass -- at a hardcoded 1/2 (ppo2.py:96-107). CORRECTION 2026-08-16, this note previously said the mix includes 'the value estimate': it does not, and that was advertising a defect as a feature. The reference sets vf_run = vf_train = fc(h_vf,'v',1) under SNI (policies.py:161) -- the value function is entirely deterministic, with the authors' own comment 'VIB for regression seems like a bad idea'. Also corrected: there is no sni_lambda knob (the reference has no such flag), and ~/Downloads/IBAC_SNI_torch is a third party's re-derivation used for wiring only, never as the semantic reference. Full list of what is ours vs the authors': docs/INTEGRATION-DELTA.md. Tier T4 for the algorithm; the only numerical checks are against the PPO host (tests/test_ibac_sni_base_parity.py). Not verified against published returns."))

for _n, _m, _p, _why in [
    ("__removed_ppg", "Phasic Policy Gradient", "Cobbe et al. 2020, arXiv:2009.04416",
     "On-policy, needs a rollout buffer, clipped surrogate and the phasic auxiliary phase. The "
     "previous `ppg.py` had none of these and no update() at all."),
    ("__removed_ibac_sni", "IBAC-SNI", "Igl et al. 2019, arXiv:1910.12911",
     "PPO + variational information bottleneck + selective noise injection. Needs the on-policy "
     "trainer that PPG needs; the reference torch port is ~/Downloads/IBAC_SNI_torch."),
]:
    register(BaselineSpec(name=_n, method=_m, backbone="unassigned", status="absent",
                          paper=_p, build=None, notes=_why))


#: The twelve the supervisor listed, in the brief's order. `tests/test_registry.py` asserts every
#: one has an entry, so a baseline cannot be quietly dropped.
BRIEF_BASELINES = ("ppg", "rad", "ibac_sni", "drq", "drqv2", "curl", "idaac", "alda",
                   "svea", "ctrl", "sgqn", "soda")


def get(name: str) -> BaselineSpec:
    if name not in BASELINES:
        raise KeyError(f"unknown baseline {name!r}. Known: {sorted(BASELINES)}")
    return BASELINES[name]


def runnable() -> list[str]:
    return sorted(n for n, s in BASELINES.items() if s.status in ("implemented", "alias"))


def status_table() -> str:
    rows = [("baseline", "status", "backbone", "method")]
    for n in ["random"] + list(BRIEF_BASELINES):
        s = BASELINES.get(n)
        rows.append((n, s.status if s else "MISSING", s.backbone if s else "-",
                     s.method if s else "-"))
    w = [max(len(r[i]) for r in rows) for i in range(4)]
    out = []
    for i, r in enumerate(rows):
        out.append("  ".join(c.ljust(w[j]) for j, c in enumerate(r)).rstrip())
        if i == 0:
            out.append("  ".join("-" * w[j] for j in range(4)))
    return "\n".join(out)
