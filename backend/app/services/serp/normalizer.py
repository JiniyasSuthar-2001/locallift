"""
LocalLift — SERP Country & Language Normalizer

Provides authoritative ISO 3166-1 country code and ISO 639-1 language code validation
and normalization across all search intelligence providers.
"""

from typing import Tuple, Dict, Optional

# Standard ISO 3166-1 Alpha-2 Country Codes mapped to canonical lowercase representation
VALID_COUNTRIES: Dict[str, str] = {
    "us": "us", "united states": "us", "usa": "us",
    "gb": "gb", "uk": "gb", "united kingdom": "gb", "england": "gb",
    "ca": "ca", "canada": "ca",
    "au": "au", "australia": "au",
    "in": "in", "india": "in",
    "de": "de", "germany": "de",
    "fr": "fr", "france": "fr",
    "es": "es", "spain": "es",
    "it": "it", "italy": "it",
    "br": "br", "brazil": "br",
    "mx": "mx", "mexico": "mx",
    "nl": "nl", "netherlands": "nl",
    "nz": "nz", "new zealand": "nz",
    "sg": "sg", "singapore": "sg",
    "za": "za", "south africa": "za",
    "ae": "ae", "uae": "ae", "united arab emirates": "ae"
}

# Standard ISO 639-1 Language Codes
VALID_LANGUAGES: Dict[str, str] = {
    "en": "en", "english": "en",
    "es": "es", "spanish": "es",
    "fr": "fr", "french": "fr",
    "de": "de", "german": "de",
    "it": "it", "italian": "it",
    "pt": "pt", "portuguese": "pt",
    "hi": "hi", "hindi": "hi", "hi-in": "hi",
    "zh": "zh", "chinese": "zh",
    "ja": "ja", "japanese": "ja",
    "nl": "nl", "dutch": "nl", "du": "nl"
}

class SERPNormalizer:
    @staticmethod
    def normalize_country(country: Optional[str]) -> str:
        """
        Normalizes country string to ISO 3166-1 alpha-2 code.
        If unknown or empty, defaults cleanly to 'us'.
        """
        if not country or not str(country).strip():
            return "us"
        
        c_clean = str(country).strip().lower()
        if c_clean in VALID_COUNTRIES:
            return VALID_COUNTRIES[c_clean]
        
        if len(c_clean) == 2 and c_clean.isalpha():
            return c_clean
            
        return "us"

    @staticmethod
    def normalize_language(language: Optional[str]) -> str:
        """
        Normalizes language string to ISO 639-1 code.
        """
        if not language or not str(language).strip():
            return "en"
            
        l_clean = str(language).strip().lower()
        if l_clean in VALID_LANGUAGES:
            return VALID_LANGUAGES[l_clean]
            
        if len(l_clean) == 2 and l_clean.isalpha():
            return l_clean
            
        return "en"

    @staticmethod
    def build_location_string(city: Optional[str] = None, state: Optional[str] = None, country: Optional[str] = None) -> Optional[str]:
        """
        Constructs a structured location string for location-aware searches.
        Example: "Ahmedabad, Gujarat, India"
        """
        parts = []
        if city and city.strip():
            parts.append(city.strip())
        if state and state.strip():
            parts.append(state.strip())
        if country and country.strip():
            parts.append(country.strip())
            
        if not parts:
            return None
            
        return ", ".join(parts)
