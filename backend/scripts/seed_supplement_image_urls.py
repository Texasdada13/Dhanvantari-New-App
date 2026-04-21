"""
Populate Supplement.image_url with direct Wikimedia Commons thumbnail URLs.

Unlike seed_supplement_images.py, this does NOT download files — it stores
the remote URL directly. That means images survive Render free-tier
ephemeral-disk restarts. Idempotent: skips rows that already have an image.

Run from backend/: python scripts/seed_supplement_image_urls.py
"""
import asyncio
import sys
import os
import urllib.parse
import urllib.request
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine
from app.models.plan import Supplement

WIKI_TITLES: dict[str, str] = {
    "Ashwagandha":             "Withania somnifera",
    "Shatavari":               "Asparagus racemosus",
    "Amalaki":                 "Phyllanthus emblica",
    "Brahmi":                  "Bacopa monnieri",
    "Shankhapushpi":           "Convolvulus pluricaulis",
    "Guduchi":                 "Tinospora cordifolia",
    "Triphala":                "Triphala",
    "Trikatu":                 "Long pepper",
    "Dashamula":               "Aegle marmelos",
    "Haritaki":                "Terminalia chebula",
    "Bibhitaki":               "Terminalia bellirica",
    "Licorice Root (Yashtimadhu)": "Glycyrrhiza glabra",
    "Turmeric (Haridra)":      "Turmeric",
    "Neem (Nimba)":            "Azadirachta indica",
    "Punarnava":               "Boerhavia diffusa",
    "Gokshura (Tribulus)":     "Tribulus terrestris",
    "Manjistha":               "Rubia cordifolia",
    "Vidanga":                 "Embelia ribes",
    "Kutki (Picrorhiza)":      "Picrorhiza kurroa",
    "Bhumyamalaki":            "Phyllanthus niruri",
    "Arjuna":                  "Terminalia arjuna",
    "Garlic (Lasuna)":         "Garlic",
    "Guggulu":                 "Commiphora wightii",
    "Sarpagandha":             "Rauvolfia serpentina",
    "Jatamansi":               "Nardostachys jatamansi",
    "Bala":                    "Sida cordifolia",
    "Chyawanprash":            "Chyawanprash",
    "Shilajit":                "Shilajit",
    "Kanchanar Guggulu":       "Bauhinia variegata",
    "Avipattikar Churna":      "Emblica officinalis",
    "Hingvastak Churna":       "Asafoetida",
    "Sitopaladi Churna":       "Bambusa arundinacea",
    "Talisadi Churna":         "Abies spectabilis",
    "Saraswatarishta":         "Bacopa monnieri",
    "Chandraprabha Vati":      "Shilajit",
    "Mahatriphala Ghrita":     "Ghee",
    "Dashamoolarishta":        "Aegle marmelos",
    "Vasarishta":              "Justicia adhatoda",
    "Kutajarishta":            "Holarrhena pubescens",
    "Bhringraj":               "Eclipta prostrata",
    "Kumari (Aloe Vera)":      "Aloe vera",
    "Karela (Bitter Melon)":   "Momordica charantia",
    "Methi (Fenugreek)":       "Fenugreek",
    "Coriander (Dhanyaka)":    "Coriander",
    "Cumin (Jiraka)":          "Cumin",
    "Fennel (Shatapushpa)":    "Fennel",
    "Ginger (Shunthi)":        "Ginger",
    "Cinnamon (Twak)":         "Cinnamon",
    "Cardamom (Ela)":          "Cardamom",
    "Clove (Lavanga)":         "Clove",
    "Black Pepper (Maricha)":  "Black pepper",
    "Pippali (Long Pepper)":   "Long pepper",
    "Kalonji (Nigella sativa)":"Nigella sativa",
    "Moringa (Shigru)":        "Moringa oleifera",
    "Holy Basil (Tulsi)":      "Ocimum tenuiflorum",
    "Giloy Satva":             "Tinospora cordifolia",
    "Haridrakhandam":          "Turmeric",
    "Vyoshadi Vatkam":         "Long pepper",
    "Neeri Tablets":           "Tribulus terrestris",
}

USER_AGENT = "DhanvantariSeedScript/1.0 (Ayurveda demo; contact@example.com)"


def fetch_wiki_thumb_url(title: str, thumb_size: int = 400) -> str | None:
    params = (
        f"action=query&titles={urllib.parse.quote(title)}"
        f"&prop=pageimages&pithumbsize={thumb_size}&format=json"
    )
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for page in data.get("query", {}).get("pages", {}).values():
            thumb = page.get("thumbnail", {}).get("source")
            if thumb:
                return thumb
    except Exception as e:
        print(f"  [WARN] Wikipedia lookup failed for '{title}': {e}")
    return None


async def main():
    async with AsyncSessionLocal() as db:
        supplements = (await db.execute(select(Supplement).order_by(Supplement.id))).scalars().all()
        print(f"Checking {len(supplements)} supplements...")
        filled = skipped = missing = failed = 0

        for s in supplements:
            if s.image_url:
                skipped += 1
                continue
            title = WIKI_TITLES.get(s.name)
            if not title:
                missing += 1
                continue
            url = fetch_wiki_thumb_url(title)
            if url:
                s.image_url = url
                filled += 1
                print(f"  + {s.name} -> {url}")
            else:
                failed += 1

        await db.commit()
        print(f"\n{filled} URLs set, {skipped} already had one, {missing} unmapped, {failed} lookup-failed.")
    # Intentionally do NOT dispose the shared engine here — it's a module
    # singleton from app.core.database and other boot-time scripts may
    # reuse it in the same interpreter process.


if __name__ == "__main__":
    asyncio.run(main())
