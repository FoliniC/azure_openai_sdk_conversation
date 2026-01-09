import argparse
import os
import shutil
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, ttk

import chardet


class UTF8ConverterApp:
    def __init__(self, root, args=None):
        self.root = root
        self.args = args
        self.auto_mode = args.auto if args else False
        self.root.title("UTF-8 File Converter - Ricorsivo")
        self.root.geometry("1100x800")
        self.root.resizable(True, True)

        # Variabili
        self.current_dir = args.dir if args and args.dir else os.getcwd()
        self.scanning = False
        self.converting = False
        self.results = []

        # Configurazione stile
        style = ttk.Style()
        style.theme_use("clam")

        # Colori personalizzati
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Stat.TFrame", relief="solid", borderwidth=1)

        self.setup_ui()

        # Applica parametri da riga di comando
        if args:
            if args.no_backup:
                self.backup_var.set(False)
            if args.newline:
                self.newline_mode.set(args.newline)

            if args.auto:
                self.log(
                    "🤖 Modalità automatica attivata. Avvio scansione tra 1 secondo...",
                    "info",
                )
                self.root.after(1000, self.start_scan)

    def setup_ui(self):
        # Frame principale
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configurazione grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)

        # Titolo
        title_label = ttk.Label(
            main_frame, text="🔤 UTF-8 File Converter", style="Title.TLabel"
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))

        # Frame directory corrente
        dir_frame = ttk.LabelFrame(main_frame, text="Directory Corrente", padding="10")
        dir_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        dir_frame.columnconfigure(0, weight=1)

        dir_inner_frame = ttk.Frame(dir_frame)
        dir_inner_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        dir_inner_frame.columnconfigure(0, weight=1)

        self.dir_label = ttk.Label(
            dir_inner_frame,
            text=self.current_dir,
            font=("Consolas", 9),
            foreground="blue",
        )
        self.dir_label.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))

        change_dir_button = ttk.Button(
            dir_inner_frame, text="Cambia", command=self.change_directory, width=10
        )
        change_dir_button.grid(row=0, column=1)

        # Frame opzioni
        options_frame = ttk.LabelFrame(
            main_frame, text="Opzioni di Scansione", padding="10"
        )
        options_frame.grid(
            row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10)
        )
        options_frame.columnconfigure(1, weight=1)

        # Estensioni da includere
        ttk.Label(options_frame, text="Estensioni da analizzare:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10)
        )
        self.extensions_var = tk.StringVar(
            value=".txt,.py,.js,.html,.css,.json,.xml,.md,.csv,.log,.yaml,.yml,.ini,.cfg,.conf,.java,.c,.cpp,.h,.hpp,.rs,.go,.php,.rb,.sh,.bat,.ps1"
        )
        self.extensions_entry = ttk.Entry(
            options_frame, textvariable=self.extensions_var, width=80
        )
        self.extensions_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 5))

        # Checkbox per creare backup
        self.backup_var = tk.BooleanVar(value=True)
        self.backup_check = ttk.Checkbutton(
            options_frame,
            text="Crea file .backup prima di convertire (consigliato)",
            variable=self.backup_var,
        )
        self.backup_check.grid(row=1, column=0, columnspan=2, sticky=tk.W)

        # Checkbox per cartelle da escludere
        self.skip_hidden_var = tk.BooleanVar(value=True)
        self.skip_hidden_check = ttk.Checkbutton(
            options_frame,
            text="Salta cartelle nascoste e di sistema (.git, node_modules, __pycache__, ecc.)",
            variable=self.skip_hidden_var,
        )
        self.skip_hidden_check.grid(row=2, column=0, columnspan=2, sticky=tk.W)

        # Frame opzioni conversione newline
        newline_frame = ttk.LabelFrame(
            main_frame, text="Opzioni Conversione Newline", padding="10"
        )
        newline_frame.grid(
            row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10)
        )
        newline_frame.columnconfigure(0, weight=1)

        # Opzioni di conversione newline
        self.newline_mode = tk.StringVar(value="none")  # none, windows, unix, auto

        newline_inner_frame = ttk.Frame(newline_frame)
        newline_inner_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        newline_inner_frame.columnconfigure(0, weight=1)

        ttk.Radiobutton(
            newline_inner_frame,
            text="Non convertire i newline",
            variable=self.newline_mode,
            value="none",
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 20))

        ttk.Radiobutton(
            newline_inner_frame,
            text="Converti a Windows (CRLF - \\r\\n)",
            variable=self.newline_mode,
            value="windows",
        ).grid(row=0, column=1, sticky=tk.W, padx=(0, 20))

        ttk.Radiobutton(
            newline_inner_frame,
            text="Converti a Unix (LF - \\n)",
            variable=self.newline_mode,
            value="unix",
        ).grid(row=0, column=2, sticky=tk.W, padx=(0, 20))

        ttk.Radiobutton(
            newline_inner_frame,
            text="Rileva e normalizza (a Windows)",
            variable=self.newline_mode,
            value="auto",
        ).grid(row=0, column=3, sticky=tk.W)

        # Informazioni sui newline
        info_label = ttk.Label(
            newline_frame,
            text="Windows: CRLF (\\r\\n) | Unix/Mac: LF (\\n) | Mac Classic: CR (\\r)",
            font=("Segoe UI", 8),
        )
        info_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))

        # Frame statistiche
        stats_frame = ttk.Frame(main_frame)
        stats_frame.grid(
            row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10)
        )
        for i in range(5):
            stats_frame.columnconfigure(i, weight=1)

        # Statistiche
        self.stat_total = self.create_stat_box(
            stats_frame, "Totale File", "0", 0, "#E3F2FD"
        )
        self.stat_utf8 = self.create_stat_box(
            stats_frame, "UTF-8/ASCII", "0", 1, "#C8E6C9"
        )
        self.stat_convertible = self.create_stat_box(
            stats_frame, "Convertibili", "0", 2, "#FFF9C4"
        )
        self.stat_newline = self.create_stat_box(
            stats_frame, "Newline Misti", "0", 3, "#E1BEE7"
        )
        self.stat_errors = self.create_stat_box(
            stats_frame, "Errori", "0", 4, "#FFCDD2"
        )

        # Progress bar
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.grid(
            row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10)
        )
        self.progress_frame.columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))

        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.progress_label.grid(row=1, column=0, sticky=tk.W)

        # Area di log
        log_frame = ttk.LabelFrame(main_frame, text="Log Operazioni", padding="5")
        log_frame.grid(
            row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10)
        )
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=15, wrap=tk.WORD, font=("Consolas", 9), bg="#FAFAFA"
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Tag per colori
        self.log_text.tag_config("success", foreground="#2E7D32")
        self.log_text.tag_config("warning", foreground="#F57C00")
        self.log_text.tag_config("error", foreground="#C62828")
        self.log_text.tag_config("info", foreground="#1565C0")
        self.log_text.tag_config("newline", foreground="#7B1FA2")

        # Frame pulsanti
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=3)

        self.scan_button = ttk.Button(
            button_frame,
            text="🔍 Scansiona Directory",
            command=self.start_scan,
            width=25,
        )
        self.scan_button.grid(row=0, column=0, padx=5)

        self.convert_button = ttk.Button(
            button_frame,
            text="🔄 Converti Tutti i File",
            command=self.start_convert_all_files,
            width=25,
            state="disabled",
        )
        self.convert_button.grid(row=0, column=1, padx=5)

        self.clear_button = ttk.Button(
            button_frame, text="🗑️ Pulisci Log", command=self.clear_log, width=25
        )
        self.clear_button.grid(row=0, column=2, padx=5)

        # Aggiunto: Pulsante per mostrare comando CLI
        self.cli_button = ttk.Button(
            button_frame,
            text="📋 Mostra Comando CLI",
            command=self.show_cli_command,
            width=25,
        )
        self.cli_button.grid(row=0, column=3, padx=5)

    def create_stat_box(self, parent, label, value, column, color):
        frame = tk.Frame(parent, relief="solid", borderwidth=1, bg=color)
        frame.grid(row=0, column=column, sticky=(tk.W, tk.E), padx=5)

        label_widget = tk.Label(
            frame, text=label, font=("Segoe UI", 9), bg=color, fg="black"
        )
        label_widget.pack(pady=(8, 2))

        value_widget = tk.Label(
            frame, text=value, font=("Segoe UI", 18, "bold"), bg=color, fg="black"
        )
        value_widget.pack(pady=(2, 8))

        return value_widget

    def log(self, message, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")

        # Colora l'ultima riga
        last_line = self.log_text.index("end-1c linestart")
        self.log_text.tag_add(level, last_line, "end-1c")

        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def clear_log(self):
        self.log_text.delete(1.0, tk.END)

    def change_directory(self):
        new_dir = filedialog.askdirectory(
            initialdir=self.current_dir, title="Seleziona Directory"
        )
        if new_dir:
            self.current_dir = new_dir
            self.dir_label.config(text=self.current_dir)
            self.results = []
            self.update_stats(0, 0, 0, 0, 0)
            self.clear_log()
            self.log(f"Directory cambiata: {self.current_dir}", "info")

    def get_extensions(self):
        ext_str = self.extensions_var.get()
        extensions = [ext.strip() for ext in ext_str.split(",")]
        return [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

    def detect_encoding(self, file_path):
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read()

            if len(raw_data) == 0:
                return "empty", 1.0

            # Verifica BOM UTF-8
            if raw_data[:3] == b"\xef\xbb\xbf":
                return "utf-8-sig", 1.0

            # Verifica BOM UTF-16
            if raw_data[:2] == b"\xff\xfe":
                return "utf-16-le", 1.0
            if raw_data[:2] == b"\xfe\xff":
                return "utf-16-be", 1.0

            # PRIORITÀ ASSOLUTA: Prova UTF-8 prima di tutto
            try:
                raw_data.decode("utf-8")
                return "utf-8", 1.0
            except UnicodeDecodeError:
                pass

            # Se è tutto ASCII, è compatibile con UTF-8
            try:
                raw_data.decode("ascii")
                return "ascii", 1.0
            except UnicodeDecodeError:
                pass

            # Solo ora usa chardet per altri encoding
            result = chardet.detect(raw_data)
            encoding = result["encoding"]
            confidence = result["confidence"]

            if encoding:
                encoding = encoding.lower()

                # Se chardet suggerisce UTF-8, verifica che sia davvero UTF-8
                if "utf-8" in encoding or "utf8" in encoding:
                    try:
                        raw_data.decode("utf-8")
                        return "utf-8", confidence
                    except UnicodeDecodeError:
                        pass

                # Se chardet suggerisce Windows-1252 o ISO-8859-1
                if encoding in ["windows-1252", "iso-8859-1", "latin-1", "cp1252"]:
                    try:
                        # Prova ancora UTF-8
                        raw_data.decode("utf-8")
                        return "utf-8", 1.0
                    except UnicodeDecodeError:
                        pass

            return encoding if encoding else "windows-1252", confidence

        except Exception:
            return None, 0.0

    def detect_newline_type(self, content):
        """Rileva il tipo di newline presente nel file"""

        # Conta le occorrenze
        crlf_count = content.count("\r\n")
        cr_count = content.count("\r") - crlf_count  # CR che non sono parte di CRLF
        lf_count = content.count("\n") - crlf_count  # LF che non sono parte di CRLF

        # Determina il tipo dominante
        if crlf_count > 0 and lf_count == 0 and cr_count == 0:
            return "windows", crlf_count, 0, 0
        elif lf_count > 0 and crlf_count == 0 and cr_count == 0:
            return "unix", 0, lf_count, 0
        elif cr_count > 0 and crlf_count == 0 and lf_count == 0:
            return "mac", 0, 0, cr_count
        else:
            # Newline misti
            return "mixed", crlf_count, lf_count, cr_count

    def normalize_newlines(self, content, target_mode):
        """Normalizza i newline secondo il modo specificato"""
        if target_mode == "windows":
            # Converti tutto a Windows (CRLF)
            # Prima sostituisci CRLF esistenti con LF per evitare duplicati
            content = content.replace("\r\n", "\n")
            # Poi sostituisci CR con LF (per file Mac classic)
            content = content.replace("\r", "\n")
            # Infine converte tutto a CRLF
            content = content.replace("\n", "\r\n")
        elif target_mode == "unix":
            # Converti tutto a Unix (LF)
            content = content.replace("\r\n", "\n")
            content = content.replace("\r", "\n")
        elif target_mode == "auto":
            # Rileva il newline più comune e normalizza a Windows
            nl_type, crlf_count, lf_count, cr_count = self.detect_newline_type(content)

            if nl_type == "unix":
                # Se è già Unix, converti a Windows (come richiesto)
                content = content.replace("\n", "\r\n")
            elif nl_type == "mac":
                # Mac classic a Windows
                content = content.replace("\r", "\r\n")
            elif nl_type == "mixed":
                # Se misti, normalizza a Windows
                content = content.replace("\r\n", "\n")
                content = content.replace("\r", "\n")
                content = content.replace("\n", "\r\n")
            # Se è già Windows, non fare nulla

        return content

    def update_stats(self, total, utf8, convertible, newline_mixed, errors):
        self.stat_total.config(text=str(total))
        self.stat_utf8.config(text=str(utf8))
        self.stat_convertible.config(text=str(convertible))
        self.stat_newline.config(text=str(newline_mixed))
        self.stat_errors.config(text=str(errors))

    def scan_directory(self):
        self.scanning = True
        self.results = []
        self.scan_button.config(state="disabled")
        # SOLO se modalità newline è "none", disattiva convert_button
        # Altrimenti mantieni lo stato corrente (potrebbe essere già attivo)
        if self.newline_mode.get() == "none":
            self.convert_button.config(state="disabled")
        self.progress_var.set(0)

        self.log("=" * 80)
        self.log("🔍 Inizio scansione ricorsiva...", "info")
        self.log(f"📁 Directory: {self.current_dir}", "info")
        self.log(f"📄 Opzione Newline: {self.newline_mode.get()}", "info")
        self.log("=" * 80)

        total_files = 0
        utf8_files = 0
        convertible_files = 0
        newline_mixed_files = 0
        error_files = 0

        # Directory da escludere
        excluded_dirs = (
            {
                ".git",
                "node_modules",
                "__pycache__",
                "venv",
                ".venv",
                "env",
                ".env",
                "dist",
                "build",
                ".idea",
                ".vscode",
                "target",
                "bin",
                "obj",
            }
            if self.skip_hidden_var.get()
            else set()
        )

        try:
            # Prima conta i file totali per la progress bar
            all_files = []
            for root, dirs, files in os.walk(self.current_dir):
                # Filtra directory da escludere
                if self.skip_hidden_var.get():
                    dirs[:] = [
                        d
                        for d in dirs
                        if not d.startswith(".") and d not in excluded_dirs
                    ]

                for filename in files:
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext in self.get_extensions():
                        all_files.append(os.path.join(root, filename))

            total_to_scan = len(all_files)
            self.progress_label.config(
                text=f"Trovati {total_to_scan} file da analizzare..."
            )

            # Scansione file
            for idx, file_path in enumerate(all_files):
                if not self.scanning:  # Permette di interrompere
                    break

                filename = os.path.basename(file_path)
                rel_path = os.path.relpath(file_path, self.current_dir)

                # Aggiorna progress bar
                progress = ((idx + 1) / total_to_scan) * 100
                self.progress_var.set(progress)
                self.progress_label.config(
                    text=f"Scansione: {idx + 1}/{total_to_scan} - {filename}"
                )
                self.root.update_idletasks()

                total_files += 1
                encoding, confidence = self.detect_encoding(file_path)

                # Rileva tipo di newline se necessario
                newline_type = "unknown"
                newline_info = ""
                newline_status = "ok"

                if encoding and encoding != "error" and encoding != "empty":
                    try:
                        # Leggi il contenuto per analizzare i newline
                        with open(
                            file_path, "r", encoding=encoding, errors="ignore"
                        ) as f:
                            content = f.read()

                        nl_type, crlf_count, lf_count, cr_count = (
                            self.detect_newline_type(content)
                        )

                        # Verifica se ci sono newline misti
                        if nl_type == "mixed":
                            newline_mixed_files += 1
                            newline_status = "mixed"
                            newline_info = f" [NL: MISTI CRLF:{crlf_count} LF:{lf_count} CR:{cr_count}]"
                            self.log(
                                f"⚠ NEWLINE MISTI: {rel_path}{newline_info}", "newline"
                            )
                        else:
                            newline_info = f" [NL: {nl_type.upper()}]"
                        newline_type = nl_type  # 'windows', 'unix', 'mac', o 'mixed'

                    except Exception as e:
                        newline_info = " [NL: ERRORE RILEVAMENTO]"
                        self.log(
                            f"⚠ Errore analisi newline: {rel_path} - {str(e)}",
                            "warning",
                        )

                if encoding is None:
                    self.log(f"❌ ERRORE: {rel_path}", "error")
                    error_files += 1
                    self.results.append(
                        {
                            "path": file_path,
                            "rel_path": rel_path,
                            "encoding": "error",
                            "confidence": 0.0,
                            "newline_status": newline_status,
                            "newline_type": newline_type,
                            "newline_info": newline_info,
                            "status": "error",
                        }
                    )
                elif encoding in ["utf-8", "ascii", "empty"]:
                    log_msg = f"✓ OK: {rel_path} [{encoding.upper()}]{newline_info}"
                    if newline_status == "mixed":
                        self.log(log_msg, "newline")
                    else:
                        self.log(log_msg, "success")
                    utf8_files += 1
                    self.results.append(
                        {
                            "path": file_path,
                            "rel_path": rel_path,
                            "encoding": encoding,
                            "confidence": confidence,
                            "newline_status": newline_status,
                            "newline_type": newline_type,
                            "newline_info": newline_info,
                            "status": "ok"
                            if newline_status == "ok"
                            else "convertible_nl",
                        }
                    )
                elif encoding == "utf-8-sig":
                    log_msg = f"⚠ DA CONVERTIRE: {rel_path} [UTF-8-SIG → UTF-8 (rimuovi BOM)]{newline_info}"
                    if newline_status == "mixed":
                        self.log(log_msg, "newline")
                    else:
                        self.log(log_msg, "warning")
                    convertible_files += 1
                    self.results.append(
                        {
                            "path": file_path,
                            "rel_path": rel_path,
                            "encoding": encoding,
                            "confidence": confidence,
                            "newline_status": newline_status,
                            "newline_type": newline_type,
                            "newline_info": newline_info,
                            "status": "convertible",
                        }
                    )
                else:
                    conf_str = f"{confidence:.0%}" if confidence else "?"
                    enc_str = encoding.upper() if encoding else "UNKNOWN"
                    log_msg = f"⚠ DA CONVERTIRE: {rel_path} [{enc_str} - {conf_str}]{newline_info}"
                    if newline_status == "mixed":
                        self.log(log_msg, "newline")
                    else:
                        self.log(log_msg, "warning")
                    convertible_files += 1
                    self.results.append(
                        {
                            "path": file_path,
                            "rel_path": rel_path,
                            "encoding": encoding,
                            "confidence": confidence,
                            "newline_status": newline_status,
                            "newline_type": newline_type,
                            "newline_info": newline_info,
                            "status": "convertible",
                        }
                    )

                # Aggiorna statistiche in tempo reale
                self.update_stats(
                    total_files,
                    utf8_files,
                    convertible_files,
                    newline_mixed_files,
                    error_files,
                )

            self.progress_var.set(100)
            self.progress_label.config(text="Scansione completata!")

            self.log("=" * 80)
            self.log(f"📊 Scansione completata: {total_files} file analizzati", "info")
            self.log(
                f"   UTF-8/ASCII: {utf8_files} | Convertibili: {convertible_files} | Newline Misti: {newline_mixed_files} | Errori: {error_files}",
                "info",
            )
            self.log("=" * 80)

            newline_mode = self.newline_mode.get()

            # Controlla se ci sono file Unix o Windows in base alla modalità
            has_target_files = False
            if newline_mode != "none":
                for r in self.results:
                    info = r.get("newline_info", "")
                    newline_type = r.get("newline_type", "")

                    # Per modalità "windows": cerca file Unix o Mac
                    if newline_mode == "windows" and (
                        newline_type in ["unix", "mac"] or "[NL: UNIX]" in info
                    ):
                        has_target_files = True
                        break
                    # Per modalità "unix": cerca file Windows o Mac
                    elif newline_mode == "unix" and (
                        newline_type in ["windows", "mac"] or "[NL: WINDOWS]" in info
                    ):
                        has_target_files = True
                        break
                    # Per modalità "auto": cerca qualsiasi file non-Windows
                    elif newline_mode == "auto" and newline_type in [
                        "unix",
                        "mac",
                        "mixed",
                    ]:
                        has_target_files = True
                        break

            # Attiva il bottone se:
            # 1. Ci sono file da convertire (encoding) O
            # 2. Ci sono file con newline misti O
            # 3. Modalità newline attiva E ci sono file target
            if (
                convertible_files > 0
                or newline_mixed_files > 0
                or (newline_mode != "none" and has_target_files)
            ):
                self.convert_button.config(state="normal")
            else:
                messagebox.showinfo(
                    "Scansione Completata",
                    "Tutti i file sono già in UTF-8/ASCII con newline consistenti!",
                )

        except Exception as e:
            self.log(f"❌ Errore durante la scansione: {str(e)}", "error")
            messagebox.showerror("Errore", f"Errore durante la scansione:\n{str(e)}")

        finally:
            self.scanning = False
            self.scan_button.config(state="normal")

            if self.auto_mode:
                self.root.after(500, self.auto_run_conversion)

    def start_scan(self):
        if not self.scanning:
            thread = threading.Thread(target=self.scan_directory, daemon=True)
            thread.start()

    def auto_run_conversion(self):
        """Avvia la conversione automaticamente senza chiedere conferma"""
        if self.converting:
            return

        newline_mode = self.newline_mode.get()
        convertible_count = 0

        for r in self.results:
            include = False
            if r["status"] in ["convertible", "convertible_nl"]:
                include = True
            if r["newline_status"] == "mixed" and newline_mode != "none":
                include = True
            if newline_mode != "none":
                nl_type = r.get("newline_type", "")
                if newline_mode == "windows" and nl_type in ["unix", "mac"]:
                    include = True
                elif newline_mode == "unix" and nl_type in ["windows", "mac"]:
                    include = True
                elif newline_mode == "auto" and nl_type in ["unix", "mac", "mixed"]:
                    include = True

            if include:
                convertible_count += 1

        if convertible_count > 0:
            self.log(
                f"🤖 Modalità automatica: avvio conversione di {convertible_count} file...",
                "info",
            )
            thread = threading.Thread(target=self.convert_all_files, daemon=True)
            thread.start()
        else:
            self.log("🤖 Modalità automatica: nulla da convertire.", "info")
            self.auto_mode = False

    def convert_file(self, file_info):
        file_path = file_info["path"]
        encoding = file_info["encoding"]
        newline_mode = self.newline_mode.get()

        try:
            # Gestione speciale per UTF-8-SIG (rimuovi BOM)
            if encoding == "utf-8-sig":
                with open(file_path, "rb") as f:
                    content_bytes = f.read()

                # Rimuovi BOM (primi 3 bytes: EF BB BF)
                if content_bytes[:3] == b"\xef\xbb\xbf":
                    content_bytes = content_bytes[3:]

                # Decodifica
                try:
                    content = content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    content = content_bytes.decode("utf-8", errors="replace")

                # Applica conversione newline se richiesta
                if newline_mode != "none":
                    content = self.normalize_newlines(content, newline_mode)

                # Crea backup se richiesto
                if self.backup_var.get():
                    backup_path = file_path + ".backup"
                    shutil.copy2(file_path, backup_path)

                # Scrivi in UTF-8 senza BOM
                with open(file_path, "w", encoding="utf-8", newline="") as f:
                    f.write(content)

                return True, None

            # Conversione normale per altri encoding
            # Prova diversi encoding in ordine di probabilità
            content = None

            # Lista di encoding da provare in ordine
            encodings_to_try = [encoding]
            if encoding and encoding not in ["utf-8", "ascii"]:
                # Aggiungi varianti comuni
                if "windows" in encoding or "cp" in encoding:
                    encodings_to_try.extend(
                        ["windows-1252", "cp1252", "latin-1", "iso-8859-1"]
                    )
                encodings_to_try.extend(["utf-8", "latin-1"])

            # Rimuovi duplicati mantenendo l'ordine
            seen = set()
            encodings_to_try = [
                x for x in encodings_to_try if x and not (x in seen or seen.add(x))
            ]

            # Prova ogni encoding
            for enc in encodings_to_try:
                try:
                    with open(file_path, "r", encoding=enc, errors="strict") as f:
                        content = f.read()
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            # Se nessun encoding ha funzionato, usa l'originale con errors='replace'
            if content is None:
                with open(
                    file_path,
                    "r",
                    encoding=encoding if encoding else "latin-1",
                    errors="replace",
                ) as f:
                    content = f.read()

            # Applica conversione newline se richiesta
            if newline_mode != "none":
                content = self.normalize_newlines(content, newline_mode)

            # Crea backup se richiesto
            if self.backup_var.get():
                backup_path = file_path + ".backup"
                shutil.copy2(file_path, backup_path)

            # Scrivi in UTF-8 senza BOM
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                f.write(content)

            return True, None

        except Exception as e:
            return False, str(e)

    def convert_all_files(self):
        self.converting = True
        self.convert_button.config(state="disabled")
        self.scan_button.config(state="disabled")
        self.progress_var.set(0)

        self.log("=" * 80)
        newline_mode = self.newline_mode.get()
        newline_text = {
            "none": "senza conversione newline",
            "windows": "con conversione a Windows (CRLF)",
            "unix": "con conversione a Unix (LF)",
            "auto": "con rilevamento e normalizzazione a Windows",
        }.get(newline_mode, "")

        self.log(f"🔄 Inizio conversione file {newline_text}...", "info")
        self.log("=" * 80)

        converted = 0
        failed = 0

        # File da convertire:
        # 1. Quelli con encoding diverso da UTF-8/ASCII
        # 2. Quelli con newline misti (se newline_mode attivo)
        # 3. Se newline_mode attivo, anche file con newline del tipo sbagliato
        convertible_files = []
        for r in self.results:
            include = False
            reason = []

            # Motivo 1: Encoding da convertire
            if r["status"] in ["convertible", "convertible_nl"]:
                include = True
                reason.append("encoding")

            # Motivo 2: Newline misti (se modalità attiva)
            if r["newline_status"] == "mixed" and newline_mode != "none":
                include = True
                reason.append("newline_mixed")

            # Motivo 3: Newline del tipo sbagliato (se modalità specifica selezionata)
            if newline_mode != "none":
                nl_type = r.get("newline_type", "")
                if newline_mode == "windows" and nl_type in ["unix", "mac"]:
                    include = True
                    reason.append("unix_to_windows")
                elif newline_mode == "unix" and nl_type in ["windows", "mac"]:
                    include = True
                    reason.append("windows_to_unix")
                elif newline_mode == "auto" and nl_type in ["unix", "mac", "mixed"]:
                    include = True
                    reason.append("auto_normalize")

            if include:
                r["convert_reason"] = ", ".join(reason)
                convertible_files.append(r)

        total_to_convert = len(convertible_files)

        for idx, file_info in enumerate(convertible_files):
            if not self.converting:  # Permette di interrompere
                break

            rel_path = file_info["rel_path"]

            # Aggiorna progress bar
            progress = ((idx + 1) / total_to_convert) * 100
            self.progress_var.set(progress)
            self.progress_label.config(
                text=f"Conversione: {idx + 1}/{total_to_convert}"
            )
            self.root.update_idletasks()

            success, error = self.convert_file(file_info)

            if success:
                reason = []
                if file_info["status"] in ["convertible", "convertible_nl"]:
                    reason.append("encoding")
                if file_info["newline_status"] == "mixed" and newline_mode != "none":
                    reason.append("newline")

                reason_text = f" ({' + '.join(reason)})" if reason else ""
                self.log(f"✓ CONVERTITO{reason_text}: {rel_path}", "success")
                converted += 1
                file_info["status"] = "converted"
                file_info["encoding"] = "utf-8"
                file_info["newline_status"] = "ok"
            else:
                self.log(f"❌ FALLITO: {rel_path} - {error}", "error")
                failed += 1
                file_info["status"] = "error"

        self.progress_var.set(100)
        self.progress_label.config(text="Conversione completata!")

        # Aggiorna statistiche
        utf8_count = len(
            [r for r in self.results if r["status"] in ["ok", "converted"]]
        )
        convertible_count = len(
            [r for r in self.results if r["status"] == "convertible"]
        )
        newline_mixed_count = len(
            [r for r in self.results if r["newline_status"] == "mixed"]
        )
        error_count = len([r for r in self.results if r["status"] == "error"])

        self.update_stats(
            len(self.results),
            utf8_count,
            convertible_count,
            newline_mixed_count,
            error_count,
        )

        self.log("=" * 80)
        self.log(
            f"✅ Conversione completata: {converted} convertiti, {failed} falliti",
            "info",
        )
        self.log("=" * 80)

        if converted > 0 and not self.auto_mode:
            messagebox.showinfo(
                "Completato",
                f"Conversione completata!\n\n"
                f"✓ Convertiti: {converted}\n"
                f"✗ Falliti: {failed}\n\n"
                f"Opzione newline: {newline_text}\n\n"
                f"{'I file originali sono stati salvati con estensione .backup' if self.backup_var.get() else ''}",
            )

        if self.auto_mode:
            self.auto_mode = False  # Disabilita dopo il completamento
            self.log("🤖 Modalità automatica: procedura completata.", "info")

        self.converting = False
        self.scan_button.config(state="normal")
        if (
            len(
                [
                    r
                    for r in self.results
                    if r["status"] in ["convertible", "convertible_nl"]
                ]
            )
            > 0
        ):
            self.convert_button.config(state="normal")

    def start_convert_all_files(self):
        if not self.converting:
            # Calcola i file da convertire usando la stessa logica di convert_all_files
            newline_mode = self.newline_mode.get()
            convertible_count = 0

            for r in self.results:
                include = False

                # Motivo 1: Encoding da convertire
                if r["status"] in ["convertible", "convertible_nl"]:
                    include = True

                # Motivo 2: Newline misti (se modalità attiva)
                if r["newline_status"] == "mixed" and newline_mode != "none":
                    include = True

                # Motivo 3: Newline del tipo sbagliato (se modalità specifica)
                if newline_mode != "none":
                    nl_type = r.get("newline_type", "")
                    if newline_mode == "windows" and nl_type in ["unix", "mac"]:
                        include = True
                    elif newline_mode == "unix" and nl_type in ["windows", "mac"]:
                        include = True
                    elif newline_mode == "auto" and nl_type in ["unix", "mac", "mixed"]:
                        include = True

                if include:
                    convertible_count += 1

            response = messagebox.askyesno(
                "Conferma Conversione",
                f"Stai per convertire {convertible_count} file.\n\n"
                f"{'Verrà creato un file .backup per ogni file convertito.' if self.backup_var.get() else 'ATTENZIONE: I file originali verranno sovrascritti!'}\n\n"
                f"Opzione newline: {self.newline_mode.get()}\n\n"
                "Continuare?",
            )

            if response:
                thread = threading.Thread(target=self.convert_all_files, daemon=True)
                thread.start()

    def show_cli_command(self):
        """Mostra il comando da riga di comando per effettuare la conversione"""
        # Ottieni il percorso dello script corrente
        script_path = os.path.abspath(__file__)

        # Costruisci il comando CLI
        command_parts = [sys.executable, script_path]

        # Aggiungi directory
        command_parts.append(f'--dir "{self.current_dir}"')

        # Aggiungi estensioni (se diverse da default)
        current_extensions = self.extensions_var.get()

        # Per semplicità, mostriamo sempre le estensioni attuali
        command_parts.append(f'--extensions "{current_extensions}"')

        # Aggiungi opzione no-backup se disabilitato
        if not self.backup_var.get():
            command_parts.append("--no-backup")

        # Aggiungi opzione newline se diversa da "none"
        if self.newline_mode.get() != "none":
            command_parts.append(f"--newline {self.newline_mode.get()}")

        # Aggiungi modalità automatica
        command_parts.append("--auto")

        # Combina tutto in un comando
        cli_command = " ".join(command_parts)

        # Mostra il comando
        self.log("=" * 80, "info")
        self.log("📋 COMANDO CLI PER LA CONVERSIONE:", "info")
        self.log("=" * 80, "info")
        self.log(cli_command, "info")
        self.log("", "info")
        self.log("Spiegazione parametri:", "info")
        self.log(f'  --dir "{self.current_dir}"     : Directory da elaborare', "info")
        self.log(
            f'  --extensions "{current_extensions}" : Tipi di file da elaborare', "info"
        )
        if not self.backup_var.get():
            self.log("  --no-backup               : Non crea file di backup", "info")
        if self.newline_mode.get() != "none":
            self.log(
                f"  --newline {self.newline_mode.get():<16} : Conversione newline",
                "info",
            )
        self.log(
            "  --auto                    : Esegue automaticamente scansione e conversione",
            "info",
        )
        self.log("=" * 80, "info")

        # Copia negli appunti
        try:
            import pyperclip

            pyperclip.copy(cli_command)
            self.log("✅ Comando copiato negli appunti!", "success")
        except ImportError:
            self.log(
                "⚠ Installare 'pyperclip' per copiare automaticamente: pip install pyperclip",
                "warning",
            )

    def force_enable_convert(self):
        """Forza l'attivazione del bottone converti (per debug)"""
        self.convert_button.config(state="normal")
        print("DEBUG: Bottone forzatamente attivato")


def run_command_line(args):
    """Esegue la conversione da riga di comando"""
    print("=" * 80)
    print("🔤 UTF-8 File Converter - Modalità Comando")
    print("=" * 80)

    if not os.path.isdir(args.dir):
        print(f"❌ ERRORE: La directory '{args.dir}' non esiste!")
        sys.exit(1)

    # Ottieni estensioni
    extensions = [ext.strip() for ext in args.extensions.split(",")]
    extensions = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

    print(f"📁 Directory: {args.dir}")
    print(f"📄 Estensioni: {', '.join(extensions)}")
    print(f"💾 Backup: {'NO (--no-backup)' if args.no_backup else 'SI (crea .backup)'}")
    print(f"↩️  Newline: {args.newline}")
    print("=" * 80)

    # Directory da escludere
    excluded_dirs = {
        ".git",
        "node_modules",
        "__pycache__",
        "venv",
        ".venv",
        "env",
        ".env",
        "dist",
        "build",
        ".idea",
        ".vscode",
        "target",
        "bin",
        "obj",
    }

    try:
        # Trova tutti i file
        print("🔍 Ricerca file...")
        all_files = []
        for root, dirs, files in os.walk(args.dir):
            # Filtra directory da escludere
            dirs[:] = [
                d for d in dirs if not d.startswith(".") and d not in excluded_dirs
            ]

            for filename in files:
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in extensions:
                    all_files.append(os.path.join(root, filename))

        print(f"📊 Trovati {len(all_files)} file da analizzare")

        if not all_files:
            print("ℹ️  Nessun file trovato con le estensioni specificate.")
            sys.exit(0)

        # Chiedi conferma
        if not args.auto:
            response = input(f"Convertire {len(all_files)} file? (s/n): ")
            if response.lower() != "s":
                print("⏹️  Operazione annullata.")
                sys.exit(0)

        # Funzione semplificata di rilevamento encoding
        def simple_detect_encoding(file_path):
            try:
                with open(file_path, "rb") as f:
                    raw_data = f.read()

                if len(raw_data) == 0:
                    return "empty"

                # Verifica BOM UTF-8
                if raw_data[:3] == b"\xef\xbb\xbf":
                    return "utf-8-sig"

                # Prova UTF-8
                try:
                    raw_data.decode("utf-8")
                    return "utf-8"
                except UnicodeDecodeError:
                    pass

                # Prova ASCII
                try:
                    raw_data.decode("ascii")
                    return "ascii"
                except UnicodeDecodeError:
                    pass

                # Usa chardet
                result = chardet.detect(raw_data)
                return result["encoding"] if result["encoding"] else "windows-1252"

            except Exception:
                return None

        # Converti i file
        converted = 0
        failed = 0

        for idx, file_path in enumerate(all_files):
            rel_path = os.path.relpath(file_path, args.dir)
            print(f"[{idx + 1}/{len(all_files)}] Analisi: {rel_path}")

            encoding = simple_detect_encoding(file_path)

            if encoding in ["utf-8", "ascii", "empty"] and args.newline == "none":
                print("  ✓ Già in UTF-8/ASCII")
                continue

            # Converti il file
            try:
                # Leggi il contenuto
                with open(
                    file_path,
                    "r",
                    encoding=encoding if encoding else "latin-1",
                    errors="replace",
                ) as f:
                    content = f.read()

                # Applica conversione newline se richiesta
                if args.newline != "none":
                    # Funzione semplificata per normalizzare newline
                    if args.newline == "windows":
                        content = (
                            content.replace("\r\n", "\n")
                            .replace("\r", "\n")
                            .replace("\n", "\r\n")
                        )
                    elif args.newline == "unix":
                        content = content.replace("\r\n", "\n").replace("\r", "\n")
                    elif args.newline == "auto":
                        # Per semplicità, converte a Windows
                        content = (
                            content.replace("\r\n", "\n")
                            .replace("\r", "\n")
                            .replace("\n", "\r\n")
                        )

                # Crea backup se richiesto
                if not args.no_backup:
                    backup_path = file_path + ".backup"
                    shutil.copy2(file_path, backup_path)

                # Scrivi in UTF-8
                with open(file_path, "w", encoding="utf-8", newline="") as f:
                    f.write(content)

                print("  ✓ Convertito a UTF-8")
                converted += 1

            except Exception as e:
                print(f"  ✗ Errore: {str(e)}")
                failed += 1

        print("=" * 80)
        print("✅ CONVERSIONE COMPLETATA")
        print(f"   ✓ Convertiti: {converted}")
        print(f"   ✗ Falliti: {failed}")
        print("=" * 80)

    except Exception as e:
        print(f"❌ Errore durante l'esecuzione: {str(e)}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="UTF-8 File Converter - Converte file in UTF-8 con normalizzazione newline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi di utilizzo:
  %(prog)s                      # Avvia l'interfaccia grafica
  %(prog)s --gui                # Avvia l'interfaccia grafica
  %(prog)s --dir . --auto       # Converti automaticamente la directory corrente
  %(prog)s --dir . --newline windows --no-backup --auto  # Converti con opzioni specifiche
  
Modalità GUI:
  Se non vengono forniti parametri o si usa --gui, si apre l'interfaccia grafica.
  
Modalità comando:
  Con i parametri --dir e --auto, esegue la conversione automaticamente.
        """,
    )
    parser.add_argument("--dir", help="Directory da elaborare", default=os.getcwd())
    parser.add_argument(
        "--no-backup", action="store_true", help="Non creare file .backup"
    )
    parser.add_argument(
        "--newline",
        choices=["none", "windows", "unix", "auto"],
        default="none",
        help="Modalità conversione newline",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Esegue automaticamente senza chiedere conferma",
    )
    parser.add_argument(
        "--extensions",
        help="Estensioni da elaborare (separate da virgola)",
        default=".txt,.py,.js,.html,.css,.json,.xml,.md,.csv,.log,.yaml,.yml,.ini,.cfg,.conf,.java,.c,.cpp,.h,.hpp,.rs,.go,.php,.rb,.sh,.bat,.ps1",
    )
    parser.add_argument(
        "--gui", action="store_true", help="Forza l'apertura dell'interfaccia grafica"
    )

    args = parser.parse_args()

    # Se non ci sono parametri OPPURE se è stato specificato --gui
    # oppure se mancano parametri essenziali per la modalità comando
    if len(sys.argv) == 1 or args.gui or (not args.auto and not args.gui):
        # Modalità GUI
        root = tk.Tk()
        _ = UTF8ConverterApp(root, args)
        root.mainloop()
    else:
        # Modalità comando
        run_command_line(args)


if __name__ == "__main__":
    main()
