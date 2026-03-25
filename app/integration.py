import os
import subprocess
import sys


def _project_root() -> str:
    # app/ -> project root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _get_screen_size() -> tuple[int, int]:
    """
    Lấy (width, height) màn hình hiện tại (Windows).
    Ưu tiên screeninfo nếu có, fallback ctypes.
    """
    try:
        try:
            from screeninfo import get_monitors  # type: ignore

            monitors = get_monitors()
            if monitors:
                m0 = monitors[0]
                return int(m0.width), int(m0.height)
        except Exception:
            pass

        import ctypes

        user32 = ctypes.windll.user32
        width = int(user32.GetSystemMetrics(0))
        height = int(user32.GetSystemMetrics(1))
        return width, height
    except Exception:
        return 1280, 720


def arrange_windows(game_title: str) -> bool:
    """
    Sắp xếp cửa sổ:
    - Game (game_title): chiếm 75% màn hình bên trái, (0,0)
    - Camera: camera_worker tự sắp xếp riêng (1/4 bên phải)

    Vì tiêu đề cửa sổ có thể khác 100%, hàm sẽ match theo "chứa" (contains).
    Trả về True nếu tìm thấy và resize/move thành công ít nhất 1 cửa sổ.
    """
    screen_w, screen_h = _get_screen_size()
    game_w = int(screen_w * 0.75)

    # 1) Try pygetwindow (dễ dùng)
    try:
        import pygetwindow as gw  # type: ignore

        # getWindowsWithTitle match theo substring (tùy OS), nhưng đôi khi không
        wins = gw.getWindowsWithTitle(game_title)
        # Fallback: lọc theo contains nếu API không match đúng
        wins = [w for w in wins if game_title.lower() in (w.title or "").lower()]

        if not wins:
            return False

        ok_any = False
        for w in wins:
            try:
                w.resizeTo(game_w, screen_h)
                w.moveTo(0, 0)
                try:
                    w.activate()
                except Exception:
                    pass
                ok_any = True
            except Exception:
                continue

        return ok_any
    except Exception:
        pass

    # 2) Fallback pywin32
    try:
        import win32gui  # type: ignore
        import win32con  # type: ignore

        hwnds = []

        def _enum_handler(hwnd, _):
            try:
                title = win32gui.GetWindowText(hwnd)
                if game_title.lower() in (title or "").lower():
                    hwnds.append(hwnd)
            except Exception:
                pass

        win32gui.EnumWindows(_enum_handler, None)
        if not hwnds:
            return False

        hwnd = hwnds[0]
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            0,
            0,
            game_w,
            screen_h,
            win32con.SWP_SHOWWINDOW,
        )
        return True
    except Exception:
        return False


def start_bridge_subprocess() -> subprocess.Popen | None:
    """
    Khởi chạy `Modules/Hardware/bridge.py` bằng subprocess.Popen.

    - bridge.py chạy vô hạn (while True), nên luôn cần terminate/kill khi dừng camera.
    - Trả về Popen để UI quản lý vòng đời.
    """
    bridge_path = os.path.join(_project_root(), "Modules", "Hardware", "bridge.py")
    if not os.path.exists(bridge_path):
        return None

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        return subprocess.Popen(
            [sys.executable, bridge_path],
            cwd=_project_root(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception:
        return None


def stop_bridge_subprocess(proc: subprocess.Popen | None) -> None:
    """
    Dừng bridge.py để giải phóng cổng Serial/Bluetooth.
    """
    if proc is None:
        return

    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

