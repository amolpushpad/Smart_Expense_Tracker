from functools import lru_cache
import re

from models import Category

TRAINING_SAMPLES = (
    ("groceries supermarket vegetables fruit milk food grocery market", "Food"),
    ("restaurant dinner lunch cafe coffee takeaway meal bakery", "Food"),
    ("buying fresh produce from the local market", "Food"),
    ("pizza delivery sandwich and snacks", "Food"),
    ("bistro brunch and refreshments", "Food"),
    ("taxi cab uber lyft bus train metro gas fuel parking travel", "Transportation"),
    ("monthly city bus pass and train ticket", "Transportation"),
    ("rideshare fare to the airport", "Transportation"),
    ("car fuel petrol toll and parking", "Transportation"),
    ("electricity water internet phone utility bill power gas bill", "Bills"),
    ("monthly broadband subscription invoice", "Bills"),
    ("pay the household electricity statement", "Bills"),
    ("mobile phone service and water charges", "Bills"),
    ("online shopping electronics laptop phone headphones store", "Shopping"),
    ("clothes shoes household purchase retail order", "Shopping"),
    ("new computer and accessories online", "Shopping"),
    ("home supplies from department store", "Shopping"),
    ("movie concert streaming music theatre event", "Entertainment"),
    ("cinema tickets and live show", "Entertainment"),
    ("music subscription and video streaming", "Entertainment"),
    ("doctor pharmacy medicine hospital clinic health", "Healthcare"),
    ("prescription medicine from pharmacy", "Healthcare"),
    ("annual medical clinic appointment", "Healthcare"),
    ("school tuition books course class education university", "Education"),
    ("college fees and textbooks", "Education"),
    ("online course and training class", "Education"),
    ("miscellaneous other service personal payment", "Other"),
    ("unclassified personal service charge", "Other"),
    ("general one-off expense", "Other"),
)

KEYWORD_RULES = (
    ("Food", re.compile(r"\b(grocery|groceries|supermarket|vegetable|fruit|restaurant|dinner|lunch|cafe|coffee|food|bakery|takeaway)\b")),
    ("Transportation", re.compile(r"\b(taxi|cab|uber|lyft|ride|bus|train|metro|fuel|petrol|gas|parking|transport)\b")),
    ("Bills", re.compile(r"\b(electricity|electric|water bill|internet|phone bill|utility|utilities|bill|broadband)\b")),
    ("Shopping", re.compile(r"\b(shopping|electronics|laptop|headphones|clothes|shoes|retail|purchase|store)\b")),
    ("Entertainment", re.compile(r"\b(movie|cinema|concert|streaming|music|theatre|theater|event)\b")),
    ("Healthcare", re.compile(r"\b(doctor|pharmacy|medicine|hospital|clinic|health|medical)\b")),
    ("Education", re.compile(r"\b(school|tuition|books|course|class|education|university|college)\b")),
)


@lru_cache(maxsize=1)
def _text_classifier():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    texts, labels = zip(*TRAINING_SAMPLES)
    classifier = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode"),
        LogisticRegression(max_iter=500, random_state=17),
    )
    classifier.fit(texts, labels)
    return classifier


def _available_category_names():
    return {category.category_name for category in Category.query.all()}


def suggest_category(description, vendor=None):
    combined = " ".join(value.strip() for value in (description, vendor or "") if value).lower()
    available = _available_category_names()
    for category, pattern in KEYWORD_RULES:
        if category in available and pattern.search(combined):
            return {
                "suggested_category": category,
                "confidence": None,
                "method": "keyword_fallback",
                "explanation": "Suggested by a transparent keyword rule. Review it before saving.",
            }

    if not combined.strip():
        return {
            "suggested_category": None,
            "confidence": None,
            "method": "no_match",
            "explanation": "No description or vendor text was available to classify.",
        }

    try:
        classifier = _text_classifier()
        category = str(classifier.predict([combined])[0])
        confidence = float(max(classifier.predict_proba([combined])[0]))
    except ImportError:
        return {
            "suggested_category": None,
            "confidence": None,
            "method": "fallback_unavailable",
            "explanation": "The text classifier is unavailable and no keyword rule matched.",
        }

    if category not in available:
        return {
            "suggested_category": None,
            "confidence": round(confidence, 4),
            "method": "unavailable_category",
            "explanation": "The suggested category is not available in this account.",
        }
    return {
        "suggested_category": category,
        "confidence": round(confidence, 4),
        "method": "tfidf_logistic_regression",
        "explanation": "Suggested by a model trained on the application's small, documented sample phrases. Verify the suggestion.",
    }
