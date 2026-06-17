# Repair Pipeline

The self-healing flow is local and auditable.

1. Run a Skill through `RPAExecutor`.
2. On failure, capture screenshot, DOM, URL, error metadata, and attempted selectors.
3. Generate `repair_request.json`.
4. Produce a selector-only `patch.json`.
5. Validate the patch with `PatchValidator`.
6. Test the patch with `SandboxRunner`.
7. If sandbox tests pass, create a new version with `VersionManager`.
8. If needed, roll back with `VersionManager.rollback_to_version`.

The sandbox must not modify the live project. A failed sandbox result must not create a new version.

Recommended validation commands:

```powershell
python -m pytest -m "not integration"
python -m pytest -m integration
python -m pytest
```

