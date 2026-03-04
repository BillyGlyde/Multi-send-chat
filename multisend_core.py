#!/usr/bin/env python3
"""Core window discovery and multi-send automation logic for Brave PWAs."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from typing import Any

FOCUS_DELAY_DEFAULT = 1.0
FOCUS_DELAY_CLAUDE = 1.6
BETWEEN_STEPS = 0.35
TYPE_DELAY = 12
POST_SEND_DELAY_DEFAULT = 0.6
POST_SEND_DELAY_CLAUDE = 1.0

# Keep probe unlikely to appear in normal prompts.
PERPLEXITY_PROBE = "__PZ_PROBE__"
PROBE_BACKSPACES = len(PERPLEXITY_PROBE)

PWA_CLASS_RE = re.compile(r"^crx_[^.]+\.Brave-browser$", re.IGNORECASE)
TERMINAL_CLASS_PATTERNS = [
    r"^gnome-terminal-server\.gnome-terminal$",
    r"^xfce4-terminal\.",
    r"^konsole\.konsole$",
    r"^xterm\.xterm$",
    r"^kitty\.kitty$",
    r"^alacritty\.alacritty$",
    r"^tilix\.tilix$",
    r"^terminator\.terminator$",
    r"^wezterm\.wezterm$",
    r"^lxterminal\.lxterminal$",
]
EDITOR_CLASS_PATTERNS = [
    r"^xed\.xed$",
    r"^code\.code$",
    r"^code-oss\.code-oss$",
    r"^gedit\.gedit$",
    r"^sublime_text\.sublime_text$",
    r"^mousepad\.mousepad$",
    r"^kate\.kate$",
    r"^nvim-qt\.nvim-qt$",
]
TERMINAL_CLASS_RES = [re.compile(pat, re.IGNORECASE) for pat in TERMINAL_CLASS_PATTERNS]
EDITOR_CLASS_RES = [re.compile(pat, re.IGNORECASE) for pat in EDITOR_CLASS_PATTERNS]
cancel_requested = False


def request_cancel() -> None:
    global cancel_requested
    cancel_requested = True


def reset_cancel() -> None:
    global cancel_requested
    cancel_requested = False


class MultiSendError(Exception):
    """Base exception for this module."""


class ToolMissingError(MultiSendError):
    """Raised when required external tools are not installed."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Missing required tool(s): {', '.join(missing)}")


def missing_tools(tools: list[str]) -> list[str]:
    """Return any missing external commands."""
    return [tool for tool in tools if shutil.which(tool) is None]


def ensure_tools(tools: list[str]) -> None:
    """Raise ToolMissingError if any required tool is missing."""
    missing = missing_tools(tools)
    if missing:
        raise ToolMissingError(missing)


def _check_output(cmd: list[str], text: bool = True) -> str | bytes:
    return subprocess.check_output(cmd, text=text).strip() if text else subprocess.check_output(cmd)


def _run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def list_windows() -> list[dict[str, Any]]:
    """
    Return all windows from wmctrl as:
    [{id_hex, id_dec, wm_class, title}, ...]
    """
    ensure_tools(["wmctrl"])
    try:
        out = _check_output(["wmctrl", "-lx"], text=True)
    except subprocess.CalledProcessError as exc:
        raise MultiSendError(f"Failed to run wmctrl -lx: {exc}") from exc

    wins: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        wid_hex, _desk, wm_class, _host, title = parts
        wid_hex = wid_hex.lower()
        try:
            wid_dec = int(wid_hex, 16)
        except ValueError:
            continue
        wins.append(
            {
                "id_hex": wid_hex,
                "id_dec": wid_dec,
                "wm_class": wm_class,
                "title": title,
            }
        )
    return wins


def list_brave_pwa_windows() -> list[dict[str, Any]]:
    """Return windows that look like Brave PWA app windows."""
    return [w for w in list_windows() if PWA_CLASS_RE.match(w["wm_class"] or "")]


def is_terminal_wm_class(wm_class: str | None) -> bool:
    value = (wm_class or "").strip()
    return any(rx.match(value) for rx in TERMINAL_CLASS_RES)


def is_editor_wm_class(wm_class: str | None) -> bool:
    value = (wm_class or "").strip()
    return any(rx.match(value) for rx in EDITOR_CLASS_RES)


def list_supported_windows() -> list[dict[str, Any]]:
    """Return chat PWAs plus terminal/editor windows used by the GUI."""
    return [
        w
        for w in list_windows()
        if PWA_CLASS_RE.match(w["wm_class"] or "")
        or is_terminal_wm_class(w["wm_class"])
        or is_editor_wm_class(w["wm_class"])
    ]


