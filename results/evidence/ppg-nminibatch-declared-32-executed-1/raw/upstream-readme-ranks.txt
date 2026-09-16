# evidence-slug: ppg-nminibatch-declared-32-executed-1
# excerpt: upstream-readme-ranks
# note: the released PPG results were produced with 4 MPI ranks
# source-kind: repo-file
# source: ext/phasic-policy-gradient/README.md
# source-bytes: 2552  source-sha256: 2811087d2a8ef65f77f6e27157e776f43a47ca4cca108718c9956c1c566d1226  source-mtime: 
# extraction: cat ext/phasic-policy-gradient/README.md | grep -n -E mpiexec | head -n 1
# matched-lines: 7  shown-lines: 1  (TRUNCATED -- the excerpt is capped; matched-lines is the full count)
# captured-at: 2026-09-16T10:45:59+00:00
#---------------------------------------------------------------------------------------------------
34:mpiexec -np 4 python -m phasic_policy_gradient.train
