# Codex Generate Skill Guide

This guide describes how to ask Codex to generate a new RPA Skill in this repository.

## How To Describe A Skill

Give Codex a business workflow, not implementation guesses. Include:

- Skill ID, using lowercase letters and underscores.
- Local fixture page name.
- Workflow steps in business order.
- Inputs and example values.
- Expected outputs.
- Required assertions.
- Any high-risk actions that require human approval.

## Input Template

```text
Create a new RPA Skill named <skill_id>.

Business goal:
<what the automation should do>

Local fixture:
tests/fixtures/<fixture_name>.html

Workflow:
1. Open the fixture page.
2. ...

Inputs:
- <input_name>: <example value>

Outputs:
- <output_name>: <meaning>

Assertions:
- <what must be true at the end>

Constraints:
- Do not modify runtime code unless I explicitly ask.
- Use selector_resolver through selector_ref.
- Add pytest coverage.
```

## Required Output

Codex must create or update:

- `example_skills/<skill_id>/skill.yaml`
- `example_skills/<skill_id>/selectors.yaml`
- `example_skills/<skill_id>/repair_policy.yaml`
- `example_skills/<skill_id>/main.py`
- `tests/fixtures/<fixture_name>.html`
- either `example_skills/<skill_id>/tests/test_skill.py` or `tests/test_<skill_id>.py`

`skill.yaml` must include:

- `id`
- `name`
- `version`
- `description`
- `inputs`
- `outputs`
- `steps`

Every step must include `id`, `type`, and `goal`.

Every selector must define `primary`. Fallback selectors are strongly recommended; missing fallbacks should be treated as warnings to fix before broad use.

## Forbidden Actions

Codex must not:

- Modify `rpa_runtime/`, `repair_agent/`, or `skill_registry/` by default.
- Bypass `selector_resolver` with direct hardcoded Playwright selectors inside Skill code.
- Write absolute local paths such as `C:\Users\...` into Skill files.
- Skip pytest.
- Skip fixture creation.
- Add LLM API calls.
- Add Web UI, real website integration, OCR, or desktop RPA.
- Hardcode real credentials, cookies, tokens, or customer data.

## Acceptance Commands

Run these commands before considering the Skill complete:

```powershell
python -m code_rpa skill validate <skill_id>
python -m code_rpa skill test <skill_id>
python -m pytest
```

For generated examples that use a root-level test instead of a Skill-local test, also run:

```powershell
python -m pytest tests/test_<skill_id>.py
```

## Example: customer_search_export

Prompt:

```text
Create a new RPA Skill named customer_search_export.

Business goal:
Open a local customer page, search for customers by keyword, export the results table to CSV, and return csv_path plus table_rows.

Local fixture:
tests/fixtures/customer_demo.html

Workflow:
1. Open the customer fixture.
2. Fill keyword "Acme".
3. Click search.
4. Wait for the result table.
5. Extract the customer table.
6. Save CSV.
7. Confirm the CSV file exists.

Outputs:
- csv_path
- table_rows
```

Expected quality gate:

```powershell
python -m code_rpa skill validate customer_search_export
python -m code_rpa skill test customer_search_export
python -m pytest
```
