# Connection

Source: `~/Downloads/Netbird Guide - Center for Cognitive Modeling.pdf`, from
`wiki.cogmodel.mipt.ru`. Netbird is **already configured on this machine** — nothing below needs
installing or re-running unless the connection is actually down.

## Commands the guide gives

```
netbird status                 # check connectivity -- this is the only one to reach for by default
netbird up                     # reconnect (a configured client needs no key)
netbird down                   # disconnect
ssh <username>@<ip-or-domain>
```

Installation and key enrolment are in the guide and are **not our step**: they need an admin, and
the key is issued per person and hostname. If the client were ever not configured, that is a stop
and a message to the administrator, not something to set up.

## The verified connection command

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 varaksin_as@100.98.2.11 <command>
```

Verified working 2026-09-08 12:22 UTC+3 (09:22 UTC): returned `/home/varaksin_as`, exit 0.

Every part of it was established from evidence rather than guessed, and that matters because a
wrong guess here produces failed authentications, which is what actually looks hostile:

- **`varaksin_as`** — from shell history, used repeatedly against this exact IP. Not inferred from
  a name.
- **`100.98.2.11`, by IP** — the form already in `~/.ssh/known_hosts` (line 70) and the form used
  historically. `cds2.cogmodel.mipt` is **not** in `known_hosts`, so connecting by domain would
  prompt for a new host key. Use the IP; there is no reason to accept a second key form for the
  same machine.
- **`BatchMode=yes`** — never prompts for a password. If key auth is unavailable it fails
  immediately instead of prompting, hanging a non-interactive session, or producing repeated
  password attempts. Repeated auth failures are exactly the pattern that gets an account flagged.
- **`ConnectTimeout=10`** — bounded, so a network problem fails fast rather than hanging.
- **No `-v`.** Verbose output on a shared host adds nothing and looks like probing.
- **Do not add `StrictHostKeyChecking=accept-new`.** The key is already known; under `BatchMode` a
  *changed* key correctly fails rather than being silently accepted, which is the behaviour we
  want.

Prefer a **single non-interactive command** over an interactive shell where possible: it is
bounded, it is auditable, and it cannot leave a stray session holding resources.

## The post-quantum warning is expected, and is NOT to be acted on

The connection prints:

```
** WARNING: connection is not using a post-quantum key exchange algorithm.
** The server may need to be upgraded. See https://openssh.com/pq.html
```

This is the local client observing the server's OpenSSH version. It is informational, the
connection is otherwise normal, and **it must not be treated as a task.** Upgrading OpenSSH — or
anything else — on that host is prohibited outright (`02-absolute-prohibitions.md`). Note it and
move on.

## Address table, reproduced for identification only

| server | IP | domain |
|---|---|---|
| aicenter1 | 100.98.208.203 | aicenter1-208-203.cogmodel.mipt |
| aicenteritl | 100.98.50.236 | aicenteritl.cogmodel.mipt |
| ccmplanner | 100.98.148.137 | ccmplanner-148-137.cogmodel.mipt |
| **cds2** | **100.98.2.11** | **cds2.cogmodel.mipt** |
| cdsserver | 100.98.28.73 | cdsserver.cogmodel.mipt |
| aicenter2 | 100.98.59.202 | aicenter2.cogmodel.mipt |
| aicenter3 | — | — |

**This table is here so `cds2` can be identified and the others recognised as NOT ours.** See
`00-authority-and-scope.md`. Reachability is not permission.

## Session discipline

A long run must survive a dropped SSH session: `tmux` (or `nohup`), never a bare foreground
command. A VPN blip that kills a 45-hour cell wastes the GPU-hours of whoever was queued behind it
as well as ours.
