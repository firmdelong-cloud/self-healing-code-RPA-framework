---
name: self-healing-rpa-engineer
description: Build, modify, test, or repair RPA Skills in this Self-Healing Code RPA repository. Use when creating a new Python + Playwright Skill, updating skill.yaml/selectors.yaml/repair_policy.yaml, handling repair_request.json or patch.json, validating selector-only self-healing patches, running sandbox repair tests, managing versions or rollback, or enforcing this repo's RPA safety rules.
---

# Self-Healing RPA Engineer

Use this skill when working inside this repository on Automation Skill Engine Skills, Procedure Skill selector-level repair flows, or Event Skill architecture.

## Skill Models

- Use `procedure_skill` for fixed, repeatable workflows such as Web report export, form submission, scraping, and admin back-office automation.
- Use `event_skill` for continuous, stateful interaction scenarios such as chat, inbox, desktop notification, and customer-service message handling.
- Do not force message automation into the fixed Procedure Skill model. Message automation must use Event Skill concepts: event detection, context building, decision policy, action policy, safety, and memory.
- WeChat-related work belongs under `experimental/adapters/wechat/` or `experimental/event_skills/` unless the user explicitly asks to maintain the legacy mock/live desktop examples.
- Event Skill defaults must be dry-run, draft-only, or human-confirm. Do not make auto-send the default.

## Core Rules

- Normal Skill execution must not call an LLM.
- Web RPA runs through Python + Playwright and YAML Skill definitions.
- Procedure Skills run through the stable code runtime and selector repair pipeline.
- Event Skills run through bounded event polling and must model decisions before actions.
- On failure, the runtime must retry and try fallback selectors before generating `repair_request.json`.
- Current automated repair is selector-only.
- `patch.json` may use only `selector_update` or `fallback_selector_add`.
- `code_changes` must be `null`.
- Patches must pass `PatchValidator`.
- Patches must pass `SandboxRunner`.
- Only `VersionManager` may apply a tested patch to the live Skill.
- High-risk steps require human confirmation and must not be auto-patched.
- Every Skill must include pytest coverage.
- Do not bypass safety checks, logs, snapshots, sandbox tests, or versioning.
- Do not modify `rpa_runtime/`, `procedure_runtime/`, `event_runtime/`, `repair_agent/`, or `skill_registry/` when the task is only to create a new Skill.
- When repairing a failed Skill, generate `patch.json` first; do not directly edit Skill files.

## Workflow

1. Read `AGENTS.md` before major runtime or repair changes.
2. For architecture context, read `references/architecture.md` and `docs/automation-skill-engine.md`.
3. For creating or updating a Skill, read `references/rpa-skill-spec.md` and use the templates in `assets/`.
4. For natural-language Skill generation, read `docs/codex-generate-skill.md`.
5. For Codex-style patch generation, read `docs/patch-format.md` and `docs/codex-generate-patch.md`.
6. For patch work, read `references/patch-json-spec.md`.
7. For repair flow or rollback work, read `references/repair-pipeline.md`.
8. Run the quality gate after changes.

## Skill Creation

Create Procedure Skills under `example_skills/<skill_id>/` with:

- `skill.yaml`
- `selectors.yaml`
- `repair_policy.yaml`
- `main.py`
- `tests/test_skill.py`

Every generated Skill must also include a local HTML fixture under `tests/fixtures/`.

Prefer `python -m code_rpa skill create <skill_id>` for scaffolding.

`skill.yaml` must include `id`, `name`, `version`, `description`, `inputs`, `outputs`, and `steps`.

`skill.yaml` must declare `type: procedure_skill` unless the task is explicitly to design an Event Skill.

Each step must include `id`, `type`, and `goal`. Selector steps must use `selector_ref` or `selector_refs`.

`selectors.yaml` must define a `primary` selector for each selector ref and should include `fallbacks`.

`repair_policy.yaml` must use `repair_scope.scope_type: selector_only`.

Event Skill declarations should use `event_skill.yaml` and include `trigger`, `observe`, `decision_policy`, `reply_policy`, `rate_limit`, `safety`, and `memory`. Event Skills should live under `experimental/event_skills/` until the runtime is productionized.

## Quality Gate

Run all of these before finishing Skill generation:

```powershell
python -m code_rpa skill validate <skill_id>
python -m code_rpa skill test <skill_id>
python -m pytest
```

Do not mark a generated Skill complete if validation fails, pytest fails, the fixture is missing, or selector refs bypass `selector_resolver`.

## Repair Constraints

Allowed repair targets:

- The failed step's selector ref in `selectors.yaml`.
- Full repository-relative selector file paths such as `example_skills/web_report_export/selectors.yaml`.

Forbidden repair targets:

- `main.py`
- `rpa_runtime/`
- `repair_agent/`
- `skill_registry/`
- unrelated steps
- high-risk steps

## Patch Generation

When the user asks to repair a failed Skill:

1. Read the provided `repair_request.json`.
2. Inspect the referenced DOM snapshot and screenshot when available.
3. Identify only the selector for `failed_step_id`.
4. Generate a selector-only `patch.json` using `docs/patch-format.md`.
5. Do not directly modify `selectors.yaml`, `main.py`, runtime code, tests, README, requirements, or AGENTS files.
6. Run:

```powershell
python -m code_rpa repair validate <repair_request_path> <patch_path>
python -m code_rpa repair sandbox <repair_request_path> <patch_path>
python -m code_rpa repair apply <repair_request_path> <patch_path>
python -m pytest
```

Only report success after validation, sandbox, apply, rerun, and pytest pass.
