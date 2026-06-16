## Slash commands — execute directly
When the user types `/rvv-miniputt run`, `/rvv-miniputt status`, `/rvv-miniputt logs`, or any other registered slash command, execute it immediately via the extension handler. Do not investigate, verify, or inspect the command first — the extension handles everything. Just run it.

When planning or changing scheduling logic, always review whether the rules report and related docs need to be updated to match the new behavior.
