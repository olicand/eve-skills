# Player Commands

These are the current player-facing skill commands bundled in this repo.

- `/system find <name>`: public World API lookup plus local system index.
- `/ship info <id>`: public World API ship detail lookup.
- `/jump-history`: protected World API path, currently dependent on discovering a valid World API bearer.
- `/move <from> <to>`: system resolution plus jump transaction contract summary; still blocked on live gate and character identifiers.
- `/launcher status`: read the local Frontier launcher status from `http://localhost:3275/status`.
- `/launcher focus`: bring the launcher window to the foreground via `http://localhost:3275/focus`.
- `/launcher journey <journeyId>`: submit a journey identifier to `http://localhost:3275/journey`.
- `/launcher connect <singleUseToken>`: forward a one-time signup/connect token to `http://localhost:3275/connect`.
