"""Tests for OutputTemplateService."""

import json

import pytest

from rename_date import config
from rename_date.models.output_template_entry import OutputTemplateEntry
from rename_date.services.preset_io import (
	ConflictPolicy,
	PresetIOError,
	PresetIOReason,
)
from rename_date.services.output_template_service import (
	MonthOutputTemplateService,
	OutputTemplateService,
	RangeOutputTemplateService,
)
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


@pytest.mark.parametrize("placeholder", ["{Y2}", "{M2}", "{D2}"])
def test_save_rejects_range_placeholders_in_single_template(
	tmp_path,
	placeholder,
):
	service = OutputTemplateService(tmp_path)

	with pytest.raises(InvalidTemplateError):
		service.save([
			OutputTemplateEntry(
				"range placeholder",
				"{Y}{M}{D}" + placeholder,
			)
		])


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


def test_range_initial_load_creates_default_preset(tmp_path):
	service = RangeOutputTemplateService(tmp_path)

	entries = service.load()

	assert entries == [
		OutputTemplateEntry(
			config.DEFAULT_RANGE_TEMPLATE_NAME,
			config.DEFAULT_RANGE_OUTPUT_TEMPLATE,
		)
	]
	assert (tmp_path / "range_output_templates.json").exists()


@pytest.mark.parametrize(
	"template",
	[
		"{Y}{M}{D}-{Y2}{M2}",
		"{Y}{M}{D}-{Y2}{D2}",
		"{Y}{M}{D}-{M2}{D2}",
	],
)
def test_range_save_rejects_missing_placeholders(tmp_path, template):
	service = RangeOutputTemplateService(tmp_path)

	with pytest.raises(InvalidTemplateError):
		service.save([OutputTemplateEntry("missing", template)])


def test_range_broken_json_falls_back_to_default(tmp_path):
	service = RangeOutputTemplateService(tmp_path)
	(tmp_path / "range_output_templates.json").write_text("{broken", encoding="utf-8")

	entries = service.load()

	assert entries == [
		OutputTemplateEntry(
			config.DEFAULT_RANGE_TEMPLATE_NAME,
			config.DEFAULT_RANGE_OUTPUT_TEMPLATE,
		)
	]


def test_range_delete_rejects_removing_last_preset(tmp_path):
	service = RangeOutputTemplateService(tmp_path)
	default_entry = service.load()[0]

	with pytest.raises(ValueError):
		service.delete(default_entry.name)


def test_range_template_uses_separate_file(tmp_path):
	single_service = OutputTemplateService(tmp_path)
	range_service = RangeOutputTemplateService(tmp_path)

	single_service.load()
	range_service.load()

	assert (tmp_path / "output_templates.json").exists()
	assert (tmp_path / "range_output_templates.json").exists()


def test_month_initial_load_creates_separate_default_preset(tmp_path):
	service = MonthOutputTemplateService(tmp_path)

	assert service.load() == [
		OutputTemplateEntry(
			config.DEFAULT_MONTH_TEMPLATE_NAME,
			config.DEFAULT_MONTH_OUTPUT_TEMPLATE,
		)
	]
	assert (tmp_path / "month_output_templates.json").exists()


@pytest.mark.parametrize(
	"template",
	[
		"{Y}",
		"{M}",
		"{Y}-{M}-{D}",
		"{Y}-{M}-{Y2}",
		"{Y}-{M}-{foo}",
		"{Y}\t{M}",
		"{Y}\x00{M}",
	],
)
def test_month_save_rejects_invalid_templates(tmp_path, template):
	service = MonthOutputTemplateService(tmp_path)

	with pytest.raises(InvalidTemplateError):
		service.save([OutputTemplateEntry("invalid", template)])


def test_month_save_and_load_json(tmp_path):
	service = MonthOutputTemplateService(tmp_path)
	entry = OutputTemplateEntry("month", "{Y}_{Y}-{M}")

	service.save([entry])

	assert service.load() == [entry]
	assert json.loads(
		(tmp_path / "month_output_templates.json").read_text(encoding="utf-8")
	) == [entry.to_dict()]


def test_month_template_json_round_trip_with_bom(tmp_path):
	source_service = MonthOutputTemplateService(tmp_path / "source")
	destination_service = MonthOutputTemplateService(tmp_path / "destination")
	entries = [
		OutputTemplateEntry("month", "{Y}-{M}"),
		OutputTemplateEntry("alternate", "{Y}_{Y}-{M}"),
	]
	source_service.save(entries)
	destination_service.save([OutputTemplateEntry("existing", "{Y}_{M}")])
	export_path = tmp_path / "month-export.json"
	source_service.export_to_json(export_path)
	exported_bytes = export_path.read_bytes()

	assert not exported_bytes.startswith(b"\xef\xbb\xbf")
	import_path = tmp_path / "month-import.json"
	import_path.write_bytes(b"\xef\xbb\xbf" + exported_bytes)

	assert destination_service.import_from_json(import_path) == [
		OutputTemplateEntry("existing", "{Y}_{M}"),
		*entries,
	]


