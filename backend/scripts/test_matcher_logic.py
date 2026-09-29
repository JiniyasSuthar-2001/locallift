import re
import urllib.parse

def test_matching_logic():
    GENERIC_WORDS = {
        "plumber", "plumbing", "dental", "dentist", "electrician", "electrical",
        "lawyer", "attorney", "seo", "marketing", "agency", "services",
        "center", "centre", "clinic", "solutions", "group", "inc", "llc",
        "ltd", "pvt", "rehab", "care", "home", "hospital", "store", "shop"
    }

    def normalize_host(url_or_domain: str) -> str:
        if not url_or_domain:
            return ""
        raw = url_or_domain.strip().lower()
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = "https://" + raw
        try:
            parsed = urllib.parse.urlparse(raw)
            host = parsed.netloc or parsed.path
            host = host.split(":")[0]
            if host.startswith("www."):
                host = host[4:]
            return host.strip("/").strip()
        except Exception:
            return ""

    def get_brand_from_domain(domain: str) -> str:
        host = normalize_host(domain)
        parts = host.split(".")
        if len(parts) >= 2:
            sld = parts[-2]
            if sld not in GENERIC_WORDS and len(sld) >= 3:
                return sld
        return ""

    def extract_brand_from_name(name: str) -> str:
        if not name:
            return ""
        # Split by separators - | : — ,
        chunks = re.split(r"[\-\|\:—,]", name)
        first_chunk = chunks[0].strip()
        clean = re.sub(r"[^\w\s]", "", first_chunk).strip().lower()
        # Remove trailing generic words
        tokens = [t for t in clean.split() if t not in GENERIC_WORDS]
        if tokens:
            return " ".join(tokens)
        return clean

    # Test cases:
    # 1. iHriday project
    proj_name = "iHriday - Occupational therapy in Vadodara - Speech therapy - Behavioral therapy - ABA therapy - Autism Centre"
    proj_domain = "www.ihriday.com"
    item_title = "iHriday Residentialcare"
    item_link = "https://ihridayresidentialcare.com/"

    brand_name = extract_brand_from_name(proj_name)
    brand_domain = get_brand_from_domain(proj_domain)
    item_clean = re.sub(r"[^\w\s]", "", item_title).strip().lower()
    item_domain = normalize_host(item_link)

    print(f"Project Name Brand: '{brand_name}'")
    print(f"Project Domain Brand: '{brand_domain}'")
    print(f"Item Clean Title: '{item_clean}'")
    print(f"Item Domain: '{item_domain}'")

    # Check prefix match
    name_matched = bool(brand_name and len(brand_name) >= 3 and (item_clean.startswith(brand_name) or brand_name.startswith(item_clean)))
    print(f"Name Matched: {name_matched}")

    # Check brand domain match
    domain_matched = bool(brand_domain and len(brand_domain) >= 3 and item_domain.startswith(brand_domain))
    print(f"Domain Matched: {domain_matched}")

    assert name_matched is True
    assert domain_matched is True
    print("ALL LOGIC ASSERTIONS PASSED!")

if __name__ == "__main__":
    test_matching_logic()