def default_ruleset() -> dict[str, Any]:
    """
    Data-driven send rules.
    Rules can be extended with:
    - by_window_id: {"0x0123abcd": {...}}
    - by_wm_class: {"crx_...Brave-browser": {...}}
    - title_contains: [{"pattern": "foo", "config": {...}}, ...]
    """
    return {
        "default": {
            "send_key": "Return",
            "press_send_key": True,
            "focus_delay": FOCUS_DELAY_DEFAULT,
            "post_send_delay": POST_SEND_DELAY_DEFAULT,
            "between_steps": BETWEEN_STEPS,
            "type_delay": TYPE_DELAY,
            "use_perplexity_probe": False,
            "perplexity_focus_steps": ["Tab", "Tab"],
        },
        "title_contains": [
            {
                "pattern": "claude",
                "config": {
                    "send_key": "ctrl+Return",
                    "focus_delay": FOCUS_DELAY_CLAUDE,
                    "post_send_delay": POST_SEND_DELAY_CLAUDE,
                },
            },
            {
                "pattern": "chatgpt",
                "config": {
                    "send_key": "Return",
                },
            },
        ],
        "by_window_id": {},
        "by_wm_class": {
            "crx_pdblnecalpedecgehiadglkhjcbjcfgj.Brave-browser": {
                "send_key": "ctrl+Return",
                "use_perplexity_probe": True,
            },
        },
    }


def _to_hex_id(window_id: int | str) -> str:
    if isinstance(window_id, int):
        return f"0x{window_id:08x}"
    value = str(window_id).strip().lower()
    if value.startswith("0x"):
        return f"0x{int(value, 16):08x}"
    return f"0x{int(value):08x}"