@pytest.mark.parametrize(
	("source_type", "source_template", "destination_type", "destination_template"),
	[
		(
			MonthOutputTemplateService,
			"{Y}-{M}",
			OutputTemplateService,
			"{Y}{M}{D}",
		),
		(
			MonthOutputTemplateService,
			"{Y}-{M}",
			RangeOutputTemplateService,
			"{Y}{M}{D}-{Y2}{M2}{D2}",
		),
		(
			OutputTemplateService,
			"{Y}{M}{D}",
			MonthOutputTemplateService,
			"{Y}-{M}",
		),
		(
			RangeOutputTemplateService,
			"{Y}{M}{D}-{Y2}{M2}{D2}",
			MonthOutputTemplateService,
			"{Y}-{M}",
		),
	],
)
def test_month_templates_cannot_be_imported_as_other_kinds(
	tmp_path,
	source_type,
	source_template,
	destination_type,
	destination_template,
):
	source_service = source_type(tmp_path / "source")
	destination_service = destination_type(tmp_path / "destination")
	source_service.save([OutputTemplateEntry("source", source_template)])
	destination_service.save(
		[OutputTemplateEntry("existing", destination_template)]
	)
	export_path = tmp_path / "cross-kind.json"
	source_service.export_to_json(export_path)
	original_config = destination_service.file_path.read_bytes()

	with pytest.raises(PresetIOError) as error:
		destination_service.import_from_json(export_path)

	assert error.value.reason is PresetIOReason.VALIDATION
	assert error.value.name == "source"
	assert destination_service.file_path.read_bytes() == original_config


@pytest.mark.parametrize(
	"invalid",
	["\u0000", "\t"],
)
def test_month_import_rejects_mixed_valid_and_invalid_entries_without_changes(
	tmp_path,
	invalid,
):
	service = MonthOutputTemplateService(tmp_path / "config")
	service.save([OutputTemplateEntry("existing", "{Y}-{M}")])
	original_config = service.file_path.read_bytes()
	import_path = tmp_path / "mixed.json"
	import_path.write_text(
		json.dumps(
			[
				{"name": "valid", "template": "{Y}-{M}"},
				{"name": "invalid", "template": f"{{Y}}{invalid}{{M}}"},
			]
		),
		encoding="utf-8",
	)
	original_import = import_path.read_bytes()

	with pytest.raises(PresetIOError) as error:
		service.import_from_json(import_path)

	assert error.value.reason is PresetIOReason.VALIDATION
	assert error.value.name == "invalid"
	assert error.value.index == 1
	assert service.file_path.read_bytes() == original_config
	assert import_path.read_bytes() == original_import


def test_month_import_rejects_duplicate_name_without_changes(tmp_path):
	service = MonthOutputTemplateService(tmp_path / "config")
	existing = OutputTemplateEntry("same", "{Y}-{M}")
	service.save([existing])
	original_config = service.file_path.read_bytes()
	import_path = tmp_path / "duplicate-month.json"
	import_path.write_text(
		json.dumps([OutputTemplateEntry("same", "{Y}_{M}").to_dict()]),
		encoding="utf-8",
	)
	original_import = import_path.read_bytes()

	with pytest.raises(PresetIOError) as error:
		service.import_from_json(import_path)

	assert error.value.reason is PresetIOReason.DUPLICATE_NAME
	assert error.value.name == "same"
	assert service.file_path.read_bytes() == original_config
	assert import_path.read_bytes() == original_import


@pytest.mark.parametrize(
	("service_type", "template"),
	[
		(OutputTemplateService, "{Y}{M}{D}"),
		(RangeOutputTemplateService, "{Y}{M}{D}-{Y2}{M2}{D2}"),
	],
)
@pytest.mark.parametrize("operation", ["export", "import"])
def test_other_template_services_reject_month_internal_path(
	tmp_path,
	service_type,
	template,
	operation,
):
	base_dir = tmp_path / "config"
	service = service_type(base_dir)
	service.save([OutputTemplateEntry("existing", template)])
	month_internal_path = base_dir / config.MONTH_OUTPUT_TEMPLATES_FILE_NAME

	with pytest.raises(PresetIOError) as error:
		if operation == "export":
			service.export_to_json(month_internal_path)
		else:
			service.import_from_json(month_internal_path)

	assert error.value.reason is PresetIOReason.INTERNAL_PATH


