import re
import unicodedata

SYNONYMS = {
    "rucksack": "backpack",
    "knapsack": "backpack",
    "cell phone": "phone",
    "cellphone": "phone",
    "mobile phone": "phone",
    "restaurants": "food court",
    "restaurant area": "food court",
    "dining area": "food court",
    "navy blue": "dark blue",
    "navy": "dark blue",
    "grey": "gray",
    "car park": "parking",
    "carpark": "parking",
    "keyring": "keychain",
    "key ring": "keychain",
    "spectacles": "glasses",
}
CATEGORY_WORDS: dict[str, tuple[str, ...]] = {
    "bag": ("bag", "backpack", "handbag", "suitcase", "tote", "purse"),
    "phone": ("phone", "mobile", "iphone", "smartphone"),
    "wallet": ("wallet", "billfold", "cardholder"),
    "keys": ("key", "keys"),
}
COLOURS = (
    "dark blue",
    "light blue",
    "black",
    "blue",
    "brown",
    "red",
    "green",
    "white",
    "gray",
    "pink",
    "yellow",
    "silver",
    "gold",
    "purple",
    "orange",
)
LOCATIONS = (
    "food court",
    "north entrance",
    "south entrance",
    "cinema",
    "parking",
    "restroom",
    "bookshop",
    "information desk",
)
BRANDS = ("samsung", "apple", "iphone", "adidas", "nike", "jansport", "nokia")


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    for phrase, replacement in SYNONYMS.items():
        value = re.sub(rf"\b{re.escape(phrase)}\b", replacement, value)
    return " ".join(re.sub(r"[^\w\s'-]", " ", value).split())


def contains(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def descriptive_tokens(text: str) -> set[str]:
    value = normalize(text)
    for phrase in (*COLOURS, *LOCATIONS, *BRANDS):
        value = re.sub(rf"\b{re.escape(phrase)}\b", " ", value)
    stop = set(
        [
            "a",
            "an",
            "the",
            "my",
            "i",
            "it",
            "is",
            "was",
            "were",
            "lost",
            "left",
            "near",
            "at",
            "in",
            "on",
            "and",
            "with",
            "has",
            "have",
            "yesterday",
            "today",
            "please",
            "actually",
            "not",
            "but",
            "no",
            "of",
            "to",
            "from",
            "around",
            "somewhere",
            "something",
            "its",
            "it's",
            "don't",
            "know",
            "maybe",
            "think",
            "last",
            "week",
        ]
    )
    stop.update(word for words in CATEGORY_WORDS.values() for word in words)
    return {word for word in value.split() if word not in stop and not word.isdigit()}
