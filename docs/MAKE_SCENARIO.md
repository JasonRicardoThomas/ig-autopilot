# Make.com scenario (build once)

1. Make → Create scenario → first module **Webhooks → Custom webhook** → Add → name `autopilot` → Save → **copy the address** (this is secret `MAKE_WEBHOOK_URL`).
2. Run the GitHub workflow **Publish approved posts** once (or send a test) so Make learns the fields. Click **Redetermine data structure** if asked.
3. Add a **Router** after the webhook with 5 routes:
   - **Reel**: filter `media_type` equals `REELS`. Module: Instagram for Business → **Create a Reel** (video URL `video_url`, caption `caption`, cover `cover_url`, share to feed on, location `location_id` if the module shows that field).
   - **1 image**: filter `media_type = IMAGE` and `image_count = 1`. Module: **Create a Photo Post** (`image_url_1`, `caption`, `alt_text`, `location_id`).
   - **4 images**: `image_count = 4`. Module: **Create a Carousel Post** with `image_url_1` to `image_url_4`.
   - **5 images**: same, `image_count = 5`, five URLs.
   - **6 images**: same, `image_count = 6`, six URLs.
   (Carousels of 2 or 3 images are not planned. The planner uses 1, 4, 5 or 6 slides.)
4. Optional safety: add a filter on the webhook route `x-autopilot-secret` equals your `MAKE_WEBHOOK_SECRET`.
5. Turn the scenario **On**, scheduling **Immediately**.
6. Test a Reel once and check whether the location tag appears. If it does not, the place name is still in the caption. That is an Instagram API limit, not a bug.

Make free plan: about 1,000 operations a month. Each post uses about 3 operations (webhook, router, Instagram), so 3 posts a day (about 90 a month) fits.
