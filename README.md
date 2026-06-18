# AI RPA Skill Platform

AI RPA Skill Platform is a componentized automation Skill platform for creating, running, observing, repairing, testing, versioning, and rolling back AI-generated RPA Skills.

It preserves the original **Self-Healing Code RPA** MVP as a code-based RPA Skill Runtime, but the main direction is now broader: Codex/AI generates a Skill DSL made of reusable components, and the runtime executes those component graphs with structured observation, local repair, sandbox validation, versioning, and rollback.

It is not a small RPA demo and not a loose collection of Python scripts. The platform is organized around these responsibilities:

- Codex/AI: generates or repairs Skill DSL from natural-language requirements.
- Component Core: defines reusable automation components with schemas, risk metadata, and repair scopes.
- Runtime: executes component flows and records every node input, output, duration, status, and error.
- Observer: captures screenshots, DOM snapshots, URLs, logs, and failed component context.
- Repair Engine: creates local repair requests for failed component nodes and validates selector-only patches.
- Sandbox + Version Manager: tests patches in isolation before applying them and supports rollback.
- Web Management Layer: planned surface for projects, Skills, components, runs, repairs, AI prompts, knowledge base, and policies.

It supports two Skill models:

- `procedure_skill`: deterministic workflow automation for Web RPA, exports, forms, scraping, and back-office tasks.
- `event_skill`: event-driven automation for chat, inbox, desktop notification, and other continuous interaction scenarios.

Procedure Skills now support component workflows through `nodes` and `edges`. Legacy `steps` are still supported for compatibility.

Safe repair flow:

1. Generate or create a standardized component-based Skill DSL.
2. Run the Skill graph through the runtime.
3. Capture screenshots, DOM snapshots, URLs, logs, and failed component node metadata when execution fails.
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

Current scope: component-based Procedure Skill runtime, selector-level self-healing, versioned repair pipeline, and an early Event Skill runtime skeleton for dry-run and draft-only interaction automations.

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
python -m code_rpa skill run report_export_and_summary
python -m pytest
```

## What This Is Not

- Not a traditional visual RPA designer.
- Not a full AI Agent that continuously controls the browser.
- Not a framework that calls an LLM during normal execution.
- Not a protocol-reverse-engineering or hook-based automation stack.
- Not a multi-instance control, batch marketing, or friend-growth automation tool.
- Not a hidden runtime that bypasses desktop safety prompts.
- Not a production message bot, OCR platform, scheduler, or real-website integration layer beyond the local examples in this repo.

## Architecture

- Component Core: component protocol, registry, context, and runner.
- Skill Core: shared schema for `procedure_skill` and `event_skill`.
- Procedure Runtime: runs component graphs for fixed business workflows.
- Event Runtime: polls events, builds context, applies decisions, chooses draft/confirm/send/skip actions, and records memory.
- Skill Registry: loads YAML Skill DSL from `example_skills/`.
- Repair Agent: generates component-node-aware `repair_request.json`, validates selector-only `patch.json`, and gates repair apply.
- Sandbox: copies the project, applies a patch in isolation, and runs tests.
- Version Manager: snapshots, creates new versions after passing tests, and rolls back.
- Experimental Adapters: WeChat desktop vision integration is kept outside the core runtime under `experimental/`.

## MVP Scope

- Component-based Procedure Skill Web RPA with Playwright.
- Event Skill runtime skeleton for continuous, stateful automations.
- `skill.yaml` component workflow DSL with `nodes` and `edges`.
- `selectors.yaml` primary and fallback selectors.
- Built-in components: `browser.*`, `file.*`, `excel.*`, `control.*`, `ai.generate_text` mock, `human.approval` mock, and `system.log`.
- Generic Web steps: `goto`, `click`, `fill`, `select`, `wait_for`, `extract_text`, `extract_table`, `download_file`, `assert_text`, `assert_url`, and `screenshot`.
- Desktop mock message steps remain for tests, but real message automation should use the Event Skill model.
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
python -m code_rpa skill run report_export_and_summary
python -m code_rpa desktop simulate wechat_auto_reply_mock
```

