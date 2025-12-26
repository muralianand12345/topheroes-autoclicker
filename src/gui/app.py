import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional

from pynput import keyboard

from ..core import ScreenImageDetector, ActionSequence
from ..embedded_assets import ASSETS


class AutoClickerApp:
    """Main GUI application for the auto-clicker."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Top Heroes Auto-Clicker")
        self.root.geometry("500x600")
        self.root.resizable(False, False)

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
        self._setup_hotkeys()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_ui(self):
        """Setup the user interface."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === Action Sequences Frame ===
        seq_frame = ttk.LabelFrame(main_frame, text="Action Sequences", padding="10")
        seq_frame.pack(fill=tk.X, pady=(0, 10))

        self.sequences_container = ttk.Frame(seq_frame)
        self.sequences_container.pack(fill=tk.X)

        # Placeholder label (will be replaced when sequences load)
        self.no_sequences_label = ttk.Label(
            self.sequences_container,
            text="No sequences loaded. Check embedded_assets.py",
            foreground="gray",
        )
        self.no_sequences_label.pack(anchor=tk.W)

        # === Settings Frame ===
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        # Settings grid
        settings_grid = ttk.Frame(settings_frame)
        settings_grid.pack(fill=tk.X)

        # Check Interval
        ttk.Label(settings_grid, text="Check Interval:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.check_interval_var = tk.StringVar(value="1.0")
        ttk.Entry(settings_grid, textvariable=self.check_interval_var, width=8).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(settings_grid, text="sec").grid(row=0, column=2, sticky=tk.W, pady=2)

        # Cooldown
        ttk.Label(settings_grid, text="Cooldown:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.cooldown_var = tk.StringVar(value="2.0")
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

        # Log text with scrollbar
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_container, height=12, state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Clear log button
        ttk.Button(log_frame, text="Clear Log", command=self._clear_log).pack(anchor=tk.E, pady=(5, 0))

        # === Control Frame ===
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X)

        # Buttons
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(side=tk.LEFT)

        self.start_btn = ttk.Button(btn_frame, text="▶ START (F6)", command=self.start, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_btn = ttk.Button(btn_frame, text="⬛ STOP (F7)", command=self.stop, width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)

        # Status
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(side=tk.RIGHT)

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=(0, 5))
        self.status_indicator = tk.Canvas(status_frame, width=12, height=12, highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 5))
        self._draw_status_indicator("gray")

        self.status_label = ttk.Label(status_frame, text="Idle")
        self.status_label.pack(side=tk.LEFT)

    def _draw_status_indicator(self, color: str):
        """Draw the status indicator circle."""
        self.status_indicator.delete("all")
        self.status_indicator.create_oval(2, 2, 10, 10, fill=color, outline=color)

    def _load_sequences(self):
        """Load sequences from embedded assets."""
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

        # Remove placeholder
        self.no_sequences_label.destroy()

        # Create checkboxes for each sequence
        for sequence in self.sequences:
            var = tk.BooleanVar(value=True)
            self.sequence_vars[sequence.name] = var

            frame = ttk.Frame(self.sequences_container)
            frame.pack(fill=tk.X, pady=2)

            cb = ttk.Checkbutton(frame, variable=var, text=f"{sequence.name}")
            cb.pack(side=tk.LEFT)

            ttk.Label(frame, text=f"({sequence.action_count} actions)", foreground="gray").pack(side=tk.LEFT, padx=(5, 0))

        self.log(f"Loaded {len(self.sequences)} sequence(s)")

    def _setup_hotkeys(self):
        """Setup global hotkeys using pynput."""

        def on_press(key):
            try:
                if key == keyboard.Key.f6:
                    self.root.after(0, self.start)
                elif key == keyboard.Key.f7:
                    self.root.after(0, self.stop)
            except Exception:
                pass

        # Start listener in daemon thread
        self.hotkey_listener = keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def log(self, message: str):
        """Add a message to the log."""
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, full_message)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self):
        """Clear the log text."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _get_enabled_sequences(self) -> set[str]:
        """Get the names of enabled sequences."""
        return {name for name, var in self.sequence_vars.items() if var.get()}

    def start(self):
        """Start the auto-clicker."""
        if self.is_running:
            return

        if not self.sequences:
            self.log("No sequences available.")
            return

        enabled = self._get_enabled_sequences()
        if not enabled:
            self.log("No sequences enabled.")
            return

        # Update confidence threshold
        try:
            confidence = float(self.confidence_var.get())
            if self.detector:
                self.detector.confidence_threshold = confidence
        except ValueError:
            pass

        self.is_running = True
        self.stop_event.clear()

        # Update UI
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self._draw_status_indicator("#22c55e")  # Green
        self.status_label.configure(text="Running")

        self.log("Started monitoring...")
        self.log(f"Enabled: {', '.join(enabled)}")

        # Start worker thread
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Stop the auto-clicker."""
        if not self.is_running:
            return

        self.log("Stopping...")
        self.stop_event.set()
        self.is_running = False

        # Update UI
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self._draw_status_indicator("gray")
        self.status_label.configure(text="Idle")

    def _worker_loop(self):
        """Main worker loop running in background thread."""
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

                    success = self.detector.execute_sequence(
                        sequence,
                        step_delay=step_delay,
                        log_callback=self._log_from_thread,
                        stop_flag=lambda: self.stop_event.is_set(),
                    )

                    if success:
                        self._log_from_thread("Completed!")
                    else:
                        self._log_from_thread("Incomplete")

                    # Cooldown
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
        """Thread-safe logging."""
        self.root.after(0, lambda: self.log(message))

    def _on_close(self):
        """Handle window close."""
        self.stop()
        if hasattr(self, "hotkey_listener"):
            self.hotkey_listener.stop()
        self.root.destroy()

    def run(self):
        """Run the application."""
        self.root.mainloop()
