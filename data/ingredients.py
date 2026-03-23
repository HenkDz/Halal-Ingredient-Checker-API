"""
Halal Ingredient Database

Sources:
- Islamic Food and Nutrition Council of America (IFANCA)
- JAKIM (Malaysian Department of Islamic Development)
- MUI (Indonesian Ulema Council)
- Halal Monitoring Authority
"""

from typing import Any

INGREDIENTS: dict[str, dict[str, Any]] = {
    # === HARAM INGREDIENTS ===
    "gelatin": {
        "name": "Gelatin",
        "alternatives": ["gelatine", "E441"],
        "verdict": "haram",
        "reason": "Usually derived from pork or non-halal slaughtered animals unless specifically certified halal.",
        "source": "IFANCA, JAKIM",
        "e_number": "E441",
    },
    "alcohol": {
        "name": "Alcohol / Ethanol",
        "alternatives": ["ethanol", "ethyl alcohol", "E1510"],
        "verdict": "haram",
        "reason": "Intoxicating alcohol is strictly prohibited in Islam.",
        "source": "Quran 5:90-91, Major scholars consensus",
        "e_number": "E1510",
    },
    "lard": {
        "name": "Lard",
        "alternatives": ["pork fat", "pig fat", "porcine fat"],
        "verdict": "haram",
        "reason": "Derived from pork. All pork products are haram in Islam.",
        "source": "Quran 2:173, 5:3, 6:145",
        "e_number": None,
    },
    "pork": {
        "name": "Pork",
        "alternatives": ["pig meat", "swine", "porcine"],
        "verdict": "haram",
        "reason": "Pork and all its by-products are strictly prohibited in Islam.",
        "source": "Quran 2:173, 5:3, 6:145",
        "e_number": None,
    },
    "carmine": {
        "name": "Carmine / Cochineal",
        "alternatives": ["cochineal extract", "E120", "crimson lake", "natural red 4"],
        "verdict": "haram",
        "reason": "Derived from crushed cochineal insects. Major scholars consider insects haram except locusts.",
        "source": "JAKIM, MUI",
        "e_number": "E120",
    },
    "cochineal": {
        "name": "Cochineal Extract",
        "alternatives": ["E120", "carminic acid"],
        "verdict": "haram",
        "reason": "Insect-derived coloring agent. Insects are generally haram in Islam.",
        "source": "JAKIM, MUI",
        "e_number": "E120",
    },
    "pepsin": {
        "name": "Pepsin",
        "alternatives": ["pepsin enzyme"],
        "verdict": "haram",
        "reason": "Typically sourced from pig stomach lining. Haram unless from halal-certified source.",
        "source": "IFANCA",
        "e_number": None,
    },
    "rennet": {
        "name": "Rennet (non-halal)",
        "alternatives": ["animal rennet", "chymosin"],
        "verdict": "doubtful",
        "reason": "Animal rennet from non-halal slaughtered animals is haram. Microbial rennet is halal. Must verify source.",
        "source": "IFANCA",
        "e_number": None,
    },
    "l-cysteine": {
        "name": "L-Cysteine",
        "alternatives": ["E920", "cysteine"],
        "verdict": "haram",
        "reason": "Often derived from human hair (non-Muslim sources) or duck feathers. Can be haram depending on source.",
        "source": "IFANCA, Halal Monitoring Authority",
        "e_number": "E920",
    },
    "e120": {
        "name": "E120 - Cochineal / Carmine",
        "alternatives": ["carmine", "cochineal", "carminic acid", "natural red 4"],
        "verdict": "haram",
        "reason": "Insect-derived coloring agent. Insects are generally haram.",
        "source": "JAKIM, MUI",
        "e_number": "E120",
    },
    "e441": {
        "name": "E441 - Gelatin",
        "alternatives": ["gelatin", "gelatine"],
        "verdict": "haram",
        "reason": "Usually derived from pork or non-halal slaughtered animals unless certified halal.",
        "source": "IFANCA, JAKIM",
        "e_number": "E441",
    },
    "e1510": {
        "name": "E1510 - Ethanol",
        "alternatives": ["alcohol", "ethyl alcohol"],
        "verdict": "haram",
        "reason": "Intoxicating alcohol is strictly prohibited in Islam.",
        "source": "Quran 5:90-91",
        "e_number": "E1510",
    },
    "e920": {
        "name": "E920 - L-Cysteine",
        "alternatives": ["l-cysteine", "cysteine"],
        "verdict": "doubtful",
        "reason": "Often derived from human hair or duck feathers. Haram if from non-halal sources, halal if synthetic or microbial.",
        "source": "IFANCA",
        "e_number": "E920",
    },
    "wine": {
        "name": "Wine",
        "alternatives": ["grape wine", "vino"],
        "verdict": "haram",
        "reason": "Alcoholic beverage made from grapes. Intoxicants are haram.",
        "source": "Quran 5:90-91",
        "e_number": None,
    },
    "rum": {
        "name": "Rum",
        "alternatives": ["rum extract", "rum flavoring"],
        "verdict": "haram",
        "reason": "Alcoholic spirit. Intoxicants are haram in any form.",
        "source": "Quran 5:90-91",
        "e_number": None,
    },
    "bacon": {
        "name": "Bacon",
        "alternatives": ["pork bacon", "smoked pork"],
        "verdict": "haram",
        "reason": "Derived from pork belly. All pork products are prohibited.",
        "source": "Quran 2:173, 5:3",
        "e_number": None,
    },
    "ham": {
        "name": "Ham",
        "alternatives": ["pork ham", "smoked ham"],
        "verdict": "haram",
        "reason": "Derived from pork leg. All pork products are prohibited.",
        "source": "Quran 2:173, 5:3",
        "e_number": None,
    },
    "e542": {
        "name": "E542 - Bone Phosphate",
        "alternatives": ["bone phosphate", "edible bone phosphate"],
        "verdict": "doubtful",
        "reason": "Derived from animal bones. Halal only if sourced from halal-slaughtered animals.",
        "source": "IFANCA",
        "e_number": "E542",
    },
    "e471": {
        "name": "E471 - Mono- and Diglycerides",
        "alternatives": ["mono and diglycerides", "glyceryl monostearate"],
        "verdict": "doubtful",
        "reason": "May be derived from plant or animal (including pork) sources. Must verify source.",
        "source": "JAKIM, IFANCA",
        "e_number": "E471",
    },
    "e472": {
        "name": "E472 - Esters of Mono-/Diglycerides",
        "alternatives": ["acetic acid esters", "lactic acid esters of mono-diglycerides"],
        "verdict": "doubtful",
        "reason": "May be derived from plant or animal sources. Source must be verified.",
        "source": "JAKIM, IFANCA",
        "e_number": "E472",
    },
    "e473": {
        "name": "E473 - Sucrose Esters",
        "alternatives": ["sucrose esters of fatty acids"],
        "verdict": "doubtful",
        "reason": "Fatty acid source may be animal-based. Must verify source.",
        "source": "JAKIM",
        "e_number": "E473",
    },
    "e474": {
        "name": "E474 - Sucroglycerides",
        "alternatives": ["sucroglyceride"],
        "verdict": "doubtful",
        "reason": "May contain animal-derived fatty acids. Verify source.",
        "source": "JAKIM",
        "e_number": "E474",
    },
    "e476": {
        "name": "E476 - Polyglycerol Esters",
        "alternatives": ["polyglycerol polyricinoleate", "PGPR"],
        "verdict": "doubtful",
        "reason": "May be derived from animal fat. Castor oil source is halal but not always used.",
        "source": "JAKIM",
        "e_number": "E476",
    },
    "e481": {
        "name": "E481 - Sodium Stearoyl Lactylate",
        "alternatives": ["SSL"],
        "verdict": "doubtful",
        "reason": "Stearic acid may be animal-derived. Must verify source.",
        "source": "IFANCA",
        "e_number": "E481",
    },
    "e482": {
        "name": "E482 - Calcium Stearoyl Lactylate",
        "alternatives": ["CSL"],
        "verdict": "doubtful",
        "reason": "Stearic acid may be animal-derived. Must verify source.",
        "source": "IFANCA",
        "e_number": "E482",
    },
    "e477": {
        "name": "E477 - Propane-1,2-diol Esters",
        "alternatives": ["propylene glycol esters"],
        "verdict": "doubtful",
        "reason": "Fatty acid source may be animal-based. Verify source.",
        "source": "JAKIM",
        "e_number": "E477",
    },

    # === CLEARLY HALAL INGREDIENTS ===
    "water": {
        "name": "Water",
        "alternatives": ["aqua"],
        "verdict": "halal",
        "reason": "Pure water is naturally halal.",
        "source": "General Islamic principle",
        "e_number": None,
    },
    "sugar": {
        "name": "Sugar",
        "alternatives": ["sucrose", "cane sugar", "beet sugar", "E960 (for stevia)"],
        "verdict": "halal",
        "reason": "Pure sugar is naturally halal. Bone char filtering is a concern for some — verify if strict.",
        "source": "General Islamic principle",
        "e_number": None,
    },
    "salt": {
        "name": "Salt",
        "alternatives": ["sodium chloride", "sea salt", "table salt"],
        "verdict": "halal",
        "reason": "Salt is a naturally occurring mineral and is halal.",
        "source": "General Islamic principle",
        "e_number": None,
    },
    "wheat flour": {
        "name": "Wheat Flour",
        "alternatives": ["flour", "all-purpose flour", "wheat"],
        "verdict": "halal",
        "reason": "Plant-based ingredient. Naturally halal.",
        "source": "General Islamic principle",
        "e_number": None,
    },
    "rice": {
        "name": "Rice",
        "alternatives": ["white rice", "brown rice", "basmati rice"],
        "verdict": "halal",
        "reason": "Plant-based grain. Naturally halal.",
        "source": "General Islamic principle",
        "e_number": None,
    },
    "olive oil": {
        "name": "Olive Oil",
        "alternatives": ["extra virgin olive oil", "EVOO"],
        "verdict": "halal",
        "reason": "Plant-based oil. Mentioned in the Quran as a blessed food.",
        "source": "Quran 24:35",
        "e_number": None,
    },
    "sunflower oil": {
        "name": "Sunflower Oil",
        "alternatives": ["sunflower seed oil"],
        "verdict": "halal",
        "reason": "Plant-based oil. Naturally halal.",
        "source": "General Islamic principle",
        "e_number": None,
    },
    "coconut oil": {
        "name": "Coconut Oil",
        "alternatives": ["coconut cream", "coconut milk"],
        "verdict": "halal",
        "reason": "Plant-based. Naturally halal.",
        "source": "General Islamic principle",
        "e_number": None,
    },
    "vanilla extract": {
        "name": "Vanilla Extract",
        "alternatives": ["vanilla"],
        "verdict": "doubtful",
        "reason": "Often contains alcohol as a solvent. Halal vanilla extract or vanilla bean powder is preferred.",
        "source": "IFANCA",
        "e_number": None,
    },
    "turmeric": {
        "name": "Turmeric",
        "alternatives": ["turmeric root", "curcumin", "E100"],
        "verdict": "halal",
        "reason": "Plant-based spice. Naturally halal.",
        "source": "General Islamic principle",
        "e_number": "E100",
    },
    "e300": {
        "name": "E300 - Ascorbic Acid (Vitamin C)",
        "alternatives": ["ascorbic acid", "vitamin c"],
        "verdict": "halal",
        "reason": "Can be derived from plants or synthesized. Generally considered halal.",
        "source": "JAKIM, IFANCA",
        "e_number": "E300",
    },
    "e330": {
        "name": "E330 - Citric Acid",
        "alternatives": ["citric acid"],
        "verdict": "halal",
        "reason": "Usually derived from plant sources (citrus fruits) or microbial fermentation. Halal.",
        "source": "JAKIM",
        "e_number": "E330",
    },
    "e160a": {
        "name": "E160a - Beta-Carotene",
        "alternatives": ["beta carotene", "provitamin a"],
        "verdict": "halal",
        "reason": "Derived from plants or synthesized. Naturally halal.",
        "source": "JAKIM",
        "e_number": "E160a",
    },
    "e162": {
        "name": "E162 - Beetroot Red",
        "alternatives": ["beetroot red", "betanin"],
        "verdict": "halal",
        "reason": "Derived from beetroot (plant source). Halal.",
        "source": "JAKIM, IFANCA",
        "e_number": "E162",
    },
}


