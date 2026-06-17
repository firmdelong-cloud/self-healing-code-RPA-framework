# AGENTS.md

This file is the long-term development contract for Codex and all future agents working on this repository. All code generation, repair, refactoring, test creation, and documentation updates must follow these rules.

## 1. Project Positioning

This project is a Self-Healing Code RPA framework.

The framework executes automation flows as stable Python code, primarily using Playwright for Web RPA. It is designed around this execution model:

1. A user describes a browser automation process in natural language.
2. The system generates or maintains a Python + Playwright RPA Skill.
3. The runtime executes deterministic code during normal operation.
4. Common failures are handled with retries, fallback selectors, and rule-based recovery.
5. Only after deterministic recovery fails, the system generates a narrow LLM Repair Request.
6. The LLM may repair only the failed node or failed selector logic.
7. Candidate repairs must pass sandbox validation before becoming a new Skill version.
8. Previous versions must remain auditable and rollback-capable.

This project is not:

- A traditional visual RPA platform.
- A full AI agent that continuously controls a computer.
- A system that calls an LLM for every step.
- A background Codex process. The background executor is the Python RPA runtime.

Phase one prioritizes Web RPA. Desktop RPA, API RPA, OCR RPA, scheduling, and FastAPI services should be added only through clear extension points.

## 2. Core Principles

- Normal execution must not call an LLM.
- The runtime must execute stable Python code first.
- On failure, the runtime must retry before any repair request is generated.
- After retry, the runtime must try fallback selectors.
- After fallback selectors, the runtime may try rule-based matching or deterministic heuristics.
- Only after retry, fallback selectors, and rule matching all fail may the system generate an LLM Repair Request.
- The LLM may repair only the failed node, failed selector, failed wait condition, or other directly related local logic.
- The LLM must not rewrite the entire workflow.
- The LLM must not modify unrelated steps.
- The LLM must not remove safety checks, logging, snapshots, or human approval gates.
- Every repair must be sandbox-tested before it can be written to a Skill.
- A successful repair must create a new Skill version.
- Old Skill versions must remain available for rollback.
- All runs must produce structured logs.
- Failed runs must produce snapshots.
- High-risk actions must require explicit human confirmation.
- Code should be modular and extension-friendly, but avoid heavy abstractions before they are needed.
- Prefer local, deterministic behavior over remote services in phase one.

## 3. Runtime Architecture Rules

The runtime should keep responsibilities separated.

`rpa_runtime.executor` owns:

- Run lifecycle.
- Run IDs.
- Skill execution order.
- Run-level status.
- Passing confirmed high-risk steps to the step runner.
- Calling observer and repair request generation after failure.

`rpa_runtime.step_runner` owns:

- Executing one step at a time.
- Recording `step_id`, `goal`, `status`, `duration`, and `error`.
- Calling selector resolution for selector-based steps.
- Enforcing human confirmation blocks for high-risk steps.

`rpa_runtime.selector_resolver` owns:

- Resolving primary selectors.
- Resolving fallback selectors.
- Returning candidates in deterministic order.
- Reporting attempted selectors when resolution fails.

`rpa_runtime.retry_policy` owns:

- Retry count.
- Retry delays.
- Deterministic retry behavior.

`rpa_runtime.observer` owns:

- Capturing failure screenshots.
- Capturing DOM.
- Capturing current URL.
- Capturing error logs.
- Capturing failed step metadata.
- Saving all snapshot artifacts under storage.

`repair_agent.repair_request` owns:

- Creating `repair_request.json`.
- Narrowly describing the failed step.
- Including enough context for repair.
- Redacting sensitive values before persistence.
- Never calling an LLM directly in phase one.

`repair_agent.sandbox_runner` owns:

- Running repair candidates in isolation.
- Returning pass/fail results.
- Preventing untested patches from becoming new Skill versions.

`skill_registry.version_manager` owns:

- Saving Skill versions.
- Preserving rollback history.
- Never mutating prior versions in place.

## 4. Skill Standard

