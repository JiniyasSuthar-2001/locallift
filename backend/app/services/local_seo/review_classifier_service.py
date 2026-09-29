import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("locallift.review_classifier")

# ─── Generic Cross-Industry Category Rules ───
GENERIC_CATEGORY_RULES: Dict[str, List[str]] = {
    "PRODUCT": [
        r"\bproducts?\b", r"\bitems?\b", r"\bgoods?\b", r"\bmerchandise\b", r"\bmaterial\b",
        r"\bchair\b", r"\bbed\b", r"\btable\b", r"\bdoor\b", r"\bfurniture\b", r"\bclothing\b",
        r"\bapparel\b", r"\bshirt\b", r"\bhardware\b", r"\bdevice\b", r"\bequipment\b",
        r"\bsoftware\b", r"\bapplication\b", r"\btool\b", r"\bparts?\b", r"\bmodel\b",
        r"\bmenu\b", r"\bfood\b", r"\bdish\b", r"\bmeal\b", r"\bdrink\b", r"\bcoffee\b"
    ],
    "SERVICE": [
        r"\bservices?\b", r"\brepair\b", r"\bfix\b", r"\bmaintenance\b", r"\binstallation\b",
        r"\bplumbing\b", r"\bleak\b", r"\bpipe\b", r"\bconsulting\b", r"\bdevelopment\b",
        r"\bdesign\b", r"\bmarketing\b", r"\bseo\b", r"\baudit\b", r"\btreatment\b",
        r"\bappointment\b", r"\bsession\b", r"\bcleaning\b", r"\binspection\b", r"\btune-up\b",
        r"\bcustomization\b", r"\bprinting\b", r"\bworkmanship\b", r"\bjob\b", r"\btask\b"
    ],
    "STAFF": [
        r"\bstaff\b", r"\bteam\b", r"\bemployee\b", r"\bemployees\b", r"\bpersonnel\b",
        r"\btechnician\b", r"\bplumber\b", r"\bdoctor\b", r"\bnurse\b", r"\bmechanic\b",
        r"\bengineer\b", r"\bmanager\b", r"\brepresentative\b", r"\bagent\b", r"\bcrew\b",
        r"\bwaiter\b", r"\bserver\b", r"\bchef\b", r"\bhost\b", r"\bowner\b", r"\bworker\b"
    ],
    "SUPPORT": [
        r"\bsupport\b", r"\bhelpdesk\b", r"\bcustomer service\b", r"\bassistance\b",
        r"\bhelp\b", r"\bresponsive\b", r"\banswering\b", r"\bhelped\b", r"\bresponse time\b",
        r"\btroubleshooting\b", r"\bguidance\b", r"\bfollow-up\b", r"\bresolved\b"
    ],
    "LOCATION": [
        r"\blocation\b", r"\bplace\b", r"\bstore\b", r"\bshop\b", r"\boffice\b",
        r"\bclinic\b", r"\bbranch\b", r"\bfacility\b", r"\bambiance\b", r"\batmosphere\b",
        r"\bparking\b", r"\bcleanliness\b", r"\bclean\b", r"\bconvenient\b", r"\baccessible\b",
        r"\benvironment\b", r"\bdecor\b", r"\bseating\b"
    ],
    "PRICING": [
        r"\bprice\b", r"\bprices\b", r"\bpricing\b", r"\bcost\b", r"\bfee\b",
        r"\brate\b", r"\brates\b", r"\bexpensive\b", r"\baffordable\b", r"\bcheap\b",
        r"\breasonable\b", r"\bvalue\b", r"\bworth\b", r"\bbill\b", r"\bquote\b",
        r"\bestimate\b", r"\bdiscount\b", r"\bbudget\b", r"\bdeal\b", r"\boverpriced\b"
    ],
    "QUALITY": [
        r"\bquality\b", r"\bstandard\b", r"\bdurability\b", r"\bdurable\b", r"\bfinish\b",
        r"\bcraftsmanship\b", r"\bflawless\b", r"\bdefect\b", r"\bbroken\b", r"\bpremium\b",
        r"\bhigh-end\b", r"\btop quality\b", r"\bsolid\b", r"\bsturdy\b", r"\bperfection\b"
    ],
    "EXPERIENCE": [
        r"\bexperience\b", r"\bprocess\b", r"\btransaction\b", r"\bcommunication\b",
        r"\bsatisfaction\b", r"\bdelight\b", r"\bseamless\b", r"\bsmooth\b", r"\beasy\b",
        r"\bhassle-free\b", r"\bquick\b", r"\bfast\b", r"\btimely\b", r"\bpunctual\b",
        r"\bon time\b", r"\bprompt\b", r"\bdelay\b", r"\bwaited\b", r"\bwaiting\b"
    ]
}

