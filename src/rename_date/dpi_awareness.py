"""Windows process DPI awareness initialization."""

import ctypes
import os


_SYSTEM_DPI_AWARE_CONTEXT = ctypes.c_void_p(-2)


def enable_system_dpi_awareness() -> None:
	"""Enable system DPI awareness before creating any Tk windows."""

	if os.name != "nt":
		raise RuntimeError("System DPI awareness is only supported on Windows.")

	try:
		user32 = ctypes.WinDLL("user32", use_last_error=True)
	except (AttributeError, OSError) as exc:
		raise RuntimeError("Unable to load the Windows DPI awareness API.") from exc

	try:
		set_awareness = user32.SetProcessDpiAwarenessContext
		set_awareness.argtypes = [ctypes.c_void_p]
		set_awareness.restype = ctypes.c_bool
		get_context = user32.GetThreadDpiAwarenessContext
		get_context.argtypes = []
		get_context.restype = ctypes.c_void_p
		get_awareness = user32.GetAwarenessFromDpiAwarenessContext
		get_awareness.argtypes = [ctypes.c_void_p]
		get_awareness.restype = ctypes.c_int
	except AttributeError as exc:
		raise RuntimeError(
			"Windows does not provide the required DPI awareness APIs."
		) from exc

	ctypes.set_last_error(0)
	if set_awareness(_SYSTEM_DPI_AWARE_CONTEXT):
		set_error = 0
	else:
		set_error = ctypes.get_last_error()

	try:
		context = get_context()
		if not context:
			raise RuntimeError(
				f"GetThreadDpiAwarenessContext failed "
				f"(Windows error {ctypes.get_last_error()})."
			)
		awareness = get_awareness(context)
		if awareness not in (0, 1, 2):
			raise RuntimeError(
				f"GetAwarenessFromDpiAwarenessContext failed "
				f"(Windows error {ctypes.get_last_error()})."
			)
	except RuntimeError as exc:
		raise RuntimeError(
			"Unable to verify the process DPI awareness after initialization."
		) from exc

	if awareness >= 1:
		return

	raise RuntimeError(
		"Unable to enable system DPI awareness; the process remains DPI-unaware "
		f"(Windows error {set_error})."
	)
