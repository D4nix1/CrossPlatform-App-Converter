from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from cpc.analyze import build_report
from cpc.portability import create_conversion_attempt, create_scaffold
from cpc.recovery import recover_apk, recovery_status_label
from cpc.reports import summarize, write_html_report, write_json_report
from cpc.ui_preferences import detect_dark_mode, detect_language, strings


class ConverterWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.language = detect_language()
        self.texts = strings(self.language)
        self._dark_mode = None
        self.root.title("CrossPlatform App Converter")
        self.root.geometry("1120x780")
        self.root.minsize(860, 580)
        self.apk_path = tk.StringVar()
        self.ipa_path = tk.StringVar()
        self.status = tk.StringVar(value=self._t("ready_status"))
        self.target = tk.StringVar(value="iOS")
        self.report = None
        self._apply_theme()
        self._build()
        self.root.after(2500, self._watch_theme)

    def _t(self, key: str, **values) -> str:
        return self.texts[key].format(**values)

    def _recovery_status(self, status: str) -> str:
        key = f"status_{status}"
        if self.language == "en" and key in self.texts:
            return self._t(key)
        return recovery_status_label(status)

    def _apply_theme(self) -> None:
        dark = detect_dark_mode()
        self._dark_mode = dark
        palette = ({"bg": "#202124", "surface": "#292a2d", "field": "#17181a", "fg": "#e8eaed", "muted": "#bdc1c6", "accent": "#8ab4f8", "warning": "#ffb4ab"}
                   if dark else {"bg": "#f2f4f7", "surface": "#ffffff", "field": "#ffffff", "fg": "#17212f", "muted": "#455468", "accent": "#315efb", "warning": "#8b1e1e"})
        self.palette = palette
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.root.configure(background=palette["bg"])
        style.configure("TFrame", background=palette["bg"])
        style.configure("TLabel", background=palette["bg"], foreground=palette["fg"])
        style.configure("TButton", background=palette["surface"], foreground=palette["fg"], padding=5)
        style.map("TButton", background=[("active", palette["accent"])], foreground=[("active", "#ffffff")])
        style.configure("TEntry", fieldbackground=palette["field"], foreground=palette["fg"], insertcolor=palette["fg"])
        style.configure("TCombobox", fieldbackground=palette["field"], background=palette["surface"], foreground=palette["fg"], arrowcolor=palette["fg"])
        style.map("TCombobox", fieldbackground=[("readonly", palette["field"])], foreground=[("readonly", palette["fg"])])
        style.configure("Horizontal.TProgressbar", troughcolor=palette["surface"], background=palette["accent"])
        self.root.option_add("*TCombobox*Listbox.background", palette["field"])
        self.root.option_add("*TCombobox*Listbox.foreground", palette["fg"])
        if hasattr(self, "output"):
            self.output.configure(background=palette["field"], foreground=palette["fg"], insertbackground=palette["fg"], selectbackground=palette["accent"], selectforeground="#ffffff")
            self.output.master.winfo_children()[-1].configure(foreground=palette["muted"])
        for widget_name, color_key in (("warning_label", "warning"),):
            widget = getattr(self, widget_name, None)
            if widget:
                widget.configure(foreground=palette[color_key])

    def _watch_theme(self) -> None:
        if self.root.winfo_exists() and detect_dark_mode() != self._dark_mode:
            self._apply_theme()
        if self.root.winfo_exists():
            self.root.after(2500, self._watch_theme)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="CrossPlatform App Converter", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(outer, text=self._t("subtitle")).pack(anchor="w", pady=(3, 14))
        self.warning_label = ttk.Label(
            outer,
            text=self._t("warning"),
            foreground=self.palette["warning"],
            wraplength=1020,
            justify="left",
        )
        self.warning_label.pack(anchor="w", pady=(0, 10))
        self._file_row(outer, "Android APK", self.apk_path, ("Android package", "*.apk"))
        self._file_row(outer, "iOS IPA", self.ipa_path, ("iOS package", "*.ipa"))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(12, 4))
        self.analyze_button = ttk.Button(controls, text=self._t("analyze"), command=self.analyze)
        self.analyze_button.pack(side="left")
        ttk.Button(controls, text=self._t("save"), command=self.save_reports).pack(side="left", padx=(8, 0))
        portability_controls = ttk.Frame(outer)
        portability_controls.pack(fill="x", pady=(4, 10))
        ttk.Label(portability_controls, text=self._t("target")).pack(side="left", padx=(0, 6))
        ttk.Combobox(portability_controls, textvariable=self.target, values=("Android", "iOS"), state="readonly", width=10).pack(side="left")
        ttk.Button(portability_controls, text=self._t("scaffold"), command=self.make_scaffold).pack(side="left", padx=(8, 0))
        ttk.Button(portability_controls, text=self._t("conversion"), command=self.try_conversion).pack(side="left", padx=(8, 0))
        ttk.Button(portability_controls, text=self._t("recover"), command=self.recover_source).pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 8))
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(0, 8))
        self.output = ScrolledText(outer, wrap="word", font=("Consolas", 10), height=28, state="disabled")
        self.output.pack(fill="both", expand=True)
        ttk.Label(outer, text=self._t("originals"), foreground=self.palette["muted"]).pack(anchor="w", pady=(8, 0))
        self._apply_theme()

    def _file_row(self, parent: ttk.Frame, label: str, variable: tk.StringVar, filetype: tuple[str, str]) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=14).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        extension = filetype[1].replace("*", "")
        ttk.Button(row, text=self._t("select"), command=lambda: self._choose(variable, extension)).pack(side="left", padx=(8, 0))

    def _choose(self, variable: tk.StringVar, extension: str) -> None:
        path = filedialog.askopenfilename(filetypes=[(extension.upper().lstrip("."), f"*{extension}"), (self._t("all_files"), "*.*")])
        if path:
            variable.set(path)

    def _set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def analyze(self) -> None:
        paths = [value for value in (self.apk_path.get().strip(), self.ipa_path.get().strip()) if value]
        if not paths:
            messagebox.showinfo(self._t("pick_package"), self._t("pick_package_body"))
            return
        self.analyze_button.configure(state="disabled")
        self.progress.start(12)
        self.status.set(self._t("reading"))
        self._set_output("")

        def worker() -> None:
            try:
                result = build_report(paths)
                error = None
            except Exception as exc:  # show parse errors in the app instead of silently exiting
                result, error = None, exc
            self.root.after(0, lambda: self._analysis_finished(result, error))

        threading.Thread(target=worker, daemon=True).start()

    def _analysis_finished(self, result, error) -> None:
        self.progress.stop()
        self.analyze_button.configure(state="normal")
        if error:
            self.status.set(self._t("analysis_failed"))
            messagebox.showerror(self._t("analysis_error"), str(error))
            return
        self.report = result
        self._set_output(summarize(result, language=self.language))
        self.status.set(self._t("analysis_done", count=len(result.analyses)))

    def save_reports(self) -> None:
        if not self.report:
            messagebox.showinfo(self._t("no_analysis"), self._t("analyze_before_save"))
            return
        folder = filedialog.askdirectory(title=self._t("report_folder"))
        if not folder:
            return
        try:
            json_path = write_json_report(self.report, folder)
            html_path = write_html_report(self.report, folder)
        except OSError as exc:
            messagebox.showerror(self._t("save_failed"), str(exc))
            return
        self.status.set(self._t("reports_saved_status"))
        messagebox.showinfo(self._t("reports_saved"), f"JSON: {json_path}\nHTML: {html_path}")

    def make_scaffold(self) -> None:
        if not self.report or not self.report.analyses:
            messagebox.showinfo(self._t("no_analysis"), self._t("no_analysis_scaffold"))
            return
        source = self.report.analyses[0]
        target = self.target.get().lower()
        if (source.kind == "apk" and target == "android") or (source.kind == "ipa" and target == "ios"):
            messagebox.showerror(self._t("invalid_target"), self._t("opposite_target"))
            return
        folder = filedialog.askdirectory(title=self._t("scaffold_folder"))
        if not folder:
            return
        try:
            created = create_scaffold(source, target, folder)
        except (OSError, ValueError) as exc:
            messagebox.showerror(self._t("create_failed"), str(exc))
            return
        self.status.set(self._t("scaffold_created"))
        messagebox.showinfo(self._t("scaffold_created_title"), f"{created}\n\n{self._t('readme_limits')}")

    def try_conversion(self) -> None:
        if not self.report or not self.report.analyses:
            messagebox.showinfo(self._t("no_analysis"), self._t("no_analysis_conversion"))
            return
        source = self.report.analyses[0]
        folder = filedialog.askdirectory(title=self._t("conversion_folder"))
        if not folder:
            return
        self.analyze_button.configure(state="disabled")
        self.progress.start(12)
        self.status.set(self._t("creating"))

        def worker() -> None:
            try:
                result = create_conversion_attempt(source, folder)
                error = None
            except Exception as exc:
                result, error = None, exc
            self.root.after(0, lambda: self._conversion_finished(result, error))

        threading.Thread(target=worker, daemon=True).start()

    def _conversion_finished(self, result, error) -> None:
        self.progress.stop()
        self.analyze_button.configure(state="normal")
        if error:
            self.status.set(self._t("attempt_failed"))
            messagebox.showerror(self._t("attempt_error"), str(error))
            return
        bundle, copied, skipped = result
        self.status.set(self._t("draft_status", copied=copied, skipped=len(skipped)))
        messagebox.showwarning(
            self._t("draft_title"),
            self._t("draft_body", bundle=bundle),
        )

    def recover_source(self) -> None:
        if not self.report or not self.report.analyses:
            messagebox.showinfo(self._t("no_analysis"), self._t("no_analysis_recover"))
            return
        source = self.report.analyses[0]
        if source.kind != "apk":
            messagebox.showwarning(
                self._t("apk_only"), self._t("ipa_recovery"),
            )
            return
        folder = filedialog.askdirectory(title=self._t("recovery_folder"))
        if not folder:
            return
        self.analyze_button.configure(state="disabled")
        self.progress.start(12)
        self.status.set(self._t("recovering"))

        def worker() -> None:
            try:
                result = recover_apk(source, folder)
                error = None
            except Exception as exc:
                result, error = None, exc
            self.root.after(0, lambda: self._recovery_finished(result, error))

        threading.Thread(target=worker, daemon=True).start()

    def _recovery_finished(self, result, error) -> None:
        self.progress.stop()
        self.analyze_button.configure(state="normal")
        if error:
            self.status.set(self._t("recovery_failed"))
            messagebox.showerror(self._t("recovery_error"), str(error))
            return
        self.status.set(
            self._t("recovery_status", status=self._recovery_status(result.status), java=result.java_files, xml=result.xml_files,
                    layouts=result.layout_count, strings=result.string_count, errors=result.decompilation_errors,
                    omitted=result.unsafe_entries_omitted)
        )
        messagebox.showwarning(
            self._t("recovery_title"),
            self._t("recovery_body", directory=result.output_dir, java=result.java_files, xml=result.xml_files,
                    images=result.image_files, layouts=result.layout_count, strings=result.string_count,
                    errors=result.decompilation_errors, omitted=result.unsafe_entries_omitted),
        )


def main() -> None:
    root = tk.Tk()
    ConverterWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
