import re
import json
import threading
from urllib.error import URLError
from typing import Optional, Tuple, Callable
from urllib.request import urlopen, Request

GITHUB_OWNER = "muralianand12345"
GITHUB_REPO = "topheroes-autoclicker"
CURRENT_VERSION = "1.2.2"

RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def parse_version(version_str: str) -> Tuple[int, ...]:
    clean = version_str.strip().lstrip("vV")
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", clean)
    
    if not match:
        return (0,)
    
    parts = []
    for group in match.groups():
        if group is not None:
            parts.append(int(group))
    
    return tuple(parts) if parts else (0,)


def compare_versions(current: str, latest: str) -> int:
    current_tuple = parse_version(current)
    latest_tuple = parse_version(latest)
    
    max_len = max(len(current_tuple), len(latest_tuple))
    current_padded = current_tuple + (0,) * (max_len - len(current_tuple))
    latest_padded = latest_tuple + (0,) * (max_len - len(latest_tuple))
    
    if current_padded < latest_padded:
        return -1
    elif current_padded > latest_padded:
        return 1
    else:
        return 0


def check_for_update() -> Optional[Tuple[str, str]]:
    try:
        request = Request(RELEASES_API_URL, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": f"{GITHUB_REPO}/{CURRENT_VERSION}"})
        
        with urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        
        latest_tag = data.get("tag_name", "")
        html_url = data.get("html_url", RELEASES_PAGE_URL)
        
        if not latest_tag:
            return None
        
        if compare_versions(CURRENT_VERSION, latest_tag) < 0:
            return (latest_tag, html_url)
        
        return None
    
    except (URLError, json.JSONDecodeError, KeyError, TimeoutError):
        return None
    except Exception:
        return None


def check_for_update_async(callback: Callable[[Optional[Tuple[str, str]]], None]) -> None:
    def worker():
        result = check_for_update()
        callback(result)
    
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()