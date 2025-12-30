import cv2
import mss
import time
import base64
import numpy as np
from typing import Callable, Optional, Tuple, List

from .window import GameWindow, WindowInfo
from .models import ActionSequence, MatchResult


class ScreenImageDetector:
    REFERENCE_SIZE = (1280, 720)
    COARSE_OFFSETS = [-0.4, -0.2, 0.0, 0.2, 0.4]
    FINE_OFFSETS = [-0.1, -0.05, 0.0, 0.05, 0.1]
    CACHED_OFFSETS = [-0.08, -0.04, 0.0, 0.04, 0.08]

    def __init__(self, confidence_threshold: float = 0.8):
        self.confidence_threshold = confidence_threshold
        self.game_window = GameWindow()
        self.use_window_capture = False
        self._last_window_size: Optional[Tuple[int, int]] = None
        self._size_changed = False
        self._scale_cache: dict[int, float] = {}
        self._expected_scale: float = 1.0

    def _compute_expected_scale(self) -> float:
        if not self.use_window_capture or not self._last_window_size:
            return 1.0
        current_w, current_h = self._last_window_size
        ref_w, ref_h = self.REFERENCE_SIZE
        scale_w = current_w / ref_w
        scale_h = current_h / ref_h
        return (scale_w + scale_h) / 2.0

    def _get_template_id(self, template: np.ndarray) -> int:
        return hash(template.tobytes()[:1024])

    def _build_scales(self, template: np.ndarray) -> List[float]:
        template_id = self._get_template_id(template)
        expected = self._compute_expected_scale()
        self._expected_scale = expected

        if template_id in self._scale_cache:
            cached = self._scale_cache[template_id]
            scales = [cached + off for off in self.CACHED_OFFSETS]
        else:
            coarse = [expected + off for off in self.COARSE_OFFSETS]
            fine = [expected + off for off in self.FINE_OFFSETS]
            seen = set()
            scales = []
            for s in coarse + fine:
                rounded = round(s, 2)
                if rounded not in seen and 0.3 <= rounded <= 2.0:
                    seen.add(rounded)
                    scales.append(rounded)
            scales.sort(key=lambda x: abs(x - expected))
        return scales

    def _update_scale_cache(self, template: np.ndarray, scale: float):
        template_id = self._get_template_id(template)
        self._scale_cache[template_id] = scale

    def clear_scale_cache(self):
        self._scale_cache.clear()

    def capture_screen(self) -> np.ndarray:
        if self.use_window_capture and self.game_window.hwnd:
            img = self.game_window.capture()
            if img is not None:
                current_size = self.game_window.get_size()
                if current_size:
                    if self._last_window_size is not None and current_size != self._last_window_size:
                        self._size_changed = True
                        self.clear_scale_cache()
                    self._last_window_size = current_size
                return img

            if self.game_window.capture_failures > 3:
                if not self.game_window.is_valid():
                    self.use_window_capture = False

        with mss.mss() as sct:
            monitor_info = sct.monitors[0]
            screenshot = sct.grab(monitor_info)
            img = np.array(screenshot)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def check_window_resized(self) -> Optional[Tuple[int, int]]:
        if self._size_changed:
            self._size_changed = False
            return self._last_window_size
        return None

    def _get_monitor_offset(self) -> Tuple[int, int]:
        if self.use_window_capture and self.game_window.hwnd:
            return self.game_window.get_offset()

        with mss.mss() as sct:
            mon = sct.monitors[0]
            return (mon["left"], mon["top"])

    def list_windows(self, min_size: Tuple[int, int] = (200, 200)) -> List[WindowInfo]:
        return GameWindow.enumerate_windows(min_size)

    def select_window(self, hwnd: int) -> bool:
        if self.game_window.set_window(hwnd):
            self.use_window_capture = True
            self._last_window_size = self.game_window.get_size()
            self._size_changed = False
            self.clear_scale_cache()
            return True
        return False

    def select_window_by_title(self, title: str, partial: bool = True) -> bool:
        if self.game_window.set_window_by_title(title, partial):
            self.use_window_capture = True
            self._last_window_size = self.game_window.get_size()
            self._size_changed = False
            self.clear_scale_cache()
            return True
        return False

    def clear_window_selection(self):
        self.game_window.hwnd = None
        self.use_window_capture = False
        self._last_window_size = None
        self.clear_scale_cache()

    def get_selected_window_info(self) -> Optional[WindowInfo]:
        if self.use_window_capture:
            return self.game_window.get_info()
        return None

    def base64_to_image(self, base64_string: str) -> np.ndarray:
        img_bytes = base64.b64decode(base64_string)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode base64 image")
        return img

    def load_embedded_sequences(self, assets_dict: dict[str, dict[str, str]]) -> list[ActionSequence]:
        sequences = []

        for sequence_name, actions in assets_dict.items():
            templates = []
            template_names = []

            for action_name in sorted(actions.keys()):
                base64_data = actions[action_name]
                template = self.base64_to_image(base64_data)
                templates.append(template)
                template_names.append(action_name)

            if templates:
                sequences.append(ActionSequence(name=sequence_name, templates=templates, template_names=template_names))

        return sequences

    def find_image(self, template: np.ndarray, screenshot: Optional[np.ndarray] = None, use_grayscale: bool = True) -> MatchResult:
        if screenshot is None:
            screenshot = self.capture_screen()

        if use_grayscale:
            screenshot_proc = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            template_proc = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            screenshot_proc = screenshot
            template_proc = template

        scales = self._build_scales(template)
        best_match = MatchResult(found=False, confidence=0.0)

        for scale in scales:
            tw = int(template_proc.shape[1] * scale)
            th = int(template_proc.shape[0] * scale)

            if tw < 10 or th < 10:
                continue
            if th > screenshot_proc.shape[0] or tw > screenshot_proc.shape[1]:
                continue

            scaled_template = cv2.resize(template_proc, (tw, th), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(screenshot_proc, scaled_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_match.confidence:
                best_match = MatchResult(found=max_val >= self.confidence_threshold, x=max_loc[0], y=max_loc[1], width=tw, height=th, confidence=max_val)

                if max_val >= self.confidence_threshold:
                    self._update_scale_cache(template, scale)
                    break

        return best_match

    def click_at(self, x: int, y: int, clicks: int = 1, button: str = "left"):
        import pyautogui

        offset_x, offset_y = self._get_monitor_offset()
        abs_x = x + offset_x
        abs_y = y + offset_y
        pyautogui.click(abs_x, abs_y, clicks=clicks, button=button)

    def find_and_click(self, template: np.ndarray, clicks: int = 1, button: str = "left", offset: Tuple[int, int] = (0, 0)) -> MatchResult:
        match = self.find_image(template)

        if match.found:
            center_x, center_y = match.center
            click_x = center_x + offset[0]
            click_y = center_y + offset[1]
            self.click_at(click_x, click_y, clicks=clicks, button=button)

        return match

    def execute_sequence(self, sequence: ActionSequence, step_delay: float = 0.5, timeout_per_step: float = 10.0, check_interval: float = 0.3, log_callback: Optional[Callable[[str], None]] = None, stop_flag: Optional[Callable[[], bool]] = None) -> bool:
        def log(msg: str):
            if log_callback:
                log_callback(msg)

        log(f"Executing: {sequence.name}")

        for i, (template, name) in enumerate(zip(sequence.templates, sequence.template_names)):
            start_time = time.time()
            found = False

            while time.time() - start_time < timeout_per_step:
                if stop_flag and stop_flag():
                    log("Stopped by user")
                    return False

                match = self.find_and_click(template)
                if match.found:
                    log(f"  [{i+1}/{len(sequence.templates)}] Clicked '{name}' at {match.center}")
                    found = True
                    time.sleep(step_delay)
                    break
                time.sleep(check_interval)

            if not found:
                log(f"  [{i+1}/{len(sequence.templates)}] Timeout: '{name}'")
                return False

        return True

    def find_first_sequence(self, sequences: list[ActionSequence], enabled_sequences: set[str], screenshot: Optional[np.ndarray] = None) -> Optional[ActionSequence]:
        if screenshot is None:
            screenshot = self.capture_screen()

        for sequence in sequences:
            if sequence.name not in enabled_sequences:
                continue

            if sequence.templates:
                match = self.find_image(sequence.templates[0], screenshot)
                if match.found:
                    return sequence

        return None