def _resolve_rule(window: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    resolved.update(default_ruleset()["default"])
    resolved.update((rules or {}).get("default", {}))

    title = (window.get("title") or "").lower()
    for item in (rules or {}).get("title_contains", []):
        pattern = str(item.get("pattern", "")).lower()
        if pattern and pattern in title:
            resolved.update(item.get("config", {}))

    by_class = (rules or {}).get("by_wm_class", {})
    class_rule = by_class.get(window.get("wm_class"))
    if class_rule:
        resolved.update(class_rule)

    by_id = (rules or {}).get("by_window_id", {})
    hex_id = window.get("id_hex")
    dec_id = str(window.get("id_dec"))
    if hex_id in by_id:
        resolved.update(by_id[hex_id])
    elif dec_id in by_id:
        resolved.update(by_id[dec_id])

    wm_class = window.get("wm_class")
    if is_terminal_wm_class(wm_class) or is_editor_wm_class(wm_class):
        resolved["press_send_key"] = False
        resolved["send_key"] = None

    return resolved


def _get_focused_window() -> int:
    out = _check_output(["xdotool", "getwindowfocus"], text=True)
    return int(out)


def _activate_window(window_id_dec: int) -> None:
    _run(["xdotool", "windowactivate", "--sync", str(window_id_dec)])


def _press_key(key_name: str) -> None:
    _run(["xdotool", "key", "--clearmodifiers", key_name])


def _type_text(text: str, type_delay: int) -> None:
    _run(
        [
            "xdotool",
            "type",
            "--delay",
            str(type_delay),
            "--clearmodifiers",
            text,
        ]
    )


def _get_clipboard() -> bytes | None:
    try:
        return subprocess.check_output(
            ["xclip", "-o", "-selection", "clipboard"], stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return None


def _set_clipboard(data: bytes | None) -> None:
    if data is None:
        # Best-effort clear when original clipboard had no owner/content.
        subprocess.run(
            ["xclip", "-i", "-selection", "clipboard", "/dev/null"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    proc = subprocess.Popen(
        ["xclip", "-i", "-selection", "clipboard"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc.communicate(data)
    if proc.returncode != 0:
        raise MultiSendError("Failed to restore clipboard contents.")


def _perplexity_focus_if_needed(rule: dict[str, Any]) -> bool:
    saved_clipboard = _get_clipboard()
    probe_bytes = PERPLEXITY_PROBE.encode("utf-8")
    between_steps = float(rule.get("between_steps", BETWEEN_STEPS))
    type_delay = int(rule.get("type_delay", TYPE_DELAY))
    focus_steps = list(rule.get("perplexity_focus_steps", ["Tab", "Tab"]))

    def probe_landed() -> bool:
        _type_text(PERPLEXITY_PROBE, type_delay)
        time.sleep(0.08)

        copied = b""
        try:
            _press_key("ctrl+a")
            time.sleep(0.06)
            _press_key("ctrl+c")
            time.sleep(0.12)
            copied = _get_clipboard() or b""
        finally:
            _set_clipboard(saved_clipboard)

        if probe_bytes in copied:
            for _ in range(PROBE_BACKSPACES):
                _press_key("BackSpace")
                time.sleep(0.02)
            time.sleep(0.06)
            return True

        _press_key("Escape")
        time.sleep(0.06)
        return False

    if probe_landed():
        return True

    for step in focus_steps:
        _press_key(step)
        time.sleep(between_steps)

    return probe_landed()


def send_to_windows(
    message: str, window_ids: list[int | str], rules: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Send one message to multiple windows.

    Returns:
      {
        "sent": [window_dict...],
        "typed_terminals": [id_hex...],
        "warnings": [str...],
        "errors": [str...]
      }
    """
    message = (message or "").strip()
    message = message.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    if not message:
        raise ValueError("Message is empty.")
    reset_cancel()

    rules = rules or default_ruleset()
    ensure_tools(["wmctrl", "xdotool"])

    all_windows = list_windows()
    by_hex = {w["id_hex"]: w for w in all_windows}

    normalized_ids: list[str] = []
    for raw in window_ids:
        try:
            normalized_ids.append(_to_hex_id(raw))
        except ValueError:
            continue

    selected_windows: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    for hex_id in normalized_ids:
        w = by_hex.get(hex_id)
        if not w:
            warnings.append(f"Window disappeared or not found: {hex_id}")
            continue
        selected_windows.append(w)
    selected_windows.sort(
        key=lambda w: "crx_pdblnecalpedecgehiadglkhjcbjcfgj" not in (w.get("wm_class") or "")
    )

    if any(_resolve_rule(w, rules).get("use_perplexity_probe") for w in selected_windows):
        ensure_tools(["xclip"])

    sent: list[dict[str, Any]] = []
    typed_terminals: list[str] = []
    original_focus: int | None = None
    try:
        try:
            original_focus = _get_focused_window()
        except Exception:
            original_focus = None

        for window in selected_windows:
            rule = _resolve_rule(window, rules)
            intended = int(window["id_dec"])

            if cancel_requested:
                break
            try:
                _activate_window(intended)
            except subprocess.CalledProcessError:
                errors.append(f"Failed to activate window {window['id_hex']}: {window['title']}")
                continue

            time.sleep(float(rule.get("focus_delay", FOCUS_DELAY_DEFAULT)))

            try:
                focused = _get_focused_window()
            except Exception:
                focused = -1
            if focused != intended:
                errors.append(f"Focus mismatch for {window['title']} ({window['id_hex']})")
                continue

            if rule.get("use_perplexity_probe"):
                ok = _perplexity_focus_if_needed(rule)
                if not ok:
                    errors.append(f"Perplexity focus/probe failed for {window['title']} ({window['id_hex']})")
                    continue

            if cancel_requested:
                break
            _type_text(message, int(rule.get("type_delay", TYPE_DELAY)))
            if is_terminal_wm_class(window.get("wm_class")):
                typed_terminals.append(str(window["id_hex"]))
            time.sleep(float(rule.get("between_steps", BETWEEN_STEPS)))
            send_key = rule.get("send_key", "Return")
            if cancel_requested:
                warnings.append(f"Cancelled before sending to {window['title']}")
                break
            if rule.get("press_send_key", True) and send_key:
                _press_key(str(send_key))
            time.sleep(float(rule.get("post_send_delay", POST_SEND_DELAY_DEFAULT)))
            sent.append(window)
    finally:
        if original_focus is not None:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", str(original_focus)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    return {"sent": sent, "typed_terminals": typed_terminals, "warnings": warnings, "errors": errors}


def terminal_enter_last_send(window_ids: list[int | str]) -> dict[str, Any]:
    """
    Press Return once in each terminal window id from a previous send.

    Returns:
      {
        "sent": [window_dict...],
        "warnings": [str...],
        "errors": [str...]
      }
    """
    reset_cancel()
    ensure_tools(["wmctrl", "xdotool"])

    all_windows = list_windows()
    by_hex = {w["id_hex"]: w for w in all_windows}

    normalized_ids: list[str] = []
    for raw in window_ids:
        try:
            normalized_ids.append(_to_hex_id(raw))
        except ValueError:
            continue

    sent: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    original_focus: int | None = None
    try:
        try:
            original_focus = _get_focused_window()
        except Exception:
            original_focus = None

        for hex_id in normalized_ids:
            if cancel_requested:
                break

            window = by_hex.get(hex_id)
            if not window:
                warnings.append(f"Window disappeared or not found: {hex_id}")
                continue
            if not is_terminal_wm_class(window.get("wm_class")):
                continue

            intended = int(window["id_dec"])
            try:
                _activate_window(intended)
            except subprocess.CalledProcessError:
                errors.append(f"Failed to activate window {window['id_hex']}: {window['title']}")
                continue

            time.sleep(FOCUS_DELAY_DEFAULT)

            try:
                focused = _get_focused_window()
            except Exception:
                focused = -1
            if focused != intended:
                errors.append(f"Focus mismatch for {window['title']} ({window['id_hex']})")
                continue

            if cancel_requested:
                break
            _press_key("Return")
            sent.append(window)
    finally:
        if original_focus is not None:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", str(original_focus)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    return {"sent": sent, "warnings": warnings, "errors": errors}
