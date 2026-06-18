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

Current scope: Web RPA Skill runtime plus Desktop Message RPA with Codex-style Skill generation and selector-only patch repair.

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
- Not a protocol-reverse-engineering or hook-based automation stack.
- Not a multi-instance control, batch marketing, or friend-growth automation tool.
- Not a hidden runtime that bypasses desktop safety prompts.
- Not an OCR, scheduling, or real-website integration layer beyond the local examples in this repo.

## Architecture

- Python Runtime: runs Skill steps, logs step results, captures failure snapshots.
- Desktop Message Runtime: reads desktop chat state, classifies intent, generates controlled replies, and applies auto-send policy.
- Skill Registry: loads YAML Skills from `example_skills/`.
- Repair Agent: generates `repair_request.json`, validates selector-only `patch.json`, and gates repair apply.
- Sandbox: copies the project, applies a patch in isolation, and runs tests.
- Version Manager: snapshots, creates new versions after passing tests, and rolls back.
- Desktop Message RPA: mock WeChat fixture plus a best-effort Windows UI Automation adapter for the official client.

## MVP Scope

The MVP is intentionally narrow:

- Web RPA with Playwright.
- Desktop Message RPA with a mock WeChat window and controlled auto-send policy.
- `skill.yaml` workflow definitions.
- `selectors.yaml` primary and fallback selectors.
- Generic Web steps: `goto`, `click`, `fill`, `select`, `wait_for`, `extract_text`, `extract_table`, `download_file`, `assert_text`, `assert_url`, and `screenshot`.
- Desktop message steps: `open_window`, `detect_unread`, `click_chat`, `read_chat_text`, `classify_intent`, `generate_reply`, `safety_check`, `auto_send_policy`, `fill_text`, and `send_message`.
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
python -m code_rpa desktop simulate wechat_auto_reply_mock
```

The web demo uses `tests/fixtures/report_demo.html`, logs in, opens the report page, selects a date range, exports the report, and verifies the success message.

The desktop demo uses `tests/fixtures/wechat_mock.html`, detects an unread chat, reads the latest message, classifies the intent, generates a reply, applies the auto-send policy, and sends only when allowed.

You can also run the Skill entrypoints directly:

```powershell
python example_skills\web_report_export\main.py
python example_skills\wechat_auto_reply_mock\main.py
```

Additional example Skills:

- `login_and_export_report`: generic step version of the login/export workflow.
- `scrape_table_to_csv`: extracts a local HTML table, saves CSV output, and returns `table_rows` plus `csv_path`.
- `form_submit_workflow`: fills a local form fixture, submits it, and verifies success text.
- `customer_search_export`: searches customer records, exports the result table to CSV, and returns `csv_path` plus `table_rows`.
- `wechat_auto_reply_mock`: opens a mock WeChat desktop window, detects unread messages, classifies intent, generates a reply, and auto-sends only when policy allows it.
- `wechat_auto_reply_live`: attaches to the visible official WeChat desktop client through Windows UI Automation and runs the same controlled reply flow with auto-send off by default.

## Run Tests

```powershell
python -m pytest
```

Run only unit tests:

```powershell
python -m pytest -m "not integration"
```

Run the real Chromium integration test set:

```powershell
python -m pytest -m integration
```

## CLI Usage

```powershell
python -m code_rpa skill list
python -m code_rpa skill run web_report_export
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

`desktop simulate wechat_auto_reply_mock` runs the mock WeChat chat flow and prints a concise JSON summary.

`desktop test wechat_auto_reply_mock` runs the pytest coverage for the desktop message Skill.

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
  -> Step Failed
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

## Desktop Message RPA

The repository now includes a Desktop Message RPA runtime aimed at safe chat automation.

- `desktop_runtime/` handles window discovery, unread detection, chat reading, input filling, sending, and screenshot capture on failure.
- `message_runtime/` handles message parsing, rule-based intent classification, reply generation, safety checks, auto-send policy decisions, and conversation logging.
- `vision_runtime/` adds screenshot-based region detection plus OCR fallback for Qt-style WeChat windows that expose very little UI Automation structure.
- `example_skills/wechat_auto_reply_mock/` provides the first end-to-end desktop message Skill.

Example:

```powershell
python -m code_rpa desktop simulate wechat_auto_reply_mock
```

Sample output:

```json
{
  "status": "success",
  "contact_name": "客户A",
  "latest_message": "你好，多少钱？",
  "intent": "price_inquiry",
  "reply_text": "您好，具体价格需要看您选择的产品规格，我可以先发您一份报价参考。",
  "auto_send_allowed": true,
  "sent": true,
  "handoff_required": false
}
```

For local development, the repo uses `tests/fixtures/wechat_mock.html`. For live Windows experiments, the desktop runtime also includes a best-effort `desktop_wechat` adapter that targets the visible official WeChat client through UI Automation. It does not use protocol reverse engineering, hook injection, or hidden control paths.

When the official WeChat client exposes too little UI Automation data, the live adapter can fall back to a visual path built on `opencv-python` and `rapidocr-onnxruntime`: it captures only the bound WeChat window, looks for unread badges or the active conversation row, OCRs the chat pane, and pastes replies into the editor through the visible client.

To run the live desktop Skill:

```powershell
python -m code_rpa skill validate wechat_auto_reply_live
python -m code_rpa skill run wechat_auto_reply_live
```

If your WeChat window title differs, set:

```powershell
$env:WECHAT_WINDOW_TITLE_REGEX = "微信|WeChat"
python -m code_rpa skill run wechat_auto_reply_live
```

The live Skill keeps `auto_send: false` by default so you can verify the window binding and draft filling path before enabling unattended sending in a controlled environment.

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

- Web RPA plus controlled Desktop Message RPA.
- Selector-level repair only.
- No Web UI.
- No real website integration.
- No OCR RPA.
- No LLM API integration.
- No automatic Python code patching.
- No production scheduler or deployment hardening.
- The live WeChat desktop adapter is best-effort and environment-specific; repeatable tests still run on the mock fixture.
- Some Weixin desktop builds expose only a minimal Qt accessibility tree, which can block unread detection and message reading without OCR, injection, or protocol-level access.
- The vision fallback depends on the WeChat window being visible, foregrounded, and laid out close to the expected desktop proportions.

## Safety Boundaries

- Normal execution must not call an LLM.
- Patches must not modify runtime code, repair framework code, registry code, or arbitrary Python files.
- Current automated repair only allows selector-level patches.
- `code_changes` must be `null`.
- High-risk steps must require human confirmation.
- High-risk patches are rejected for automatic application.
- Secrets, passwords, tokens, cookies, and session data must not be written to logs or repair requests.
- Desktop message automation must not use protocol reverse engineering, hook injection, stealth execution, or bulk marketing behavior.

## License

This project is licensed under the Apache License, Version 2.0.

See [LICENSE](LICENSE) for the full license text.
