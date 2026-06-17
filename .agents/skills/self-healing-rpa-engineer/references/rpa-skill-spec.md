# RPA Skill Spec

Each Skill lives under `example_skills/<skill_id>/`.

Required files:

- `skill.yaml`
- `selectors.yaml`
- `repair_policy.yaml`
- `main.py`
- `tests/test_skill.py`

`skill.yaml` must include:

- `id`
- `name`
- `version`
- `entrypoint`
- `selectors`
- `repair_policy`
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

Tests should cover Skill loading and at least one execution path with fake pages or local fixtures.

