"""Pin SODA's effective source contract at the production seam.

These are source-level guards. They do not pretend to prove CUDA training, but they prevent the
generic dmc_gb launcher from silently replacing the official SODA profile with argparse defaults.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(*parts):
    return (ROOT.joinpath(*parts)).read_text()


def test_production_launcher_preserves_official_soda_auxiliary_lr():
    official = _text("ext", "dmcontrol-generalization-benchmark", "scripts", "soda.sh")
    launcher = _text("runnable", "_launch", "dmc_gb.sh")

    assert "--aux_lr 3e-4" in official
    assert 'if [[ "$ALGO" == "soda" ]]' in launcher
    assert "ALGO_ARGS+=(--aux_lr 3e-4)" in launcher
    assert '"${ALGO_ARGS[@]}" "$@"' in launcher


def test_soda_source_path_keeps_policy_raw_and_auxiliary_augmented_streams():
    soda = _text("runnable", "dmc_gb", "src", "algorithms", "soda.py")
    replay = _text("runnable", "dmc_gb", "src", "utils.py")

    assert "obs, action, reward, next_obs, not_done = replay_buffer.sample()" in soda
    assert "x = replay_buffer.sample_soda(self.soda_batch_size)" in soda
    assert "x = augmentations.random_crop(x)" in soda
    assert "aug_x = augmentations.random_crop(aug_x)" in soda
    assert "aug_x = augmentations.random_overlay(aug_x)" in soda
    assert "if step % self.aux_update_freq == 0" in soda
    assert "obs = augmentations.random_crop(obs)" in replay
    assert "next_obs = augmentations.random_crop(next_obs)" in replay


def test_soda_geometry_and_auxiliary_values_are_source_pinned():
    args = _text("runnable", "dmc_gb", "src", "arguments.py")
    soda = _text("runnable", "dmc_gb", "src", "algorithms", "soda.py")
    wrappers = _text("runnable", "dmc_gb", "src", "env", "wrappers.py")

    assert "parser.add_argument('--frame_stack', default=3" in args
    assert "parser.add_argument('--soda_batch_size', default=256" in args
    assert "parser.add_argument('--soda_tau', default=0.005" in args
    assert "if args.algorithm in {'rad', 'curl', 'pad', 'soda'}:" in args
    assert "args.image_size = 100" in args
    assert "assert x.size(-1) == 100" in soda
    assert "self.aux_update_freq = args.aux_update_freq" in soda
    assert "self.soda_optimizer = torch.optim.Adam" in soda
    assert "return FrameStack(env, frame_stack)" in wrappers


def test_soda_eval_is_policy_only_and_deterministic():
    train = _text("runnable", "dmc_gb", "src", "train.py")
    evaluator = _text("scripts", "eval_grid.py")

    assert "action = agent.select_action(obs)" in train
    assert "action = agent.sample_action(obs)" not in train[train.index("def evaluate"):train.index("def evaluate") + 1800]
    assert "with torch.no_grad(), utils.eval_mode(agent):" in evaluator
    assert "action = agent.select_action(obs)" in evaluator
