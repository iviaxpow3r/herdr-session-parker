---
name: herdr-session-parker
description: Park and resume agent sessions inside Herdr tabs without manually tracking session IDs. Use when the user asks to park a tab/session, resume a parked tab, list parked sessions, free computer resources, hibernate idle agent panes, or manage Herdr Session Parker.
---

# Herdr Session Parker

Use this skill when Herdr tabs should act like lightweight bookmarks for expensive running agent panes.

## Plugin basics

Install:

```bash
herdr plugin install iviaxpow3r/herdr-session-parker
```

Plugin id:

```text
herdr-session-parker
```

Runtime registry:

```text
~/.local/state/herdr/plugins/herdr-session-parker/parked-sessions.json
```

The registry can contain local paths, tab labels, session IDs, and captured foreground commands. Do not publish a user's registry.

## Actions

```bash
herdr plugin action list --plugin herdr-session-parker
herdr plugin action invoke herdr-session-parker.list-parked
herdr plugin action invoke herdr-session-parker.snapshot-current
herdr plugin action invoke herdr-session-parker.park-current-pane
herdr plugin action invoke herdr-session-parker.park-current-tab
herdr plugin action invoke herdr-session-parker.resume-current
```

## Agent workflow

Before parking/resuming:

```bash
herdr status
herdr pane list
herdr agent list
herdr plugin action list --plugin herdr-session-parker
```

For automatic resume, target panes need a supported Herdr `agent_session.value`. If OpenCode is missing a session id, install/reinstall the Herdr integration and restart/resume the pane first:

```bash
herdr integration install opencode
herdr integration status
```

## Park current pane

If the user asks “park this pane”, “hibernate this agent”, or “free resources for this session”:

1. Confirm which Herdr tab/pane is targeted if ambiguous.
2. Snapshot first when the session is important:

```bash
herdr plugin action invoke herdr-session-parker.snapshot-current
```

3. Do not park a `working` pane unless the user explicitly confirms interruption is safe.
4. Park:

```bash
herdr plugin action invoke herdr-session-parker.park-current-pane
```

## Park current tab

If the user asks “park this tab”, use:

```bash
herdr plugin action invoke herdr-session-parker.park-current-tab
```

This records every pane in the tab, creates one marker pane, and closes the original panes. Unsupported processes become manual-only records.

## Resume current tab/session

If the user asks “resume this tab”:

```bash
herdr plugin action invoke herdr-session-parker.resume-current
```

Verify:

```bash
herdr pane read <pane_id> --source recent-unwrapped --lines 80
herdr agent list
```

## List and filter parked sessions

```bash
herdr plugin action invoke herdr-session-parker.list-parked
```

For current-tab prioritization, locate the plugin root with `herdr plugin list --plugin herdr-session-parker --json`, then run:

```bash
python3 /path/to/session_parker.py list --current
python3 /path/to/session_parker.py list --workspace "Workspace Label"
python3 /path/to/session_parker.py list --tab "Tab Label"
```

## Safety rules

- Never park/close a `working` pane without explicit confirmation.
- Never close a pane until cwd, workspace label, tab label, and either session id or foreground process info are recorded.
- Prefer `snapshot-current` before `park-current-pane` or `park-current-tab` when the session matters.
- Do not require the user to remember or paste session IDs unless the registry is missing/corrupt.
- If multiple parked sessions match a tab label, list records and ask which one to resume.
