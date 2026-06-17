# Architecture

The framework is split into five small parts.

## Python Runtime

`rpa_runtime/` executes stable automation code. `executor.py` owns run lifecycle, `step_runner.py` owns one step at a time, `selector_resolver.py` resolves primary and fallback selectors, `observer.py` captures failures, and `logger.py` writes JSONL logs.

## Skill Registry

`skill_registry/` loads YAML Skill definitions from `example_skills/`. `version_manager.py` stores immutable Skill versions and restores previous versions.

## Repair Agent

`repair_agent/` creates `repair_request.json`, validates `patch.json`, and runs candidate repairs in a sandbox. It must not call an LLM in normal execution.

## Sandbox

`SandboxRunner` copies the project to a temporary directory, applies a selector-only patch there, runs tests, and returns the patched Skill path. It must not modify the live project.

## Version Manager

`VersionManager` is the only component that should apply a tested patch to the live Skill. It records metadata and supports rollback.

