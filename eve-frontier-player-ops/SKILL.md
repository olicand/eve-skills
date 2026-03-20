---
name: eve-frontier-player-ops
description: Use when the user wants to run or integrate player-facing EVE Frontier commands. ALL skills are cloud-based, require login, and interact through remote APIs only.
---

# EVE Frontier Player Ops

ALL skills are **cloud-based** and **require authentication** before use.

## Official References

- Interfacing: https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world
- Sandbox: https://docs.evefrontier.com/troubleshooting/sandbox-access
- EVE Vault: https://docs.evefrontier.com/eve-vault/browser-extension

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│         player_skill_commands.py (Login Required)            │
│         ┌────────────────────────────────┐                   │
│         │  Auth Gate (every command)     │                   │
│         │  EVE Vault wallet / SSO bearer │                   │
│         └────────────────────────────────┘                   │
├──────────────┬──────────────┬──────────┬────────────────────┤
│ World API    │ Sui GraphQL  │ Message  │ Gateway RPC        │
│ (Read)       │ (Read/Write) │ Bridge   │ (ConnectRPC)       │
├──────────────┼──────────────┼──────────┼────────────────────┤
│ /system find │ /gate info   │ /moveme  │ /launcher status   │
│ /ship info   │ /gate list   │ /giveitem│ /launcher focus    │
│ /jump-history│ /assembly *  │          │ /launcher journey  │
│ /killmails   │ /character * │          │ /launcher connect  │
│              │ /events *    │          │                    │
│              │ /move (tx)   │          │                    │
├──────────────┴──────────────┴──────────┴────────────────────┤
│ auth_flow.py (EVE Vault + SSO + Auth Companion)              │
│ game_api_client.py (WorldApi + SuiGraphQL + Bridge + Gateway)│
│ smart_assembly_api.py (Gate/Turret/SSU + Sui Transaction)    │
└──────────────────────────────────────────────────────────────┘
```

## Primary Entry Point

```bash
python3 "/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/player_skill_commands.py" ...
```

## Authentication (Required for ALL commands)

Three auth methods:

1. **EVE Vault wallet**: `--wallet 0x...` or `EVE_FRONTIER_WALLET` env var
   - Required for write operations (Sui transactions)
   - Ref: https://docs.evefrontier.com/eve-vault/browser-extension

2. **SSO bearer token**: `--bearer-token ...` or `EVE_FRONTIER_BEARER` env var

3. **Refresh token**: `EVE_FRONTIER_REFRESH_TOKEN` + `EVE_FRONTIER_CLIENT_ID` env vars

Without authentication, ALL commands return an `authentication_required` error.

## Environment

Set via `--env` flag or `EVE_FRONTIER_ENV` env var.

| Env | World API | GraphQL | Message Bridge |
|-----|-----------|---------|----------------|
| utopia | world-api-utopia.uat.pub.evefrontier.com | graphql.testnet.sui.io | message-bridge-nebula.test.tech.evefrontier.com |
| stillness | world-api-stillness.live.tech.evefrontier.com | graphql.testnet.sui.io | message-bridge-stillness.live.tech.evefrontier.com |

## Commands

### Sandbox Commands (in-game chat + message bridge)

Per [official docs](https://docs.evefrontier.com/troubleshooting/sandbox-access):

- `/moveme` — Displays a list of star systems for instant travel (in-game chat command)
- `/giveitem <item> <quantity>` — Spawns items into ship cargo (in-game chat command)

These are server-side slash commands. The skill relays via message bridge and also returns the exact chat command for in-game entry.

### World API Reads

- `/system find <name>` — Search solar systems
- `/ship info <id>` — Ship details
- `/jump-history` — Character jump history (requires bearer)
- `/killmails` — Recent killmails

### Sui Chain Queries

- `/gate info <address>` — Query Smart Gate on-chain state
- `/gate list` — List all Smart Gates
- `/assembly info <address>` — Query Smart Assembly (World API + GraphQL fallback)
- `/assembly list` — List Smart Assemblies from World API
- `/character info <wallet>` — Query character by wallet address
- `/events jumps` — Recent Smart Gate jump events
- `/events kills` — Recent Smart Turret kill events

### Write Path — Sui Transactions

Per [official docs](https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world):
Write path = Sui TypeScript SDK → build Transaction → sign via EVE Vault → submit

- `/move <from> <to>` — Build a Sui jump transaction plan
  - `--source-gate <addr>` — Source gate on-chain address
  - `--dest-gate <addr>` — Destination gate on-chain address
  - `--character <addr>` — Character on-chain address
  - `--wallet <addr>` — EVE Vault wallet for signing

Returns a complete Sui `moveCall` descriptor with TypeScript code example for EVE Vault signing.

### Gateway RPC (replaces localhost launcher calls)

- `/launcher status` — Get launcher status via remote gateway
- `/launcher focus` — Focus launcher via remote gateway
- `/launcher journey <journeyId>` — Submit journey via remote gateway
- `/launcher connect <token>` — Forward connect token via remote gateway

### Auth

- `/auth resolve` — Resolve a valid World API bearer token remotely

## Quick Usage

ALL commands require `--bearer-token` or `--wallet` (or env vars).

```bash
# Sandbox commands (requires login)
python3 .../player_skill_commands.py /moveme --bearer-token "$TOKEN"
python3 .../player_skill_commands.py /giveitem 84210 2 --bearer-token "$TOKEN"

# Read path (World API + Sui GraphQL)
python3 .../player_skill_commands.py /system find "A 2560" --bearer-token "$TOKEN"
python3 .../player_skill_commands.py /ship info 81609 --wallet "0x..."
python3 .../player_skill_commands.py /gate list --wallet "0x..."
python3 .../player_skill_commands.py /assembly info "0xabc..." --bearer-token "$TOKEN"
python3 .../player_skill_commands.py /character info "0xdef..." --wallet "0x..."
python3 .../player_skill_commands.py /events jumps --wallet "0x..."

# Write path (Sui transaction via EVE Vault)
python3 .../player_skill_commands.py /move "A 2560" "M 974" \
  --source-gate "0x..." --dest-gate "0x..." --character "0x..." --wallet "0x..."

# Gateway RPC
python3 .../player_skill_commands.py /launcher status --bearer-token "$TOKEN"

# Auth
python3 .../player_skill_commands.py /auth resolve --bearer-token "$TOKEN"
```

## Guardrails

- **ALL commands require authentication** — unauthenticated calls return `authentication_required` error.
- All interactions are remote — no osascript, no `ps`, no localhost calls.
- Bearer tokens are always masked in output.
- `/moveme` and `/giveitem` are sandbox chat commands per [official docs](https://docs.evefrontier.com/troubleshooting/sandbox-access).
- `/move` returns a Sui transaction descriptor with TypeScript code for EVE Vault signing.
- Write operations follow the official pattern: borrow OwnerCap -> call -> return OwnerCap.
