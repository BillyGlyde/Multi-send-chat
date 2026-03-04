#!/usr/bin/env python3
# Run:
#   python3 multisend_gui.py

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

import multisend_core as core
from pynput import keyboard


class MultiSendGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Brave PWA MultiSend")
        self.geometry("780x520")
        self.minsize(640, 420)
        self.configure(bg="#000000")

        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Cyber.TFrame", background="#050505")
        self.style.configure(
            "Cyber.TLabel",
            background="#000000",
            foreground="#00FFFF",
            font=("Courier", 11),
        )
        self.style.configure(
            "Cyber.TButton",
            background="#111111",
            foreground="#00FFFF",
            borderwidth=0,
            font=("Courier", 11),
        )
        self.style.map(
            "Cyber.TButton",
            background=[("active", "#00FF9F"), ("pressed", "#00FF9F"), ("disabled", "#111111")],
            foreground=[("active", "#000000"), ("pressed", "#000000"), ("disabled", "#444444")],
        )
        self.style.configure(
            "Cyber.TEntry",
            fieldbackground="#050505",
            foreground="#00FFFF",
            font=("Courier", 11),
        )
        self.style.configure(
            "Cyber.TCheckbutton",
            background="#050505",
            foreground="#00FFFF",
            font=("Courier", 11),
        )
        self.style.map(
            "Cyber.TCheckbutton",
            background=[("active", "#050505"), ("selected", "#050505")],
            foreground=[("active", "#00FFFF"), ("selected", "#00FFFF")],
        )
        self.style.configure(
            "Cyber.Vertical.TScrollbar",
            background="#111111",
            troughcolor="#050505",
            bordercolor="#050505",
            arrowcolor="#00FFFF",
            darkcolor="#111111",
            lightcolor="#111111",
        )
        self._ui_images: dict[str, tk.PhotoImage] = {}
        self._ui_images["button_main"] = tk.PhotoImage(file="/home/sb/Thumbs_Up/assets/ui/button_main.png")
        self._ui_images["button_main_scaled"] = self._ui_images["button_main"].zoom(5, 3).subsample(2, 4)

        self.message_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready.")
        self.window_vars: dict[str, tk.BooleanVar] = {}
        self.window_rows: dict[str, dict] = {}
        self.last_typed_terminals: list[str] = []
        self._send_in_progress = False
        self._escape_listener = None

        self.ruleset = core.default_ruleset()

        self._build_ui()
        self._start_escape_listener()
        self._check_tools()
        self.refresh_windows()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=(10, 10, 10, 6), style="Cyber.TFrame")
        top.pack(fill=tk.X)

        self.entry = tk.Entry(
            top,
            textvariable=self.message_var,
            bg="#050505",
            fg="#00FFFF",
            insertbackground="#00FFFF",
            font=("Courier", 11),
            borderwidth=0,
            relief=tk.FLAT,
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", self.on_send_enter)
        self.bind("<Escape>", lambda _event: core.request_cancel())

        send_btn = tk.Button(
            top,
            text="Send",
            command=self.send_message,
            image=self._ui_images["button_main_scaled"],
            compound="center",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            font=("Courier", 12, "bold"),
            padx=10,
            pady=6,
            width=160,
            height=50,
            fg="#000000",
            bg="#000000",
            activebackground="#000000",
            activeforeground="#000000",
            disabledforeground="#000000",
        )
        send_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.terminal_enter_btn = tk.Button(
            top,
            text="Terminal Enter (last send)",
            command=self.terminal_enter_last_send,
            state=tk.DISABLED,
            image=self._ui_images["button_main_scaled"],
            compound="center",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            font=("Courier", 12, "bold"),
            padx=10,
            pady=6,
            width=160,
            height=50,
            fg="#000000",
            bg="#000000",
            activebackground="#000000",
            activeforeground="#000000",
            disabledforeground="#000000",
        )
        self.terminal_enter_btn.pack(side=tk.LEFT, padx=(8, 0))

        middle = ttk.Frame(self, padding=(10, 6, 10, 6), style="Cyber.TFrame")
        middle.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            middle,
            borderwidth=0,
            highlightthickness=0,
            bg="#050505",
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            middle,
            orient=tk.VERTICAL,
            command=self.canvas.yview,
            style="Cyber.Vertical.TScrollbar",
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.window_list_frame = ttk.Frame(self.canvas, style="Cyber.TFrame")
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.window_list_frame, anchor="nw"
        )
        for w in (self.canvas, self.window_list_frame):
            w.bind("<Button-4>", self._on_wheel_up)
            w.bind("<Button-5>", self._on_wheel_down)
            w.bind("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Button-4>", self._on_wheel_up)
        self.bind_all("<Button-5>", self._on_wheel_down)
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        self.window_list_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        bottom = ttk.Frame(self, padding=(10, 6, 10, 10), style="Cyber.TFrame")
        bottom.pack(fill=tk.X)

        refresh_btn = ttk.Button(
            bottom,
            text="Refresh windows",
            command=self.refresh_windows,
            style="Cyber.TButton",
        )
        refresh_btn.pack(side=tk.LEFT)

        status_label = ttk.Label(
            bottom,
            textvariable=self.status_var,
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=560,
            style="Cyber.TLabel",
        )
        status_label.pack(side=tk.LEFT, padx=(12, 0), fill=tk.X, expand=True)

    def _on_frame_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _is_over_window_list(self, event: tk.Event) -> bool:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self.canvas or widget is self.window_list_frame:
                return True
            widget = widget.master
        return False

    def _wheel_scroll(self, direction: int) -> None:
        # direction: -1 up, +1 down
        self.canvas.yview_scroll(direction * 3, "units")

    def _on_wheel_up(self, event: tk.Event) -> str | None:
        if not self._is_over_window_list(event):
            return None
        self._wheel_scroll(-1)
        return "break"

    def _on_wheel_down(self, event: tk.Event) -> str | None:
        if not self._is_over_window_list(event):
            return None
        self._wheel_scroll(1)
        return "break"

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        if not self._is_over_window_list(event):
            return None
        if event.delta > 0:
            self._wheel_scroll(-1)
        else:
            self._wheel_scroll(1)
        return "break"

    def _start_escape_listener(self) -> None:
        def on_press(key):
            if key == keyboard.Key.esc:
                core.request_cancel()
                self.after(0, lambda: self.status_var.set("Cancelled"))

        listener = keyboard.Listener(on_press=on_press)
        listener.daemon = True
        listener.start()
        self._escape_listener = listener

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _check_tools(self) -> None:
        missing = core.missing_tools(["wmctrl", "xdotool", "xclip"])
        if missing:
            self._set_status(f"Missing tool(s): {', '.join(missing)}")

    def _window_display_base(self, window: dict) -> str:
        title = (window.get("title") or "").lower()
        wm_class = window.get("wm_class")
        if "chatgpt" in title:
            return "ChatGPT"
        if "perplexity" in title:
            return "Perplexity"
        if "claude" in title:
            return "Claude"
        if core.is_terminal_wm_class(wm_class):
            return "Terminal"
        if core.is_editor_wm_class(wm_class):
            return "Editor"
        return "Chat"

    def _display_name_map(self, windows: list[dict]) -> dict[str, str]:
        counts: dict[str, int] = {}
        display: dict[str, str] = {}
        for w in windows:
            base = self._window_display_base(w)
            counts[base] = counts.get(base, 0) + 1
            display[w["id_hex"]] = f"{base} {counts[base]}"
        return display

    def refresh_windows(self) -> None:
        previous_checked = {wid for wid, var in self.window_vars.items() if var.get()}
        self.window_vars = {}
        self.window_rows = {}

        for child in self.window_list_frame.winfo_children():
            child.destroy()

        try:
            windows = core.list_supported_windows()
        except core.ToolMissingError as exc:
            self._set_status(str(exc))
            return
        except Exception as exc:
            self._set_status(f"Failed to load windows: {exc}")
            return

        if not windows:
            ttk.Label(self.window_list_frame, text="No supported windows found.", style="Cyber.TLabel").pack(
                anchor=tk.W, pady=4
            )
            self._set_status("No supported windows found. Open chat/terminal/editor windows, then refresh.")
            return

        display_names = self._display_name_map(windows)
        for idx, win in enumerate(windows):
            wid = win["id_hex"]
            var = tk.BooleanVar(value=(wid in previous_checked))
            self.window_vars[wid] = var

            row = ttk.Frame(self.window_list_frame, padding=(2, 2), style="Cyber.TFrame")
            row.grid(row=idx, column=0, sticky="ew")
            row.columnconfigure(0, weight=1)

            cb = ttk.Checkbutton(row, text=display_names[wid], variable=var, style="Cyber.TCheckbutton")
            cb.grid(row=0, column=0, sticky="w")

            hint = self._window_rule_hint(win)
            detail = ttk.Label(
                row,
                text=f"{win['wm_class']}  |  {hint}",
                foreground="#00FFFF",
                font=("Courier", 11),
                background="#000000",
                style="Cyber.TLabel",
            )
            detail.grid(row=1, column=0, sticky="w", padx=(24, 0))

            self.window_rows[wid] = win

        self._set_status(f"Loaded {len(windows)} supported window(s).")

    def _window_rule_hint(self, window: dict) -> str:
        if core.is_terminal_wm_class(window.get("wm_class")) or core.is_editor_wm_class(
            window.get("wm_class")
        ):
            return "send: type only (no Enter)"
        t = (window.get("title") or "").lower()
        if "perplexity" in t:
            return "send: Ctrl+Return, focus probe enabled"
        if "claude" in t:
            return "send: Ctrl+Return, longer delays"
        if "chatgpt" in t:
            return "send: Return"
        return "send: Return (default)"

    def on_send_enter(self, _event: tk.Event) -> str:
        self.send_message()
        return "break"

    def _refresh_terminal_enter_button(self) -> None:
        if self.last_typed_terminals and not self._send_in_progress:
            self.terminal_enter_btn.configure(state=tk.NORMAL)
            return
        self.terminal_enter_btn.configure(state=tk.DISABLED)

    def send_message(self) -> None:
        if self._send_in_progress:
            self._set_status("Send already in progress. Press Escape to cancel.")
            return

        msg = self.message_var.get().strip()
        if not msg:
            self._set_status("Type a message first.")
            return

        window_ids = [wid for wid, var in self.window_vars.items() if var.get()]
        if not window_ids:
            self._set_status("Select at least one window.")
            return

        self._send_in_progress = True
        self._refresh_terminal_enter_button()
        self._set_status(f"Sending to {len(window_ids)} window(s)... Press Escape to cancel.")
        threading.Thread(target=self._send_worker, args=(msg, window_ids), daemon=True).start()

    def terminal_enter_last_send(self) -> None:
        if self._send_in_progress:
            self._set_status("Send already in progress. Press Escape to cancel.")
            return
        if not self.last_typed_terminals:
            self._set_status("No terminal windows from last send.")
            return
        self._send_in_progress = True
        self._refresh_terminal_enter_button()
        self._set_status(
            f"Pressing Enter in {len(self.last_typed_terminals)} terminal window(s)... Press Escape to cancel."
        )
        threading.Thread(
            target=self._terminal_enter_worker, args=(list(self.last_typed_terminals),), daemon=True
        ).start()

    def _send_worker(self, msg: str, window_ids: list[str]) -> None:
        try:
            result = core.send_to_windows(msg, window_ids, self.ruleset)
            self.after(0, lambda: self._on_send_complete(result=result, error=None))
        except core.ToolMissingError as exc:
            self.after(0, lambda exc=exc: self._on_send_complete(result=None, error=exc))
        except Exception as exc:
            self.after(0, lambda exc=exc: self._on_send_complete(result=None, error=exc))

    def _terminal_enter_worker(self, window_ids: list[str]) -> None:
        try:
            result = core.terminal_enter_last_send(window_ids)
            self.after(0, lambda: self._on_terminal_enter_complete(result=result, error=None))
        except core.ToolMissingError as exc:
            self.after(0, lambda exc=exc: self._on_terminal_enter_complete(result=None, error=exc))
        except Exception as exc:
            self.after(0, lambda exc=exc: self._on_terminal_enter_complete(result=None, error=exc))

    def _on_send_complete(self, result: dict | None, error: Exception | None) -> None:
        self._send_in_progress = False
        self._refresh_terminal_enter_button()
        if isinstance(error, core.ToolMissingError):
            self._set_status(str(error))
            return
        if error is not None:
            self._set_status(f"Send failed: {error}")
            return

        if result is None:
            self._set_status("Send failed: no result")
            return
        sent_count = len(result["sent"])
        if core.cancel_requested:
            self._set_status("Send cancelled")
            return
        self.last_typed_terminals = list(result.get("typed_terminals", []))
        self._refresh_terminal_enter_button()
        parts = [f"Sent to {sent_count} window(s)."]
        if result["warnings"]:
            parts.append("Warnings: " + " | ".join(result["warnings"]))
        if result["errors"]:
            parts.append("Errors: " + " | ".join(result["errors"]))
        self._set_status(" ".join(parts))
        self.message_var.set("")
        self.entry.focus_set()

    def _on_terminal_enter_complete(self, result: dict | None, error: Exception | None) -> None:
        self._send_in_progress = False
        self._refresh_terminal_enter_button()
        if isinstance(error, core.ToolMissingError):
            self._set_status(str(error))
            return
        if error is not None:
            self._set_status(f"Terminal Enter failed: {error}")
            return
        if result is None:
            self._set_status("Terminal Enter failed: no result")
            return
        if core.cancel_requested:
            self._set_status("Terminal Enter cancelled")
            return
        sent_count = len(result["sent"])
        parts = [f"Pressed Enter in {sent_count} terminal window(s)."]
        if result["warnings"]:
            parts.append("Warnings: " + " | ".join(result["warnings"]))
        if result["errors"]:
            parts.append("Errors: " + " | ".join(result["errors"]))
        self._set_status(" ".join(parts))


def main() -> int:
    app = MultiSendGUI()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
