"""
Графический лаунчер для Linux (и др. ОС с Tk): запуск клиента, лог, правка .env.

Требуется пакет Tk: на Debian/Ubuntu — `sudo apt install python3-tk`
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except ImportError as e:
    print("Нужен Tkinter. На Linux: sudo apt install python3-tk", file=sys.stderr)
    raise SystemExit(1) from e

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
MAIN_SCRIPT = BASE_DIR / "main.py"


def load_env_lines() -> dict[str, str]:
    data: dict[str, str] = {}
    if not ENV_PATH.is_file():
        return data
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def save_env(updates: dict[str, str]) -> None:
    existing = load_env_lines()
    existing.update({k: v for k, v in updates.items() if v is not None})
    lines_out: list[str] = []
    if ENV_PATH.is_file():
        raw = ENV_PATH.read_text(encoding="utf-8").splitlines()
        seen = set()
        for line in raw:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in existing:
                    lines_out.append(f"{k}={existing[k]}")
                    seen.add(k)
                    continue
            lines_out.append(line)
        for k, v in existing.items():
            if k not in seen:
                lines_out.append(f"{k}={v}")
    else:
        lines_out.append("# QRPass Client — см. .env.example")
        for k, v in existing.items():
            lines_out.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines_out) + "\n", encoding="utf-8")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("QRPass Client")
        self.geometry("720x560")
        self.proc: subprocess.Popen[str] | None = None
        self.log_q: queue.Queue[str] = queue.Queue()
        self._build()
        self.after(200, self._drain_log)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        env = load_env_lines()
        pad = {"padx": 8, "pady": 4}

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text=f"Каталог: {BASE_DIR}").pack(anchor=tk.W)
        btn_row = ttk.Frame(frm)
        btn_row.pack(anchor=tk.W, pady=4)
        ttk.Button(btn_row, text="Открыть каталог", command=self._open_folder).pack(side=tk.LEFT, padx=(0, 8))

        grid = ttk.Frame(frm)
        grid.pack(fill=tk.X, **pad)

        self.var_server = tk.StringVar(value=env.get("SERVER_URL", "http://127.0.0.1:8000"))
        self.var_token = tk.StringVar(value=env.get("API_TOKEN", ""))
        self.var_mdb = tk.BooleanVar(value=env.get("USE_MDB_CAMERAS", "").lower() in ("1", "true", "yes"))
        self.var_mdb_dir = tk.StringVar(value=env.get("MDB_PARENT_DIR", ""))
        self.var_cam_name = tk.StringVar(value=env.get("CAMERA_NAME", "Камера 1"))
        self.var_cam_src = tk.StringVar(value=env.get("CAMERA_SOURCE", "0"))

        r = 0
        ttk.Label(grid, text="SERVER_URL").grid(row=r, column=0, sticky=tk.W, **pad)
        ttk.Entry(grid, textvariable=self.var_server, width=64).grid(row=r, column=1, sticky=tk.EW, **pad)
        r += 1
        ttk.Label(grid, text="API_TOKEN").grid(row=r, column=0, sticky=tk.W, **pad)
        ttk.Entry(grid, textvariable=self.var_token, width=64, show="•").grid(row=r, column=1, sticky=tk.EW, **pad)
        r += 1
        ttk.Checkbutton(grid, text="Камеры из mdb / users.db (USE_MDB_CAMERAS)", variable=self.var_mdb).grid(
            row=r, column=1, sticky=tk.W, **pad
        )
        r += 1
        ttk.Label(grid, text="MDB_PARENT_DIR").grid(row=r, column=0, sticky=tk.W, **pad)
        ttk.Entry(grid, textvariable=self.var_mdb_dir, width=64).grid(row=r, column=1, sticky=tk.EW, **pad)
        ttk.Button(grid, text="…", width=3, command=self._pick_mdb_dir).grid(row=r, column=2, **pad)
        r += 1
        ttk.Label(grid, text="CAMERA_NAME (одна камера)").grid(row=r, column=0, sticky=tk.W, **pad)
        ttk.Entry(grid, textvariable=self.var_cam_name, width=64).grid(row=r, column=1, sticky=tk.EW, **pad)
        r += 1
        ttk.Label(grid, text="CAMERA_SOURCE").grid(row=r, column=0, sticky=tk.W, **pad)
        ttk.Entry(grid, textvariable=self.var_cam_src, width=64).grid(row=r, column=1, sticky=tk.EW, **pad)
        grid.columnconfigure(1, weight=1)

        btn_bar = ttk.Frame(frm)
        btn_bar.pack(fill=tk.X, pady=8)
        ttk.Button(btn_bar, text="Сохранить .env", command=self._save_env).pack(side=tk.LEFT, padx=(0, 8))
        self.btn_start = ttk.Button(btn_bar, text="Запустить клиент", command=self._start)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_stop = ttk.Button(btn_bar, text="Остановить", command=self._stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)

        ttk.Label(frm, text="Лог (stdout/stderr):").pack(anchor=tk.W, pady=(8, 0))
        self.log = scrolledtext.ScrolledText(frm, height=16, state=tk.DISABLED, font=("Monospace", 10))
        self.log.pack(fill=tk.BOTH, expand=True, pady=4)

    def _append_log(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text)
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _drain_log(self) -> None:
        try:
            while True:
                line = self.log_q.get_nowait()
                self._append_log(line)
        except queue.Empty:
            pass
        self.after(200, self._drain_log)

    def _open_folder(self) -> None:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(BASE_DIR)])
        elif sys.platform == "win32":
            os.startfile(str(BASE_DIR))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(BASE_DIR)])

    def _pick_mdb_dir(self) -> None:
        d = filedialog.askdirectory(title="Каталог с mdb.py и users.db")
        if d:
            self.var_mdb_dir.set(d)

    def _save_env(self) -> None:
        try:
            save_env(
                {
                    "SERVER_URL": self.var_server.get().strip(),
                    "API_TOKEN": self.var_token.get().strip(),
                    "USE_MDB_CAMERAS": "true" if self.var_mdb.get() else "false",
                    "MDB_PARENT_DIR": self.var_mdb_dir.get().strip(),
                    "CAMERA_NAME": self.var_cam_name.get().strip(),
                    "CAMERA_SOURCE": self.var_cam_src.get().strip(),
                }
            )
            messagebox.showinfo("QRPass", f"Сохранено: {ENV_PATH}")
        except OSError as e:
            messagebox.showerror("Ошибка", str(e))

    def _start(self) -> None:
        if self.proc and self.proc.poll() is None:
            messagebox.showwarning("QRPass", "Клиент уже запущен.")
            return
        if not MAIN_SCRIPT.is_file():
            messagebox.showerror("Ошибка", f"Нет файла: {MAIN_SCRIPT}")
            return
        self._save_env_silent()
        self._append_log(f"\n--- Запуск: {sys.executable} {MAIN_SCRIPT} ---\n")
        try:
            self.proc = subprocess.Popen(
                [sys.executable, str(MAIN_SCRIPT)],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except OSError as e:
            messagebox.showerror("Ошибка запуска", str(e))
            return
        self.btn_start.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)

        def reader() -> None:
            assert self.proc and self.proc.stdout
            for line in self.proc.stdout:
                self.log_q.put(line)
            code = self.proc.wait()
            self.log_q.put(f"\n--- Процесс завершился, код {code} ---\n")
            self.after(0, self._proc_exited)

        threading.Thread(target=reader, daemon=True).start()

    def _save_env_silent(self) -> None:
        try:
            save_env(
                {
                    "SERVER_URL": self.var_server.get().strip(),
                    "API_TOKEN": self.var_token.get().strip(),
                    "USE_MDB_CAMERAS": "true" if self.var_mdb.get() else "false",
                    "MDB_PARENT_DIR": self.var_mdb_dir.get().strip(),
                    "CAMERA_NAME": self.var_cam_name.get().strip(),
                    "CAMERA_SOURCE": self.var_cam_src.get().strip(),
                }
            )
        except OSError:
            pass

    def _proc_exited(self) -> None:
        self.proc = None
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)

    def _stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self._append_log("\n--- Остановка (SIGTERM) ---\n")
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        if self.proc and self.proc.poll() is None:
            if messagebox.askokcancel("Выход", "Клиент ещё работает. Остановить и выйти?"):
                self.proc.terminate()
                self.destroy()
        else:
            self.destroy()


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
