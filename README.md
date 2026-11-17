# Instagram autopilot for @growing.connections

Drafts 3 posts a day (about 80% Reels, 15% carousels, 5% single pictures), waits for your approval on a phone review page, then publishes through Make.com.

- Nothing posts until you tap **Approve** on `https://JasonRicardoThomas.github.io/<repo>/`.
- Real photos only, from Mexico and Spain, never reused for 90 days.
- Max 5 hashtags, a location on every post, every post ends with a booking call.
- Setup: see `SETUP.md`. Make scenario: `docs/MAKE_SCENARIO.md`.

Commands (`PYTHONPATH=src python -m autopilot ...`): `draft`, `redo`, `reset`, `publish`, `index`, `locations`, `refresh-token`, `calendar`, `boost`, `test`.
