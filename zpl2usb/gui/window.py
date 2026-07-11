"""Okno ustawień (Tkinter) spięte z ``App``.

Obsługuje pojedyncze mapowanie (mappings[0]) — zgodnie z założeniem „start od
jednej wirtualnej drukarki". Log zdarzeń jest aktualizowany wątkowo-bezpiecznie
przez ``root.after``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..config import DPIS, Config, Mapping
from ..server import ServerEvent
from .formstate import form_to_mapping, mapping_to_form


class SettingsWindow:
    def __init__(self, app, root: tk.Misc) -> None:
        self.app = app
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.title("zpl2usb — ustawienia wirtualnej drukarki ZPL")
        self.win.protocol("WM_DELETE_WINDOW", self.hide)
        self._vars: dict[str, tk.Variable] = {}
        self._build()
        self._load_from_config()
        self.app.add_log_handler(self._on_event_threadsafe)
        self._refresh_status()

    # --- budowa UI ----------------------------------------------------------
    def _build(self) -> None:
        frm = ttk.Frame(self.win, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")
        self.win.columnconfigure(0, weight=1)
        self.win.rowconfigure(0, weight=1)

        row = 0
        ttk.Label(frm, text="Drukarka docelowa:").grid(row=row, column=0, sticky="w")
        self._vars["target_printer"] = tk.StringVar()
        self.printer_cb = ttk.Combobox(frm, textvariable=self._vars["target_printer"],
                                       width=32, state="readonly")
        self.printer_cb.grid(row=row, column=1, sticky="we", pady=3)
        ttk.Button(frm, text="Odśwież", command=self.refresh_printers).grid(
            row=row, column=2, padx=4)

        row += 1
        ttk.Label(frm, text="Tryb:").grid(row=row, column=0, sticky="w")
        self._vars["mode"] = tk.StringVar(value="raw")
        mode_frm = ttk.Frame(frm)
        mode_frm.grid(row=row, column=1, sticky="w")
        ttk.Radiobutton(mode_frm, text="Surowy ZPL (raw)", value="raw",
                        variable=self._vars["mode"]).pack(side="left")
        ttk.Radiobutton(mode_frm, text="Renderuj (dla drukarek bez ZPL)", value="render",
                        variable=self._vars["mode"]).pack(side="left", padx=8)

        row += 1
        ttk.Label(frm, text="DPI:").grid(row=row, column=0, sticky="w")
        self._vars["dpi"] = tk.StringVar(value="203")
        ttk.Combobox(frm, textvariable=self._vars["dpi"], width=8, state="readonly",
                     values=[str(d) for d in DPIS]).grid(row=row, column=1, sticky="w", pady=3)

        row += 1
        ttk.Label(frm, text="Port nasłuchu:").grid(row=row, column=0, sticky="w")
        self._vars["listen_port"] = tk.StringVar(value="9100")
        ttk.Entry(frm, textvariable=self._vars["listen_port"], width=10).grid(
            row=row, column=1, sticky="w", pady=3)

        row += 1
        ttk.Label(frm, text="Domyślna etykieta (mm):").grid(row=row, column=0, sticky="w")
        size_frm = ttk.Frame(frm)
        size_frm.grid(row=row, column=1, sticky="w")
        self._vars["label_w"] = tk.StringVar(value="100")
        self._vars["label_h"] = tk.StringVar(value="40")
        ttk.Entry(size_frm, textvariable=self._vars["label_w"], width=6).pack(side="left")
        ttk.Label(size_frm, text=" × ").pack(side="left")
        ttk.Entry(size_frm, textvariable=self._vars["label_h"], width=6).pack(side="left")

        row += 1
        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=3, sticky="we", pady=(10, 4))
        ttk.Button(btns, text="Zapisz i uruchom", command=self.save_and_restart).pack(side="left")
        ttk.Button(btns, text="Stop", command=self.stop).pack(side="left", padx=6)
        self.status_var = tk.StringVar(value="—")
        ttk.Label(btns, textvariable=self.status_var).pack(side="left", padx=12)

        row += 1
        ttk.Label(frm, text="Log:").grid(row=row, column=0, sticky="w")
        row += 1
        self.log_text = tk.Text(frm, height=12, width=64, state="disabled", wrap="none")
        self.log_text.grid(row=row, column=0, columnspan=3, sticky="nsew")
        frm.rowconfigure(row, weight=1)
        frm.columnconfigure(1, weight=1)

    # --- dane <-> UI --------------------------------------------------------
    def _current_mapping(self) -> Mapping:
        return self.app.config.mappings[0]

    def _load_from_config(self) -> None:
        form = mapping_to_form(self._current_mapping())
        for key, val in form.items():
            if key in self._vars:
                self._vars[key].set(val)
        self.refresh_printers()

    def refresh_printers(self) -> None:
        try:
            printers = self.app.list_printers()
        except Exception as exc:
            printers = []
            self._append_log("error", f"Nie można pobrać listy drukarek: {exc}")
        current = self._vars["target_printer"].get()
        values = printers or ([current] if current else [])
        self.printer_cb["values"] = values
        if current and current not in values and values:
            pass  # zachowaj wpisaną wartość
        elif current:
            self._vars["target_printer"].set(current)

    def _gather_form(self) -> dict:
        return {k: v.get() for k, v in self._vars.items()}

    # --- akcje --------------------------------------------------------------
    def save_and_restart(self) -> None:
        try:
            mapping = form_to_mapping(self._gather_form())
        except ValueError as exc:
            messagebox.showerror("Błąd konfiguracji", str(exc), parent=self.win)
            return
        cfg = Config(mappings=[mapping])
        errors = self.app.apply_config(cfg)
        if errors:
            messagebox.showerror("Błąd uruchomienia", "\n".join(errors), parent=self.win)
        self._refresh_status()

    def stop(self) -> None:
        self.app.stop()
        self._refresh_status()

    def _refresh_status(self) -> None:
        running = self.app.is_running()
        self.status_var.set("● Działa" if running else "○ Zatrzymana")

    # --- log ----------------------------------------------------------------
    def _on_event_threadsafe(self, event: ServerEvent) -> None:
        # Wywoływane z wątku serwera — przełóż na wątek Tk.
        try:
            self.root.after(0, lambda: self._append_log(event.level, event.message))
        except RuntimeError:
            pass

    def _append_log(self, level: str, message: str) -> None:
        prefix = {"info": "•", "warning": "⚠", "error": "✖"}.get(level, "•")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{prefix} {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # --- widoczność ---------------------------------------------------------
    def show(self) -> None:
        self.win.deiconify()
        self.win.lift()
        self.refresh_printers()
        self._refresh_status()

    def hide(self) -> None:
        self.win.withdraw()
