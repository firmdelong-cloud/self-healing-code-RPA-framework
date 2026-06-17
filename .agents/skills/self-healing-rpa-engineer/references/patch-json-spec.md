# patch.json Spec

Phase three supports selector-only patches.

Required fields:

- `patch_id`
- `skill_id`
- `skill_name`
- `base_version`
- `target_step_id`
- `patch_type`
- `selector_changes`
- `code_changes`
- `allowed_repair_scope`
- `reason`
- `risk_level`
- `test_command`
- `created_at`

Allowed `patch_type` values:

- `selector_update`
- `fallback_selector_add`

`code_changes` must be `null`.

`test_command` must start with:

```json
["python", "-m", "pytest"]
```

`selector_changes.target_file` must be a complete repository-relative path:

```text
example_skills/web_report_export/selectors.yaml
```

`allowed_repair_scope` must include:

- `scope_type: selector_only`
- `failed_step_id`
- `allowed_files`
- `allowed_selector_refs`
- `must_not_touch_other_steps`
- `must_not_touch_runtime`

Reject patches that target `main.py`, `rpa_runtime/`, `repair_agent/`, `skill_registry/`, unrelated steps, or high-risk steps.

