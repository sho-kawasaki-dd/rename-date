import ctypes
from types import SimpleNamespace

import pytest

from rename_date import dpi_awareness
from rename_date import __main__ as main_module


class ApiFunction:
	def __init__(self, result):
		self.result = result
		self.argtypes = None
		self.restype = None
		self.calls = []

	def __call__(self, *args):
		self.calls.append(args)
		return self.result


def stub_user32(set_result, awareness):
	return SimpleNamespace(
		SetProcessDpiAwarenessContext=ApiFunction(set_result),
		GetThreadDpiAwarenessContext=ApiFunction(123),
		GetAwarenessFromDpiAwarenessContext=ApiFunction(awareness),
	)


@pytest.fixture
def windows_api(monkeypatch):
	monkeypatch.setattr(dpi_awareness.os, "name", "nt")
	monkeypatch.setattr(ctypes, "set_last_error", lambda error: None)
	monkeypatch.setattr(ctypes, "get_last_error", lambda: 5)
	return lambda user32: monkeypatch.setattr(
		dpi_awareness.ctypes, "WinDLL", lambda *args, **kwargs: user32, raising=False
	)


def test_sets_system_dpi_awareness(windows_api):
	user32 = stub_user32(True, 1)
	windows_api(user32)

	dpi_awareness.enable_system_dpi_awareness()

	assert user32.SetProcessDpiAwarenessContext.argtypes == [ctypes.c_void_p]
	assert (
		user32.SetProcessDpiAwarenessContext.calls[0][0].value
		== ctypes.c_void_p(-2).value
	)
	assert user32.GetAwarenessFromDpiAwarenessContext.argtypes == [ctypes.c_void_p]


@pytest.mark.parametrize("awareness", [1, 2])
def test_accepts_existing_system_or_per_monitor_awareness(windows_api, awareness):
	windows_api(stub_user32(False, awareness))

	dpi_awareness.enable_system_dpi_awareness()


def test_rejects_process_that_remains_dpi_unaware(windows_api):
	windows_api(stub_user32(False, 0))

	with pytest.raises(RuntimeError, match="remains DPI-unaware.*Windows error 5"):
		dpi_awareness.enable_system_dpi_awareness()


def test_rejects_unaware_state_even_if_setting_api_succeeds(windows_api):
	windows_api(stub_user32(True, 0))

	with pytest.raises(RuntimeError, match="remains DPI-unaware"):
		dpi_awareness.enable_system_dpi_awareness()


def test_reports_awareness_query_failure(windows_api):
	user32 = stub_user32(True, -1)
	windows_api(user32)

	with pytest.raises(RuntimeError, match="Unable to verify"):
		dpi_awareness.enable_system_dpi_awareness()


def test_main_initializes_dpi_before_creating_fallback_tk_window(monkeypatch):
	events = []

	class AlreadyRunningGuard:
		already_running = True

		def __enter__(self):
			return self

		def __exit__(self, *args):
			pass

		def activate_existing_window(self):
			return False

	monkeypatch.setattr(
		main_module, "enable_system_dpi_awareness", lambda: events.append("dpi")
	)
	monkeypatch.setattr(main_module, "SingleInstanceGuard", AlreadyRunningGuard)

	def create_tk():
		events.append("tk")
		return SimpleNamespace(withdraw=lambda: None, destroy=lambda: None)

	monkeypatch.setattr(main_module.tk, "Tk", create_tk)
	monkeypatch.setattr(
		main_module.messagebox,
		"showinfo",
		lambda *args, **kwargs: events.append("message"),
	)

	main_module.main()

	assert events == ["dpi", "tk", "message"]


def test_main_reports_dpi_initialization_failure_without_creating_tk(monkeypatch):
	errors = []

	def fail_dpi_setup():
		raise RuntimeError("DPI setup failed")

	monkeypatch.setattr(main_module, "enable_system_dpi_awareness", fail_dpi_setup)
	monkeypatch.setattr(
		main_module.ctypes,
		"windll",
		SimpleNamespace(
			user32=SimpleNamespace(
				MessageBoxW=lambda *args: errors.append(args),
			)
		),
		raising=False,
	)
	monkeypatch.setattr(
		main_module.tk,
		"Tk",
		lambda: pytest.fail("Tk must not be created when DPI setup fails"),
	)

	main_module.main()

	assert errors[0][1:] == ("DPI setup failed", "rename-date", 0x10)
