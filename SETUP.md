# Setup on your phone (one step at a time)

Do each step, then tell Claude "done" or send what you see. Never paste secret values in chat; paste them only into GitHub or Make.

## A. Repo and pages
1. GitHub app/website → **+** → New repository → name `ig-autopilot` → **Public** → Create. (Public is needed so Instagram can fetch the media files and Pages is free.)
2. Tell Claude "repo created". Claude uploads the code.
3. Repo → **Settings** → **Pages** → Source: *Deploy from a branch* → Branch `main`, folder `/docs` → Save. Your review page is `https://jasonricardothomas.github.io/ig-autopilot/`.
4. Repo → **Settings** → **Actions** → **General** → Workflow permissions → *Read and write* → Save.

## B. Review-page token
5. GitHub → profile photo → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → Generate. Name `review-page`, 1 year, only repository `ig-autopilot`, permission **Contents: Read and write**. Copy it.
6. Open the review page on your phone, paste the token once, tap Save. Add the page to your home screen.
7. Make a second token named `autopilot-secrets` (same repo, add **Secrets: Read and write**). This is secret `GH_PAT`.

## C. Secrets (Repo → Settings → Secrets and variables → Actions → New repository secret)
| Secret name | What it is | Needed |
|---|---|---|
| ANTHROPIC_API_KEY | console.anthropic.com → API keys | yes (photo checks, copy) |
| PEXELS_API_KEY | pexels.com/api, free | recommended |
| UNSPLASH_ACCESS_KEY | unsplash.com/developers, free | optional |
| PIXABAY_API_KEY | pixabay.com/api/docs, free | optional |
| GOOGLE_SERVICE_ACCOUNT_JSON | Google Cloud service account key (JSON) with Drive read access | for your own photos |
| DRIVE_FOLDER_ID | the ID in your photo folder's link; share the folder with the service account email | for your own photos |
| MAKE_WEBHOOK_URL | from the Make scenario (see docs/MAKE_SCENARIO.md) | yes |
| MAKE_WEBHOOK_SECRET | any random text you choose (optional extra safety) | optional |
| META_ACCESS_TOKEN | long-lived Meta token | yes (location IDs, refresh) |
| META_APP_ID | Meta developer app | yes (refresh) |
| META_APP_SECRET | Meta developer app | yes (refresh) |
| IG_USER_ID | your Instagram professional account ID | yes |
| GH_PAT | the `autopilot-secrets` token from step 7 | yes (token refresh) |
| HF_TOKEN | huggingface.co token | optional |

## D. Instagram and Make
8. Instagram app → Settings → Account type → **Professional**. Link it to a Facebook Page in **Meta Business Suite**.
9. Build the Make scenario using `docs/MAKE_SCENARIO.md`. Connect Instagram for Business there.
10. Your own photos: put real photos in the Drive folder (or in `inbox/photos` in the repo). Short clips go in `inbox/clips`, event videos in `inbox/events`, optional music in `assets/audio`.

## E. First run (Repo → Actions → pick the workflow → Run workflow)
11. **Index photos and find locations**
12. **Test** (should be green)
13. **Draft new posts**
14. Open the review page → review → **Approve**. Approved posts go out at their scheduled time (every 10 minutes the Publish workflow checks).

## Buttons you have
Draft new posts, Redo unapproved posts, Reset everything (type RESET), Test, Index photos, Refresh token.

## $100 boost
Run `python -m autopilot boost` for the plan: after about a week, boost the Reel with the most saves and shares, $10 a day for 10 days, goal Profile visits, audience Mexico City, Madrid and Seville, ages 25 to 45.