# ─── Dynamic Topic Detectors ───
DYNAMIC_TOPIC_RULES: Dict[str, List[str]] = {
    "Product Quality": [r"\bproduct\b", r"\bproduct quality\b", r"\bhigh quality\b", r"\bgreat quality\b", r"\bpoor quality\b", r"\bdurable\b", r"\bmaterial\b", r"\bcraftsmanship\b", r"\bsturdy\b"],
    "Customer Support": [r"\bsupport\b", r"\bcustomer support\b", r"\bcustomer service\b", r"\bsupport team\b", r"\bquick response\b", r"\bhelpful support\b", r"\bresponsive support\b"],
    "Pricing & Value": [r"\bpricing\b", r"\bprice\b", r"\bgreat value\b", r"\baffordable\b", r"\breasonable price\b", r"\bexpensive\b", r"\boverpriced\b", r"\bworth the money\b", r"\bcost\b", r"\bfair price\b"],
    "Speed & Delivery": [r"\bdelivery\b", r"\bshipping\b", r"\bdelay\b", r"\bdelayed\b", r"\bfast delivery\b", r"\bquick turnaround\b", r"\bon time\b", r"\bfast\b", r"\bprompt\b", r"\bpunctual\b", r"\bspeedy\b", r"\bsame day\b"],
    "Staff & Hospitality": [r"\bstaff\b", r"\bteam\b", r"\bfriendly staff\b", r"\bprofessional staff\b", r"\bpolite\b", r"\bcourteous\b", r"\brude\b", r"\bwelcoming\b", r"\bknowledgeable\b", r"\bkind\b"],
    "Location & Atmosphere": [r"\blocation\b", r"\bgreat location\b", r"\beasy parking\b", r"\bclean facility\b", r"\bambiance\b", r"\bclean store\b", r"\bconvenient location\b", r"\bcozy\b"],
    "Service Reliability": [r"\bservice\b", r"\brepair\b", r"\bfix\b", r"\bplumbing\b", r"\bleak\b", r"\breliable service\b", r"\btrustworthy\b", r"\bhonest\b", r"\bexpert service\b", r"\bprofessional service\b", r"\bjob well done\b"],
    "Communication": [r"\bcommunication\b", r"\bgreat communication\b", r"\bclear communication\b", r"\bkept informed\b", r"\blistened\b", r"\btransparent\b", r"\bresponsive\b"],
    "Overall Experience": [r"\bexperience\b", r"\bgreat experience\b", r"\bhighly recommend\b", r"\bwill come back\b", r"\bpleasure to work with\b", r"\bdisappointed\b", r"\bnever again\b", r"\b10/10\b"]
}

POSITIVE_WORDS = {
    "great", "excellent", "best", "amazing", "wonderful", "professional", "fantastic",
    "awesome", "love", "impressed", "highly recommend", "good", "helpful", "fast",
    "reliable", "top-notch", "stellar", "perfect", "exceptional", "friendly", "pleasure",
    "outstanding", "superb", "brilliant", "expert", "quality", "satisfied", "satisfaction",
    "seamless", "smooth", "honest", "polite", "flawless", "delighted", "terrific"
}

NEGATIVE_WORDS = {
    "terrible", "bad", "worst", "poor", "slow", "scam", "awful", "horrible",
    "unprofessional", "useless", "disappointed", "avoid", "rude", "never again", "waste",
    "broken", "delayed", "regret", "unresponsive", "lied", "overpriced", "garbage",
    "incompetent", "fraud", "unacceptable", "mess", "dirty", "overcharged", "damaged"
}


