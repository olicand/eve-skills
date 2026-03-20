# Move And Auth Flow

- The local Frontier client session can expose an SSO token and refresh token.
- Refresh-token exchange currently succeeds, but the resulting OAuth tokens are still rejected by `GET /v2/characters/me/jumps`.
- The launcher also exposes a local HTTP bridge on `http://localhost:3275` with `/status`, `/focus`, `/journey`, and `/connect`.
- `POST /connect` accepts a `singleUseToken` and dispatches `signup/exchange-token` inside the launcher.
- The launcher resolves that one-time token through `https://signup.eveonline.com/api/v2/token/launcher`, which returns an access/refresh/id token trio for launcher auth.
- One-time signup/connect tokens may be consumed when exchanged, so test scripts should not assume the same token can be replayed safely against both the live launcher and a direct probe.
- `/move` can already resolve systems and load `PrepareJumpTransactionRequest`, but it still needs live `source_gate`, `destination_gate`, and `character` identifiers.
- The next capture target is the official browser or launcher flow that converts the logged-in session into the World API-specific bearer or transaction signing context.
