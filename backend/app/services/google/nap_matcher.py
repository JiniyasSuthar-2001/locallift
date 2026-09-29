import re
import unicodedata
from typing import Dict, Any, Optional, List, Tuple


class NAPMatcher:
    """
    Engine for normalizing and matching Name, Address, Phone, and Website (NAP)
    between a LocalLift project and discovered Google Business Profile locations.
    """

    ROAD_ABBREVIATIONS = {
        r'\bst\b': 'street',
        r'\bstr\b': 'street',
        r'\brd\b': 'road',
        r'\bave\b': 'avenue',
        r'\bav\b': 'avenue',
        r'\bblvd\b': 'boulevard',
        r'\bdr\b': 'drive',
        r'\bln\b': 'lane',
        r'\bct\b': 'court',
        r'\bpl\b': 'place',
        r'\bpkwy\b': 'parkway',
        r'\bhwy\b': 'highway',
        r'\bste\b': 'suite',
        r'\bapt\b': 'apartment',
        r'\bfl\b': 'floor',
        r'\bunit\b': 'unit',
        r'\bbldg\b': 'building',
        r'\bn\b': 'north',
        r'\bs\b': 'south',
        r'\be\b': 'east',
        r'\bw\b': 'west',
        r'\bne\b': 'northeast',
        r'\bnw\b': 'northwest',
        r'\bse\b': 'southeast',
        r'\bsw\b': 'southwest',
    }

    LEGAL_SUFFIXES = [
        r'\bllc\b', r'\binc\b', r'\bcorp\b', r'\bcorporation\b',
        r'\bltd\b', r'\blimited\b', r'\bco\b', r'\bcompany\b',
        r'\bpllc\b', r'\bllp\b', r'\bp\.c\.\b', r'\bpc\b'
    ]

    @classmethod
    def normalize_text(cls, text: Optional[str]) -> str:
        if not text:
            return ""
        # Unicode normalization (NFKD)
        norm = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('utf-8')
        norm = norm.lower().strip()
        # Replace multiple whitespace
        norm = re.sub(r'\s+', ' ', norm)
        return norm

    @classmethod
    def normalize_business_name(cls, name: Optional[str]) -> str:
        norm = cls.normalize_text(name)
        if not norm:
            return ""
        # Strip legal entity suffixes
        for suffix_pat in cls.LEGAL_SUFFIXES:
            norm = re.sub(suffix_pat, '', norm)
        # Strip remaining punctuation
        norm = re.sub(r'[^a-z0-9\s]', '', norm)
        return re.sub(r'\s+', ' ', norm).strip()

    @classmethod
    def normalize_phone(cls, phone: Optional[str]) -> str:
        if not phone:
            return ""
        # Keep only digits
        digits = re.sub(r'\D', '', str(phone))
        # Strip common international country codes if present
        if digits.startswith('61') and len(digits) >= 10:
            digits = digits[2:]
        elif digits.startswith('44') and len(digits) >= 11:
            digits = digits[2:]
        elif digits.startswith('1') and len(digits) == 11:
            digits = digits[1:]
        # Strip leading trunk zero (e.g. 03 -> 3, 04 -> 4, 02 -> 2)
        if digits.startswith('0') and len(digits) >= 9:
            digits = digits[1:]
        return digits

    @classmethod
    def normalize_website(cls, url: Optional[str]) -> str:
        norm = cls.normalize_text(url)
        if not norm:
            return ""
        # Remove protocol
        norm = re.sub(r'^https?:\/\/', '', norm)
        # Remove www.
        norm = re.sub(r'^www\.', '', norm)
        # Remove trailing slash and path
        norm = norm.rstrip('/')
        norm = norm.split('/')[0].split('?')[0].split('#')[0]
        return norm.strip()

    @classmethod
    def normalize_address(cls, address: Optional[str]) -> str:
        norm = cls.normalize_text(address)
        if not norm:
            return ""
        # Remove commas, periods, hashes
        norm = re.sub(r'[,.#]', ' ', norm)
        # Standardize road abbreviations
        for abbr, full in cls.ROAD_ABBREVIATIONS.items():
            norm = re.sub(abbr, full, norm)
        norm = re.sub(r'\s+', ' ', norm).strip()
        return norm

    @classmethod
    def _calculate_similarity(cls, str1: str, str2: str) -> float:
        if not str1 or not str2:
            return 0.0
        if str1 == str2:
            return 1.0
        if str1 in str2 or str2 in str1:
            return 0.85
        # Token overlap ratio (Jaccard)
        tokens1 = set(str1.split())
        tokens2 = set(str2.split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        return len(intersection) / len(union)

    @classmethod
    def evaluate_nap_match(
        cls,
        project_data: Dict[str, Any],
        gbp_candidate: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compares Project NAP against GBP candidate NAP and generates transparent evaluation.
        """
        p_name = project_data.get("name") or project_data.get("business_name") or ""
        p_addr = project_data.get("address") or project_data.get("primary_address") or ""
        p_phone = project_data.get("phone") or project_data.get("primary_phone") or ""
        p_web = project_data.get("website") or project_data.get("website_url") or project_data.get("domain") or ""

        g_name = gbp_candidate.get("location_name") or gbp_candidate.get("business_name") or gbp_candidate.get("title") or ""
        g_addr = gbp_candidate.get("address") or ""
        g_phone = gbp_candidate.get("phone") or ""
        g_web = gbp_candidate.get("website_url") or gbp_candidate.get("websiteUri") or ""

        # Normalize values
        norm_p_name = cls.normalize_business_name(p_name)
        norm_g_name = cls.normalize_business_name(g_name)

        norm_p_addr = cls.normalize_address(p_addr)
        norm_g_addr = cls.normalize_address(g_addr)

        norm_p_phone = cls.normalize_phone(p_phone)
        norm_g_phone = cls.normalize_phone(g_phone)

        norm_p_web = cls.normalize_website(p_web)
        norm_g_web = cls.normalize_website(g_web)

        # Evaluate Name (Weight: 35)
        name_sim = cls._calculate_similarity(norm_p_name, norm_g_name)
        if name_sim >= 0.95 or (norm_p_name and norm_p_name == norm_g_name):
            name_status = "MATCH"
            name_score = 100
            name_reason = "Business name matches canonical listing"
        elif name_sim >= 0.5:
            name_status = "PARTIAL_MATCH"
            name_score = int(name_sim * 100)
            name_reason = f"Partial name overlap ({norm_p_name} vs {norm_g_name})"
        else:
            name_status = "NO_MATCH"
            name_score = int(name_sim * 100)
            name_reason = "Business names differ significantly"

        # Evaluate Website (Weight: 30)
        web_match = (bool(norm_p_web) and bool(norm_g_web) and (norm_p_web == norm_g_web or norm_p_web in norm_g_web or norm_g_web in norm_p_web))
        if web_match:
            web_status = "MATCH"
            web_score = 100
            web_reason = f"Website domains match ({norm_p_web})"
        elif not norm_p_web or not norm_g_web:
            web_status = "NOT_PROVIDED"
            web_score = 50 if (name_status == "MATCH") else 0
            web_reason = "Website not provided on one or both records"
        else:
            web_status = "NO_MATCH"
            web_score = 0
            web_reason = f"Websites differ ({norm_p_web} vs {norm_g_web})"

        # Evaluate Phone (Weight: 20)
        phone_match = (bool(norm_p_phone) and bool(norm_g_phone) and norm_p_phone == norm_g_phone)
        if phone_match:
            phone_status = "MATCH"
            phone_score = 100
            phone_reason = "Phone numbers match exactly after normalization"
        elif not norm_p_phone or not norm_g_phone:
            phone_status = "NOT_PROVIDED"
            phone_score = 50 if (name_status == "MATCH") else 0
            phone_reason = "Phone not provided on one or both records"
        else:
            phone_status = "NO_MATCH"
            phone_score = 0
            phone_reason = "Phone numbers differ"

        # Evaluate Address (Weight: 15)
        addr_sim = cls._calculate_similarity(norm_p_addr, norm_g_addr)
        if addr_sim >= 0.8:
            addr_status = "MATCH"
            addr_score = 100
            addr_reason = "Storefront address matches canonical location"
        elif addr_sim >= 0.4:
            addr_status = "PARTIAL_MATCH"
            addr_score = int(addr_sim * 100)
            addr_reason = "Address components partially match"
        elif not norm_p_addr or not norm_g_addr:
            addr_status = "NOT_PROVIDED"
            addr_score = 50 if (name_status == "MATCH") else 0
            addr_reason = "Address not provided on one or both records"
        else:
            addr_status = "NO_MATCH"
            addr_score = int(addr_sim * 100)
            addr_reason = "Addresses differ"

        # Weighted Total Score
        total_score = (
            (name_score * 0.35) +
            (web_score * 0.30) +
            (phone_score * 0.20) +
            (addr_score * 0.15)
        )
        total_score = round(total_score)

        # Classification
        if (name_status == "MATCH" and (web_status == "MATCH" or phone_status == "MATCH" or addr_status == "MATCH")) or total_score >= 80:
            overall_status = "MATCH"
        elif total_score >= 45 or name_status == "MATCH" or web_status == "MATCH" or phone_status == "MATCH":
            overall_status = "PARTIAL_MATCH"
        else:
            overall_status = "NO_MATCH"

        return {
            "overall_status": overall_status,
            "overall_score": total_score,
            "name": {
                "status": name_status,
                "score": name_score,
                "project_value": p_name,
                "gbp_value": g_name,
                "reason": name_reason
            },
            "website": {
                "status": web_status,
                "score": web_score,
                "project_value": p_web,
                "gbp_value": g_web,
                "reason": web_reason
            },
            "phone": {
                "status": phone_status,
                "score": phone_score,
                "project_value": p_phone,
                "gbp_value": g_phone,
                "reason": phone_reason
            },
            "address": {
                "status": addr_status,
                "score": addr_score,
                "project_value": p_addr,
                "gbp_value": g_addr,
                "reason": addr_reason
            }
        }

    @classmethod
    def classify_candidates(
        cls,
        project_data: Dict[str, Any],
        gbp_candidates: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Evaluates a list of GBP candidate locations against a project.
        Marks overall result as MATCH, PARTIAL_MATCH, NO_MATCH, or AMBIGUOUS.
        """
        evaluated_candidates = []
        high_matches = []

        for cand in gbp_candidates:
            match_res = cls.evaluate_nap_match(project_data, cand)
            cand_copy = dict(cand)
            cand_copy["nap_match"] = match_res
            evaluated_candidates.append(cand_copy)

            if match_res["overall_status"] == "MATCH" or match_res["overall_score"] >= 75:
                high_matches.append(cand_copy)

        if len(high_matches) > 1:
            overall_state = "AMBIGUOUS"
        elif len(high_matches) == 1:
            overall_state = "MATCH"
        elif any(c["nap_match"]["overall_status"] == "PARTIAL_MATCH" for c in evaluated_candidates):
            overall_state = "PARTIAL_MATCH"
        else:
            overall_state = "NO_MATCH"

        # Sort candidates descending by match score
        evaluated_candidates.sort(key=lambda c: c["nap_match"]["overall_score"], reverse=True)
        return overall_state, evaluated_candidates


NAPMatcher.match = NAPMatcher.evaluate_nap_match

