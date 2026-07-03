# Security notes

Herdr Session Parker is a local workflow plugin. It runs as the current user and calls the local `herdr` CLI.

## Data stored locally

The runtime registry is stored under Herdr's plugin state directory:

```text
~/.local/state/herdr/plugins/herdr-session-parker/parked-sessions.json
```

It may contain local paths, tab labels, native agent session IDs, and captured foreground process command lines. Treat it as local state, not as shareable configuration.

## Network behavior

The plugin itself makes no network requests. It may resume an agent command such as `opencode --session <id>`; that resumed agent may use network access according to its own behavior.

## Process behavior

Parking closes Herdr pane processes after recording metadata. `working` panes are refused by default unless the direct script is run with `--force` after explicit user confirmation.
