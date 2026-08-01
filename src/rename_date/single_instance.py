"""Windows named-mutex guard for the application process."""

import ctypes


class SingleInstanceGuard:
	"""Prevent multiple application processes from running at once."""

	MUTEX_NAME = r"Local\rename-date-single-instance"
	ERROR_ALREADY_EXISTS = 183

	def __init__(self) -> None:
		self.already_running = False
		self._handle: int | None = None

	def __enter__(self) -> "SingleInstanceGuard":
		self._handle = ctypes.windll.kernel32.CreateMutexW(
			None,
			False,
			self.MUTEX_NAME,
		)
		if not self._handle:
			raise ctypes.WinError(ctypes.get_last_error())
		last_error = ctypes.get_last_error()
		if last_error == 0:
			last_error = ctypes.windll.kernel32.GetLastError()
		self.already_running = last_error in {
			self.ERROR_ALREADY_EXISTS,
			1183,
		}
		return self

	def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
		if self._handle is not None:
			ctypes.windll.kernel32.CloseHandle(self._handle)
			self._handle = None

	def activate_existing_window(self) -> bool:
		hwnd = ctypes.windll.user32.FindWindowW(None, "rename-date")
		if not hwnd:
			return False
		ctypes.windll.user32.SetForegroundWindow(hwnd)
		return True