class ReviewClassifierService:
    """
    Intelligence service for public & GBP customer reviews across all business types:
    1. Cross-Industry Category Classification (PRODUCT, SERVICE, STAFF, SUPPORT, LOCATION, PRICING, QUALITY, EXPERIENCE, OTHER)
    2. Dynamic Topic Detection (Product Quality, Customer Support, Pricing, Delivery, Staff, etc.)
    3. Sentiment Polarity Analysis (Derived independently from review text and rating)
    """

    @classmethod
    def classify_review(cls, review_text: Optional[str], rating: Optional[int] = None) -> Dict[str, Any]:
        """
        Classifies review into a universal category (PRODUCT, SERVICE, STAFF, SUPPORT, LOCATION, PRICING, QUALITY, EXPERIENCE, OTHER).
        """
        if not review_text or not review_text.strip():
            return {
                "category": "OTHER",
                "confidence": 1.0,
                "source": "rule_engine",
                "matched_terms": [],
                "topics": []
            }

        text_lower = review_text.lower()
        scores: Dict[str, int] = {}
        matched_dict: Dict[str, list] = {}

        for category, patterns in GENERIC_CATEGORY_RULES.items():
            matches = []
            for pat in patterns:
                found = re.findall(pat, text_lower)
                if found:
                    matches.extend(found)
            if matches:
                scores[category] = len(matches)
                matched_dict[category] = matches

        # Extract dynamic topics
        extracted_topics: List[str] = []
        for topic_name, patterns in DYNAMIC_TOPIC_RULES.items():
            for pat in patterns:
                if re.search(pat, text_lower):
                    extracted_topics.append(topic_name)
                    break

        if not scores:
            return {
                "category": "EXPERIENCE" if len(review_text) > 30 else "OTHER",
                "confidence": 0.8,
                "source": "rule_engine",
                "matched_terms": [],
                "topics": extracted_topics or ["Overall Experience"]
            }

        sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_category, match_count = sorted_cats[0]
        confidence = min(1.0, 0.75 + (match_count * 0.08))

        return {
            "category": top_category,
            "confidence": round(confidence, 2),
            "source": "rule_engine",
            "matched_terms": matched_dict.get(top_category, []),
            "topics": extracted_topics
        }

    @classmethod
    def extract_topics(cls, review_text: Optional[str]) -> List[str]:
        """
        Extracts dynamic topics from review text.
        """
        if not review_text or not review_text.strip():
            return []

        text_lower = review_text.lower()
        topics: List[str] = []
        for topic_name, patterns in DYNAMIC_TOPIC_RULES.items():
            for pat in patterns:
                if re.search(pat, text_lower):
                    topics.append(topic_name)
                    break
        return topics

    @classmethod
    def analyze_sentiment(cls, review_text: Optional[str], rating: Optional[int] = None) -> Dict[str, Any]:
        """
        Evaluates Positive, Neutral, or Negative sentiment polarity derived from
        the review text content, cross-referenced with star rating.
        """
        # 1. Fallback when review contains no text (star rating only)
        if not review_text or not review_text.strip():
            if rating is not None:
                if rating >= 4:
                    return {"sentiment": "positive", "sentiment_score": 0.9, "has_text": False, "confidence": 0.9}
                elif rating == 3:
                    return {"sentiment": "neutral", "sentiment_score": 0.5, "has_text": False, "confidence": 0.8}
                else:
                    return {"sentiment": "negative", "sentiment_score": 0.1, "has_text": False, "confidence": 0.9}
            return {"sentiment": "neutral", "sentiment_score": 0.5, "has_text": False, "confidence": 0.5}

        # 2. Text polarity evaluation
        text_lower = review_text.lower()
        pos_matches = [w for w in POSITIVE_WORDS if w in text_lower]
        neg_matches = [w for w in NEGATIVE_WORDS if w in text_lower]

        pos_count = len(pos_matches)
        neg_count = len(neg_matches)

        if pos_count > neg_count:
            text_sentiment = "positive"
            text_score = 0.7 + min(0.3, (pos_count - neg_count) * 0.1)
        elif neg_count > pos_count:
            text_sentiment = "negative"
            text_score = max(0.0, 0.3 - (neg_count - pos_count) * 0.1)
        else:
            text_sentiment = "neutral"
            text_score = 0.5

        final_sentiment = text_sentiment
        final_score = text_score

        # Distinguish sentiment from rating (e.g. 5 star with complaint or 1 star with constructive praise)
        if rating is not None:
            if rating >= 4:
                if neg_count >= 2 and pos_count <= 1:
                    # 5 stars but text is full of complaints
                    final_sentiment = "negative"
                    final_score = 0.35
                elif neg_count > pos_count:
                    final_sentiment = "neutral"
                else:
                    final_sentiment = "positive"
                    final_score = max(final_score, 0.8)
            elif rating <= 2:
                if pos_count >= 2 and neg_count == 0:
                    # 1-2 stars but text is positive praise
                    final_sentiment = "positive"
                    final_score = 0.75
                elif pos_count > neg_count:
                    final_sentiment = "neutral"
                else:
                    final_sentiment = "negative"
                    final_score = min(final_score, 0.2)
            elif rating == 3:
                if pos_count > neg_count:
                    final_sentiment = "positive"
                elif neg_count > pos_count:
                    final_sentiment = "negative"
                else:
                    final_sentiment = "neutral"
                    final_score = 0.5

        return {
            "sentiment": final_sentiment,
            "sentiment_score": round(final_score, 2),
            "has_text": True,
            "confidence": 0.95 if (pos_count > 0 or neg_count > 0) else 0.85
        }