@pytest.mark.parametrize(
	("service_type", "template"),
	[
		(OutputTemplateService, "{Y}-{M}-{D}"),
		(RangeOutputTemplateService, "{Y}{M}{D} - {Y2}{M2}{D2}"),
	],
)
def test_output_template_json_round_trip_with_bom(
	tmp_path,
	service_type,
	template,
):
	source_service = service_type(tmp_path / "source")
	destination_service = service_type(tmp_path / "destination")
	existing = OutputTemplateEntry("existing", template)
	entries = [
		OutputTemplateEntry("既定以外", template),
		OutputTemplateEntry("second", template),
	]
	source_service.save(entries)
	destination_service.save([existing])
	export_path = tmp_path / "export.json"
	source_service.export_to_json(export_path)
	exported_bytes = export_path.read_bytes()

	assert not exported_bytes.startswith(b"\xef\xbb\xbf")
	import_path = tmp_path / "import.json"
	import_path.write_bytes(b"\xef\xbb\xbf" + exported_bytes)

	assert destination_service.import_from_json(import_path) == [existing, *entries]
	assert not destination_service.file_path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_single_and_range_templates_cannot_be_imported_by_other_service(tmp_path):
	single_service = OutputTemplateService(tmp_path / "single")
	range_service = RangeOutputTemplateService(tmp_path / "range")
	single_service.save([OutputTemplateEntry("single", "{Y}{M}{D}")])
	range_service.save(
		[OutputTemplateEntry("range", "{Y}{M}{D}-{Y2}{M2}{D2}")]
	)
	single_export = tmp_path / "single.json"
	range_export = tmp_path / "range.json"
	single_service.export_to_json(single_export)
	range_service.export_to_json(range_export)

	with pytest.raises(PresetIOError) as single_error:
		range_service.import_from_json(single_export)
	with pytest.raises(PresetIOError) as range_error:
		single_service.import_from_json(range_export)

	assert single_error.value.reason is PresetIOReason.VALIDATION
	assert single_error.value.name == "single"
	assert range_error.value.reason is PresetIOReason.VALIDATION
	assert range_error.value.name == "range"


@pytest.mark.parametrize(
	("payload", "reason", "name", "index"),
	[
		("{broken", PresetIOReason.INVALID_JSON, None, None),
		("[]", PresetIOReason.INVALID_FORMAT, None, None),
		(
			'[{"name":"bad","template":3}]',
			PresetIOReason.INVALID_FORMAT,
			"bad",
			0,
		),
		(
			'[{"name":"bad","template":"{Y}{M}"}]',
			PresetIOReason.VALIDATION,
			"bad",
			0,
		),
		(
			'[{"name":"duplicate","template":"{Y}{M}{D}"},'
			'{"name":"duplicate","template":"{Y}{M}{D}"}]',
			PresetIOReason.DUPLICATE_NAME,
			"duplicate",
			1,
		),
	],
)
@pytest.mark.parametrize(
	("service_type", "valid_template"),
	[
		(OutputTemplateService, "{Y}{M}{D}"),
		(RangeOutputTemplateService, "{Y}{M}{D}-{Y2}{M2}{D2}"),
	],
)
def test_import_rejects_malformed_presets_without_changing_either_file(
	tmp_path,
	payload,
	reason,
	name,
	index,
	service_type,
	valid_template,
):
	service = service_type(tmp_path / "config")
	service.save([OutputTemplateEntry("existing", valid_template)])
	original_config = service.file_path.read_bytes()
	import_path = tmp_path / "invalid.json"
	if reason is PresetIOReason.DUPLICATE_NAME:
		payload = json.dumps(
			[
				{"name": "duplicate", "template": valid_template},
				{"name": "duplicate", "template": valid_template},
			]
		)
	import_path.write_text(payload, encoding="utf-8")
	original_import = import_path.read_bytes()

	with pytest.raises(PresetIOError) as error:
		service.import_from_json(import_path)

	assert error.value.reason is reason
	assert error.value.name == name
	assert error.value.index == index
	assert service.file_path.read_bytes() == original_config
	assert import_path.read_bytes() == original_import


