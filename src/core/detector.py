import base64
import time
from typing import Callable, Optional, Tuple

import cv2
import mss
import numpy as np

from .models import ActionSequence, MatchResult


class ScreenImageDetector:
    """Detects images on screen and performs click actions."""

    def __init__(self, confidence_threshold: float = 0.8):
        self.confidence_threshold = confidence_threshold
        self.sct = mss.mss()

    def capture_screen(self) -> np.ndarray:
        """Capture all monitors combined."""
        monitor_info = self.sct.monitors[0]
        screenshot = self.sct.grab(monitor_info)
        img = np.array(screenshot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def base64_to_image(self, base64_string: str) -> np.ndarray:
        """Convert base64 string to OpenCV image."""
        img_bytes = base64.b64decode(base64_string)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode base64 image")
        return img

    def load_embedded_sequences(self, assets_dict: dict[str, dict[str, str]]) -> list[ActionSequence]:
        """
        Load action sequences from embedded base64 assets.

        Args:
            assets_dict: Dictionary structure:
                {
                    "sequence-name": {
                        "action-1": "base64...",
                        "action-2": "base64...",
                    }
                }

        Returns:
            List of ActionSequence objects.
        """
        sequences = []

        for sequence_name, actions in assets_dict.items():
            templates = []
            template_names = []

            # Sort actions by name to ensure correct order
            for action_name in sorted(actions.keys()):
                base64_data = actions[action_name]
                template = self.base64_to_image(base64_data)
                templates.append(template)
                template_names.append(action_name)

            if templates:
                sequences.append(
                    ActionSequence(
                        name=sequence_name,
                        templates=templates,
                        template_names=template_names,
                    )
                )

        return sequences

    def find_image(
        self,
        template: np.ndarray,
        screenshot: Optional[np.ndarray] = None,
        use_grayscale: bool = True,
    ) -> MatchResult:
        """Find a template image on the screen."""
        if screenshot is None:
            screenshot = self.capture_screen()

        if use_grayscale:
            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        else:
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        h, w = template.shape[:2]

        if max_val >= self.confidence_threshold:
            return MatchResult(
                found=True,
                x=max_loc[0],
                y=max_loc[1],
                width=w,
                height=h,
                confidence=max_val,
            )

        return MatchResult(found=False, confidence=max_val)

    def click_at(self, x: int, y: int, clicks: int = 1, button: str = "left"):
        """Click at specified coordinates with multi-monitor support."""
        import pyautogui

        mon = self.sct.monitors[0]
        abs_x = x + mon["left"]
        abs_y = y + mon["top"]
        pyautogui.click(abs_x, abs_y, clicks=clicks, button=button)

    def find_and_click(
        self,
        template: np.ndarray,
        clicks: int = 1,
        button: str = "left",
        offset: Tuple[int, int] = (0, 0),
    ) -> MatchResult:
        """Find an image on screen and click on it."""
        match = self.find_image(template)

        if match.found:
            center_x, center_y = match.center
            click_x = center_x + offset[0]
            click_y = center_y + offset[1]
            self.click_at(click_x, click_y, clicks=clicks, button=button)

        return match

    def execute_sequence(
        self,
        sequence: ActionSequence,
        step_delay: float = 0.5,
        timeout_per_step: float = 10.0,
        check_interval: float = 0.3,
        log_callback: Optional[Callable[[str], None]] = None,
        stop_flag: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """
        Execute a full action sequence.

        Args:
            sequence: The action sequence to execute.
            step_delay: Delay between actions.
            timeout_per_step: Max time to wait for each action.
            check_interval: Time between screen checks.
            log_callback: Function to call for logging.
            stop_flag: Function that returns True if execution should stop.

        Returns:
            True if all actions completed successfully.
        """

        def log(msg: str):
            if log_callback:
                log_callback(msg)

        log(f"Executing: {sequence.name}")

        for i, (template, name) in enumerate(zip(sequence.templates, sequence.template_names)):
            start_time = time.time()
            found = False

            while time.time() - start_time < timeout_per_step:
                # Check if we should stop
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

    def find_first_sequence(
        self,
        sequences: list[ActionSequence],
        enabled_sequences: set[str],
        screenshot: Optional[np.ndarray] = None,
    ) -> Optional[ActionSequence]:
        """Find which sequence's first action is currently visible."""
        if screenshot is None:
            screenshot = self.capture_screen()

        for sequence in sequences:
            # Skip disabled sequences
            if sequence.name not in enabled_sequences:
                continue

            if sequence.templates:
                match = self.find_image(sequence.templates[0], screenshot)
                if match.found:
                    return sequence

        return None
