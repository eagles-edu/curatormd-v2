# PLEASE CHECK ALL SYSTEMS, PROFILES, LOGS, CRONS, SKILLS, PLUGINS, MCPS, CONFIGS ,SYSTEMS

DEFAUT PROFILE SHOULD BE CONFIGURED AND AGGRESSIVELY MAINTAINING THIS SERVERS' PERFORMANCE,
FREE SSD SPACE, BLOAT, ENSURING OPTIMUM OPERATIONS - PLUGINGS, SKILLS, MCPs MUST BE CHOSEN FOR
THIS THOUGHFULLY & COMPREHENSIELY, ASA WELL AS CULLING UNUSED, SUPERFLUOUS BLOAT. LIKEWISE,
CURATORMD2 PROFILES SHOULD BE FREE OF UNUSED, SUPERFLUOUS BLOAT, FOCUSED ON CMD2 FUNCTIONS AND
THEIR CONFIGURATIONS NORMALIZED THE SAME. ASK, DEELY RESEARCH OPTIIZATION OF HERMES, SERIOULY
PROMOTE DISK SPACE, PERFORMANCE, STABILITY BEST PRACTICES -

└─ Response

┊ The disk is critically tight: / is 96% used, with 2.7 GB free. Hermes accounts for about 13
GB under ~/.hermes; its largest areas are installs (3.7 GB), tools (3.6 GB), and cache (1.9
GB). The root filesystem also has about 3.5 GiB of swap in use. These are audit findings—not
authorization to delete anything.

    A few safety and performance points from the audit:

    • The gateway is running, and CuratorMD2 processes point at
    /home/eaglesvn/dockerz/curatormd-v2.0. The Hermes checkout that AGENTS.md protects also has a
    local modification; I did not touch it.
    • Some Hermes tool directories are large staging folders. They may be in use, so they need
    process/lease checks before cleanup.
    • Hermes’ documented pm gc removes eligible unreferenced artifacts; it does not justify
    manually deleting installs/ or tools/. Official guidance also supports ordinary uv cache
    prune for recoverable cache entries. (hermes-agent.nousresearch.com)
    • For gateway memory, Hermes documents bounds for its per-session agent cache. MCP servers
    can also be lazy-started, and discovery concurrency can be limited—useful options to evaluate
    after identifying what each profile needs. (hermes-agent.nousresearch.com)
    • Profiles are isolated, and bundled skills sync across profiles during updates; deleting or
    disabling them blindly could affect other workflows. (hermes-agent.nousresearch.com)

    No cleanup or configuration changes were made. One unplanned side effect: hermes profile list
    triggered Hermes’ automatic source/skill update, which reported updating bundled skills
    across profiles, then timed out while preparing the Computer Use dependency. I’ll avoid
    further Hermes CLI commands that trigger that path until we decide how to proceed.

    The clarification prompt timed out unanswered, so I still need your policy before making
    changes: which profiles to include, what capabilities must stay enabled in default, and
    whether routine cleanup may run automatically. The conservative starting point is to audit
    profiles first, then—once approved—use only verified, recoverable cache/PM cleanup, and
    present a per-profile proposal before culling skills, plugins, MCPs, or dependencies.

───

❯ reclaim in all profiles al reclaimable cache/stle session space; check what's taking install
space, cull hogs i dont use, ...then timed out while preparing the Computer Use dependency -
fix; thprough audit of ALL BLOAT!

───

❯ [STILL IN PROGRESS — this is the active request, restated after the compaction boundary
because it was not finished yet. Continue it; do not start over.]
reclaim in all profiles al reclaimable cache/stle session space; check what's taking install
space, cull hogs i dont use, ...then timed out while preparing the Computer Use dependency -
fix; thprough audit of ALL BLOAT!

└─ ▾ Tool calls (21)
├─ ● Terminal("printf '== CUA CLI health ==\n' + 10 commands")
├─ ● Terminal("printf '== All-profile stale-session dry-run (90 days) ==\n' + …")
├─ ● Terminal("printf '== Managed install generations and leases ==\n' + 12 co…")
├─ ● Tool Search("Searching tools · session search conversation history query ful…")
├─ ● Tool Describe("Reading tool details · 1 tool")
├─ ● Tool Call("Searching past sessions")
├─ ● Tool Call("Searching past sessions")
├─ ● Skill View("hermes-agent")
├─ ● Read File("update_lock.py")
├─ ● Read File("source_completion.py")
├─ ● Read File("venv_sync.py")
├─ ● Read File("hermes_bootstrap.py L540-659")
├─ ● Terminal("python3 -c 'import os,pathlib,time,datetime,json; roots=[pathli…")
├─ ● Skill View("hermes-agent → references/troubleshooting.md")
├─ ● Skill View("hermes-agent → references/cli-reference.md")
├─ ● Terminal("printf '== Update-owner and child processes ==\n' + 5 commands")
├─ ● Tool Call("Searching past sessions")
├─ ● Terminal("git -C /usr/local/lib/hermes-agent status --short --branch + 7 …")
├─ ● Terminal("do printf '\n=== %s PM doctor ===\n' "$p" if [ "$p" = default ]…")
├─ ● Terminal("printf '== Top-level Hermes tool-store consumers ==\n' + 7 comm…")
└─ ● Clarify("May I take a short maintenance window to stop/restart the gatew…")

