# Self-Healing Code RPA

Self-Healing Code RPA is a code-based RPA Skill Runtime for building, running, testing, repairing, and versioning browser automation skills.

It is designed around a safe self-healing workflow:

1. Generate or create a standardized RPA Skill.
2. Run the Skill through the runtime.
3. Capture screenshots, DOM snapshots, URLs, logs, and failed step metadata when execution fails.
4. Generate a structured `repair_request.json`.
5. Let Codex or a repair agent propose a selector-only `patch.json`.
6. Validate the patch with strict safety rules.
7. Test the patch in an isolated sandbox.
8. Apply the patch only after validation and tests pass.
9. Create a new version snapshot.
10. Support rollback to a previous working version.

The project does not let AI freely rewrite runtime code. AI can propose repairs, but the runtime validates, tests, versions, and applies them safely.

## Status

This project is an experimental MVP.

Current scope: Web RPA Skill runtime with Codex-style Skill generation and selector-only patch repair.

It is not ready for production use without additional security review, scheduling, authentication, deployment hardening, and environment-specific approval controls.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m code_rpa doctor
python -m code_rpa skill list
python -m code_rpa skill run web_report_export
python -m pytest
```

## What This Is Not

- Not a traditional visual RPA designer.
- Not a full AI Agent that continuously controls the browser.
- Not a framework that calls an LLM during normal execution.
- Not a desktop RPA, OCR, scheduling, or real-website integration layer yet.

## Architecture

- Python Runtime: runs Skill steps, logs step results, captures failure snapshots.
- Skill Registry: loads YAML Skills from `example_skills/`.
- Repair Agent: generates `repair_request.json`, validates selector-only `patch.json`, and gates repair apply.
- Sandbox: copies the project, applies a patch in isolation, and runs tests.
- Version Manager: snapshots, creates new versions after passing tests, and rolls back.

## MVP Scope

The MVP is intentionally narrow:

- Web RPA with Playwright.
- `skill.yaml` workflow definitions.
- `selectors.yaml` primary and fallback selectors.
- Generic Web steps: `goto`, `click`, `fill`, `select`, `wait_for`, `extract_text`, `extract_table`, `download_file`, `assert_text`, `assert_url`, and `screenshot`.
- Structured Skill outputs through `RunResult.outputs`.
- Skill quality validation with `python -m code_rpa skill validate <skill_id>`.
- Failure screenshots and DOM snapshots.
- Selector-only repair patches.
- `repair apply` flow with validate, sandbox, version snapshot, and rerun.
- Sandbox-tested version updates.
- Rollback to previous Skill versions.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

If `python` is not on PATH, use the installed Python executable directly.

## Run Demo

```powershell
python -m code_rpa skill run web_report_export
```

The demo uses `tests/fixtures/report_demo.html`, logs in, opens the report page, selects a date range, exports the report, and verifies the success message.

You can also run the Skill entrypoint directly:

```powershell
python example_skills\web_report_export\main.py
```

Additional example Skills:

- `login_and_export_report`: generic step version of the login/export workflow.
- `scrape_table_to_csv`: extracts a local HTML table, saves CSV output, and returns `table_rows` plus `csv_path`.
- `form_submit_workflow`: fills a local form fixture, submits it, and verifies success text.
- `customer_search_export`: searches customer records, exports the result table to CSV, and returns `csv_path` plus `table_rows`.

## Run Tests

```powershell
python -m pytest
```

Run only unit tests:

```powershell
python -m pytest -m "not integration"
```

Run the real Chromium integration test:

```powershell
python -m pytest -m integration
```

## CLI Usage

```powershell
python -m code_rpa skill list
python -m code_rpa skill run web_report_export
python -m code_rpa skill test web_report_export
python -m code_rpa skill create my_new_skill
python -m code_rpa skill validate my_new_skill
python -m code_rpa repair validate path\to\repair_request.json path\to\patch.json
python -m code_rpa repair sandbox path\to\repair_request.json path\to\patch.json
python -m code_rpa repair apply path\to\repair_request.json path\to\patch.json
python -m code_rpa version list web_report_export
python -m code_rpa version rollback web_report_export <version_id>
python -m code_rpa doctor
python -m code_rpa demo repair
python -m code_rpa demo codex-patch
```

`doctor` prints structured checks for Python, Playwright, pytest, project directories, and Skill registry loading.

`demo repair` runs a local selector repair demonstration in a temporary project copy: it forces a selector failure, generates a repair request, applies a mock selector patch in the sandbox, creates a new version, and reruns the Skill.

`demo codex-patch` simulates Codex-generated selector repair without calling an LLM API.

## Repair Pipeline

The repair pipeline is local, selector-only, and test-gated:

1. Run a Skill through the Python runtime.
2. Capture screenshot, DOM, URL, error logs, and attempted selectors on failure.
3. Generate `repair_request.json`.
4. Validate a selector-only `patch.json`.
5. Apply the patch only inside `SandboxRunner`.
6. Run the patch test command inside the sandbox.
7. Apply a new version with `VersionManager` only after tests pass.

Core flow:

```text
Skill Run
  ↓
Step Failed
  ↓
Observer captures screenshot / DOM / URL / logs
  ↓
repair_request.json
  ↓
Codex proposes selector-only patch.json
  ↓
patch_validator
  ↓
sandbox_runner
  ↓
pytest passes
  ↓