def lookup_ingredient(query: str) -> dict[str, Any] | None:
    """Look up an ingredient by name, E-number, or alternative name.

    Returns the ingredient dict if found, None otherwise.
    """
    q = query.strip().lower()

    # Direct match
    if q in INGREDIENTS:
        return INGREDIENTS[q]

    # Check alternatives and E-numbers
    for _key, ingredient in INGREDIENTS.items():
        # Check alternatives
        for alt in ingredient.get("alternatives", []):
            if alt.lower() == q:
                return ingredient
        # Check E-number match
        if ingredient.get("e_number") and ingredient["e_number"].lower() == q:
            return ingredient

    return None


def check_ingredients(ingredient_list: list[str]) -> list[dict[str, Any]]:
    """Check a list of ingredient names against the database.

    Returns a list of results, each containing:
    - query: the original search term
    - name: the canonical ingredient name
    - verdict: halal | haram | doubtful | unknown
    - reason: explanation
    - source: authority/source
    """
    results = []
    for item in ingredient_list:
        match = lookup_ingredient(item)
        if match:
            results.append({
                "query": item,
                "name": match["name"],
                "verdict": match["verdict"],
                "reason": match["reason"],
                "source": match["source"],
                "e_number": match.get("e_number"),
            })
        else:
            results.append({
                "query": item,
                "name": item,
                "verdict": "unknown",
                "reason": "Ingredient not found in our database. Please verify independently.",
                "source": None,
                "e_number": None,
            })
    return results
