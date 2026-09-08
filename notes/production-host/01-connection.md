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
