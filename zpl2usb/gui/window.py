"""Okno ustawień (Tkinter): lista wirtualnych drukarek + panel edycji.

Po lewej lista mapowań (Dodaj/Duplikuj/Usuń), po prawej formularz edytujący
zaznaczone mapowanie. Na dole: autostart, zapis+restart wszystkich serwerów i log.
"""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, ttk

from ..config import DPIS, Config, ConfigError, Mapping
from ..server import ServerEvent
from .formstate import form_to_mapping, mapping_label, mapping_to_form, wms_hint


class SettingsWindow:
    def __init__(self, app, root: tk.Misc) -> None:
        self.app = app
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.title("zpl2usb — wirtualne drukarki ZPL")
        self.win.protocol("WM_DELETE_WINDOW", self.hide)

        # Robocza kopia mapowań (zapis dopiero na „Zapisz i uruchom").
        self._mappings: list[Mapping] = [copy.deepcopy(m) for m in app.config.mappings]
        if not self._mappings:
            self._mappings = [Mapping()]
        self._selected: int | None = None
        self._vars: dict[str, tk.Variable] = {}

        self._build()
        self._refresh_list()
        self._select_index(0)
        self.app.add_log_handler(self._on_event_threadsafe)
        self._refresh_status()

    # --- budowa UI ----------------------------------------------------------
    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.grid(row=0, column=0, sticky="nsew")
        self.win.columnconfigure(0, weight=1)
        self.win.rowconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        self._build_list_panel(outer)
        self._build_edit_panel(outer)
        self._build_bottom(outer)

    def _build_list_panel(self, outer) -> None:
        panel = ttk.LabelFrame(outer, text="Wirtualne drukarki", padding=6)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.listbox = tk.Listbox(panel, width=34, height=10, exportselection=False)
        self.listbox.grid(row=0, column=0, columnspan=3, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)
        panel.rowconfigure(0, weight=1)

        ttk.Button(panel, text="+ Dodaj", command=self.add_mapping).grid(
            row=1, column=0, pady=(6, 0), sticky="we"
        )
        ttk.Button(panel, text="Duplikuj", command=self.duplicate_mapping).grid(
            row=1, column=1, pady=(6, 0), sticky="we"
        )
        ttk.Button(panel, text="Usuń", command=self.remove_mapping).grid(
            row=1, column=2, pady=(6, 0), sticky="we"
        )

    def _build_edit_panel(self, outer) -> None:
        frm = ttk.LabelFrame(outer, text="Ustawienia zaznaczonej drukarki", padding=8)
        frm.grid(row=0, column=1, sticky="nsew")
        frm.columnconfigure(1, weight=1)
        r = 0

        ttk.Label(frm, text="Drukarka docelowa:").grid(row=r, column=0, sticky="w")
        self._vars["target_printer"] = tk.StringVar()
        self.printer_cb = ttk.Combobox(
            frm, textvariable=self._vars["target_printer"], width=28, state="readonly"
        )
        self.printer_cb.grid(row=r, column=1, sticky="we", pady=2)
        ttk.Button(frm, text="Odśwież", command=self.refresh_printers).grid(row=r, column=2, padx=4)

        r += 1
        ttk.Label(frm, text="Adres nasłuchu (ten komputer):").grid(row=r, column=0, sticky="w")
        self._vars["listen_host"] = tk.StringVar()
        self.host_cb = ttk.Combobox(
            frm, textvariable=self._vars["listen_host"], width=28, state="readonly"
        )
        self.host_cb.grid(row=r, column=1, sticky="we", pady=2)
        ttk.Button(frm, text="Odśwież", command=self.refresh_hosts).grid(row=r, column=2, padx=4)

        r += 1
        self.hint_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.hint_var, foreground="#227a3a").grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        self._vars["listen_host"].trace_add("write", lambda *_: self._update_hint())

        r += 1
        ttk.Label(frm, text="Tryb:").grid(row=r, column=0, sticky="w")
        self._vars["mode"] = tk.StringVar(value="raw")
        mode_frm = ttk.Frame(frm)
        mode_frm.grid(row=r, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(
            mode_frm, text="Surowy ZPL (raw)", value="raw", variable=self._vars["mode"]
        ).pack(side="left")
        ttk.Radiobutton(
            mode_frm, text="Renderuj", value="render", variable=self._vars["mode"]
        ).pack(side="left", padx=8)

        r += 1
        ttk.Label(frm, text="DPI:").grid(row=r, column=0, sticky="w")
        self._vars["dpi"] = tk.StringVar(value="203")
        ttk.Combobox(
            frm,
            textvariable=self._vars["dpi"],
            width=8,
            state="readonly",
            values=[str(d) for d in DPIS],
        ).grid(row=r, column=1, sticky="w", pady=2)

        r += 1
        ttk.Label(frm, text="Port nasłuchu:").grid(row=r, column=0, sticky="w")
        self._vars["listen_port"] = tk.StringVar(value="9100")
        ttk.Entry(frm, textvariable=self._vars["listen_port"], width=10).grid(
            row=r, column=1, sticky="w", pady=2
        )
        self._vars["listen_port"].trace_add("write", lambda *_: self._update_hint())

        r += 1
        ttk.Label(frm, text="Domyślna etykieta (mm):").grid(row=r, column=0, sticky="w")
        size_frm = ttk.Frame(frm)
        size_frm.grid(row=r, column=1, sticky="w")
        self._vars["label_w"] = tk.StringVar(value="100")
        self._vars["label_h"] = tk.StringVar(value="40")
        ttk.Entry(size_frm, textvariable=self._vars["label_w"], width=6).pack(side="left")
        ttk.Label(size_frm, text=" × ").pack(side="left")
        ttk.Entry(size_frm, textvariable=self._vars["label_h"], width=6).pack(side="left")

        r += 1
        self._vars["enabled"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="Włączona (nasłuchuje)", variable=self._vars["enabled"]).grid(
            row=r, column=1, sticky="w", pady=2
        )

    def _build_bottom(self, outer) -> None:
        bar = ttk.Frame(outer)
        bar.grid(row=1, column=0, columnspan=2, sticky="we", pady=(10, 4))
        self.autostart_var = tk.BooleanVar(value=self.app.config.autostart)
        ttk.Checkbutton(
            bar, text="Uruchamiaj przy starcie systemu", variable=self.autostart_var
        ).pack(side="left")
        ttk.Button(bar, text="Zapisz i uruchom wszystkie", command=self.save_and_restart).pack(
            side="left", padx=(12, 0)
        )
        ttk.Button(bar, text="Stop", command=self.stop).pack(side="left", padx=6)
        self.status_var = tk.StringVar(value="—")
        ttk.Label(bar, textvariable=self.status_var).pack(side="left", padx=12)

        ttk.Label(outer, text="Log:").grid(row=2, column=0, sticky="w")
        self.log_text = tk.Text(outer, height=10, width=80, state="disabled", wrap="none")
        self.log_text.grid(row=3, column=0, columnspan=2, sticky="nsew")
        outer.rowconfigure(3, weight=1)

    # --- lista mapowań ------------------------------------------------------
    def _refresh_list(self) -> None:
        sel = self.listbox.curselection()
        self.listbox.delete(0, "end")
        for m in self._mappings:
            self.listbox.insert("end", mapping_label(m))
        if sel:
            self.listbox.selection_set(sel[0])

    def _select_index(self, idx: int) -> None:
        idx = max(0, min(idx, len(self._mappings) - 1))
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(idx)
        self._load_mapping(idx)

    def _on_list_select(self, _event=None) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        new_idx = sel[0]
        if self._selected is not None and self._selected != new_idx:
            if not self._commit_form():
                # cofnij zaznaczenie do poprzedniego (błąd walidacji)
                self.listbox.selection_clear(0, "end")
                self.listbox.selection_set(self._selected)
                return
            self.listbox.delete(self._selected)
            self.listbox.insert(self._selected, mapping_label(self._mappings[self._selected]))
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(new_idx)
        self._load_mapping(new_idx)

    def _load_mapping(self, idx: int) -> None:
        self._selected = idx
        form = mapping_to_form(self._mappings[idx])
        for key, val in form.items():
            if key in self._vars:
                self._vars[key].set(val)
        self.refresh_printers()
        self.refresh_hosts()
        self._update_hint()

    def _commit_form(self) -> bool:
        """Zapisz bieżący formularz do roboczej listy. False przy błędzie walidacji."""
        if self._selected is None:
            return True
        try:
            self._mappings[self._selected] = form_to_mapping(self._gather_form())
        except ValueError as exc:
            messagebox.showerror("Błąd konfiguracji", str(exc), parent=self.win)
            return False
        return True

    def add_mapping(self) -> None:
        if not self._commit_form():
            return
        # nowy port, żeby nie kolidował
        used = {(m.listen_host, m.listen_port) for m in self._mappings}
        port = 9100
        while ("0.0.0.0", port) in used:
            port += 1
        self._mappings.append(Mapping(listen_port=port))
        self._refresh_list()
        self._select_index(len(self._mappings) - 1)

    def duplicate_mapping(self) -> None:
        if self._selected is None or not self._commit_form():
            return
        clone = copy.deepcopy(self._mappings[self._selected])
        clone.listen_port += 1
        self._mappings.append(clone)
        self._refresh_list()
        self._select_index(len(self._mappings) - 1)

    def remove_mapping(self) -> None:
        if self._selected is None:
            return
        if len(self._mappings) == 1:
            messagebox.showinfo(
                "Nie można usunąć",
                "Musi zostać co najmniej jedna wirtualna drukarka.",
                parent=self.win,
            )
            return
        idx = self._selected
        del self._mappings[idx]
        self._selected = None
        self._refresh_list()
        self._select_index(min(idx, len(self._mappings) - 1))

    # --- dane <-> UI --------------------------------------------------------
    def _gather_form(self) -> dict:
        return {k: v.get() for k, v in self._vars.items()}

    def refresh_printers(self) -> None:
        try:
            printers = self.app.list_printers()
        except Exception as exc:
            printers = []
            self._append_log("error", f"Nie można pobrać listy drukarek: {exc}")
        current = self._vars["target_printer"].get()
        values = list(printers)
        if current and current not in values:
            values = [current, *values]
        self.printer_cb["values"] = values

    def refresh_hosts(self) -> None:
        from ..netutil import list_local_ipv4

        current = self._vars["listen_host"].get()
        try:
            hosts = list_local_ipv4()
        except Exception as exc:
            hosts = ["0.0.0.0"]
            self._append_log("warning", f"Nie można wykryć adresów IP: {exc}")
        if current and current not in hosts:
            hosts = [current, *hosts]
        self.host_cb["values"] = hosts
        if not current and hosts:
            self._vars["listen_host"].set(hosts[0])
        self._update_hint()

    def _update_hint(self) -> None:
        self.hint_var.set(
            wms_hint(self._vars["listen_host"].get(), self._vars["listen_port"].get())
        )

    # --- akcje --------------------------------------------------------------
    def save_and_restart(self) -> None:
        if not self._commit_form():
            return
        cfg = Config(
            mappings=[copy.deepcopy(m) for m in self._mappings],
            autostart=bool(self.autostart_var.get()),
        )
        try:
            cfg.validate()
        except ConfigError as exc:
            messagebox.showerror("Błąd konfiguracji", str(exc), parent=self.win)
            return
        errors = self.app.apply_config(cfg)
        self.app.set_autostart(bool(self.autostart_var.get()))
        self._refresh_list()
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
        self.refresh_hosts()
        self._refresh_status()

    def hide(self) -> None:
        self.win.withdraw()
