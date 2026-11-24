"""Shared helpers: pseudonymisation, text cleaning, tech-era tagging."""
import hashlib, hmac, html, os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SALT_FILE = ROOT / ".pseudonym_salt"   # git-ignored: keeps pseudonyms non-reversible

ADJ = ["amber","brisk","calm","dusky","eager","fuzzy","gentle","hazy","ivory","jolly","keen","lunar",
       "mellow","nimble","opal","plucky","quiet","rustic","silver","tidy","umber","vivid","witty","zesty"]
NOUN = ["otter","falcon","heron","lynx","magpie","newt","osprey","panda","quokka","raven","stoat","tapir",
        "urchin","vole","walrus","yak","badger","civet","dingo","egret","finch","gecko","ibis","jackal"]

def _salt() -> bytes:
    if not SALT_FILE.exists():
        SALT_FILE.write_bytes(os.urandom(32))
    return SALT_FILE.read_bytes()

def pseudonym(username) -> str:
    """Stable, non-reversible handle. The raw username is never written to disk."""
    if not username:
        return "anon-deleted"
    d = hmac.new(_salt(), username.lower().encode(), hashlib.sha256).digest()
    n = int.from_bytes(d[:4], "big")
    return f"{ADJ[n % 24]}-{NOUN[(n // 24) % 24]}-{(n // 576) % 1000:03d}"

_TAG = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://\S+")
def clean(text) -> str:
    if not text:
        return ""
    t = html.unescape(re.sub(r"<p>|<br\s*/?>", "\n", text))
    t = html.unescape(_TAG.sub("", t))
    return re.sub(r"\s+", " ", t).strip()

def scrub_mentions(text: str) -> str:
    """Remove @handles / 'u/handle' style references so usernames can't leak via body text."""
    return re.sub(r"(?<!\w)(@|u/)[A-Za-z0-9_\-]{2,}", "@user", text)

OLD_TECH = ["fax","telephone","landline","radio","television","tv ","mainframe","cobol","unix","nuclear",
            "moon landing","apollo","fluoride","chemtrail","satellite","electric grid","vaccine","microwave",
            "light bulb","planned obsolescence","gps","airplane","aviation","y2k","pager","newspaper"]
NEW_TECH = ["ai ","a.i.","artificial intelligence","chatgpt","llm","gpt","openai","crypto","bitcoin","blockchain",
            "5g","mrna","deepfake","social media","facebook","twitter","tiktok","algorithm","starlink","metaverse",
            "elon","neuralink","smart ","iot","big tech","surveillance","chatbot","covid","machine learning"]

def tech_era(text: str) -> str:
    t = " " + text.lower() + " "
    old = sum(k in t for k in OLD_TECH); new = sum(k in t for k in NEW_TECH)
    if old and new: return "both"
    if new: return "new"
    if old: return "old"
    return "none"

REL = re.compile(r"conspir|chemtrail|qanon|flat earth|moon landing|hoax|deep state|false flag|tinfoil|misinformation|disinformation|cover-?up", re.I)
