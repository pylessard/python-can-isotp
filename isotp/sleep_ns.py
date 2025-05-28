import sys
import time
import ctypes
import ctypes.util


def _precise_sleep_windows(duration_sec: float) -> None:
    """High-precision sleep implementation for Windows"""
    kernel32 = ctypes.windll.kernel32   # type: ignore[attr-defined]
    
    # Create a waitable timer
    timer = kernel32.CreateWaitableTimerExW(
        None, None, 0x00000002, 0x1F0003
    )
    
    # Time unit is 100 nanoseconds, negative value means relative time
    delay = ctypes.c_longlong(int(-duration_sec * 10000000))
    
    # Set the timer
    kernel32.SetWaitableTimer(
        timer, ctypes.byref(delay), 0, None, None, False
    )
    
    # Wait for the timer to trigger
    kernel32.WaitForSingleObject(timer, 0xFFFFFFFF)
    
    # Close the handle
    kernel32.CloseHandle(timer)

def _precise_sleep_linux(duration_sec: float)-> None:
    """High-precision sleep implementation for Linux"""
    try:
        # Try to use clock_nanosleep (most precise)
        librt = ctypes.CDLL(ctypes.util.find_library("rt"), use_errno=True)
        
        class timespec(ctypes.Structure):
            _fields_ = [("tv_sec", ctypes.c_long),
                        ("tv_nsec", ctypes.c_long)]
        
        req = timespec()
        req.tv_sec = int(duration_sec)
        req.tv_nsec = int((duration_sec - req.tv_sec) * 1e9)
        
        CLOCK_MONOTONIC = 1
        result = librt.clock_nanosleep(
            CLOCK_MONOTONIC, 0, ctypes.byref(req), None
        )
        
        if result != 0:
            errno = ctypes.get_errno()
            raise OSError(errno, f"clock_nanosleep failed with errno {errno}")
    
    except Exception as e:
        # If clock_nanosleep fails, fallback to select
        if duration_sec > 0:
            time.sleep(duration_sec)


def precise_sleep(duration_sec: float)-> None:
    """
    Cross-platform high-precision sleep function
    :param duration_sec: Sleep time in seconds (can be float)
    """
    if sys.platform == 'win32':
        _precise_sleep_windows(duration_sec)
    else:
        _precise_sleep_linux(duration_sec)
