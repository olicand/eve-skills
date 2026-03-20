# Player Command Requirements

## Capture Scope

- Capture file: `output/eve_frontier_utopia/captures/proxy_loopback_20260320T164953.pcapng`
- Interface/filter used when recording: `lo0`, `tcp port 7890`
- This capture shows local proxy traffic on port `7890`.
- This capture does **not** directly cover `localhost:3275`, so it cannot prove whether `GET /status`, `POST /focus`, `POST /journey`, or `POST /connect` were hit during the browser flow.

## Network Findings

- `world-api-utopia.uat.pub.evefrontier.com` appeared through the proxy at:
  - `2026-03-20T17:39:24+0800`
  - `2026-03-20T17:39:25+0800`
  - `2026-03-20T17:50:12+0800`
  - `2026-03-20T17:50:13+0800`
  - `2026-03-20T17:50:14+0800`
  - `2026-03-20T17:50:39+0800`
  - `2026-03-20T17:50:40+0800`
  - `2026-03-20T17:50:41+0800`
- `test.auth.evefrontier.com` appeared through the proxy at:
  - `2026-03-20T17:01:09+0800`
  - `2026-03-20T17:50:01+0800`
  - `2026-03-20T17:50:11+0800`
  - `2026-03-20T17:50:38+0800`
  - `2026-03-20T17:50:39+0800`
- Browser dApp + wallet flow evidence:
  - `uat.dapps.evefrontier.com` at `2026-03-20T17:39:26+0800`, `2026-03-20T17:44:34+0800`, `2026-03-20T17:47:56+0800`
  - `initialize.slush.app` at `2026-03-20T17:39:33+0800`, `2026-03-20T17:44:30+0800`, `2026-03-20T17:44:40+0800`, `2026-03-20T17:44:48+0800`, `2026-03-20T17:45:43+0800`
  - `api.enoki.mystenlabs.com` at `2026-03-20T17:39:35+0800`, `2026-03-20T17:44:45+0800`, `2026-03-20T17:45:38+0800`
  - `wallet-rpc.mainnet.sui.io` at `2026-03-20T17:45:39+0800`, `2026-03-20T17:48:03+0800`
- No `signup.eveonline.com` traffic was observed in this capture.
- No `localhost:3275` traffic was observed in this capture.
- Because the proxy trace is CONNECT-tunnel level, it proves host-level access but not the inner HTTP path. It cannot confirm `/v2/characters/me/jumps` from this file alone.

## Command Requirements

### `/system find <name>`

- Uses the public World API plus the local `system_search_index.json`.
- Does not require launcher login.
- Does not require wallet connection.
- Does not require the game client to be running.

### `/ship info <id>`

- Uses the public World API.
- Does not require launcher login.
- Does not require wallet connection.
- Does not require the game client to be running.

### `/jump-history`

- Depends on `GET /v2/characters/me/jumps`.
- The current locally-derived Frontier session tokens are **not** accepted by that endpoint.
- Current observed state:
  - launcher running: yes
  - Utopia client running: yes
  - zk signer running: yes
  - World API probe result for available local tokens: `401 invalid token in authorization header`
- Practical requirement:
  - a World API-specific bearer accepted by `/v2/characters/me/jumps`
- Non-requirement:
  - opening the external browser dApp and linking Slush alone does not satisfy this.

### `/move <from> <to>`

- Public read side is already solved:
  - source system resolution
  - destination system resolution
- The write side is gated by the jump transaction contract:
  - `eve.assembly.gate.api.PrepareJumpTransactionRequest`
  - required fields:
    - `source_gate` (`eve.assembly.gate.Identifier`)
    - `destination_gate` (`eve.assembly.gate.Identifier`)
    - `character` (`eve.character.Identifier`)
- The transaction preparation response returns:
  - `prepared_transaction`
  - `prepared_transaction_attributes`
- That means `/move` is not a simple HTTP read. It needs:
  - a live character identifier
  - a live source gate identifier
  - a live destination gate identifier
  - a valid route/gate link in the current world state
  - a signing/submission context for the prepared transaction
- Current observed runtime state:
  - launcher running: yes
  - Utopia client running: yes
  - zk signer running: yes
- Current blockers:
  - missing live gate identifiers
  - missing character identifier
  - no captured launcher/world-auth exchange tying the browser flow back to game context

## What The Browser Slush Connection Means

- It proves the external browser dApp can reach the Utopia site and talk to the Slush/Sui wallet stack.
- It does **not** prove that the launcher local bridge was used.
- It does **not** prove that a World API bearer was issued for `/jump-history`.
- It does **not** provide the character and gate identifiers needed for `/move`.

## Implication For Skill Design

- Keep `/system find` and `/ship info` as public HTTP skills.
- Treat `/jump-history` as a protected read skill that must wait for a real World API bearer source.
- Treat `/move` as an in-game transactional skill, not a plain public HTTP lookup.
- The next useful capture should include `localhost:3275` and the actual in-game gate/jump flow, not only the browser wallet connection.
