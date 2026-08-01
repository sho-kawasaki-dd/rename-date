"""Shared fixtures for service tests."""

import pytest

from rename_date import config
from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.models.pattern_entry import PatternEntry


@pytest.fixture
def default_pattern() -> PatternEntry:
	return PatternEntry(
		name=config.DEFAULT_PATTERN_NAME,
		pattern=config.DEFAULT_PATTERN_REGEX,
	)


@pytest.fixture
def default_output_template() -> OutputTemplateEntry:
	return OutputTemplateEntry(
		name=config.DEFAULT_TEMPLATE_NAME,
		template=config.DEFAULT_OUTPUT_TEMPLATE,
	)


@pytest.fixture
def sample_tree(tmp_path):
	root = tmp_path / "sample"
	(root / "sub").mkdir(parents=True)
	(root / ".hidden").mkdir()
	(root / ".git").mkdir()

	for relative_path in (
		"テスト (2024.1.5).txt",
		"メモ (2024.12.31) v2.txt",
		"二重 (2023.1.1) と (2023.2.2).txt",
		"不正 (2024.13.45).txt",
		"既存 20240105.txt",
		"既存 (2024.1.5).txt",
		".hidden/隠し (2024.1.1).txt",
		".git/x (2024.1.1).txt",
		"sub/報告 (2025.3.7).pdf",
	):
		path = root / relative_path
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text("sample", encoding="utf-8")
	return root