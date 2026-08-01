"""Tests for OutputTemplateService."""

import json

import pytest

from rename_date import config
from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.services.output_template_service import OutputTemplateService
from rename_date.services.validation import InvalidTemplateError


def test_initial_load_creates_default_preset(tmp_path):
	service = OutputTemplateService(tmp_path)

	entries = service.load()

	assert entries == [
		OutputTemplateEntry(
			config.DEFAULT_TEMPLATE_NAME,
			config.DEFAULT_OUTPUT_TEMPLATE,
		)
	]
	assert (tmp_path / "output_templates.json").exists()


def test_save_and_load_json(tmp_path, default_output_template):
	service = OutputTemplateService(tmp_path)
	custom = OutputTemplateEntry("custom", "{Y}-{M}-{D}")

	service.save([default_output_template, custom])

	assert service.load() == [default_output_template, custom]
	assert json.loads(
		(tmp_path / "output_templates.json").read_text(encoding="utf-8")
	) == [default_output_template.to_dict(), custom.to_dict()]


def test_save_rejects_invalid_templates(tmp_path, default_output_template):
	service = OutputTemplateService(tmp_path)

	with pytest.raises(InvalidTemplateError):
		service.save([OutputTemplateEntry("missing", "{Y}{M}")])
	with pytest.raises(InvalidTemplateError):
		service.save([OutputTemplateEntry("forbidden", "{Y}:{M}:{D}")])


def test_broken_json_falls_back_to_default(tmp_path):
	service = OutputTemplateService(tmp_path)
	(tmp_path / "output_templates.json").write_text("{broken", encoding="utf-8")

	entries = service.load()

	assert entries == [
		OutputTemplateEntry(
			config.DEFAULT_TEMPLATE_NAME,
			config.DEFAULT_OUTPUT_TEMPLATE,
		)
	]


def test_schema_error_falls_back_to_default(tmp_path):
	service = OutputTemplateService(tmp_path)
	(tmp_path / "output_templates.json").write_text("{}", encoding="utf-8")

	entries = service.load()

	assert entries[0].name == config.DEFAULT_TEMPLATE_NAME


def test_upsert_replaces_same_name(tmp_path, default_output_template):
	service = OutputTemplateService(tmp_path)
	service.save([default_output_template])
	replacement = OutputTemplateEntry(
		default_output_template.name,
		"{Y}-{M}-{D}",
	)

	entries = service.upsert(replacement)

	assert entries == [replacement]
	assert service.load() == [replacement]


def test_delete_rejects_removing_last_preset(tmp_path, default_output_template):
	service = OutputTemplateService(tmp_path)
	service.save([default_output_template])

	with pytest.raises(ValueError):
		service.delete(default_output_template.name)