Every RPA Skill must be a directory with this minimum structure:

```text
skill_name/
  skill.yaml
  main.py
  selectors.yaml
  repair_policy.yaml
  tests/
```

Optional files:

```text
skill_name/
  README.md
  fixtures/
  data/
```

`skill.yaml` must define:

- `id`
- `name`
- `version`
- `entrypoint`
- `selectors`
- `repair_policy`
- `steps`

Each step should define:

- `id`
- `type`
- `goal`
- `target_description` for UI actions where repair may need intent
- `selector_ref` for selector-based actions
- `requires_human_confirmation` when the step is high risk
- `risk_reason` when human confirmation is required

`selectors.yaml` must define selectors by stable logical names. Each selector entry should support:

- `primary`
- `fallbacks`

Selector names should describe intent, not implementation details. Prefer `export_button` over `button_1`.

`repair_policy.yaml` must define:

- Retry policy.
- Allowed patch scope.
- Sandbox requirements.
- Any limits on repair attempts.

`main.py` should be a thin executable entrypoint. It should load the Skill and call the runtime executor. Business flow logic belongs in `skill.yaml`, selectors belong in `selectors.yaml`, and recovery policy belongs in `repair_policy.yaml`.

Skill tests must live in `tests/` inside the Skill directory. Framework tests must live in the repository-level `tests/` directory.

## 5. Coding Standards

- Use Python 3.11+ compatible code.
- Use clear type hints for public functions, dataclasses, and module boundaries.
- Add docstrings for key modules, public classes, and non-obvious functions.
- Use `pathlib.Path` for all filesystem paths.
- Use structured logs, preferably JSON or JSONL.
- Keep modules small and focused.
- Prefer dataclasses for structured runtime results.
- Prefer explicit exceptions over generic failures.
- Do not use bare `except`.
- Do not catch `Exception` unless the code records the error and has a clear recovery or fallback path.
- Do not silently swallow failures.
- Do not hard-code account names, passwords, tokens, cookies, API keys, or private URLs.
- Do not commit generated runtime artifacts except intentional fixtures.
- Do not introduce heavy dependencies without a clear reason.
- Keep Playwright-specific logic isolated so future Desktop, API, and OCR runtimes can be added.
- Do not make Codex, an LLM, or an external API part of normal step execution.
- Prefer tests before or alongside runtime changes.

## 6. Safety Standards

The framework must block high-risk actions unless explicit human approval has been provided.

High-risk actions include:

- Delete.
- Payment.
- Approval.
- Bulk submit.
- Permission changes.
- Sending external messages.
- Publishing public content.
- Irreversible data changes.
- Any action that may create financial, legal, operational, or compliance impact.

High-risk Skill steps must include:

- `requires_human_confirmation: true`
- `risk_reason`
- A clear `goal`

The executor must not run high-risk steps automatically.

Sensitive information must not be written to logs, snapshots, or repair requests. This includes:

- Passwords.
- Tokens.
- Cookies.
- Session IDs.
- Personal identifiers.
- Payment information.
- Internal secrets.

Before writing `repair_request.json`, the repair request layer must redact sensitive values from:

- URLs.
- DOM fragments.
- Error logs.
- Step inputs.
- Headers.
- Form values.
- Screenshot metadata where applicable.

Automatic repair must never:

- Bypass permission checks.
- Remove human approval requirements.
- Disable logging.
- Disable snapshot capture.
- Increase action scope from one item to many items.
- Turn a read-only step into a write action.
- Change account, tenant, workspace, or environment without explicit instruction.

## 7. Repair Rules

Repair is local, auditable, and versioned.

A valid repair may:

- Adjust the failed selector.
- Add fallback selectors for the failed selector ref.
- Adjust a wait condition for the failed step.
- Add a narrow deterministic guard for the failed step.
- Improve error reporting for the failed step.

A valid repair must not:

