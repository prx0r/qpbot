# pi-xmrecon — Pi modes over the arena

`raw.ts`: no tools, minimal prompt, manual `--model=`. `redteam.ts`:
explicit arena tools only (`arena_probe`, `arena_submit`) via argv-safe
`core.cli` calls. Key via env at runtime, never repo. `npm install` done.
