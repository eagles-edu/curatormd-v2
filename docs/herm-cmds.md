# (^_^)? Available Commands

 │                                                                                              │
 │  Session                                                                                     │
 │  /new                Start a new session (fresh session ID + history) (usage: /new [name])   │
 │  /clear              Clear screen and start a new session                                    │
 │  /redraw             Force a full UI repaint (recovers from terminal drift)                  │
 │  /history            Show conversation history                                               │
 │  /save               Export the current conversation (bare /save shows usage) (usage: /sav…  │
 │  /retry              Retry the last message (resend to agent)                                │
 │  /prompt             Compose your next prompt in $EDITOR (markdown), then send it (usage: …  │
 │  /undo               Back up N user turns and re-prompt (default 1) (usage: /undo [N])       │
 │  /rewind             Rewind to an earlier prompt to edit & resend it, or fork from there (…  │
 │  /title              Set a title for the current session (usage: /title [name])              │
 │  /handoff            Hand off this session to a messaging platform (Telegram, Discord, etc…  │
 │  /branch             Branch the current session (new thread on Discord/Telegram/Slack/Matr…  │
 │  /worktree           Show, list, create, or prune isolated git worktrees (usage: /worktree…  │
 │  /compress           Compress conversation context (add 'here [N]' to keep recent N turns;…  │
 │  /rollback           List or restore filesystem checkpoints (restores keep your hand-edits…  │
 │  /snapshot           Create or restore state snapshots of Hermes config/state (usage: /sna…  │
 │  /stop               Kill all running background processes                                   │
 │  /bg                 Run a prompt in a separate background session (usage: /bg <prompt>)     │
 │  /btw                Ask a side question about the current conversation without interrupti…  │
 │  /agents             Show active agents and running tasks                                    │
 │  /journey            Open the learning journey timeline (usage: /journey [list|delete <id>…  │
 │  /queue              Queue a prompt for the next turn, or list/edit/rm/move/clear queued p…  │
 │  /steer              Inject a message after the next tool call without interrupting (usage…  │
 │  /goal               Set a standing goal Hermes works on across turns until achieved (usag…  │
 │  /heartbeat          Set a recurring prompt that re-enters this session when idle (usage: …  │
 │  /refine             Review this conversation now and save lessons to memory/skills (usage…  │
 │  /review             Spawn an independent subagent to review the work just discussed (PR, …  │
 │  /loop               Re-run a prompt on a recurring interval in this session (usage: /loop…  │
 │  /plan               Write a markdown implementation plan to .hermes/plans/ without execut…  │
 │  /moa                Run one prompt through the default Mixture of Agents preset, then res…  │
 │  /subgoal            Add or manage extra criteria on the active goal (usage: /subgoal [tex…  │
 │  /status             Show session, model, token, and context info                            │
 │  /egress             Show Docker egress proxy status (usage: /egress [status])               │
 │  /context            Show detailed context window view with usage gauge, category breakdow…  │
 │  /resume             Resume a previously-named session (usage: /resume [name])               │
 │  /sessions           Browse and resume previous sessions                                     │
 │                                                                                              │
 │  Configuration                                                                               │
 │  /export             Export a profile (config, skills, theme) to a shareable archive (usag…  │
 │  /import             Import a shared profile archive as a new profile (usage: /import <arc…  │
 │  /config             Show current configuration                                              │
 │  /model              Switch model (session-scoped; --global to persist) (usage: /model [mo…  │
 │  /codex-runtime      Toggle codex app-server runtime for OpenAI/Codex models (usage: /code…  │
 │  /personality        Set a predefined personality (usage: /personality [name])               │
 │  /statusbar          Toggle the context/model status bar                                     │
 │  /battery            Toggle a color-coded battery indicator in the status bar (usage: /bat…  │
 │  /timestamps         Toggle [HH:MM] timestamps on messages and /history (usage: /timestamp…  │
 │  /verbose            Cycle tool progress display: off -> new -> all -> verbose               │
 │  /focus              Toggle focus view — show only your prompt and the final response (usa…  │
 │  /footer             Toggle gateway runtime-metadata footer on final replies (usage: /foot…  │
 │  /yolo               Toggle YOLO mode (skip all dangerous command approvals)                 │
 │  /approvals          Show or set the persistent dangerous-command approval mode (usage: /a…  │
 │  /reasoning          Manage reasoning effort and display (usage: /reasoning [level|show|hi…  │
 │  /fast               Fast mode — OpenAI Priority Processing / Anthropic Fast Mode (normal/…  │
 │  /skin               Show or change the display skin/theme (usage: /skin [name])             │
 │  /indicator          Pick the TUI busy-indicator style (usage: /indicator [ascii|emoji|kao…  │
 │  /voice              Toggle voice mode (usage: /voice [on|off|tts|status])                   │
 │  /wake               Toggle the 'Hey Hermes' wake word listener (usage: /wake [on|off|stat…  │
 │  /busy               Control how messages behave while Hermes is working (usage: /busy [qu…  │
 │  /autoprune          Turn automatic pruning of old sessions on or off (usage: /autoprune […  │
 │                                                                                              │
 │  Info                                                                                        │
 │  /whoami             Show your slash command access (admin / user)                           │
 │  /profile            Show active profile name and home directory                             │
 │  /diff               Show git changes in the working directory (usage: /diff [staged|all|s…  │
 │  /help               Show available commands (/help skills lists skill commands, /help <te…  │
 │  /palette            Open the fuzzy command palette (also Ctrl+P)                            │
 │  /usage              Show token usage and rate limits; `reset` redeems a banked Codex limi…  │
 │  /subscription       View your Nous plan and change it in the browser                        │
 │  /login              Sign in with a Nous account (keeps your connectors)                     │
 │  /topup              Show your Nous balance and manage billing on the portal                 │
 │  /insights           Show usage insights and analytics (usage: /insights [days])             │
 │  /platforms          Show gateway/messaging platform status                                  │
 │  /copy               Copy the last assistant response to clipboard (usage: /copy [number])   │
 │  /paste              Attach clipboard image from your clipboard                              │
 │  /image              Attach a local image file for your next prompt (usage: /image <path>)   │
 │  /update             Update Hermes Agent to the latest version                               │
 │  /version            Show Hermes Agent version                                               │
 │  /debug              Upload debug report (system info + logs) and get shareable links (usa…  │
 │                                                                                              │
 │  Tools & Skills                                                                              │
 │  /tools              Manage tools: /tools [list|disable|enable] [name...] (usage: /tools […  │
 │  /toolsets           List available toolsets                                                 │
 │  /skills             Search, install, inspect, or manage skills                              │
 │  /memory             Review pending memory writes / toggle the approval gate (usage: /memo…  │
 │  /bundles            List skill bundles (aliases /<name> for multiple skills)                │
 │  /pet                Toggle or adopt a petdex mascot (/pet, /pet list, /pet <slug>) (usage…  │
 │  /hatch              Generate a new petdex pet from a description (usage: /hatch [descript…  │
 │  /learn              Learn a reusable skill from anything you describe (dirs, URLs, this c…  │
 │  /init               Generate or update AGENTS.md project instructions from a repo scan (u…  │
 │  /cron               Manage scheduled tasks (usage: /cron [subcommand])                      │
 │  /suggestions        Review suggested automations (accept/dismiss) (usage: /suggestions [a…  │
 │  /blueprint          Set up an automation from a blueprint template (usage: /blueprint [na…  │
 │  /curator            Background skill maintenance (status, run, pin, archive, list-archive…  │
 │  /kanban             Multi-profile collaboration board (tasks, links, comments) (usage: /k…  │
 │  /reload             Reload .env variables into the running session                          │
 │  /reload-mcp         Reload MCP servers from config                                          │
 │  /reload-skills      Re-scan ~/.hermes/skills/ for newly installed or removed skills         │
 │  /browser            Connect browser tools to your live Chromium-family browser via CDP (u…  │
 │  /plugins            List installed plugins and their status (usage: /plugins [update|auto…  │
 │                                                                                              │
 │  Exit                                                                                        │
 │  /quit               Exit the CLI (use --delete to also remove session history) (usage: /q…  │
 │                                                                                              │
 │  TUI                                                                                         │
 │  /density            Toggle compact display mode                                             │
 │  /logs               Show recent gateway log lines                                           │
 │  /mouse              Set mouse tracking preset [on|off|toggle|wheel|buttons|all]             │
 │                                                                                              │
 │  55 skill commands available — /skills to browse                                             │
 │                                                                                              │
 │  TUI                                                                                         │
 │  /connectors         manage connector accounts (rename, add another, reconnect, remove)      │
 │  /details [hidden|collapsed|expanded|cycle]set global agent detail visibility mode           │
 │  /details <section> [hidden|collapsed|expanded|reset]override one section (thinking/tools/…  │
 │  /fortune [random|daily]show a random or daily local fortune                                 │
 │  /grid-test [cols]x[rows]open the interactive widget-grid demo                               │
 │  /dialog-test [zone] open a sample dialog overlay with a faked backdrop                      │
 │                                                                                              │
 │  Hotkeys                                                                                     │
 │  Ctrl+C              copy selection / clear draft / interrupt / exit                         │
 │  Ctrl+D              exit                                                                    │
 │  Ctrl+G / Alt+G      open $EDITOR (Alt+G fallback for VSCode/Cursor)                         │
 │  Ctrl+L              redraw / repaint                                                        │
 │  Alt+V / /paste      paste text; /paste attaches clipboard image                             │
 │  Esc Esc             discard draft (recall with ↑)                                           │
 │  Esc Esc             empty composer, idle: Esc then Esc browses earlier prompts to edit (/…  │
 │  Tab                 apply completion                                                        │
 │  ↑/↓                 completions / queue edit / history                                      │
 │  Ctrl+X              open live session switcher (deletes queued message while editing)       │
 │  Ctrl+T              expand live agents (keeps your draft)                                   │
 │  Ctrl+P              expand / collapse a pasted-text chip (sent pastes when the composer h…  │
 │  Ctrl+R / F7         collapse / restore live agent preview                                   │
 │  Ctrl+O              open model picker (keeps your draft; applies to next turn mid-stream)   │
 │  Ctrl+A/E            home / end of line                                                      │
 │  Ctrl+Z / Ctrl+Y     undo / redo input edits                                                 │
 │  Ctrl+W              delete word                                                             │
 │  Ctrl+U/K            kill to line start / end (repeat across lines)                          │
 │  Ctrl+←/→            jump word                                                               │
 │  Home/End            start / end of line                                                     │
 │  Shift+Enter / Alt+Enterinsert newline                                                       │
 │  \+Enter             multi-line continuation (fallback)                                      │
 │  !<cmd>              run a shell command (e.g. !ls, !git status)                             │
 │  {!<cmd>}            interpolate shell output inline (e.g. "branch is {!git branch --show-…  │
 │                                                                                              │
 ╰──────────────────────────────────────────────────────────────────────────────────────────────╯
