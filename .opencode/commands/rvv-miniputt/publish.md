Run the full RVV Miniputt pipeline and publish the result to GitHub Pages.

Use:

```bash
scripts/rvv-miniputt operator run --resume-from 1 --publish --confirm-public <user-args>
```

`--resume-from 1` is intentional: it prevents the operator from short-circuiting as “nothing to do” when checkpoints are already fresh, so the Pages publish step actually runs. Do not run `/rvv-miniputt publish` in the shell.

Report the published URL, any verification warning, and any pipeline/export failure.
