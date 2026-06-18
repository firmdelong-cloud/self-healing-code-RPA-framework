# Automation Skill Engine Architecture

This project now separates two automation Skill models.

## Procedure Skill

Procedure Skills are deterministic workflows.

Use them for:

- Web report export
- Form submission
- Table scraping
- CRM or admin back-office workflows

Core contract:

- `type: procedure_skill`
- ordered `steps`
- `selectors.yaml`
- `repair_policy.yaml`
- selector fallback
- repair request
- selector-only patch
- sandbox validation
- version snapshot and rollback

The current implementation lives in `rpa_runtime/` and is named explicitly by
the compatibility package `procedure_runtime/`.

## Event Skill

Event Skills are continuous, stateful automations.

Use them for:

- Chat message handling
- Customer service inboxes
- Email triage
- Desktop notification handling

Core contract:

- `type: event_skill`
- `trigger`
- `observe`
- `decision_policy`
- `reply_policy`
- `rate_limit`
- `safety`
- `memory`

The event model is implemented by `event_runtime/`. Adapters provide sensing and
actions; the runtime decides whether an event should become a draft, require
human confirmation, be sent, or be skipped.

## WeChat Boundary

WeChat is not a main Procedure Skill. It is an experimental Event Skill adapter
under `experimental/adapters/wechat/` with a draft-only Skill declaration under
`experimental/event_skills/wechat_auto_reply/`.

The first Event Skill phase is dry-run and draft-only by default. Auto-send is
not the default behavior for message automations.
