# Architecture

The framework is now an Automation Skill Engine with two Skill models.

## Skill Core

`skill_core/` owns shared schema helpers, Skill type parsing, policy primitives, and local state storage.

## Procedure Runtime

Procedure Skills are fixed workflows. Use them for Web report export, form submission, scraping, CRM/admin workflows, and other deterministic RPA tasks.

`rpa_runtime/` executes stable Procedure Skill code. `procedure_runtime/` is a compatibility namespace that names the existing RPA runtime as the Procedure Skill runtime. `executor.py` owns run lifecycle, `step_runner.py` owns one step at a time, `selector_resolver.py` resolves primary and fallback selectors, `observer.py` captures failures, and `logger.py` writes JSONL logs.

Procedure Skills support selector repair, `repair_request.json`, selector-only `patch.json`, sandbox validation, version snapshots, and rollback.

## Event Runtime

Event Skills are continuous and stateful. Use them for chat, inbox, desktop notification, customer-service message handling, and similar interaction loops.

`event_runtime/` processes one bounded batch of events at a time. It separates event detection, context building, decision policy, action policy, and memory. Event Skills should default to dry-run, draft-only, or human-confirm modes.

WeChat is not a main Procedure Skill. WeChat-related integration belongs under `experimental/adapters/wechat/` and `experimental/event_skills/wechat_auto_reply/`.

## Skill Registry

`skill_registry/` loads YAML Skill definitions from `example_skills/`. `version_manager.py` stores immutable Procedure Skill versions and restores previous versions.

## Repair Agent

`repair_agent/` creates `repair_request.json`, validates `patch.json`, and runs candidate repairs in a sandbox. It must not call an LLM in normal execution.

## Sandbox

`SandboxRunner` copies the project to a temporary directory, applies a selector-only patch there, runs tests, and returns the patched Skill path. It must not modify the live project.

## Version Manager

`VersionManager` is the only component that should apply a tested patch to the live Skill. It records metadata and supports rollback.
