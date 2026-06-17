# Skill Contract

This document defines the minimum contract for a Self-Healing Code RPA Skill.

## skill.yaml Required Fields

Every Skill must provide:

- `id`: stable lowercase Skill ID, matching the directory name.
- `name`: human-readable Skill name.
- `version`: semantic version string, for example `0.1.0`.
- `description`: short purpose statement.
- `entrypoint`: Python entrypoint, normally `main.py`.
- `selectors`: selector file path, normally `selectors.yaml`.
- `repair_policy`: repair policy file path, normally `repair_policy.yaml`.
- `inputs`: structured input definitions. Use defaults for local demos only.
- `outputs`: structured output definitions.
- `steps`: ordered workflow steps.

## inputs Format

`inputs` is a mapping of input names to type metadata:

```yaml
inputs:
  username:
    type: string
    default: demo_user
```

Do not hardcode real passwords, tokens, cookies, or customer secrets in `inputs`.

## steps Format

Each step must include:

- `id`: stable step ID.
- `type`: runtime step type.
- `goal`: short business goal.

Selector-based steps must include `selector_ref`.

Supported Web step types include:

- `goto`
- `click`
- `fill`
- `select`
- `wait_for`
- `extract_text`
- `extract_table`
- `download_file`
- `assert_text`
- `assert_url`
- `screenshot`

Backward-compatible demo step types are still supported:

- `navigate`
- `login`
- `select_date_range`
- `wait_for_selector`

## selectors.yaml Format

Each selector reference must define a primary selector and fallback selectors:

```yaml
submit_button:
  primary: "#submit"
  fallbacks:
    - "[data-testid='submit']"
    - "text=Submit"
```

Runtime selector steps always try the primary selector first, then fallbacks.

## repair_policy.yaml Format

`repair_policy.yaml` defines retry and sandbox behavior:

```yaml
retry:
  max_attempts: 1
  delay_seconds: 0
repair_scope:
  scope_type: selector_only
  must_not_touch_runtime: true
sandbox:
  required: true
  command:
    - python
    - -m
    - pytest
    - example_skills/my_skill/tests/test_skill.py
```

The first production repair scope is `selector_only`.

## outputs Format

Skill execution returns `RunResult.outputs`, a structured dictionary collected from steps.

Examples:

```json
{
  "download_path": "storage/outputs/<run_id>/report.csv",
  "table_rows": 10,
  "extracted_text": "Export ready"
}
```

Steps can write outputs with `output_key`, `row_count_output_key`, and `output_path_key`.

## Version Rules

- Skill versions use semantic versioning.
- A successful repair increments the patch version.
- `VersionManager` stores snapshots under `storage/versions/<skill_id>/`.
- Every version must include metadata with `created_at`, `patch_id`, `base_version`, `test_result`, and `changed_files`.
- Rollback must restore both files and runtime behavior.

## Repair Scope Rules

Repair scope must be explicit and narrow:

```yaml
allowed_repair_scope:
  scope_type: selector_only
  failed_step_id: click_export
  allowed_files:
    - example_skills/web_report_export/selectors.yaml
  allowed_selector_refs:
    - export_button
  must_not_touch_other_steps: true
  must_not_touch_runtime: true
```

Selector-only patches must not modify `main.py`, `rpa_runtime/`, `repair_agent/`, or `skill_registry/`.

High-risk actions such as delete, payment, approval, and batch submit must require human approval.

## Minimal Example

```yaml
id: my_skill
name: My Skill
version: 0.1.0
description: Open a page and verify it loaded.
entrypoint: main.py
selectors: selectors.yaml
repair_policy: repair_policy.yaml
inputs: {}
outputs:
  page_title:
    type: string
steps:
  - id: open_page
    type: goto
    goal: Open the local page.
    url: "about:blank"

  - id: read_title
    type: extract_text
    goal: Read the page title.
    selector_ref: page_title
    output_key: page_title
```
