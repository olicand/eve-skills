# Move And Auth Flow

## Current Findings

- A running Utopia client session can be detected locally from the native `SharedCache/utopia/EVE.app` process.
- The local refresh token can be exchanged at `test.auth.evefrontier.com/oauth2/token` into OAuth `access_token` and `id_token`.
- None of the locally-derived JWTs currently pass `World API /v2/characters/me/jumps`; all return `401` with `invalid token in authorization header`.
- The jump contract is visible in `eve.assembly.gate.api.PrepareJumpTransactionRequest` and requires `source_gate`, `destination_gate`, and `character`.
- Static `mapObjects.db` data gives gate presence hints by solar system, but it does not provide the live gate identifiers required to prepare a jump transaction.

## Capture Strategy

### 1. Electron TLS key logging

Use this first when the goal is to decrypt launcher and webview HTTPS traffic in Wireshark.

```bash
"eve-frontier-utopia-analysis/scripts/launch_frontier_with_sslkeylog.sh"
```

Then point Wireshark TLS key log file to:

```text
/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/captures/electron_tls_keys.log
```

This is the strongest option for EVE Vault, SSO, and other Chromium/Electron requests. It will not automatically decrypt native non-Chromium TLS from the `utopia` client process.

### 2. Electron remote debugging

Use this when you need request headers, response bodies, and storage state from the launcher/webview without packet decryption.

Recommended launch pattern:

```bash
env SSLKEYLOGFILE="/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/captures/electron_tls_keys.log" \
  "/Applications/EVE Frontier.app/Contents/MacOS/EVE Frontier" \
  --frontier-test-servers=Utopia \
  --remote-debugging-port=9222
```

This is a high-value fallback if Wireshark capture is noisy or if the auth exchange is visible in the renderer DevTools Network panel.

### 3. Loopback proxy capture

The native `utopia` client is currently connected to local `127.0.0.1:7890`, which is ClashX. Use loopback capture to inspect proxy handshakes and destination hosts.

```bash
"eve-frontier-utopia-analysis/scripts/capture_proxy_loopback.sh"
```

This is useful for confirming that traffic traverses the local proxy and for recovering target hosts. It will not, by itself, reveal bearer headers inside tunneled HTTPS.

## Blocking Items For `/move`

- Need a valid write-side auth or wallet bridge for the official logged-in flow.
- Need live `source_gate` and `destination_gate` identifiers.
- Need the active `character` identifier used by the jump transaction.
- Need a reproducible way to observe or reconstruct the launcher or browser exchange that turns the logged-in state into a World API-compatible bearer or equivalent transaction context.