└─ Response

┊ Partial cleanup completed; the runtime still needs a safe maintenance pass. I stopped before
restarting services or removing optional workloads because the approval prompt timed out.

    Completed

    • Enabled automatic session pruning in all five profiles, including setting
    sessions.auto_prune: true for curatormd-v2-dev-alpha. The effective retention is 90 days. A
    dry run found no sessions older than the cutoff (August 16, 2026), so no session history was
    deleted. Hermes only prunes eligible ended/stale sessions; its documented automatic VACUUM
    also has safeguards to avoid rewriting a dense database too often.
    (hermes-agent.nousresearch.com)
    • Pruned the Hermes uv cache: 90 files / about 1.1 MiB removed. The latest pnpm prune found
    nothing eligible.
    • Computer Use’s cua-driver 0.21.0 is installed and its runtime contract reports ready. Its
    doctor check is still degraded: this host has neither reachable X11 nor a Wayland display, so
    it cannot capture or control a desktop here. That’s a display limitation, not a missing
    driver dependency. (hermes-agent.nousresearch.com)
    • Inventoried plugins and MCP names across the five profiles; I did not remove any. The
    plugin directories total only about 2.4 MiB, and the skill files are small compared with the
    install/runtime footprint. I can’t infer non-use from a component being installed or
    disabled.

    Space and performance findings

    • / is currently 91% used, with 5.7 GiB available. The earlier recorded baseline was 96% used
    with about 2.7 GiB available.
    • ~/.hermes is about 11 GiB: roughly 3.6 GiB installs, 2.4 GiB tools, 1.7 GiB caches, and 2.6
    GiB source checkout.
    • The largest plausible reclaim targets are unselected Python generations and test
    environments: the main install has about 832 MiB in an older environment and 933 MiB across
    test-environment generations. The tools store also contains 393 MiB of Python 3.14.7, 255 MiB
    of Python 3.14.9, 438 MiB of FFmpeg, 364 MiB of Chromium, and two Node versions around 220
    MiB each. Hermes’ supported pm gc is designed to remove eligible unreferenced tools and
    unleased generations; I will not manually delete these directories.
    (hermes-agent.nousresearch.com)
    • The gateway was using about 695 MiB RAM, with 4.1 GiB swap in use at the last check. The
    system has about 4.1 GiB RAM available; swap use is worth monitoring.

    Still unresolved

    Package state is not stable yet. Immediately after reinstalling Node, Python, and uv, hermes
    pm doctor passed for the default and Curator profiles. Later profile commands again
    reported Node out of sync. The shared tool facts currently reflect Node 26.7.0 / Python
    3.14.7 / uv 0.12.3, while the installed release expects Node 26.12.1 / Python 3.14.9 / uv
    0.13.5. There is also a pending source-completion record in install state 9fbb…. This
    appears to involve two Hermes checkouts sharing runtime state; both have local changes, so I
    left them untouched. The global update check reported the installed release is already
    current.

    Session database optimization was refused because the live dashboard and gateway were using
    the database. Hermes explicitly refuses that rewrite under live writers; I did not force it.
    (hermes-agent.nousresearch.com) The final all-profile verification command also did not run
    because its approval prompt timed out.

    To finish safely, reply “maintenance window approved” if I may briefly stop/restart the
    gateway and dashboard, and tell me which workloads you want to keep: local Whisper/STT/voice,
    FFmpeg/media, Browser/Computer Use, and Hermes test environments. Until then, I’ll leave
    those workloads and the live services unchanged.

## Hermes source Git object footprint — 2026-11-14

The checkout at `/home/eaglesvn/.hermes/hermes-agent` had 1.1 GiB in `.git/objects`. The
`fork` remote already used the blobless partial-clone filter, but `origin` did not. Its reflog
showed an unfiltered `fetch origin main` on November 7, which populated the oversized object
store.

I replaced only the Git metadata with a single-branch clone of the existing branch using
`--filter=blob:none`. The checkout remains at commit `6d9760ba0de6c2f7e4375cb51e7353d49742b0a7`,
and the pre-existing edit in `tools/curator_v2_health.py` is unchanged. The active object store is
152 MiB after fetching upstream `main`; connectivity-only `git fsck` passed. Both `origin` and
`fork` now have `promisor=true` and `partialclonefilter=blob:none`. After confirming the retired
metadata copy had no refs, index entries, reachable objects, or live process users, I removed its
orphaned 269.8 MiB promisor pack. Only 16 KiB of metadata remains there. The active object store
is down about 0.95 GiB from the original checkout.

Keep those two remote filter settings on this checkout. Use
`git fetch --filter=blob:none --no-tags origin main` for explicit upstream fetches. Fresh source
clones should use `git clone --filter=blob:none --single-branch`; do not fetch every fork branch
unless they are needed locally. Hermes' installer already documents blobless clones, and the
promisor filter on `origin` makes updater fetches follow the same policy.
