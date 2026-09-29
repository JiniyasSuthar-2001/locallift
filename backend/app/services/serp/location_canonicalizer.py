"""
LocalLift — SerpApi Location Canonicalizer & Resolver
Provides standardized, provider-compliant location formatting for SerpApi local searches without silent global fallbacks.
"""

from typing import Optional, Dict, Tuple
import re

# Australian State Abbreviations to Full Names
AU_STATE_MAP: Dict[str, str] = {
    "vic": "Victoria",
    "victoria": "Victoria",
    "nsw": "New South Wales",
    "new south wales": "New South Wales",
    "qld": "Queensland",
    "queensland": "Queensland",
    "wa": "Western Australia",
    "western australia": "Western Australia",
    "sa": "South Australia",
    "south australia": "South Australia",
    "tas": "Tasmania",
    "tasmania": "Tasmania",
    "act": "Australian Capital Territory",
    "australian capital territory": "Australian Capital Territory",
    "nt": "Northern Territory",
    "northern territory": "Northern Territory"
}

# US State Abbreviations to Full Names
US_STATE_MAP: Dict[str, str] = {
    "al": "Alabama", "ak": "Alaska", "az": "Arizona", "ar": "Arkansas", "ca": "California",
    "co": "Colorado", "ct": "Connecticut", "de": "Delaware", "fl": "Florida", "ga": "Georgia",
    "hi": "Hawaii", "id": "Idaho", "il": "Illinois", "in": "Indiana", "ia": "Iowa",
    "ks": "Kansas", "ky": "Kentucky", "la": "Louisiana", "me": "Maine", "md": "Maryland",
    "ma": "Massachusetts", "mi": "Michigan", "mn": "Minnesota", "ms": "Mississippi", "mo": "Missouri",
    "mt": "Montana", "ne": "Nebraska", "nv": "Nevada", "nh": "New Hampshire", "nj": "New Jersey",
    "nm": "New Mexico", "ny": "New York", "nc": "North Carolina", "nd": "North Dakota", "oh": "Ohio",
    "ok": "Oklahoma", "or": "Oregon", "pa": "Pennsylvania", "ri": "Rhode Island", "sc": "South Carolina",
    "sd": "South Dakota", "tn": "Tennessee", "tx": "Texas", "ut": "Utah", "vt": "Vermont",
    "va": "Virginia", "wa": "Washington", "wv": "West Virginia", "wi": "Wisconsin", "wy": "Wyoming",
    "dc": "District of Columbia"
}

# Canadian Province Abbreviations to Full Names
CA_PROVINCE_MAP: Dict[str, str] = {
    "on": "Ontario", "bc": "British Columbia", "qc": "Quebec", "ab": "Alberta",
    "mb": "Manitoba", "sk": "Saskatchewan", "ns": "Nova Scotia", "nb": "New Brunswick",
    "nl": "Newfoundland and Labrador", "pe": "Prince Edward Island", "yt": "Yukon",
    "nt": "Northwest Territories", "nu": "Nunavut"
}

COUNTRY_MAP: Dict[str, str] = {
    "au": "Australia", "aus": "Australia", "australia": "Australia",
    "us": "United States", "usa": "United States", "united states": "United States", "united states of america": "United States",
    "gb": "United Kingdom", "uk": "United Kingdom", "great britain": "United Kingdom", "england": "United Kingdom",
    "ca": "Canada", "can": "Canada", "canada": "Canada",
    "nz": "New Zealand", "new zealand": "New Zealand",
    "in": "India", "india": "India",
    "ie": "Ireland", "ireland": "Ireland",
    "de": "Germany", "germany": "Germany",
    "fr": "France", "france": "France",
    "za": "South Africa", "south africa": "South Africa",
    "sg": "Singapore", "singapore": "Singapore"
}

_LOCATION_CACHE: Dict[Tuple[str, str], str] = {}


class LocationCanonicalizer:
    """
    Canonicalizes local search locations for SerpApi to prevent 400 errors and avoid silent global retries.
    """

    @classmethod
    def canonicalize(cls, location: Optional[str], country: Optional[str] = "us") -> Optional[str]:
        if not location:
            return None
        
        loc_str = str(location).strip()
        if not loc_str or len(loc_str) < 2:
            return None

        # Check in-memory cache
        c_code = (country or "us").strip().lower()
        cache_key = (loc_str.lower(), c_code)
        if cache_key in _LOCATION_CACHE:
            return _LOCATION_CACHE[cache_key]

        country_full = COUNTRY_MAP.get(c_code, c_code.upper())
        parts = [p.strip() for p in loc_str.split(",") if p.strip()]

        if not parts:
            return None

        city = parts[0]
        state_part = parts[1] if len(parts) > 1 else None
        country_part = parts[2] if len(parts) > 2 else None

        # Resolve state / province / region
        resolved_state = None
        resolved_country = None
        if state_part:
            s_clean = state_part.lower().strip()
            if c_code in ("au", "aus", "australia") or "australia" in loc_str.lower() or (s_clean in AU_STATE_MAP and s_clean not in US_STATE_MAP):
                resolved_state = AU_STATE_MAP.get(s_clean, state_part)
                if not country_part and (c_code in ("us", "au", "aus") or not country):
                    resolved_country = "Australia"
            elif c_code in ("ca", "can", "canada") or "canada" in loc_str.lower() or (s_clean in CA_PROVINCE_MAP and s_clean not in US_STATE_MAP):
                resolved_state = CA_PROVINCE_MAP.get(s_clean, state_part)
                if not country_part:
                    resolved_country = "Canada"
            else:
                resolved_state = US_STATE_MAP.get(s_clean, state_part)
        
        # Resolve country part
        if not resolved_country:
            if country_part:
                c_clean = country_part.lower().strip()
                resolved_country = COUNTRY_MAP.get(c_clean, country_part)
            else:
                resolved_country = country_full

        # Build SerpApi standardized location string (comma separated without extraneous spaces)
        canonical_components = [city]
        if resolved_state and resolved_state.lower() != city.lower():
            canonical_components.append(resolved_state)
        if resolved_country and resolved_country.lower() not in [c.lower() for c in canonical_components]:
            canonical_components.append(resolved_country)

        canonical_loc = ",".join(canonical_components)
        _LOCATION_CACHE[cache_key] = canonical_loc
        return canonical_loc