@pytest.mark.parametrize("operation", ["export", "import"])
@pytest.mark.parametrize("storage_state", ["missing", "corrupt"])
@pytest.mark.parametrize(
	("service_type", "valid_template"),
	[
		(OutputTemplateService, "{Y}{M}{D}"),
		(RangeOutputTemplateService, "{Y}{M}{D}-{Y2}{M2}{D2}"),
	],
)
def test_json_operations_do_not_restore_missing_or_corrupt_internal_storage(
	tmp_path,
	operation,
	storage_state,
	service_type,
	valid_template,
):
	service = service_type(tmp_path / "config")
	if storage_state == "corrupt":
		service.base_dir.mkdir(parents=True)
		service.file_path.write_bytes(b"{broken")
	original_config = (
		service.file_path.read_bytes() if service.file_path.exists() else None
	)
	import_path = tmp_path / "valid.json"
	import_path.write_text(
		json.dumps(
			[{"name": "custom", "template": valid_template}],
		),
		encoding="utf-8",
	)

	with pytest.raises((FileNotFoundError, ValueError)):
		if operation == "export":
			service.export_to_json(tmp_path / "export.json")
		else:
			service.import_from_json(import_path)

	if original_config is None:
		assert not service.file_path.exists()
	else:
		assert service.file_path.read_bytes() == original_config


@pytest.mark.parametrize(
	("service_type", "valid_template"),
	[
		(OutputTemplateService, "{Y}{M}{D}"),
		(RangeOutputTemplateService, "{Y}{M}{D}-{Y2}{M2}{D2}"),
	],
)
def test_late_invalid_import_entry_preserves_source_and_internal_files(
	tmp_path,
	service_type,
	valid_template,
):
	service = service_type(tmp_path / "config")
	service.save([OutputTemplateEntry("existing", valid_template)])
	original_config = service.file_path.read_bytes()
	invalid_template = (
		"{Y}{M}" if service_type is OutputTemplateService else "{Y}{M}{D}"
	)
	import_path = tmp_path / "late-invalid.json"
	import_path.write_text(
		json.dumps(
			[
				{"name": "valid", "template": valid_template},
				{"name": "invalid", "template": invalid_template},
			]
		),
		encoding="utf-8",
	)
	original_import = import_path.read_bytes()

	with pytest.raises(PresetIOError) as error:
		service.import_from_json(import_path)

	assert error.value.reason is PresetIOReason.VALIDATION
	assert error.value.name == "invalid"
	assert error.value.index == 1
	assert service.file_path.read_bytes() == original_config
	assert import_path.read_bytes() == original_import


@pytest.mark.parametrize(
	("service_type", "template"),
	[
		(OutputTemplateService, "{Y}{M}{D}"),
		(RangeOutputTemplateService, "{Y}{M}{D}-{Y2}{M2}{D2}"),
		(MonthOutputTemplateService, "{Y}-{M}"),
	],
)
def test_import_plan_overwrites_in_place_and_appends_in_import_order(
	tmp_path,
	service_type,
	template,
):
	service = service_type(tmp_path / "config")
	existing = [
		OutputTemplateEntry("first", template),
		OutputTemplateEntry("replace", template),
		OutputTemplateEntry("last", template),
	]
	service.save(existing)
	imported = [
		OutputTemplateEntry("new-first", template),
		OutputTemplateEntry("replace", template),
		OutputTemplateEntry("new-last", template),
	]
	import_path = tmp_path / "import.json"
	import_path.write_text(
		json.dumps([entry.to_dict() for entry in imported]),
		encoding="utf-8",
	)

	plan = service.prepare_import(import_path)
	result = service.apply_import(plan, ConflictPolicy.OVERWRITE)

	assert plan.conflicting_names == ("replace",)
	assert result.updated_entries == [
		existing[0],
		imported[1],
		existing[2],
		imported[0],
		imported[2],
	]
	assert (result.added_count, result.overwritten_count, result.skipped_count) == (
		2,
		1,
		0,
	)
	assert result.changed
	assert service.load() == result.updated_entries


@pytest.mark.parametrize(
	("service_type", "template"),
	[
		(OutputTemplateService, "{Y}{M}{D}"),
		(RangeOutputTemplateService, "{Y}{M}{D}-{Y2}{M2}{D2}"),
		(MonthOutputTemplateService, "{Y}-{M}"),
	],
)
def test_all_skipped_import_does_not_write(
	tmp_path,
	service_type,
	template,
):
	service = service_type(tmp_path / "config")
	existing = OutputTemplateEntry("same", template)
	service.save([existing])
	original_bytes = service.file_path.read_bytes()
	import_path = tmp_path / "import.json"
	import_path.write_text(
		json.dumps([existing.to_dict()]),
		encoding="utf-8",
	)

	result = service.apply_import(
		service.prepare_import(import_path),
		ConflictPolicy.SKIP,
	)

	assert result.updated_entries == [existing]
	assert (result.added_count, result.overwritten_count, result.skipped_count) == (
		0,
		0,
		1,
	)
	assert not result.changed
	assert service.file_path.read_bytes() == original_bytes
