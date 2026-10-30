# Parka MW Propagation Navigator

**Ashraf Chaabane · KF5EYY** — Parka Arctic MW DXpedition, **17–22 November 2026**.

A **complete, brand-new GitHub repository**, not an update patch. It has exactly **two website pages** in a compact, light design:

1. **Live propagation** — archived real NOAA planetary Kp, solar-wind speed, IMF Bz, ≥10 MeV proton flux, directional space-weather assessments, charts and CSV export.
2. **Propagation field guide** — step-by-step interpretation, antenna strategy, darkness and auroral considerations, benchmarks, storms, recovery, case examples, and the operating routine.

The six installed Parka Beverage bearings used in the guide are **52°, 351°, 330°, 308°, 296°, 253°**. The directional assessments are *heuristic risk indicators*, **not observed signal strength or guaranteed reception**. Actual polar/local K, auroral-path intersection and all-path darkness are not measured.

## Set up from scratch (GitHub Desktop, recommended)

1. Go to <https://github.com/new>. Create a **public** repository named `parka-mw-propagation` (or another name). Select **Add a README file**, then **Create repository**.
2. Install <https://desktop.github.com/> and sign in. In GitHub Desktop choose **File > Clone repository**, select the new repository and click **Clone**.
3. Extract the provided ZIP. **Copy everything inside the ZIP, including the hidden `.github` directory**, into the local repository folder. Replace the default `README.md` when asked. Do **not** put all files inside a new parent folder.
4. Verify the exact path `<repository>/.github/workflows/collect.yml` exists. If Windows hides dot-prefixed folders, enable **View > Show > Hidden items** in File Explorer.
5. In GitHub Desktop, enter the commit summary `Install Parka MW Propagation Navigator`, click **Commit to main**, then **Push origin**.
6. On your repository's GitHub website, choose **Settings > Pages > Build and deployment > Source > GitHub Actions**. Do **not** install a suggested Pages workflow template.
7. Under **Settings > Actions > General**, ensure Actions are allowed. If data commits fail with permission error **403**, check **Workflow permissions > Read and write permissions** and any repository/organization branch rules. Save changes.
8. Click **Actions > Collect and publish Parka propagation > Run workflow > Run workflow** (branch `main`). A successful run collects NOAA data, saves it into `data/` and publishes the site.
9. Go to **Settings > Pages** to get the published address. Normally it is `https://YOUR-USERNAME.github.io/parka-mw-propagation/`. Confirm latest observation shows a real UTC time rather than an empty value.
10. From then on the workflow is scheduled **twice an hour**, near **:07 and :37 UTC**, while GitHub Actions is enabled. GitHub scheduled runs are best-effort and may be delayed or skipped. The webpage re-fetches archived data every five minutes while open.

## Repository layout

```text
parka-mw-propagation/
  index.html                    # two-page website shell
  assets/
    app.js                      # NOAA charts, directional ratings, field guide
    styles.css                  # compact light styling
  data/
    latest.json                 # initially {}, populated at first successful run
    history.json                # initially [], grows from real samples
    history.csv                 # initially header only, grows from real samples
  collector.py                  # standard-library NOAA fetch and archive
  .github/workflows/collect.yml # scheduled collector + Pages deployment
  .nojekyll
  README.md
```

## What happens with old data?

This new archive **starts empty**, and the first successful workflow run creates the first observations. If the old GitHub repository and its history were deleted and no backup exists, earlier collection history **cannot be reconstructed from the new package**. You can manually restore a backed-up `data/history.csv` and `data/history.json` later, if available.

## Troubleshooting

- **Workflow missing under Actions:** Make sure `.github/workflows/collect.yml` is at the root of `main`, not inside a nested extracted folder.
- **Workflow run fails fetching NOAA:** Open its log (Collect NOAA observations). NOAA services or GitHub network may temporarily be unavailable; rerun later. No fictitious samples are generated.
- **Workflow fails at git push:** Check Actions workflow write permissions and branch protection.
- **Workflow fails at Deploy Pages:** Check Pages source is GitHub Actions; inspect repository Settings > Pages and environment restrictions.
- **Dashboard opens but shows no metrics:** Check whether `data/latest.json` and `data/history.json` were updated after the successful first workflow run. An empty starting archive is expected before collection.
- **Future runs missing:** GitHub cron schedules are not guarantees. Check the Actions tab; if disabled, enable the workflow.
- **Website still old:** Use Ctrl+F5 to bypass browser cache after a successful deployment.
- **After November 22:** To stop automated runs, use **Actions > Collect and publish Parka propagation > ... > Disable workflow**. Data already recorded stays in the repository.

**Source feeds:** <https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json>, <https://services.swpc.noaa.gov/products/summary/solar-wind-speed.json>, <https://services.swpc.noaa.gov/products/summary/solar-wind-mag-field.json>, and <https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json>.

**Data limitations:** NOAA's March 2026 JSON format change is supported. Kp is planetary Kp, not Parka-specific Polar K. Kp is a three-hour index; fetching it twice per hour does not make its resolution 30 minutes. Site output is public when the repository is public.
