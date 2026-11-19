# Maintaining the profile images

`scripts/build.py` draws the SVGs used by the profile README. Text uses the
vendored fonts in `src/fonts/`; icons and face artwork are also vendored in
`src/`. Install the generator's existing dependencies first:

```sh
python -m pip install fonttools brotli
```

## Draw from saved data

Run the generator from the repository root with `GITHUB_TOKEN` unset:

```sh
python scripts/build.py
```

This reads `assets/github.json` and writes 22 SVGs into `assets/`. It makes no
GitHub API request without a token. The saved data's `updated` value appears on
the activity image, so an offline redraw does not imply fresh GitHub data.

If a token is already set, clear it for this command (`Remove-Item
Env:GITHUB_TOKEN -ErrorAction SilentlyContinue` in PowerShell, or
`unset GITHUB_TOKEN` in a POSIX shell). Never put a token in a file or commit.

## Refresh live data

With `GITHUB_TOKEN` set, the generator first requests contributions, public
repositories, stars, and languages from GitHub and updates `assets/github.json`.
The optional workflow secret `PROFILE_TOKEN` can include private contributions;
the built-in workflow token sees public activity only. Only contribution counts
are requested for that calendar, not private repository names.

`.github/workflows/refresh.yml` runs daily at 00:17 UTC (05:47 India time), on
manual dispatch, and after relevant pushes to `main`. Those events commit changed
assets. Pull requests use GitHub's default event checkout, draw from saved data,
and do not commit or push.

## Local checks

```sh
python scripts/check_refresh.py
python scripts/check_saved_profile.py
```

The first checks PR checkout and the four events' write behavior. The second
runs the generator in a temporary copy with no token, parses the SVG output,
and compares it with the committed images. It leaves `assets/` untouched.
