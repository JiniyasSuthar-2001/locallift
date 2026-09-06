import asyncio
import re
import urllib.parse
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup

class WebsiteCrawler:
    def __init__(self, start_url: str, max_pages: int = 15):
        self.start_url = start_url.strip().rstrip("/")
        self.parsed_start = urllib.parse.urlparse(self.start_url)
        self.base_domain = self.parsed_start.netloc
        self.max_pages = max_pages
        self.visited_urls = set()
        self.results = []

    async def crawl(self):
        queue = [self.start_url]
        self.visited_urls.add(self.start_url)

        headers = {
            "User-Agent": "LocalLiftBot/1.0 (+https://locallift.io/bot; SEO Audit & Health Check)"
        }

        async with httpx.AsyncClient(headers=headers, timeout=12.0, follow_redirects=True) as client:
            while queue and len(self.results) < self.max_pages:
                current_url = queue.pop(0)
                start_time = asyncio.get_event_loop().time()

                try:
                    resp = await client.get(current_url)
                    load_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                    
                    if "text/html" not in resp.headers.get("content-type", "").lower():
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")
                    page_data = self._analyze_html(current_url, resp.status_code, soup, load_time_ms)
                    self.results.append(page_data)

                    # Extract internal links
                    for a_tag in soup.find_all("a", href=True):
                        href = a_tag["href"].strip()
                        full_url = urllib.parse.urljoin(current_url, href)
                        parsed = urllib.parse.urlparse(full_url)

                        # Clean fragment
                        cleaned_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))
                        
                        if parsed.netloc == self.base_domain and cleaned_url not in self.visited_urls:
                            # Skip media/assets
                            if not re.search(r"\.(pdf|png|jpg|jpeg|gif|svg|css|js|webp|zip)$", parsed.path.lower()):
                                self.visited_urls.add(cleaned_url)
                                queue.append(cleaned_url)

                except Exception as e:
                    self.results.append({
                        "url": current_url,
                        "status_code": 0,
                        "title": None,
                        "meta_description": None,
                        "h1": None,
                        "h2_list": [],
                        "word_count": 0,
                        "canonical_url": None,
                        "is_indexable": False,
                        "load_time_ms": 0,
                        "schema_types": [],
                        "images_count": 0,
                        "missing_alt_count": 0,
                        "internal_links_count": 0,
                        "external_links_count": 0,
                        "broken_links": [],
                        "issues_detected": [f"Connection Failed: {str(e)[:100]}"]
                    })

        return self.results

    def _analyze_html(self, url: str, status_code: int, soup: BeautifulSoup, load_time_ms: int) -> dict:
        issues = []
        
        # Title
        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else None
        if not title:
            issues.append("Missing page title")
        elif len(title) < 30:
            issues.append("Title tag too short (< 30 chars)")
        elif len(title) > 65:
            issues.append("Title tag too long (> 65 chars)")

        # Meta description
        meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag else None
        if not meta_description:
            issues.append("Missing meta description")
        elif len(meta_description) < 70:
            issues.append("Meta description too short (< 70 chars)")
        elif len(meta_description) > 160:
            issues.append("Meta description too long (> 160 chars)")

        # Headings
        h1_tags = soup.find_all("h1")
        h1 = h1_tags[0].get_text().strip() if h1_tags else None
        if not h1_tags:
            issues.append("Missing H1 heading")
        elif len(h1_tags) > 1:
            issues.append(f"Multiple H1 headings found ({len(h1_tags)})")

        h2_list = [h.get_text().strip() for h in soup.find_all("h2") if h.get_text().strip()][:10]

        # Word count
        body_text = soup.get_text(separator=" ")
        words = [w for w in body_text.split() if len(w) > 1]
        word_count = len(words)
        if word_count < 250:
            issues.append("Thin content page (< 250 words)")

        # Canonical
        canonical_tag = soup.find("link", rel=re.compile(r"canonical", re.I))
        canonical_url = canonical_tag.get("href") if canonical_tag else None
        if not canonical_url:
            issues.append("Missing canonical tag")

        # Robots & Indexability
        robots_meta = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
        robots_content = robots_meta.get("content", "").lower() if robots_meta else ""
        is_indexable = "noindex" not in robots_content and status_code == 200

        # Images & Alt
        images = soup.find_all("img")
        missing_alt = [img for img in images if not img.get("alt")]
        if missing_alt:
            issues.append(f"{len(missing_alt)} images missing descriptive alt tags")

        # Schemas & Structured Data
        schema_types = []
        json_ld_schemas = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                raw_text = script.string or "{}"
                data = json.loads(raw_text)
                if isinstance(data, dict):
                    json_ld_schemas.append(data)
                    st = data.get("@type")
                    if st:
                        schema_types.append(st if isinstance(st, str) else str(st))
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            json_ld_schemas.append(item)
                            if "@type" in item:
                                schema_types.append(str(item["@type"]))
            except Exception:
                issues.append("Malformed JSON-LD structured data script found on page")

        if not schema_types:
            issues.append("No structured data (JSON-LD schema) found")

        # Local Signals: Phone Numbers
        phones_found = set()
        for tel_a in soup.find_all("a", href=re.compile(r"^tel:", re.I)):
            clean_tel = tel_a["href"].replace("tel:", "").strip()
            if clean_tel:
                phones_found.add(clean_tel)
        
        # Phone text pattern fallback
        phone_matches = re.findall(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}", body_text)
        for pm in phone_matches:
            digits_only = re.sub(r"\D", "", pm)
            if 8 <= len(digits_only) <= 14:
                phones_found.add(pm.strip())

        # Local Signals: Emails
        emails_found = set()
        for mail_a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
            clean_mail = mail_a["href"].replace("mailto:", "").split("?")[0].strip()
            if clean_mail:
                emails_found.add(clean_mail.lower())

        # Local Signals: Google Maps Embed
        has_map_embed = bool(soup.find("iframe", src=re.compile(r"google\.com/maps|maps\.google\.com", re.I)))

        # Links (Internal vs External)
        internal_links = 0
        external_links = 0
        for a in soup.find_all("a", href=True):
            parsed_a = urllib.parse.urlparse(a["href"])
            if parsed_a.netloc == "" or parsed_a.netloc == self.base_domain:
                internal_links += 1
            else:
                external_links += 1

        if load_time_ms > 1500:
            issues.append(f"Slow page response time ({load_time_ms}ms)")

        return {
            "url": url,
            "status_code": status_code,
            "title": title,
            "meta_description": meta_description,
            "h1": h1,
            "h2_list": h2_list,
            "word_count": word_count,
            "canonical_url": canonical_url,
            "is_indexable": is_indexable,
            "load_time_ms": load_time_ms,
            "schema_types": list(set(schema_types)),
            "json_ld_schemas": json_ld_schemas,
            "phones_found": list(phones_found)[:5],
            "emails_found": list(emails_found)[:5],
            "has_map_embed": has_map_embed,
            "images_count": len(images),
            "missing_alt_count": len(missing_alt),
            "internal_links_count": internal_links,
            "external_links_count": external_links,
            "broken_links": [],
            "issues_detected": issues
        }
