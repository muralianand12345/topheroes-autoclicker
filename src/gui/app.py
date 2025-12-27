import time
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional
from pynput import keyboard

from embedded_assets import ASSETS
from core import Config, ScreenImageDetector, ActionSequence, WindowInfo


class WindowSelectorDialog:
    def __init__(self, parent: tk.Tk, windows: list[WindowInfo]):
        self.result: Optional[WindowInfo] = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Game Window")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        # Instructions
        ttk.Label(self.dialog, text="Select the game window to monitor:", padding=(10, 10)).pack(anchor=tk.W)
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(self.dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(list_frame,  yscrollcommand=scrollbar.set, font=("Consolas", 10), selectmode=tk.SINGLE)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Populate list
        self.windows = windows
        for win in windows:
            title = win.title[:50] + "..." if len(win.title) > 50 else win.title
            self.listbox.insert(tk.END, f"{title} ({win.width}x{win.height})")
        
        # Double-click to select
        self.listbox.bind("<Double-Button-1>", lambda e: self._on_select())
        
        # Buttons
        btn_frame = ttk.Frame(self.dialog, padding=10)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Refresh", command=self._refresh).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Select", command=self._on_select).pack(side=tk.RIGHT, padx=5)
        
        self.dialog.protocol("WM_DELETE_WINDOW", self.dialog.destroy)
    
    def _refresh(self):
        from core import GameWindow
        self.windows = GameWindow.enumerate_windows()
        self.listbox.delete(0, tk.END)
        for win in self.windows:
            title = win.title[:50] + "..." if len(win.title) > 50 else win.title
            self.listbox.insert(tk.END, f"{title} ({win.width}x{win.height})")
    
    def _on_select(self):
        selection = self.listbox.curselection()
        if selection:
            self.result = self.windows[selection[0]]
            self.dialog.destroy()
    
    def show(self) -> Optional[WindowInfo]:
        self.dialog.wait_window()
        return self.result


class AutoClickerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Top Heroes Auto-Clicker")

        screen_height = self.root.winfo_screenheight()
        window_height = min(600, screen_height - 100)
        window_width = 500

        self.root.geometry(f"{window_width}x{window_height}")
        self.root.minsize(400, 450)
        self.root.resizable(True, True)

        # Config
        self.config = Config()

        # State
        self.is_running = False
        self.stop_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None
        self.detector: Optional[ScreenImageDetector] = None
        self.sequences: list[ActionSequence] = []
        self.sequence_vars: dict[str, tk.BooleanVar] = {}

        # Setup
        self._setup_ui()
        self._load_sequences()
        self._load_saved_config()
        self._setup_hotkeys()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_ui(self):
        self.canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        main_frame = ttk.Frame(self.scrollable_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === Window Selection Frame ===
        window_frame = ttk.LabelFrame(main_frame, text="Target Window", padding="10")
        window_frame.pack(fill=tk.X, pady=(0, 10))
        
        window_info_frame = ttk.Frame(window_frame)
        window_info_frame.pack(fill=tk.X)
        
        self.window_status_label = ttk.Label(window_info_frame, text="No window selected (using full screen)", foreground="gray")
        self.window_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        window_btn_frame = ttk.Frame(window_frame)
        window_btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.select_window_btn = ttk.Button(window_btn_frame, text="🎯 Select Window", command=self._show_window_selector)
        self.select_window_btn.pack(side=tk.LEFT)
        
        self.clear_window_btn = ttk.Button(window_btn_frame, text="Clear", command=self._clear_window_selection, state=tk.DISABLED)
        self.clear_window_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Label(window_frame, text="Selecting a window is faster and auto-handles resize", foreground="gray", font=("", 8)).pack(anchor=tk.W, pady=(5, 0))

        # === Action Sequences Frame ===
        seq_frame = ttk.LabelFrame(main_frame, text="Action Sequences", padding="10")
        seq_frame.pack(fill=tk.X, pady=(0, 10))

        self.sequences_container = ttk.Frame(seq_frame)
        self.sequences_container.pack(fill=tk.X)

        self.no_sequences_label = ttk.Label(self.sequences_container, text="No sequences loaded. Check embedded_assets.py", foreground="gray")
        self.no_sequences_label.pack(anchor=tk.W)

        # === Settings Frame ===
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        settings_grid = ttk.Frame(settings_frame)
        settings_grid.pack(fill=tk.X)

        # Check Interval
        ttk.Label(settings_grid, text="Check Interval:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.check_interval_var = tk.StringVar(value="1.0")
        ttk.Entry(settings_grid, textvariable=self.check_interval_var, width=8).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(settings_grid, text="sec").grid(row=0, column=2, sticky=tk.W, pady=2)

        # Cooldown
        ttk.Label(settings_grid, text="Cooldown:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.cooldown_var = tk.StringVar(value="1.0")
        ttk.Entry(settings_grid, textvariable=self.cooldown_var, width=8).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(settings_grid, text="sec").grid(row=1, column=2, sticky=tk.W, pady=2)

        # Step Delay
        ttk.Label(settings_grid, text="Step Delay:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.step_delay_var = tk.StringVar(value="0.5")
        ttk.Entry(settings_grid, textvariable=self.step_delay_var, width=8).grid(row=2, column=1, padx=5, pady=2)
        ttk.Label(settings_grid, text="sec").grid(row=2, column=2, sticky=tk.W, pady=2)

        # Confidence
        ttk.Label(settings_grid, text="Confidence:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.confidence_var = tk.StringVar(value="0.8")
        ttk.Entry(settings_grid, textvariable=self.confidence_var, width=8).grid(row=3, column=1, padx=5, pady=2)
        ttk.Label(settings_grid, text="(0.0-1.0)").grid(row=3, column=2, sticky=tk.W, pady=2)

        # === Log Frame ===
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_container, height=10, state=tk.DISABLED, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(log_frame, text="Clear Log", command=self._clear_log).pack(anchor=tk.E, pady=(5, 0))

        # === Control Frame ===
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(10, 0))

        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(side=tk.LEFT)

        self.start_btn = ttk.Button(btn_frame, text="▶ START (F6)", command=self.start, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_btn = ttk.Button(btn_frame, text="⬛ STOP (F7)", command=self.stop, width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)

        status_frame = ttk.Frame(control_frame)
        status_frame.pack(side=tk.RIGHT)

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=(0, 5))
        self.status_indicator = tk.Canvas(status_frame, width=12, height=12, highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 5))
        self._draw_status_indicator("gray")

        self.status_label = ttk.Label(status_frame, text="Idle")
        self.status_label.pack(side=tk.LEFT)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _draw_status_indicator(self, color: str):
        self.status_indicator.delete("all")
        self.status_indicator.create_oval(2, 2, 10, 10, fill=color, outline=color)

    def _show_window_selector(self):
        if not self.detector:
            self.log("Detector not initialized")
            return
        
        windows = self.detector.list_windows()
        if not windows:
            self.log("No windows found")
            return
        
        dialog = WindowSelectorDialog(self.root, windows)
        selected = dialog.show()
        
        if selected:
            if self.detector.select_window(selected.hwnd):
                self._update_window_status(selected)
                self.log(f"Selected: {selected.title} ({selected.width}x{selected.height})")
                self.config.set_window(selected.title)
            else:
                self.log("Failed to select window")
    
    def _update_window_status(self, window_info: Optional[WindowInfo]):
        if window_info:
            title = window_info.title[:40] + "..." if len(window_info.title) > 40 else window_info.title
            self.window_status_label.configure(text=f"✓ {title} ({window_info.width}x{window_info.height})", foreground="green")
            self.clear_window_btn.configure(state=tk.NORMAL)
        else:
            self.window_status_label.configure(text="No window selected (using full screen)", foreground="gray")
            self.clear_window_btn.configure(state=tk.DISABLED)
    
    def _clear_window_selection(self):
        if self.detector:
            self.detector.clear_window_selection()
        self._update_window_status(None)
        self.config.clear_window()
        self.log("Cleared window selection, using full screen")

    def _load_sequences(self):
        if not ASSETS:
            self.log("No embedded assets found.")
            self.log("Run: python scripts/embed_assets.py")
            return

        try:
            confidence = float(self.confidence_var.get())
        except ValueError:
            confidence = 0.8

        self.detector = ScreenImageDetector(confidence_threshold=confidence)
        self.sequences = self.detector.load_embedded_sequences(ASSETS)

        if not self.sequences:
            self.log("No sequences loaded from assets.")
            return

        self.no_sequences_label.destroy()

        for sequence in self.sequences:
            var = tk.BooleanVar(value=True)
            self.sequence_vars[sequence.name] = var

            frame = ttk.Frame(self.sequences_container)
            frame.pack(fill=tk.X, pady=2)

            cb = ttk.Checkbutton(frame, variable=var, text=f"{sequence.name}")
            cb.pack(side=tk.LEFT)

            ttk.Label(frame, text=f"({sequence.action_count} actions)", foreground="gray").pack(side=tk.LEFT, padx=(5, 0))

        self.log(f"Loaded {len(self.sequences)} sequence(s)")

    def _load_saved_config(self):
        settings = self.config.get_settings()
        if settings:
            if "check_interval" in settings:
                self.check_interval_var.set(settings["check_interval"])
            if "cooldown" in settings:
                self.cooldown_var.set(settings["cooldown"])
            if "step_delay" in settings:
                self.step_delay_var.set(settings["step_delay"])
            if "confidence" in settings:
                self.confidence_var.set(settings["confidence"])
        
        saved_window = self.config.get_window()
        if saved_window and self.detector:
            if self.detector.select_window_by_title(saved_window, partial=True):
                info = self.detector.get_selected_window_info()
                if info:
                    self._update_window_status(info)
                    self.log(f"Restored window: {info.title}")

    def _save_settings(self):
        settings = {
            "check_interval": self.check_interval_var.get(),
            "cooldown": self.cooldown_var.get(),
            "step_delay": self.step_delay_var.get(),
            "confidence": self.confidence_var.get(),
        }
        self.config.set_settings(settings)

    def _setup_hotkeys(self):
        def on_press(key):
            try:
                if key == keyboard.Key.f6:
                    self.root.after(0, self.start)
                elif key == keyboard.Key.f7:
                    self.root.after(0, self.stop)
            except Exception:
                pass

        self.hotkey_listener = keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, full_message)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _get_enabled_sequences(self) -> set[str]:
        return {name for name, var in self.sequence_vars.items() if var.get()}

    def start(self):
        if self.is_running:
            return

        if not self.sequences:
            self.log("No sequences available.")
            return

        enabled = self._get_enabled_sequences()
        if not enabled:
            self.log("No sequences enabled.")
            return

        try:
            confidence = float(self.confidence_var.get())
            if self.detector:
                self.detector.confidence_threshold = confidence
        except ValueError:
            pass

        self.is_running = True
        self.stop_event.clear()

        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.select_window_btn.configure(state=tk.DISABLED)
        self._draw_status_indicator("#22c55e")
        self.status_label.configure(text="Running")

        self.log("Started monitoring...")
        self.log(f"Enabled: {', '.join(enabled)}")
        
        if self.detector.use_window_capture:
            info = self.detector.get_selected_window_info()
            if info:
                self.log(f"Target: {info.title} ({info.width}x{info.height})")
        else:
            self.log("Target: Full screen")

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        if not self.is_running:
            return

        self.log("Stopping...")
        self.stop_event.set()
        self.is_running = False

        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.select_window_btn.configure(state=tk.NORMAL)
        self._draw_status_indicator("gray")
        self.status_label.configure(text="Idle")

    def _worker_loop(self):
        try:
            check_interval = float(self.check_interval_var.get())
        except ValueError:
            check_interval = 1.0

        try:
            cooldown = float(self.cooldown_var.get())
        except ValueError:
            cooldown = 2.0

        try:
            step_delay = float(self.step_delay_var.get())
        except ValueError:
            step_delay = 0.5

        execution_count = 0

        while not self.stop_event.is_set():
            try:
                enabled = self._get_enabled_sequences()
                if not enabled:
                    time.sleep(check_interval)
                    continue

                screenshot = self.detector.capture_screen()
                new_size = self.detector.check_window_resized()
                if new_size:
                    self._log_from_thread(f"Window resized to {new_size[0]}x{new_size[1]}")
                
                sequence = self.detector.find_first_sequence(self.sequences, enabled, screenshot)

                if sequence:
                    execution_count += 1
                    self._log_from_thread(f"Found '{sequence.name}' (#{execution_count})")

                    success = self.detector.execute_sequence(sequence, step_delay=step_delay, log_callback=self._log_from_thread, stop_flag=lambda: self.stop_event.is_set())
                    if success:
                        self._log_from_thread("Completed!")
                    else:
                        self._log_from_thread("Incomplete")

                    for _ in range(int(cooldown * 10)):
                        if self.stop_event.is_set():
                            break
                        time.sleep(0.1)
                else:
                    time.sleep(check_interval)

            except Exception as e:
                self._log_from_thread(f"Error: {e}")
                time.sleep(check_interval)

        self._log_from_thread(f"Stopped. Total: {execution_count}")

    def _log_from_thread(self, message: str):
        self.root.after(0, lambda: self.log(message))

    def _on_close(self):
        self.stop()
        self._save_settings()
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")
        if hasattr(self, "hotkey_listener"):
            self.hotkey_listener.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()