# DPP Registry watch

Checks the Commission's DPP pages every 15 minutes and writes an RSS feed
(`feed.xml`) whenever a new file (API specs, OpenAPI ZIP, semantic artifacts,
user guides, battery data points) is uploaded or a page changes.

## Setup (about 5 minutes)
1. Create a new **public** GitHub repository, e.g. `dpp-registry-watch`.
2. Upload these files, keeping the `.github/workflows` folder.
3. Go to the **Actions** tab, enable workflows, open "DPP Registry watch" and click **Run workflow**.
   The first run saves a baseline, so you are only told about things that are new from then on.
4. In NetNewsWire, add this feed:
   `https://raw.githubusercontent.com/sarowar-dppl/dpp-registry-watch/main/feed.xml`

## Notes
- A file that appears on two pages is reported once.
- If GitHub ever stops the schedule (it pauses scheduled workflows after 60 days without repo activity), open the Actions tab and re-enable it. The watcher commits every time something changes, which normally keeps it active.

## Pages watched
Edit `PAGES` in `dpp_watch.py` to add more.
