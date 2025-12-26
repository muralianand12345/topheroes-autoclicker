import time
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional
from pynput import keyboard

from embedded_assets import ASSETS
from core import Config, ScreenImageDetector, ActionSequence


class AutoClickerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Top Heroes Auto-Clicker")

        screen_height = self.root.winfo_screenheight()
        screen_width = self.root.winfo_screenwidth()
        window_height = min(650, screen_height - 100)
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

        # Handle window close
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

        # === Action Sequences Frame ===
        seq_frame = ttk.LabelFrame(main_frame, text="Action Sequences", padding="10")
        seq_frame.pack(fill=tk.X, pady=(0, 10))

        self.sequences_container = ttk.Frame(seq_frame)
        self.sequences_container.pack(fill=tk.X)

        self.no_sequences_label = ttk.Label(self.sequences_container, text="No sequences loaded. Check embedded_assets.py", foreground="gray")
        self.no_sequences_label.pack(anchor=tk.W)

        # === Calibration Frame ===
        calib_frame = ttk.LabelFrame(main_frame, text="Calibration", padding="10")
        calib_frame.pack(fill=tk.X, pady=(0, 10))

        calib_info = ttk.Label(calib_frame, text="If clicks are offset, open the game and click Calibrate.", foreground="gray")
        calib_info.pack(anchor=tk.W)

        calib_btn_frame = ttk.Frame(calib_frame)
        calib_btn_frame.pack(fill=tk.X, pady=(5, 0))

        self.calibrate_btn = ttk.Button(calib_btn_frame, text="🔧 Calibrate", command=self._calibrate)
        self.calibrate_btn.pack(side=tk.LEFT)

        self.reset_scale_btn = ttk.Button(calib_btn_frame, text="Reset", command=self._reset_scale)
        self.reset_scale_btn.pack(side=tk.LEFT, padx=(5, 0))

        self.scale_label = ttk.Label(calib_btn_frame, text="Scale: 1.0x", foreground="gray")
        self.scale_label.pack(side=tk.LEFT, padx=(10, 0))

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
        saved_scale = self.config.get_scale()
        if saved_scale and self.detector:
            self.detector.detected_scale = saved_scale
            self.scale_label.configure(text=f"Scale: {saved_scale:.2f}x")
            self.log(f"Loaded saved scale: {saved_scale:.2f}x")

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

    def _save_settings(self):
        settings = {
            "check_interval": self.check_interval_var.get(),
            "cooldown": self.cooldown_var.get(),
            "step_delay": self.step_delay_var.get(),
            "confidence": self.confidence_var.get(),
        }
        self.config.set_settings(settings)

    def _calibrate(self):
        if not self.detector or not self.sequences:
            self.log("No sequences loaded. Cannot calibrate.")
            return

        if self.is_running:
            self.log("Stop the auto-clicker before calibrating.")
            return

        self.log("Calibrating... (make sure game is visible)")
        self.calibrate_btn.configure(state=tk.DISABLED)

        def do_calibrate():
            try:
                scale, confidence = self.detector.calibrate_with_sequences(self.sequences)
                self.root.after(0, lambda: self._on_calibrate_complete(scale, confidence))
            except Exception as e:
                self.root.after(0, lambda: self._on_calibrate_error(str(e)))

        threading.Thread(target=do_calibrate, daemon=True).start()

    def _on_calibrate_complete(self, scale: float, confidence: float):
        self.calibrate_btn.configure(state=tk.NORMAL)
        self.scale_label.configure(text=f"Scale: {scale:.2f}x")

        self.config.set_scale(scale)

        if confidence >= self.detector.confidence_threshold:
            self.log(f"Calibration successful! Scale: {scale:.2f}x (confidence: {confidence:.2f})")
            self.log("Scale saved - no need to recalibrate next time.")
        else:
            self.log(f"Calibration done. Scale: {scale:.2f}x (low confidence: {confidence:.2f})")
            self.log("Tip: Make sure the game UI is visible on screen.")

    def _on_calibrate_error(self, error: str):
        self.calibrate_btn.configure(state=tk.NORMAL)
        self.log(f"Calibration failed: {error}")

    def _reset_scale(self):
        if self.detector:
            self.detector.reset_scale()
            self.config.clear_scale()
            self.scale_label.configure(text="Scale: 1.0x")
            self.log("Scale reset to 1.0x")

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
        self.calibrate_btn.configure(state=tk.DISABLED)
        self._draw_status_indicator("#22c55e")
        self.status_label.configure(text="Running")

        self.log("Started monitoring...")
        self.log(f"Enabled: {', '.join(enabled)}")
        if self.detector.detected_scale and self.detector.detected_scale != 1.0:
            self.log(f"Using scale: {self.detector.detected_scale:.2f}x")

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
        self.calibrate_btn.configure(state=tk.NORMAL)
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