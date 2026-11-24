"""Topic modelling (TF-IDF + NMF) and sentiment (VADER) -> dashboard/data.json"""
import json, re, collections, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.decomposition import NMF
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from common import DATA, ROOT, REL

K = 12
EXTRA_STOP = set("""conspiracy conspiracies conspiratorial theory theories theorist theorists theorists believe believers people like just don think know really make time good use way want thing things said say going actually
point need right better lot sure maybe yes does did doesn didn isn wasn aren ve ll com www http https https href""".split())

stories = json.loads((DATA / "stories.json").read_text())
comments = json.loads((DATA / "comments.json").read_text())
by_story = collections.defaultdict(list)
for c in comments: by_story[c["story_id"]].append(c)

# keep stories on-topic: keyword hit in title/text, or conspiracy talk inside their comments
def relevant(s):
    if REL.search(s["title"] + " " + s["text"]): return True
    cs = by_story.get(s["id"], [])
    return sum(bool(REL.search(c["text"])) for c in cs) >= 3
stories = [s for s in stories if relevant(s)]
ids = {s["id"] for s in stories}
vs = SentimentIntensityAnalyzer()

for s in stories:
    s["year"] = int(s["created_at"][:4])
    s["title_sentiment"] = vs.polarity_scores(s["title"])["compound"]
    cs = by_story.get(s["id"], [])
    for c in cs: c["sentiment"] = vs.polarity_scores(c["text"])["compound"]
    s["n_scored"] = len(cs)
    s["sentiment"] = float(np.mean([c["sentiment"] for c in cs])) if cs else None  # comment sentiment only; no fallback to title
    s["doc"] = " ".join([s["title"]] * 3 + [s["text"]] + [c["text"] for c in cs])

stop = list(ENGLISH_STOP_WORDS | EXTRA_STOP)
vec = TfidfVectorizer(stop_words=stop, max_df=0.5, min_df=5, max_features=6000, ngram_range=(1, 2),
                      token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]{2,}\b")
X = vec.fit_transform([s["doc"] for s in stories])
nmf = NMF(n_components=K, random_state=0, init="nndsvda", max_iter=500)
W = nmf.fit_transform(X); terms = np.array(vec.get_feature_names_out())
for s, w in zip(stories, W):
    s["topic"] = int(w.argmax()); s["topic_weight"] = float(w.max() / (w.sum() or 1))

# traction groups: quartiles of points
pts = np.array([s["points"] for s in stories]); hi, lo = np.percentile(pts, 75), np.percentile(pts, 25)
for s in stories: s["traction"] = "high" if s["points"] >= hi else "low" if s["points"] <= lo else "mid"

topics = []
for k in range(K):
    ss = [s for s in stories if s["topic"] == k]
    top = terms[nmf.components_[k].argsort()[::-1][:8]].tolist()
    topics.append({"id": k, "terms": top, "label": ", ".join(top[:3]), "n": len(ss),
                   "mean_points": float(np.mean([s["points"] for s in ss])) if ss else 0,
                   "mean_comments": float(np.mean([s["num_comments"] for s in ss])) if ss else 0,
                   "mean_sentiment": float(np.mean([s["sentiment"] for s in ss if s["sentiment"] is not None] or [0])),
                   "high_share": float(np.mean([s["traction"] == "high" for s in ss])) if ss else 0,
                   "low_share": float(np.mean([s["traction"] == "low" for s in ss])) if ss else 0})

# example comments per topic (pseudonymous authors only)
examples = collections.defaultdict(list)
tmap = {s["id"]: s["topic"] for s in stories}
for c in comments:
    if c["story_id"] in tmap and "sentiment" in c and 120 < len(c["text"]) < 600 and "http" not in c["text"]:
        examples[tmap[c["story_id"]]].append(c)
ex_out = {}
for k, cs in examples.items():
    cs.sort(key=lambda c: c["sentiment"])
    pick = cs[:2] + cs[-2:]
    ex_out[k] = [{"author": c["author"], "sentiment": round(c["sentiment"], 3), "text": c["text"], "story_id": c["story_id"]} for c in pick]

yearly = collections.defaultdict(lambda: {"n": 0, "pts": 0, "sent": []})
for s in stories:
    y = yearly[s["year"]]; y["n"] += 1; y["pts"] += s["points"]
    if s["sentiment"] is not None: y["sent"].append(s["sentiment"])
yearly = [{"year": y, "n": v["n"], "mean_points": v["pts"] / v["n"], "n_scored": len(v["sent"]),
           "mean_sentiment": float(np.mean(v["sent"])) if v["sent"] else None} for y, v in sorted(yearly.items())]

slim = [{k: s[k] for k in ("id", "title", "hn_link", "year", "points", "num_comments", "tech_era", "topic",
         "sentiment", "title_sentiment", "traction", "n_scored", "comments_fetched")} for s in stories]
sc = [c["sentiment"] for c in comments if c["story_id"] in ids and "sentiment" in c]
out = {"meta": {"stories": len(slim), "comments_scored": len(sc), "topics": K,
        "points_q25": float(lo), "points_q75": float(hi),
        "note": "All usernames replaced with salted-HMAC pseudonyms; raw handles never stored."},
       "stories": slim, "topics": topics, "yearly": yearly, "examples": ex_out,
       "comment_sentiment": [round(x, 2) for x in sc]}
(ROOT / "dashboard" / "data.json").write_text(json.dumps(out, separators=(",", ":")))
print(len(slim), "stories;", len(sc), "comments"); [print(t["id"], t["n"], t["terms"][:6]) for t in topics]
