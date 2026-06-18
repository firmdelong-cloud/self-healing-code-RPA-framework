# Procedure Skill Spec

Each fixed workflow Procedure Skill lives under `example_skills/<skill_id>/`.

Use this spec for Web RPA, exports, form submission, scraping, and other deterministic workflows. Do not use this fixed-step spec for chat or inbox-style message automation; use Event Skill architecture instead.

Required files:

- `skill.yaml`
- `selectors.yaml`
- `repair_policy.yaml`
- `main.py`
- `tests/test_skill.py`
- a local fixture in `tests/fixtures/`

`skill.yaml` must include:

- `id`
- `name`
- `version`
- `type: procedure_skill`
- `description`
- `entrypoint`
- `selectors`
- `repair_policy`
- `inputs`
- `outputs`
- `steps`

Each step must include:

- `id`
- `type`
- `goal`

Selector-based steps should include:

- `selector_ref`
- `target_description`

High-risk steps must include:

- `requires_human_confirmation: true`
- `risk_reason`

Selectors must use logical names and define:

- `primary`
- `fallbacks`

`repair_policy.yaml` must use:

- `repair_scope.scope_type: selector_only`
- repository-relative `allowed_files`
- `must_not_touch_runtime: true`

Tests should cover Skill loading and at least one execution path with fake pages or local fixtures.

Quality gate:

```powershell
python -m code_rpa skill validate <skill_id>
python -m code_rpa skill test <skill_id>
python -m pytest
```
