# User Skill Delivery

The product goal is to expose EVE Frontier abilities as user-facing skills, not to expose raw transport or token plumbing.

## Skills Ready For Players Now

- `/system find <name>`: public lookup skill.
- `/ship info <id>`: public lookup skill.

## Skills Ready Only For Local Operator Agents

- `/launcher status`
- `/launcher focus`
- `/launcher journey <journeyId>`
- These are host-local bridge calls and should stay internal.

## Skills Not Ready To Expose Yet

- `/jump-history`: blocked on a World API bearer source that the endpoint actually accepts.
- `/move <from> <to>`: blocked on live gate and character identifiers plus transaction execution readiness.
- `/launcher connect <singleUseToken>`: depends on an official one-time token source and should stay operator-only.

## Product Guidance

- Build the player experience around intent-level commands.
- Keep raw auth exchange, localhost bridge calls, and token-sensitive flows behind internal tooling.
- Only expose action skills after runtime guards and entity-resolution checks are proven.