The web demo uses `tests/fixtures/report_demo.html`, logs in, opens the report page, selects a date range, exports the report, and verifies the success message.

The complex component demo `report_export_and_summary` exports local report data, writes CSV output, reads it back through the `excel.read` component, generates a deterministic mock AI summary, writes `summary.txt`, and records a structured run log.

The desktop mock demo uses `tests/fixtures/wechat_mock.html`, detects an unread chat, reads the latest message, classifies the intent, generates a deterministic reply, applies the auto-send policy, and sends only when allowed.

Example Skills:

- `web_report_export`: original self-healing report export demo.
- `report_export_and_summary`: component-flow demo for export, file, excel, mock AI summary, and logging.
- `login_and_export_report`: generic step version of the login/export workflow.
- `scrape_table_to_csv`: extracts a local HTML table, saves CSV output, and returns `table_rows` plus `csv_path`.
- `form_submit_workflow`: fills a local form fixture, submits it, and verifies success text.
- `customer_search_export`: searches customer records, exports the result table to CSV, and returns `csv_path` plus `table_rows`.
- `wechat_auto_reply_mock`: local mock for desktop message runtime primitives.
- `wechat_auto_reply_live`: experimental visible-client desktop adapter with `auto_send: false` by default.

## Run Tests

```powershell
python -m pytest
```

Run only unit tests:

```powershell
python -m pytest -m "not integration"
```

Run Chromium integration tests:

```powershell
python -m pytest -m integration
```

## CLI Usage

```powershell
python -m code_rpa skill list
python -m code_rpa skill run web_report_export
python -m code_rpa skill run report_export_and_summary
python -m code_rpa skill run wechat_auto_reply_live
python -m code_rpa skill test web_report_export
python -m code_rpa skill create my_new_skill
python -m code_rpa skill validate my_new_skill
python -m code_rpa repair validate path\to\repair_request.json path\to\patch.json
python -m code_rpa repair sandbox path\to\repair_request.json path\to\patch.json
python -m code_rpa repair apply path\to\repair_request.json path\to\patch.json
python -m code_rpa version list web_report_export
python -m code_rpa version rollback web_report_export <version_id>
python -m code_rpa desktop simulate wechat_auto_reply_mock
python -m code_rpa desktop test wechat_auto_reply_mock
python -m code_rpa doctor
python -m code_rpa demo repair
python -m code_rpa demo codex-patch
```

`doctor` prints structured checks for Python, Playwright, pytest, project directories, and Skill registry loading.

`demo repair` runs a local selector repair demonstration in a temporary project copy: it forces a selector failure, generates a repair request, applies a mock selector patch in the sandbox, creates a new version, and reruns the Skill.

`demo codex-patch` simulates Codex-generated selector repair without calling an LLM API.

## Repair Pipeline

The repair pipeline is local, selector-only, and test-gated:

1. Run a component-based Skill through the Python runtime.
2. Capture screenshot, DOM, URL, error logs, component node inputs/outputs, and attempted selectors on failure.
3. Generate `repair_request.json`.
4. Validate a selector-only `patch.json`.
5. Apply the patch only inside `SandboxRunner`.
6. Run the patch `test_command` inside the sandbox.
7. Apply a new version with `VersionManager` only after tests pass.

Core flow:

```text
Skill Run
  -> Component Node Failed
  -> Observer captures screenshot / DOM / URL / logs
  -> repair_request.json
  -> Codex proposes selector-only patch.json
  -> patch_validator
  -> sandbox_runner
  -> pytest passes
  -> Apply patch
  -> Create version snapshot
  -> Rerun Skill
  -> Success or rollback
```

## repair_request.json

When a component node fails after retry and fallback selectors, the runtime captures failure context and writes `storage/repair_requests/<run_id>/repair_request.json`.

