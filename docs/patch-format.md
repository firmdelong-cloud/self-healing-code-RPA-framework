# Patch Format

`patch.json` is the only repair artifact Codex should output for selector-only repairs.

## Required Fields

- `repair_request_id`
- `skill_id`
- `failed_step_id`
- `scope`
- `changes`
- `rationale`

Recommended fields:

- `patch_id`
- `risk_level`
- `created_at`
- `test_command`

## Scope

`scope` must be:

```json
"selector_only"
```

No other scope is allowed for automated repair.

## Changes

`changes` must be a list of selector-only edits. Each change must target the current Skill's `selectors.yaml` file and only the failed step's related selector.

Allowed fields:

- `file`
- `selector_id`
- `field`
- `old`
- `new`

Allowed `field` values:

- `primary`
- `fallbacks`

Forbidden targets:

- runtime code
- tests
- README
- requirements files
- AGENTS files
- Python source files

## Example

```json
{
  "repair_request_id": "a1f2c3d4",
  "skill_id": "web_report_export",
  "failed_step_id": "click_export",
  "scope": "selector_only",
  "changes": [
    {
      "file": "example_skills/web_report_export/selectors.yaml",
      "selector_id": "export_button",
      "field": "primary",
      "old": "#exportBtn",
      "new": "button[data-testid='export']"
    }
  ],
  "rationale": "The DOM snapshot shows the export button now uses data-testid='export'."
}
```

## Validation Rule

Always run:

```powershell
python -m code_rpa repair validate <repair_request_path> <patch_path>
python -m code_rpa repair sandbox <repair_request_path> <patch_path>
python -m pytest
```
