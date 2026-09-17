# 35 — What the remaining campaign costs, at rates we have actually measured

**2026-09-17, 21:30 MSK.** Written because the campaign is counted in cells (36) and run in hours,
and nobody had put the two together with measured numbers. Every figure below is either measured on
this host or labelled as unknown. No figure is extrapolated silently.

## What a cell costs, measured

Wall clock from launch to `NATIVE_CELL_COMPLETED`, for the two cells that completed here:

| cell | bootstrap | training (`time -v`) | in-cell grid | total |
|---|---|---|---|---|
| `ibac_sni` s101 (16–17 Sep) | ~13 min | 31 min 32 s | ~13.9 h | **14 h 41 m** |
| `idaac` s102 (16–17 Sep) | ~22 min | 7 h 15 m 18 s | ~13.6 h | **21 h 11 m** |

Both shared card 1 with each other and with a co-tenant for part of the time, so these are
*achieved* rates on a shared card, which is the only rate that matters for planning here.

**The grid, not the training, is the cost.** It is a fixed 3,476 episodes whatever produced the
checkpoints, and it took 13.6 and 13.9 hours in the two cells. Training ranged from 0.5 h to 7.3 h.

**What is not measured, and must not be guessed:** the grid's per-episode cost at other render
sizes (the RL-ViGen five render 84×84 and `rad`/`soda` 100→84, against 64×64 for the three that have
run), and training time for any of the nine baselines that have never trained here. The off-policy
five update every step against a replay buffer; there is no basis in our own data for their rate.

## What has been achieved per day

Production cells that completed and were collected on this host: `idaac` s101 and `ppg` s1 on
9 Sep, `ibac_sni` s101 and `idaac` s102 on 16–17 Sep. That is **4 cells over 9 calendar days**,
against **eight** failed attempts: seven stopped by the memory floor when the co-tenant
returned, one killed by an EGL worker dying 24 s in.

The binding constraint is not throughput. It is **card availability under the ten-minute vacancy
rule**: we hold one card of two, shared, and a cell needs its memory to stay free for 15–21 hours.

## The arithmetic for what is left

32 cells are MISSING and one is PARTIAL. At the measured 15–21 hours per cell:

- **Serially, one cell at a time:** 480–670 hours of cell time ≈ **20–28 days** of uninterrupted
  card time, before counting a single failed attempt.
- **Two cells packed on one card** (measured throughput ratio r = 0.90 for two and three cells):
  roughly **11–16 days**, again uninterrupted.
- **At the rate actually achieved** — 4 cells in 9 days, including the failures and the days spent
  on defects — 32 cells is **about 70 days**.

None of those fits the time available. This is not a scheduling problem to be solved by working
harder on the host; **the full 36-cell campaign cannot be completed here**, and a subset has to be
chosen deliberately rather than by whichever cell happened to fit a window.

## What I would prioritise, and why

This is my recommendation, not a decision taken: the scope belongs to the owner.

**Finish the sampled-estimand block first: `idaac`, `ppg`, `ibac_sni` at three seeds each.**

- Those three are the only families that report a **sampled** return, and
  `scripts/comparison_blocks.py`, run on 2026-09-17, prints exactly their three pairs as the
  PRIMARY set of the on-policy block:

      on-policy PPO, differing in what regularizes it
        6 pairs: 3 primary, 3 descriptive (RAW RETURN)
          PRIMARY      idaac vs ibac_sni
          PRIMARY      idaac vs ppg
          PRIMARY      ibac_sni vs ppg
          descriptive  idaac vs ctrl   (differs on: policy mode)

  So finishing these three completes a whole primary block rather than a fragment of one. See
  `docs/COMPARABILITY_CONTRACT.md` and OPERATOR-GUIDE §4c.
- Three of the nine are already banked (`idaac` s101, `idaac` s102, `ibac_sni` s101) and `ppg` s1
  is banked at an off-schedule seed, which is an open owner item rather than a rerun.
- The remaining cells are the cheapest we have measured: `ibac_sni` trains in half an hour and
  `idaac` in 5–7 hours, against an unknown and probably larger cost for every other family.
- **What it buys:** the first result with a real seed spread — three baselines × three seeds, on
  identical axes. Today's two-seed `idaac` reading already showed why that matters: the
  train → eval-easy gap changed *sign* between seeds (note 34), so nothing about cross-baseline
  ranking can be said at n = 1.

Concretely, in order: `idaac` s103 (makes the first baseline at n = 3), `ibac_sni` s102 rerun from
zero, `ibac_sni` s103, then `ppg`'s two remaining seeds. **Five cells**; at measured rates and with
windows like today's, that is on the order of a week, not a day.

**If there is time after that**, the same tool names the next target: the off-policy block has
7 primary pairs, and the cheapest entry into it is `drqv2` with `drq`, a PRIMARY pair that needs
**no Places365** — only a payload shipped (O2) and a first cell of a family that has never trained
here, whose cost is unknown (O3). `rad` with `soda` is also PRIMARY, but `soda` needs the corpus.

**What that leaves undone, stated rather than hidden:** the nine baselines with no production
record — `drqv2`, `svea`, `drq`, `sgqn`, `curl`, `rad`, `soda`, `alda`, `ctrl`. Three of them are
blocked on Places365 (OPERATOR-GUIDE §11.4 O1), `ctrl` needs an empty card (O4), and the rest need a
payload shipped and a first cell that nobody has ever run (O2, O3). A report that draws a
generalisation conclusion from the sampled block alone must say that it covers three of twelve
baselines, all of them on-policy, and none of the augmentation-based methods the benchmark exists
to compare.
