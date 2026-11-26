"""Collect files and calculate safe rename targets."""

import os
import stat
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from threading import Event

from rename_date import config
from rename_date.models.rename_item import ItemStatus, RenameItem
from rename_date.services import date_span
from rename_date.services.validation import (
	InvalidPatternError,
	compile_pattern,
	pattern_kind,
	validate_output_template,
	validate_range_output_template,
)


class ScannerService:
	"""Build a preview of files that can be renamed."""

	def scan(
		self,
		targets: Iterable[Path | str] | Path | str,
		patterns: list[str],
		output_template: str,
		cancel_event: Event | None = None,
		progress_callback: Callable[[int, int], None] | None = None,
		range_output_template: str = config.DEFAULT_RANGE_OUTPUT_TEMPLATE,
	) -> list[RenameItem]:
		"""Scan targets and calculate collision-free rename destinations."""
		if not patterns:
			raise InvalidPatternError("at least one pattern is required")
		validate_range_output_template(range_output_template)
		validate_output_template(output_template)
		compiled_patterns = [compile_pattern(pattern) for pattern in patterns]
		ordered_patterns = sorted(
			compiled_patterns,
			key=lambda compiled: pattern_kind(compiled).value == "single",
		)
		files = self._collect_files(targets, cancel_event)
		reservations: dict[Path, set[str]] = {}
		results: list[RenameItem] = []

		total = len(files)
		for index, source in enumerate(files, start=1):
			if cancel_event is not None and cancel_event.is_set():
				break

			try:
				working_stem = source.stem
				matched_any = False
				invalid_date = False
				for compiled in ordered_patterns:
					matches = list(compiled.finditer(working_stem))
					if not matches:
						continue
					matched_any = True
					kind = pattern_kind(compiled)

					try:
						for match in matches:
							date_span.parse_match(match, kind)
					except ValueError:
						invalid_date = True
						break

					def replace_match(match: re.Match[str]) -> str:
						span = date_span.parse_match(match, kind)
						template = (
							range_output_template
							if kind.value == "range"
							else output_template
						)
						return date_span.render(span, template)

					working_stem = compiled.sub(replace_match, working_stem)

				if invalid_date:
					results.append(
						RenameItem(
							original_path=source,
							target_path=source,
							status=ItemStatus.INVALID_DATE,
							message="matched value is not a valid date",
						)
					)
					continue
				if not matched_any:
					continue

				new_stem = re.sub(r"\s{2,}", " ", working_stem).strip()
				if new_stem == source.stem:
					continue

				reserved = reservations.setdefault(
					source.parent,
					self._existing_names(source.parent),
				)
				reserved.discard(source.name.casefold())
				target_stem, resolved_conflict = self._resolve_conflict(
					new_stem,
					source.suffix,
					reserved,
				)
				target = source.with_name(target_stem + source.suffix)
				reserved.add(target.name.casefold())
				results.append(
					RenameItem(
						original_path=source,
						target_path=target,
						status=(
							ItemStatus.RESOLVED_CONFLICT
							if resolved_conflict
							else ItemStatus.PENDING
						),
					)
				)
			finally:
				if progress_callback is not None:
					progress_callback(index, total)

		return results

	def _collect_files(
		self,
		targets: Iterable[Path | str] | Path | str,
		cancel_event: Event | None,
	) -> list[Path]:
		if isinstance(targets, (str, os.PathLike)):
			target_list = [Path(targets)]
		else:
			target_list = [Path(target) for target in targets]

		collected: dict[Path, Path] = {}
		for target in target_list:
			if cancel_event is not None and cancel_event.is_set():
				break
			if target.is_dir():
				if self._is_hidden(target) or self._is_link_or_junction(target):
					continue
				for root, dirnames, filenames in os.walk(
					target,
					topdown=True,
					followlinks=False,
				):
					if cancel_event is not None and cancel_event.is_set():
						return self._sorted_unique(collected)
					root_path = Path(root)
					dirnames[:] = [
						dirname
						for dirname in dirnames
						if not self._excluded_directory(root_path / dirname)
					]
					for filename in filenames:
						if cancel_event is not None and cancel_event.is_set():
							return self._sorted_unique(collected)
						path = root_path / filename
						if not self._is_hidden(path) and not self._is_link_or_junction(path):
							self._add_resolved(collected, path)
			elif target.is_file() and not self._is_hidden(target):
				self._add_resolved(collected, target)

		return self._sorted_unique(collected)

	@staticmethod
	def _add_resolved(collected: dict[Path, Path], path: Path) -> None:
		try:
			resolved = path.resolve()
		except OSError:
			return
		collected.setdefault(resolved, resolved)

	@staticmethod
	def _sorted_unique(collected: dict[Path, Path]) -> list[Path]:
		return sorted(
			collected.values(),
			key=lambda path: (str(path.parent).casefold(), path.name.casefold(), path.name),
		)

	@classmethod
	def _excluded_directory(cls, path: Path) -> bool:
		return (
			cls._is_hidden(path)
			or cls._is_link_or_junction(path)
			or path.name.casefold() in {name.casefold() for name in config.EXCLUDED_DIR_NAMES}
		)

	@staticmethod
	def _is_hidden(path: Path) -> bool:
		if path.name.startswith("."):
			return True
		try:
			attributes = path.stat(follow_symlinks=False).st_file_attributes
		except (AttributeError, OSError):
			return False
		return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2))

	@staticmethod
	def _is_link_or_junction(path: Path) -> bool:
		if path.is_symlink():
			return True
		is_junction = getattr(path, "is_junction", None)
		if is_junction is not None and is_junction():
			return True
		try:
			attributes = path.stat(follow_symlinks=False).st_file_attributes
		except (AttributeError, OSError):
			return False
		return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))

	@staticmethod
	def _existing_names(parent: Path) -> set[str]:
		try:
			return {entry.name.casefold() for entry in parent.iterdir()}
		except OSError:
			return set()

	@staticmethod
	def _resolve_conflict(
		stem: str,
		suffix: str,
		reserved: set[str],
	) -> tuple[str, bool]:
		candidate = stem
		counter = 0
		while (candidate + suffix).casefold() in reserved:
			counter += 1
			candidate = f"{stem}_{counter}"
		return candidate, counter > 0