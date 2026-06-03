import re
from typing import List, Dict, Any, Tuple

class OutputValidator:
    """
    Programmatically validates generated mutual fund response content against strict safety constraints.
    - Sentence count limit (<= 3 sentences, ignoring decimals and abbreviations).
    - Citation count and matching Groww URL (exactly 1 URL matching context source).
    - Footer pattern: 'Last updated from sources: <date>'.
    - Absence of investment opinions, projections, buy/sell advice, or recommendations.
    """
    def __init__(self, target_url: str = None, last_scraped_date: str = None):
        self.target_url = target_url
        self.last_scraped_date = last_scraped_date

    def count_sentences(self, text: str) -> int:
        """
        Accurately counts sentences using a robust tokenizer that ignores decimal numbers,
        common abbreviations, and single-letter initials.
        """
        if not text:
            return 0
            
        # 1. Mask URLs to avoid dots in URL path counting as sentence delimiters
        temp = re.sub(r'https?://\S+?(?=[.,?!]*(?:\s|$))', 'URL_PLACEHOLDER', text)
        
        # 2. Mask decimal values (e.g. 1.25% or 42.50) to 1_25 or 42_50
        temp = re.sub(r'(\d+)\.(\d+)', r'\1_\2', temp)
        
        # 3. Mask standard abbreviations
        abbrevs = [
            r'\bMr\.', r'\bDr\.', r'\bRs\.', r'\bVs\.', r'\bi\.e\.', r'\be\.g\.', 
            r'\bLtd\.', r'\bCo\.', r'\bInc\.', r'\ba\.m\.', r'\bp\.m\.', 
            r'\bcapt\.', r'\bprof\.', r'\bsr\.', r'\bjr\.'
        ]
        for abbrev in abbrevs:
            temp = re.compile(abbrev, re.IGNORECASE).sub('ABBREV', temp)
            
        # 4. Mask single-letter initials (e.g. S. Naren or A. K. Goel)
        temp = re.sub(r'\b[A-Za-z]\.', 'INITIAL', temp)
            
        # 5. Split using standard delimiters (. ! ?)
        sentences = re.split(r'[.!?]+', temp)
        
        # 6. Filter out empty tokens
        sentences = [s.strip() for s in sentences if s.strip()]
        return len(sentences)

    def extract_citations(self, text: str) -> List[str]:
        """
        Extracts all Groww mutual fund URLs found in the text.
        """
        if not text:
            return []
        pattern = r'https?://groww\.in/mutual-funds/[\w-]+'
        return re.findall(pattern, text, re.IGNORECASE)

    def validate(self, text: str) -> Tuple[bool, List[str]]:
        """
        Runs the full programmatic suite of validations.
        Returns:
        - (is_valid, list_of_errors)
        """
        errors = []
        if not text:
            return False, ["Response is empty"]

        # Constraint 1: Sentence count <= 3
        sentence_count = self.count_sentences(text)
        if sentence_count > 3:
            errors.append(f"Sentence count exceeds limit of 3 (got {sentence_count} sentences)")

        # Constraint 2: Citation checks
        citations = self.extract_citations(text)
        if len(citations) != 1:
            errors.append(f"Response must contain exactly one Groww citation link (found {len(citations)})")
        elif self.target_url:
            clean_target = self.target_url.strip().lower()
            clean_found = citations[0].strip().lower()
            if clean_target != clean_found:
                errors.append(f"Citation URL mismatch: expected {self.target_url}, found {citations[0]}")

        # Constraint 3: Footer checks
        footer_match = re.search(r'Last updated from sources:\s*([\w\s:+-]+)', text, re.IGNORECASE)
        if not footer_match:
            errors.append("Footer is missing or invalid. Format must be: 'Last updated from sources: <date>'")
        elif self.last_scraped_date:
            found_date = footer_match.group(1).strip()
            if self.last_scraped_date.strip() not in found_date:
                errors.append(f"Footer date mismatch: expected '{self.last_scraped_date}', found '{found_date}'")

        # Constraint 4: Advisory language guardrails
        # Strictly scan for words denoting advisory recommendations, predictions, buy/sell suggestions
        advisory_pattern = r'\b(should|recommend|recommendation|advice|advise|advisor|advisory|opinion|buy|sell|forecast|projection)\b'
        advisory_matches = re.findall(advisory_pattern, text, re.IGNORECASE)
        if advisory_matches:
            errors.append(f"Advisory/opinionated language detected: {list(set(advisory_matches))}")

        return len(errors) == 0, errors
