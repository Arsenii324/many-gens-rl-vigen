# Privacy, and not looking like an attacker

On a shared research machine, some perfectly ordinary commands read as reconnaissance. The point is
not only that inspecting other people's work is wrong — it is that being *seen* doing it costs the
account, and the project with it.

## Do not

- **`ps aux`** or any full process listing. It enumerates every user's running work.
- Read, list or traverse other users' home directories, scratch space or output paths
- `docker inspect` / `docker logs` / `docker exec` on containers that are not ours
- Read other users' container images, volumes or configuration
- Port scanning, host sweeps, or connecting to machines outside the one authorised (`00`)
- Anything that enumerates the machine's users, keys or credentials

## Instead

- Scope every query to our own things: our container by its known name, our directories by their
  known paths.
- For resources, use the aggregate views that exist for it — `nvidia-smi` for the GPU, `df` for the
  filesystem we are writing to, `free` for memory totals. These answer "is there room" without
  enumerating who is using it.
- When a resource is occupied, that is the whole answer. **Do not investigate whose it is or what
  it is doing.** "Card 0 is busy, use card 1 or wait" is complete; going further is the part that
  looks malicious.

## If something unexpected appears

A container we do not recognise, a file we did not write, a process using our expected resource —
leave it alone and report it. Do not investigate, do not clean it up, do not "just check what it
is". Curiosity is indistinguishable from probing from the outside.
