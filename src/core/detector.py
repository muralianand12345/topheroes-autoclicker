import cv2
import mss
import time
import base64
import numpy as np
from typing import Callable, Optional, Tuple

from .models import ActionSequence, MatchResult


class ScreenImageDetector:
    def __init__(self, confidence_threshold: float = 0.8):
        self.confidence_threshold = confidence_threshold
        self.detected_scale: Optional[float] = None

    def capture_screen(self) -> np.ndarray:
        with mss.mss() as sct:
            monitor_info = sct.monitors[0]
            screenshot = sct.grab(monitor_info)
            img = np.array(screenshot)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def _get_monitor_offset(self) -> Tuple[int, int]:
        with mss.mss() as sct:
            mon = sct.monitors[0]
            return (mon["left"], mon["top"])

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

    def calibrate_scale(self, template: np.ndarray, screenshot: Optional[np.ndarray] = None) -> Tuple[float, float]:
        if screenshot is None:
            screenshot = self.capture_screen()

        screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        scales = [1.0, 0.95, 1.05, 0.9, 1.1, 0.85, 1.15, 0.8, 1.2, 0.75, 1.25, 0.7, 1.3]
        best_scale = 1.0
        best_conf = 0.0

        for scale in scales:
            tw = int(template_gray.shape[1] * scale)
            th = int(template_gray.shape[0] * scale)

            if tw < 10 or th < 10:
                continue
            if th > screenshot_gray.shape[0] or tw > screenshot_gray.shape[1]:
                continue

            scaled = cv2.resize(template_gray, (tw, th), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(screenshot_gray, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_conf:
                best_conf = max_val
                best_scale = scale

        self.detected_scale = best_scale
        return best_scale, best_conf

    def calibrate_with_sequences(self, sequences: list[ActionSequence], screenshot: Optional[np.ndarray] = None) -> Tuple[float, float]:
        if screenshot is None:
            screenshot = self.capture_screen()

        best_scale = 1.0
        best_conf = 0.0

        for sequence in sequences:
            for template in sequence.templates:
                scale, conf = self.calibrate_scale(template, screenshot)
                if conf > best_conf:
                    best_conf = conf
                    best_scale = scale

        self.detected_scale = best_scale
        return best_scale, best_conf

    def reset_scale(self):
        self.detected_scale = None

    def find_image(self, template: np.ndarray, screenshot: Optional[np.ndarray] = None, use_grayscale: bool = True) -> MatchResult:
        if screenshot is None:
            screenshot = self.capture_screen()

        if use_grayscale:
            screenshot_proc = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            template_proc = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            screenshot_proc = screenshot
            template_proc = template

        scale = self.detected_scale or 1.0

        if scale != 1.0:
            tw = int(template_proc.shape[1] * scale)
            th = int(template_proc.shape[0] * scale)
            template_proc = cv2.resize(template_proc, (tw, th), interpolation=cv2.INTER_AREA)

        if template_proc.shape[0] > screenshot_proc.shape[0] or template_proc.shape[1] > screenshot_proc.shape[1]:
            return MatchResult(found=False, confidence=0.0)

        result = cv2.matchTemplate(screenshot_proc, template_proc, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        h, w = template_proc.shape[:2]

        return MatchResult(found=max_val >= self.confidence_threshold, x=max_loc[0], y=max_loc[1], width=w, height=h, confidence=max_val)

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