The request includes:

- Skill identity and version.
- Failed component node ID, component ID, inputs, selector ref, and goal.
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

Each change must target the failed step's selector in the current Skill's `selectors.yaml`, for example:

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

## Desktop Message RPA

The repository includes an experimental Desktop Message RPA layer for safe chat automation experiments. It is now treated as an Event Skill direction, not as a normal fixed-step Procedure Skill.

- `desktop_runtime/` handles window discovery, unread detection, chat reading, input filling, sending, and screenshot capture on failure.
- `message_runtime/` handles message parsing, rule-based intent classification, reply generation, safety checks, auto-send policy decisions, and conversation logging.
- `event_runtime/` models continuous event handling with detection, context, decision, action policy, and memory.
- `vision_runtime/` adds screenshot-based region detection plus OCR fallback for desktop windows that expose little UI Automation structure.
- `example_skills/wechat_auto_reply_mock/` remains a local mock used for testing desktop primitives.
- `experimental/event_skills/wechat_auto_reply/event_skill.yaml` shows the intended draft-only Event Skill declaration.

Example:

```powershell
python -m code_rpa desktop simulate wechat_auto_reply_mock
```

Sample output:

```json
{
  "status": "success",
  "contact_name": "Customer A",
  "latest_message": "hello, how much is it?",
  "intent": "price_inquiry",
  "reply_text": "Hello, the exact price depends on the product specification. I can share a quotation reference first.",
  "auto_send_allowed": true,
  "sent": true,
  "handoff_required": false
}
```

For live Windows experiments, `wechat_auto_reply_live` targets only the visible official WeChat client through UI Automation. It does not use protocol reverse engineering, hook injection, or hidden control paths. It keeps `auto_send: false` by default.

## Auto-Send Policy

Desktop message Skills are intentionally constrained.

- High-risk intents such as `refund_dispute`, `legal_issue`, `payment_sensitive`, and `complaint` are blocked from unattended sending.
- Group chats can be blocked by policy.
- Per-contact and global hourly reply limits are enforced through `ConversationLogger`.
- When policy blocks a message, the runtime keeps the generated reply as a draft path for handoff and returns `sent=false` with `handoff_required=true`.

## Unsupported Desktop Behaviors

The Desktop Message RPA runtime does not support:

- WeChat protocol reverse engineering
- hook or code injection into the client
- multi-instance control or mass orchestration
- batch friend adds
- batch marketing or group spam
- stealth execution or wind-control bypass

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

Codex must not modify runtime core code by default, bypass `selector_resolver`, write absolute local paths, skip pytest, call an LLM API, add Web UI, connect real websites, add OCR, or add desktop RPA surfaces that bypass the desktop safety model.

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

- Procedure Skill Web RPA plus controlled desktop mock primitives.
- Event Skill runtime is an early skeleton, not a production message agent.
- Selector-level repair only.
- No Web UI.
- No real website integration.
- No OCR RPA.
- No LLM API integration.
- No automatic Python code patching.
- No production scheduler or deployment hardening.
- The live WeChat desktop adapter is best-effort and environment-specific; repeatable tests still run on the mock fixture.
- The vision fallback depends on the target window being visible, foregrounded, and laid out close to expected desktop proportions.

## Safety Boundaries

- Normal execution must not call an LLM.
- Patches must not modify runtime code, repair framework code, registry code, or arbitrary Python files.
- Current automated repair only allows selector-level patches.
- `code_changes` must be `null`.
- High-risk steps must require human confirmation.
- High-risk patches are rejected for automatic application.
- Secrets, passwords, tokens, cookies, and session data must not be written to logs or repair requests.
- Desktop message automation must not use protocol reverse engineering, hook injection, stealth execution, or bulk marketing behavior.
- Event Skills for messaging should default to dry-run, draft-only, or human-confirm modes.

## License

This project is licensed under the Apache License, Version 2.0.

See [LICENSE](LICENSE) for the full license text.
