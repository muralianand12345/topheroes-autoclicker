import cv2
import mss
import ctypes
import numpy as np
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional, Tuple, List


user32 = ctypes.windll.user32
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

@dataclass
class WindowInfo:
    hwnd: int
    title: str
    rect: Tuple[int, int, int, int]  # left, top, right, bottom
    
    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]
    
    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]
    
    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)
    
    def __str__(self) -> str:
        return f"{self.title} ({self.width}x{self.height})"


class GameWindow:
    def __init__(self, window_title: Optional[str] = None):
        self.window_title = window_title
        self.hwnd: Optional[int] = None
        self.last_size: Optional[Tuple[int, int]] = None
        self._capture_failed_count = 0
    
    @staticmethod
    def enumerate_windows(min_size: Tuple[int, int] = (200, 200)) -> List[WindowInfo]:
        windows: List[WindowInfo] = []
        
        def enum_callback(hwnd: int, _: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
            
            if not title.strip():
                return True
            
            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True
            
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            
            if width < min_size[0] or height < min_size[1]:
                return True
            
            windows.append(WindowInfo(hwnd=hwnd, title=title, rect=(rect.left, rect.top, rect.right, rect.bottom)))
            
            return True
        
        callback = WNDENUMPROC(enum_callback)
        user32.EnumWindows(callback, 0)
        
        windows.sort(key=lambda w: w.title.lower())
        
        return windows
    
    @staticmethod
    def find_windows_by_title(search: str, partial: bool = True) -> List[WindowInfo]:
        all_windows = GameWindow.enumerate_windows()
        search_lower = search.lower()
        
        if partial:
            return [w for w in all_windows if search_lower in w.title.lower()]
        else:
            return [w for w in all_windows if w.title.lower() == search_lower]
    
    def set_window(self, hwnd: int) -> bool:
        self.hwnd = hwnd
        self.last_size = None
        self._capture_failed_count = 0
        
        if not user32.IsWindowVisible(hwnd):
            self.hwnd = None
            return False
        
        return True
    
    def set_window_by_title(self, title: str, partial: bool = True) -> bool:
        self.window_title = title
        
        matches = self.find_windows_by_title(title, partial)
        if matches:
            self.hwnd = matches[0].hwnd
            self.last_size = None
            self._capture_failed_count = 0
            return True
        
        self.hwnd = None
        return False
    
    def find_window(self) -> bool:
        if not self.window_title:
            return False
        return self.set_window_by_title(self.window_title)
    
    def is_valid(self) -> bool:
        if not self.hwnd:
            return False
        return bool(user32.IsWindowVisible(self.hwnd))
    
    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        if not self.hwnd:
            return None
        
        rect = wintypes.RECT()
        if user32.GetWindowRect(self.hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
        return None
    
    def get_client_rect(self) -> Optional[Tuple[int, int, int, int]]:
        if not self.hwnd:
            return None
        
        client_rect = wintypes.RECT()
        if not user32.GetClientRect(self.hwnd, ctypes.byref(client_rect)):
            return None
        
        point = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(self.hwnd, ctypes.byref(point)):
            return None
        
        left = point.x
        top = point.y
        right = left + client_rect.right
        bottom = top + client_rect.bottom
        
        return (left, top, right, bottom)
    
    def get_size(self) -> Optional[Tuple[int, int]]:
        rect = self.get_client_rect()
        if rect:
            return (rect[2] - rect[0], rect[3] - rect[1])
        return None
    
    def get_info(self) -> Optional[WindowInfo]:
        if not self.hwnd:
            return None
        
        length = user32.GetWindowTextLengthW(self.hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(self.hwnd, buffer, length + 1)
        
        rect = self.get_window_rect()
        if not rect:
            return None
        
        return WindowInfo(hwnd=self.hwnd, title=buffer.value, rect=rect)
    
    def capture(self) -> Optional[np.ndarray]:
        rect = self.get_client_rect()
        if not rect:
            self._capture_failed_count += 1
            return None
        
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        
        if width <= 0 or height <= 0:
            self._capture_failed_count += 1
            return None
        
        try:
            with mss.mss() as sct:
                monitor = {"left": left, "top": top, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                self._capture_failed_count = 0
                return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception:
            self._capture_failed_count += 1
            return None
    
    def has_resized(self) -> bool:
        current_size = self.get_size()
        if not current_size:
            return False
        
        if self.last_size is None:
            self.last_size = current_size
            return False
        
        if current_size != self.last_size:
            self.last_size = current_size
            return True
        
        return False
    
    def get_offset(self) -> Tuple[int, int]:
        rect = self.get_client_rect()
        if rect:
            return (rect[0], rect[1])
        return (0, 0)
    
    def window_to_screen(self, x: int, y: int) -> Tuple[int, int]:
        offset = self.get_offset()
        return (x + offset[0], y + offset[1])
    
    @property
    def capture_failures(self) -> int:
        return self._capture_failed_count