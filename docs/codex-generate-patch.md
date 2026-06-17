# Codex Generate Patch

This guide describes how Codex should repair a failed Skill by generating a selector-only `patch.json`.

## Read Repair Request

Start from `repair_request.json`.

Use it to identify:

- `failed_step_id`
- `skill_id`
- failure message
- current URL
- screenshot path
- DOM snapshot path
- allowed repair scope
- original selector and fallback selectors

## Inspect Evidence

Use the DOM snapshot and screenshots to determine whether:

- the selector changed,
- the selector is too specific,
- a new fallback selector is more stable,
- or the primary selector should be updated.

Do not infer changes beyond the failed step.

## Output Only Patch JSON

Codex must output only `patch.json`.

Codex must not directly edit files.

Codex must not modify runtime code, test files, README files, requirements files, or AGENTS files.

Codex must not bypass `selector_resolver`.

## Required Repair Flow

After generating `patch.json`, run:

```powershell
python -m code_rpa repair validate <repair_request_path> <patch_path>
python -m code_rpa repair sandbox <repair_request_path> <patch_path>
python -m pytest
```

If validation fails, revise the patch.

If sandbox fails, revise the patch or selector choice.

If pytest fails, revise the patch or the Skill contract.

## Successful Repair

When validation and sandbox tests pass:

1. Apply the patch to the live Skill.
2. Create a new version snapshot.
3. Rerun the Skill.
4. Keep rollback metadata.

Use `python -m code_rpa repair apply <repair_request_path> <patch_path>` for the full local repair flow.

## Example Patch

```json
{
  "repair_request_id": "a1f2c3d4",
  "skill_id": "customer_search_export",
  "failed_step_id": "enter_customer_keyword",
  "scope": "selector_only",
  "changes": [
    {
      "file": "example_skills/customer_search_export/selectors.yaml",
      "selector_id": "customer_keyword_input",
      "field": "primary",
      "old": "#missing-customer-keyword",
      "new": "#customer-keyword"
    }
  ],
  "rationale": "The input still exists but the primary selector is stale."
}
```