Apply patch
  ↓
Create version snapshot
  ↓
Rerun Skill
  ↓
Success or rollback
```

## repair_request.json

When a step fails after retry and fallback selectors, the runtime captures failure context and writes `storage/repair_requests/<run_id>/repair_request.json`.

The request includes:

- Skill identity and version.
- Failed step ID and goal.
- Error type and message.
- Current URL.
- Screenshot and DOM snapshot paths.
- Original selector and fallback selectors.
- `allowed_repair_scope` with `scope_type: selector_only`.
- Test command and rollback version.
- Risk level and human approval flag.

The request is for repair planning only. It does not call an LLM.

## patch.json

`patch.json` is the proposed local repair. Current automated repair only allows selector-level patches.

Required fields include:

- `repair_request_id`
- `skill_id`
- `failed_step_id`
- `scope: selector_only`
- `changes`
- `rationale`

Each change must target the failed step's selector in the current Skill's `selectors.yaml`:

```text
example_skills/web_report_export/selectors.yaml
```

See `docs/patch-format.md` for the full format.

## Codex Patch Repair

Codex patch repair is a constrained local workflow:

1. Read `repair_request.json`.
2. Inspect the DOM snapshot and screenshot.
3. Generate only `patch.json`.
4. Run:

```powershell
python -m code_rpa repair validate <repair_request_path> <patch_path>
python -m code_rpa repair sandbox <repair_request_path> <patch_path>
python -m code_rpa repair apply <repair_request_path> <patch_path>
python -m pytest
```

Codex must not directly modify Skill files, runtime code, tests, README, requirements, or AGENTS files during patch generation.

See `docs/codex-generate-patch.md`.

## Sandbox Testing

`SandboxRunner` never modifies the live project. It:

1. Copies the project to a temporary directory.
2. Applies the selector patch in the copy.
3. Runs the patch `test_command`.
4. Returns `success`, `stdout`, `stderr`, `duration`, and `patched_skill_path`.

Only a successful sandbox result may be passed to `VersionManager.create_new_version`.

## Rollback

`VersionManager` stores Skill versions under `storage/versions/<skill_id>/`.

It supports:

- `snapshot`
- `create_new_version`
- `list_versions`
- `get_current_version`
- `rollback_to_version`

Every version stores `metadata.json` with patch ID, base version, test result, changed files, and creation time. Rollback restores the Skill files and updates the current version pointer.

## Create a New Skill

Use the CLI scaffold:

```powershell
python -m code_rpa skill create invoice_export
```

This creates:

```text
example_skills/invoice_export/
  skill.yaml
  selectors.yaml
  repair_policy.yaml
  main.py
  tests/test_skill.py
tests/fixtures/invoice_export.html
```

Then edit:

- `skill.yaml` for workflow steps.
- `selectors.yaml` for primary and fallback selectors.
- `repair_policy.yaml` for retry and sandbox policy.
- `tests/test_skill.py` for Skill-level pytest coverage.

The formal Skill contract is documented in `docs/skill-contract.md`.

## Skill Quality Gate

Before a Skill is considered usable, run:

```powershell
python -m code_rpa skill validate <skill_id>
python -m code_rpa skill test <skill_id>
python -m pytest
```

`skill validate` checks the Skill directory, required YAML files, required `skill.yaml` fields, step `id/type/goal`, selector references, selector `primary` entries, repair scope, pytest coverage, and local HTML fixtures. Missing fallback selectors are warnings, not hard failures.

## Codex Generate Skill

When asking Codex to generate a new Skill, describe the business workflow, local fixture, inputs, outputs, and assertions. Codex should create the Skill files, a local fixture, and pytest coverage, then run the quality gate.

Read the full guide at `docs/codex-generate-skill.md`.

Codex must not modify runtime core code by default, bypass `selector_resolver`, write absolute local paths, skip pytest, call an LLM API, add Web UI, connect real websites, add OCR, or add desktop RPA.

Example target:

```powershell
python -m code_rpa skill validate customer_search_export
python -m code_rpa skill test customer_search_export
python -m code_rpa skill run customer_search_export
```

## Codex Repo Skill

This repository includes a Codex repo skill at:

```text
.agents/skills/self-healing-rpa-engineer/
```

It teaches future Codex runs to follow this framework's rules: no LLM calls during normal execution, selector-only patches, `PatchValidator`, `SandboxRunner`, `VersionManager`, pytest coverage, and human confirmation for high-risk steps.

## Current Limitations

- Web RPA only.
- Selector-level repair only.
- Phase five focuses on Skill quality gates and Codex Skill generation, not new automation surfaces.
- Phase six focuses on Codex-style selector-only patch repair, not LLM API integration.
- No Web UI.
- No real website integration.
- No desktop RPA.
- No OCR RPA.
- No LLM API integration.
- No automatic Python code patching.
- No production scheduler or deployment hardening.

## Safety Boundaries

- Normal execution must not call an LLM.
- Patches must not modify runtime code, repair framework code, registry code, or arbitrary Python files.
- Current automated repair only allows selector-level patches.
- `code_changes` must be `null`.
- High-risk steps must require human confirmation.
- High-risk patches are rejected for automatic application.
- Secrets, passwords, tokens, cookies, and session data must not be written to logs or repair requests.

## License

This project is licensed under the Apache License, Version 2.0.

See [LICENSE](LICENSE) for the full license text.