- Rewrite the whole Skill.
- Modify unrelated steps.
- Delete tests to make a repair pass.
- Remove safety checks.
- Remove human confirmation.
- Hide errors.
- Disable snapshots or logs.
- Persist directly into the current version without versioning.

Each repair attempt must record:

- Skill ID.
- Previous Skill version.
- Failed run ID.
- Failed step ID.
- Snapshot path.
- Original selector.
- Attempted selectors.
- Target description.
- Proposed patch summary.
- Sandbox result.
- Human approval state when required.
- New Skill version when accepted.

Repair patches must pass `sandbox_runner` before they are accepted. If sandbox tests fail, the patch must be rejected and the original Skill version must remain active.

## 8. Logging and Snapshot Standards

Every run must have a unique run ID.

Every step log must include:

- `run_id`
- `step_id`
- `goal`
- `status`
- `duration`
- `error`
- `selector_used` when applicable
- `attempted_selectors` when applicable

Failure snapshots must include:

- Screenshot.
- DOM.
- Current URL.
- Error log.
- Failed step metadata.
- Original selector.
- Attempted selectors.
- Target description when available.

Logs and snapshots must be stored under `storage/` or another configured local storage root. Runtime artifacts should be ignored by Git unless they are deliberate test fixtures.

## 9. Testing Standards

Use pytest.

Every Skill must have at least one loading test.

Every Skill with executable steps should have at least one execution test using a fake page or controlled test page.

`selector_resolver` must have unit tests covering:

- Primary selector resolution.
- Fallback selector ordering.
- Missing selector refs.
- Empty selector definitions.

Failure handling tests must prove that a failed step can generate:

- Screenshot.
- DOM.
- Current URL.
- Error metadata.
- `repair_request.json`.

Repair tests must prove:

- Candidate patches are sandboxed before acceptance.
- Failed sandbox validation rejects the patch.
- Accepted repairs create a new version.
- Old versions remain rollback-capable.

Unit tests should avoid requiring a real browser unless the test is explicitly marked as an integration test. Use fake Playwright-like pages for core runtime tests.

Integration tests may use real Playwright browsers when validating browser startup, selector behavior, downloads, or real page interactions.

## 10. Versioning and Rollback Standards

Skill versions are immutable once accepted.

Changing a Skill must create a new version when the change affects:

- Workflow steps.
- Selectors.
- Repair policy.
- Safety policy.
- Entry behavior.

Rollback must restore:

- `skill.yaml`
- `main.py`
- `selectors.yaml`
- `repair_policy.yaml`
- Skill tests
- Optional Skill documentation relevant to that version

The version manager must preserve metadata connecting versions to runs and repair requests.

## 11. Development Workflow for Codex

When making changes:

1. Read the relevant Skill and runtime files before editing.
2. Keep edits scoped to the requested behavior.
3. Add or update tests for behavior changes.
4. Run the smallest relevant tests first.
5. Run the full test suite when runtime behavior changes.
6. Do not remove safety, logging, snapshots, or versioning behavior to simplify a task.
7. Do not introduce LLM calls into the normal execution path.
8. Document new extension points briefly and clearly.

When fixing failures:

1. Reproduce or identify the failing path.
2. Check logs and snapshots.
3. Prefer deterministic fixes.
4. Update selectors before changing workflow logic when the failure is selector-related.
5. Keep repair scope local to the failed node.
6. Add regression coverage.

When adding dependencies:

1. Prefer the standard library first.
2. Prefer small, well-maintained packages.
3. Explain why the dependency is needed.
4. Update `requirements.txt`.
5. Avoid dependencies that make the runtime platform-heavy in phase one.

## 12. Non-Negotiable Constraints

- Normal execution must not call an LLM.
- LLM repair must be a fallback, not the execution engine.
- LLM repair must be limited to the failed node.
- High-risk actions must require human approval.
- Sensitive data must be redacted from logs and repair requests.
- Repairs must pass sandbox tests before acceptance.
- Accepted repairs must create new versions.
- Old versions must be rollback-capable.
- Runtime behavior must be testable without a real browser where possible.

