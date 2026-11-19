# GitHub profile

This is the personal `harsh4k/harsh4k` profile repository. Its README references
generated SVG images in `assets/`; it is not a web application.

## Generation

- `scripts/build.py` reads artwork/fonts in `src/` and writes profile SVGs.
- Python dependencies are `fonttools` and `brotli`.
- Without `GITHUB_TOKEN`, it reads the committed `assets/github.json` snapshot.
- With a token, it first refreshes that snapshot through GitHub GraphQL.
- Keep credentials outside files and git; offline tests must unset the token.
- The daily GitHub Actions workflow may update assets on non-PR events.
- Pull requests validate a saved-data build and must not commit or push.

## Verification

Install the generator dependencies, then run:

```sh
python scripts/check_refresh.py
python scripts/check_saved_profile.py
node "$HOME/.agents/gates/verify.mjs"
```

The saved-data check generates in a temporary copy and leaves presentation
assets unchanged. Read `docs/profile-images.md` before changing generation.

## Existing limits

`scripts/build.py` is an existing module over 300 lines. Keep unrelated styling
and asset generation out of workflow fixes. A live hosted workflow run is a
separate verification from the local event-contract checks.
