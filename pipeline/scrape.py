"""Collect HN stories + comment trees about conspiracy theories via the public Algolia HN API.
Usernames are pseudonymised in-memory; raw handles are never written to disk."""
import json, sys, time, requests
from concurrent.futures import ThreadPoolExecutor
from common import DATA, REL, clean, scrub_mentions, pseudonym, tech_era

API = "https://hn.algolia.com/api/v1"
QUERIES = ["conspiracy theories", "conspiracy theory", "conspiracy", "conspiracist", "chemtrails",
           "moon landing hoax", "5G conspiracy", "QAnon", "misinformation", "flat earth", "deep state",
           "AI conspiracy", "crypto conspiracy", "vaccine conspiracy", "tinfoil", "false flag"]
YEARS = range(2007, 2027)
S = requests.Session(); S.headers["User-Agent"] = "distant-reading-research/0.1"

def get(url, **params):
    for i in range(5):
        try:
            r = S.get(url, params=params, timeout=30)
            if r.status_code == 429: time.sleep(5 * (i + 1)); continue
            r.raise_for_status(); return r.json()
        except requests.RequestException:
            time.sleep(2 * (i + 1))
    return None

def search_stories():
    found = {}
    for q in QUERIES:
        for y in YEARS:   # year slicing gets past the 1000-hit cap per query
            lo = int(time.mktime((y, 1, 1, 0, 0, 0, 0, 0, 0))); hi = int(time.mktime((y + 1, 1, 1, 0, 0, 0, 0, 0, 0)))
            for page in range(3):
                d = get(f"{API}/search", query=q, tags="story", page=page, hitsPerPage=100,
                        numericFilters=f"created_at_i>={lo},created_at_i<{hi}")
                if not d or not d["hits"]: break
                for h in d["hits"]: found[h["objectID"]] = h
                if page >= d["nbPages"] - 1: break
        print(f"{q!r}: {len(found)} stories so far", file=sys.stderr)
    return found

def walk(node, out, story_id, depth=0):
    for c in node.get("children", []):
        if c.get("text"):
            out.append({"id": c["id"], "story_id": story_id, "parent_id": c.get("parent_id"), "depth": depth,
                        "author": pseudonym(c.get("author")), "created_at": c.get("created_at"),
                        "text": scrub_mentions(clean(c["text"]))})
        walk(c, out, story_id, depth + 1)

def fetch_comments(sid):
    d = get(f"{API}/items/{sid}")
    out = []
    if d: walk(d, out, int(sid))
    return out

def main():
    stories = search_stories()
    rows = []
    for h in stories.values():
        title = h.get("title") or ""
        if not REL.search(title + " " + (h.get("story_text") or "")):
            continue  # loose queries ("AI conspiracy") also return off-topic stories; drop them here
        text = scrub_mentions(clean(h.get("story_text")))
        rows.append({"id": int(h["objectID"]), "title": title, "url": h.get("url"), "text": text,
                     "author": pseudonym(h.get("author")), "created_at": h["created_at"],
                     "points": h.get("points") or 0, "num_comments": h.get("num_comments") or 0,
                     "tech_era": tech_era(title + " " + (h.get("url") or "") + " " + text),
                     "hn_link": f"https://news.ycombinator.com/item?id={h['objectID']}"})
    rows.sort(key=lambda r: -r["points"])
    # comments: all high-traction stories + a sample of low-traction ones, so both ends are compared
    discussed = [r for r in rows if r["num_comments"] >= 5]
    top = discussed[:250]
    low = [r for r in discussed if r["points"] <= 5][:150]
    target = {r["id"] for r in top + low}
    for r in rows: r["comments_fetched"] = r["id"] in target
    print(f"{len(rows)} stories; fetching comments for {len(target)}", file=sys.stderr)
    comments = []
    with ThreadPoolExecutor(6) as ex:
        for i, c in enumerate(ex.map(fetch_comments, sorted(target))):
            comments += c
            if i % 25 == 0: print(f"  {i}/{len(target)} threads, {len(comments)} comments", file=sys.stderr)
    DATA.mkdir(exist_ok=True)
    (DATA / "stories.json").write_text(json.dumps(rows))
    (DATA / "comments.json").write_text(json.dumps(comments))
    print("done", len(rows), len(comments))

if __name__ == "__main__":
    main()
