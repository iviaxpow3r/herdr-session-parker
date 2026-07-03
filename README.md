# Herdr Session Parker

Park Herdr panes or whole tabs, free the running process resources, and resume supported agent sessions later without manually remembering session IDs.

## The problem

Agent terminals are useful, but they are not free. If you keep several OpenCode, Claude Code, Codex, or other agent panes running in [Herdr](https://herdr.dev/), each pane can keep a real process, child tools, MCP servers, and memory alive even when the work is idle.

The obvious fix is to close idle panes. The problem is that once you close a pane, it is easy to forget:

- what was running there
- which project directory it belonged to
- which Herdr tab/workspace it lived in
- which native agent session ID you need to resume it later

So people leave everything running just to avoid losing context.

## The solution

Herdr Session Parker lets you treat a Herdr tab like a lightweight bookmark.

When you park a pane or tab, the plugin records what was there, saves the session/cwd/tab metadata, leaves a small marker pane behind, and closes the expensive running process. Later, you can list parked sessions or resume the matching one from the current tab without remembering the session ID yourself.

In short:

```text
park = remember what was here + free the resources
resume = bring the saved agent session back when needed
```

## What it does

- Captures the current Herdr workspace, tab, pane, cwd, agent status, and foreground process metadata.
- Captures native agent session IDs when Herdr integrations report them.
- Creates a lightweight marker shell pane before closing parked pane(s).
- Resumes supported agent sessions in the current tab later.
- Stores state in Herdr's plugin state directory, not in the repository checkout.

## Supported automatic resume providers

Session Parker currently ships resume templates for:

- OpenCode: `opencode --session <id>`
- Claude Code: `claude --resume <id>`
- Codex: `codex resume <id>`
- GitHub Copilot CLI: `copilot --resume=<id>`
- Cursor Agent CLI: `cursor-agent --resume <id>`
- Devin CLI: `devin --resume <id>`
- Droid: `droid --resume <id>`
- Hermes Agent: `hermes --resume <id>`
- Kilo Code CLI: `kilo --session <id>`
- Kimi Code CLI: `kimi --session <id>`
- OMP: `omp --resume=<id>`
- Pi: `pi --session <id>`
- Qoder CLI: `qodercli --resume <id>`

Automatic resume only works when Herdr has an `agent_session.value` for the pane. Install the relevant Herdr integration first, then start/restart the agent pane so it can report session identity.

For OpenCode:

```bash
herdr integration install opencode
herdr integration status
```

## Install

From GitHub:

```bash
herdr plugin install iviaxpow3r/herdr-session-parker
```

For local development:

```bash
git clone https://github.com/iviaxpow3r/herdr-session-parker.git
herdr plugin link ./herdr-session-parker
```

Verify:

```bash
herdr plugin action list --plugin herdr-session-parker
```

## Actions

```bash
herdr plugin action invoke herdr-session-parker.list-parked
herdr plugin action invoke herdr-session-parker.snapshot-current
herdr plugin action invoke herdr-session-parker.park-current-pane
herdr plugin action invoke herdr-session-parker.park-current-tab
herdr plugin action invoke herdr-session-parker.resume-current
```

### `snapshot-current`

Records the current pane metadata without closing anything. Useful before parking important sessions.

### `park-current-pane`

Records the current pane, creates a lightweight marker shell pane, then closes the original pane.

If the pane is `working`, the plugin refuses to park it unless the direct script is run with `--force` after explicit confirmation.

### `park-current-tab`

Records every pane in the current tab, creates one marker shell pane, then closes the original panes.

### `resume-current`

Finds parked records matching the current tab first, then resumes the matching supported agent session in the current pane.

If multiple sessions match, it lists them and asks you to choose by session id.

### `list-parked`

Prints the registry path and all saved parked/snapshotted sessions.

## Direct script usage

The Herdr action surface is intentionally simple. For automation or agent workflows, call the script directly from the plugin root:

```bash
python3 session_parker.py list --current
python3 session_parker.py list --workspace "Content Jams"
python3 session_parker.py list --tab "agent"
python3 session_parker.py park-current-pane --pane w1:p1 --dry-run
python3 session_parker.py park-current-tab --pane w1:p1 --dry-run
python3 session_parker.py resume-current --pane w1:p2 --session-id ses_abc123 --dry-run
```

## Targeting non-current tabs without stealing focus

The Herdr plugin actions operate on the currently focused Herdr context. Use them only when you truly mean “the tab I am in right now.”

When an agent needs to park or resume a different tab, use the direct script with `--pane <pane_id>`. The script resolves the pane's workspace/tab from Herdr state and does not need to focus that tab first.

Recommended non-current workflow:

1. Identify the target from Herdr state:

```bash
herdr tab list
herdr pane list
```

2. Dry-run the exact targeted operation:

```bash
python3 session_parker.py snapshot-current --pane <pane_id> --dry-run
python3 session_parker.py park-current-tab --pane <pane_id> --dry-run
python3 session_parker.py resume-current --pane <pane_id> --dry-run
```

3. Confirm the dry-run output shows the intended workspace, tab, and pane.

4. Run the same command without `--dry-run` only after confirming the target:

```bash
python3 session_parker.py park-current-tab --pane <pane_id>
```

For working panes, parking still requires explicit operator intent:

```bash
python3 session_parker.py park-current-tab --pane <pane_id> --allow-working
```

Aliases are available for targeted workflows:

```bash
python3 session_parker.py snapshot-pane --pane <pane_id> --dry-run
python3 session_parker.py park-pane --pane <pane_id> --dry-run
python3 session_parker.py park-tab --pane <pane_id> --dry-run
python3 session_parker.py resume-pane --pane <pane_id> --dry-run
```

## State and privacy

The plugin writes runtime state to:

```text
~/.local/state/herdr/plugins/herdr-session-parker/parked-sessions.json
```

The registry can contain:

- local paths
- tab/workspace labels
- agent session ids
- foreground process command lines captured at park time

Do not publish your local registry file. This repository's `.gitignore` excludes common runtime state files.

## Agent skill

This repo includes an optional agent skill at:

```text
agent-skill/herdr-session-parker/SKILL.md
```

Install it in an OpenCode-style agent skill directory:

```bash
mkdir -p ~/.agents/skills
cp -R agent-skill/herdr-session-parker ~/.agents/skills/herdr-session-parker
mkdir -p ~/.config/opencode/skill ~/.config/opencode/skills
ln -s ~/.agents/skills/herdr-session-parker ~/.config/opencode/skill/herdr-session-parker
ln -s ~/.agents/skills/herdr-session-parker ~/.config/opencode/skills/herdr-session-parker
```

Then agents can respond to requests like:

- “park this tab”
- “resume this tab”
- “show parked sessions for this space”
- “free resources by hibernating idle agent panes”

## Safety model

- Parking is process-stopping. It closes Herdr pane(s) after recording metadata.
- `working` panes are refused by default.
- Manual-only records are allowed for unsupported processes, but they cannot be resumed automatically.
- Always inspect `list-parked` before deleting registry records.

## Marketplace listing

Herdr indexes public GitHub repositories tagged with the `herdr-plugin` topic at [herdr.dev/plugins](https://herdr.dev/plugins/). This repo is intended to be installable with:

```bash
herdr plugin install iviaxpow3r/herdr-session-parker
```
