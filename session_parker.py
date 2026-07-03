#!/usr/bin/env python3
"""Herdr Session Parker.

Shareable Herdr plugin for parking panes/tabs and restoring supported agent
sessions later. The plugin stores durable metadata in
HERDR_PLUGIN_STATE_DIR/parked-sessions.json.

Supported automatic resume providers are intentionally template-based so more
agents can be added without changing the registry shape.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any


PLUGIN_ID = "herdr-session-parker"

RESUME_TEMPLATES = {
    "opencode": "opencode --session {session_id}",
    "claude": "claude --resume {session_id}",
    "codex": "codex resume {session_id}",
    "copilot": "copilot --resume={session_id}",
    "cursor": "cursor-agent --resume {session_id}",
    "cursor-agent": "cursor-agent --resume {session_id}",
    "devin": "devin --resume {session_id}",
    "droid": "droid --resume {session_id}",
    "hermes": "hermes --resume {session_id}",
    "kilo": "kilo --session {session_id}",
    "kimi": "kimi --session {session_id}",
    "omp": "omp --resume={session_id}",
    "pi": "pi --session {session_id}",
    "qodercli": "qodercli --resume {session_id}",
}


def herdr_bin() -> str:
    return os.environ.get("HERDR_BIN_PATH") or "herdr"


def state_dir() -> Path:
    raw = os.environ.get("HERDR_PLUGIN_STATE_DIR")
    if raw:
        path = Path(raw)
    else:
        path = Path.home() / ".local" / "state" / "herdr" / "plugins" / PLUGIN_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def registry_path() -> Path:
    return state_dir() / "parked-sessions.json"


def run_herdr(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [herdr_bin(), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit(f"herdr {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"herdr {' '.join(args)} returned non-JSON output: {proc.stdout.strip()}") from exc


def run_herdr_text(*args: str) -> str:
    proc = subprocess.run(
        [herdr_bin(), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit(f"herdr {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def load_registry() -> list[dict[str, Any]]:
    path = registry_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise SystemExit(f"Invalid registry format at {path}")
    return data


def save_registry(records: list[dict[str, Any]]) -> None:
    path = registry_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def current_pane_id() -> str:
    env_id = os.environ.get("HERDR_PANE_ID")
    if env_id:
        return env_id
    current = run_herdr("pane", "current", "--current")
    result = current.get("result", {})
    pane = result.get("pane") or result.get("current") or result
    pane_id = pane.get("pane_id") if isinstance(pane, dict) else None
    if not pane_id:
        raise SystemExit("Could not determine current Herdr pane id")
    return str(pane_id)


def list_panes() -> list[dict[str, Any]]:
    return run_herdr("pane", "list").get("result", {}).get("panes", [])


def list_tabs() -> list[dict[str, Any]]:
    return run_herdr("tab", "list").get("result", {}).get("tabs", [])


def list_workspaces() -> list[dict[str, Any]]:
    return run_herdr("workspace", "list").get("result", {}).get("workspaces", [])


def find_by(items: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    return next((item for item in items if str(item.get(key)) == value), None)


def state_snapshot() -> dict[str, Any]:
    return {"panes": list_panes(), "tabs": list_tabs(), "workspaces": list_workspaces()}


def pane_context(pane: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    tab = find_by(snapshot["tabs"], "tab_id", str(pane.get("tab_id"))) or {}
    workspace = find_by(snapshot["workspaces"], "workspace_id", str(pane.get("workspace_id"))) or {}
    return {"pane": pane, "tab": tab, "workspace": workspace}


def get_context(pane_id: str | None = None) -> dict[str, Any]:
    snapshot = state_snapshot()
    target_id = pane_id or current_pane_id()
    pane = find_by(snapshot["panes"], "pane_id", target_id)
    if not pane:
        raise SystemExit(f"Pane not found: {target_id}")
    return pane_context(pane, snapshot)


def panes_for_current_tab(pane_id: str | None = None) -> list[dict[str, Any]]:
    snapshot = state_snapshot()
    target_id = pane_id or current_pane_id()
    current = find_by(snapshot["panes"], "pane_id", target_id)
    if not current:
        raise SystemExit(f"Pane not found: {target_id}")
    tab_id = current.get("tab_id")
    return [pane_context(pane, snapshot) for pane in snapshot["panes"] if pane.get("tab_id") == tab_id]


def shell_join(argv: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in argv)


def process_info(pane_id: str) -> dict[str, Any] | None:
    try:
        return run_herdr("pane", "process-info", "--pane", pane_id).get("result", {}).get("process_info")
    except SystemExit:
        return None


def resume_command(agent: str | None, session_id: str | None, cwd: str | None) -> str | None:
    if not agent or not session_id or not cwd:
        return None
    template = RESUME_TEMPLATES.get(agent.lower())
    if not template:
        return None
    agent_command = template.format(session_id=shlex.quote(session_id))
    return f"cd {shlex.quote(cwd)} && {agent_command}"


def record_from_context(ctx: dict[str, Any], *, status: str, scope: str) -> dict[str, Any]:
    pane = ctx["pane"]
    tab = ctx["tab"]
    workspace = ctx["workspace"]
    pane_id = str(pane.get("pane_id"))
    agent_session = pane.get("agent_session") or {}
    session_id = agent_session.get("value")
    agent = pane.get("agent")
    cwd = pane.get("cwd") or pane.get("foreground_cwd")
    proc_info = process_info(pane_id)
    command = resume_command(str(agent) if agent else None, str(session_id) if session_id else None, str(cwd) if cwd else None)
    foreground = (proc_info or {}).get("foreground_processes") or []
    foreground_commands = [item.get("cmdline") or shell_join(item.get("argv") or []) for item in foreground if item]
    return {
        "agent": agent,
        "created_or_updated_unix": int(time.time()),
        "cwd": cwd,
        "foreground_commands_at_capture": [cmd for cmd in foreground_commands if cmd],
        "last_known_pane_id": pane.get("pane_id"),
        "last_known_tab_id": pane.get("tab_id"),
        "last_known_workspace_id": pane.get("workspace_id"),
        "pane_status_at_capture": pane.get("agent_status"),
        "process_restore_note": None if command else "No automatic resume template is available for this pane. Review captured foreground_commands_at_capture before restarting manually.",
        "restore_kind": "agent-session" if command else "manual",
        "resume_command": command,
        "scope": scope,
        "session_id": session_id,
        "status": status,
        "tab_label": tab.get("label") or str(pane.get("tab_id")),
        "workspace_label": workspace.get("label") or str(pane.get("workspace_id")),
    }


def record_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(record.get("workspace_label") or ""),
        str(record.get("tab_label") or ""),
        str(record.get("last_known_pane_id") or ""),
        str(record.get("session_id") or record.get("resume_command") or ""),
    )


def upsert_records(new_records: list[dict[str, Any]]) -> None:
    records = load_registry()
    new_keys = {record_key(record) for record in new_records}
    filtered = [record for record in records if record_key(record) not in new_keys]
    filtered.extend(new_records)
    save_registry(filtered)


def print_record(record: dict[str, Any]) -> None:
    print(f"{record.get('workspace_label')} / {record.get('tab_label')} / pane {record.get('last_known_pane_id')}")
    print(f"  status: {record.get('status')} ({record.get('restore_kind')})")
    print(f"  agent: {record.get('agent') or 'unknown'}")
    if record.get("session_id"):
        print(f"  session: {record.get('session_id')}")
    print(f"  cwd: {record.get('cwd')}")
    if record.get("resume_command"):
        print(f"  resume: {record.get('resume_command')}")
    else:
        print("  resume: manual review required")
        for command in record.get("foreground_commands_at_capture") or []:
            print(f"    captured: {command}")


def print_records(records: list[dict[str, Any]], *, title: str) -> None:
    print(title)
    for index, record in enumerate(records, 1):
        print(f"\n[{index}]")
        print_record(record)


def ensure_can_close(records: list[dict[str, Any]], *, force: bool, allow_working: bool) -> None:
    working = [record for record in records if record.get("pane_status_at_capture") == "working"]
    if working and not (force or allow_working):
        names = ", ".join(str(record.get("last_known_pane_id")) for record in working)
        raise SystemExit(f"Refusing to park working pane(s): {names}. Re-run with --force only after explicit confirmation.")


def create_marker(anchor_pane_id: str, records: list[dict[str, Any]], label: str) -> str:
    cwd = next((record.get("cwd") for record in records if record.get("cwd")), str(Path.home()))
    marker = run_herdr(
        "pane",
        "split",
        anchor_pane_id,
        "--direction",
        "right",
        "--cwd",
        str(cwd),
        "--no-focus",
    ).get("result", {}).get("pane", {})
    marker_id = marker.get("pane_id")
    if not marker_id:
        raise SystemExit("Failed to create parked marker pane")
    lines = ["", f"Parked by Herdr Session Parker: {label}", ""]
    for record in records:
        lines.append(f"- {record.get('agent') or 'manual'} pane {record.get('last_known_pane_id')}")
        if record.get("session_id"):
            lines.append(f"  session: {record.get('session_id')}")
        if record.get("resume_command"):
            lines.append(f"  resume: {record.get('resume_command')}")
    lines.append("")
    marker_text = "\n".join(lines)
    shell = os.environ.get("SHELL") or "/bin/sh"
    run_herdr_text("pane", "run", str(marker_id), f"printf %s {shlex.quote(marker_text)}; exec {shlex.quote(shell)} -l")
    run_herdr_text("pane", "rename", str(marker_id), "parked sessions")
    return str(marker_id)


def snapshot_current(args: argparse.Namespace) -> None:
    ctx = get_context(args.pane)
    record = record_from_context(ctx, status="snapshotted", scope="pane")
    if not args.dry_run:
        upsert_records([record])
    print_records([record], title="Dry-run snapshot:" if args.dry_run else "Snapshotted pane:")


def park_contexts(contexts: list[dict[str, Any]], args: argparse.Namespace, *, scope: str) -> None:
    records = [record_from_context(ctx, status="parked", scope=scope) for ctx in contexts]
    if args.dry_run:
        warning = ""
        if any(record.get("pane_status_at_capture") == "working" for record in records):
            warning = "\nwarning: actual park requires --force or --allow-working because at least one pane is working"
        print_records(records, title=f"Dry-run park; no pane will be changed:{warning}")
        return
    ensure_can_close(records, force=args.force, allow_working=args.allow_working)
    if args.require_auto_resume:
        manual = [record for record in records if not record.get("resume_command")]
        if manual:
            names = ", ".join(str(record.get("last_known_pane_id")) for record in manual)
            raise SystemExit(f"Refusing to park pane(s) without automatic resume: {names}")
    upsert_records(records)
    anchor_id = str(contexts[0]["pane"]["pane_id"])
    marker_id = create_marker(anchor_id, records, label=scope)
    for ctx in contexts:
        pane_id = str(ctx["pane"].get("pane_id"))
        if pane_id != marker_id:
            run_herdr_text("pane", "close", pane_id)
    print_records(records, title=f"Parked {scope} and created marker pane {marker_id}:")


def park_current_pane(args: argparse.Namespace) -> None:
    park_contexts([get_context(args.pane)], args, scope="pane")


def park_current_tab(args: argparse.Namespace) -> None:
    park_contexts(panes_for_current_tab(args.pane), args, scope="tab")


def matches_current_tab(record: dict[str, Any], ctx: dict[str, Any]) -> bool:
    tab = ctx["tab"]
    workspace = ctx["workspace"]
    return (
        record.get("last_known_tab_id") == tab.get("tab_id")
        or (
            record.get("tab_label") == tab.get("label")
            and record.get("workspace_label") == workspace.get("label")
        )
    )


def matching_records(args: argparse.Namespace, ctx: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    records = load_registry()
    if args.session_id:
        return [record for record in records if record.get("session_id") == args.session_id]
    if args.workspace:
        records = [record for record in records if record.get("workspace_label") == args.workspace or record.get("last_known_workspace_id") == args.workspace]
    if args.tab:
        records = [record for record in records if record.get("tab_label") == args.tab or record.get("last_known_tab_id") == args.tab]
    if args.current:
        current = ctx or get_context(args.pane)
        current_matches = [record for record in records if matches_current_tab(record, current)]
        if current_matches:
            return current_matches
    return records


def resume_current(args: argparse.Namespace) -> None:
    ctx = get_context(args.pane)
    records = matching_records(args, ctx)
    auto_records = [record for record in records if record.get("resume_command")]
    if not auto_records:
        raise SystemExit("No automatically resumable parked session matches. Run list-parked to inspect saved records.")
    if len(auto_records) > 1 and not args.session_id:
        print_records(auto_records, title="Multiple parked sessions match this tab. Re-run with --session-id for the one to resume:")
        raise SystemExit(2)
    record = auto_records[0]
    pane_id = str(ctx["pane"]["pane_id"])
    command = str(record["resume_command"])
    if args.dry_run:
        print(f"Dry-run resume in pane {pane_id}: {command}")
        return
    run_herdr_text("pane", "run", pane_id, command)
    all_records = load_registry()
    for item in all_records:
        if record_key(item) == record_key(record):
            item["status"] = "resumed"
            item["last_resumed_unix"] = int(time.time())
            break
    save_registry(all_records)
    print_records([record], title=f"Resuming parked session in pane {pane_id}:")


def list_records(args: argparse.Namespace) -> None:
    records = matching_records(args) if (args.current or args.workspace or args.tab or args.session_id) else load_registry()
    if not records:
        print(f"No parked sessions match. Registry: {registry_path()}")
        return
    print(f"Parked session registry: {registry_path()}")
    if args.current:
        print("Showing current tab matches first when available.")
    for index, record in enumerate(records, 1):
        print(f"\n[{index}]")
        print_record(record)


def add_common_park_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pane")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="allow parking working panes after explicit confirmation")
    parser.add_argument("--allow-working", action="store_true", help="alias for --force with clearer operator intent")
    parser.add_argument("--require-auto-resume", action="store_true", help="refuse panes without a known resume command")


def add_match_flags(parser: argparse.ArgumentParser, *, current_default: bool) -> None:
    parser.add_argument("--pane")
    parser.add_argument("--current", action="store_true", default=current_default)
    parser.add_argument("--workspace")
    parser.add_argument("--tab")
    parser.add_argument("--session-id")


def main() -> int:
    parser = argparse.ArgumentParser(description="Park/resume Herdr panes and supported agent sessions")
    sub = parser.add_subparsers(dest="command", required=True)

    snapshot = sub.add_parser(
        "snapshot-current",
        aliases=["snapshot-pane"],
        help="Record current pane without closing it; pass --pane to target a non-current pane without changing focus",
    )
    snapshot.add_argument("--pane")
    snapshot.add_argument("--dry-run", action="store_true")
    snapshot.set_defaults(func=snapshot_current)

    park_pane = sub.add_parser(
        "park-current-pane",
        aliases=["park-current", "park-pane"],
        help="Record and stop current pane, leaving a lightweight marker pane; pass --pane to target a non-current pane without changing focus",
    )
    add_common_park_flags(park_pane)
    park_pane.set_defaults(func=park_current_pane)

    park_tab = sub.add_parser(
        "park-current-tab",
        aliases=["park-tab"],
        help="Record and stop every pane in the target pane's tab, leaving a marker pane; pass --pane to target a non-current tab without changing focus",
    )
    add_common_park_flags(park_tab)
    park_tab.set_defaults(func=park_current_tab)

    resume = sub.add_parser(
        "resume-current",
        aliases=["resume-pane"],
        help="Resume a parked session for the current or targeted tab; pass --pane to target a non-current marker pane without changing focus",
    )
    add_match_flags(resume, current_default=True)
    resume.add_argument("--dry-run", action="store_true")
    resume.set_defaults(func=resume_current)

    listing = sub.add_parser("list", help="List parked sessions")
    add_match_flags(listing, current_default=False)
    listing.set_defaults(func=list_records)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
