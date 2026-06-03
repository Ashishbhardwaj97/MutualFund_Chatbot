import re

class DataScrubber:
    """
    Absolute privacy data scrub utility to redact PII (PAN, Aadhaar, Email, Bank Account, OTP)
    before logging, caching, or passing to search engines and language models.
    """
    def __init__(self):
        self.email_regex = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.aadhaar_regex = re.compile(r'\b[2-9][0-9]{3}[-\s]?[0-9]{4}[-\s]?[0-9]{4}\b')
        self.pan_regex = re.compile(r'\b[A-Za-z]{5}[0-9]{4}[A-Za-z]\b')
        self.account_regex = re.compile(r'\b\d{9,18}\b')
        
        # Contextual OTP matching (4-6 digits near security/verification keywords)
        self.otp_context_regex = re.compile(
            r'\b(?:otp|one[- ]time[- ]password|code|pin|verify|verification|password|login)\b\s*(?:is|:|=|\s)\s*\b\d{4,6}\b', 
            re.IGNORECASE
        )
        # Standalone OTP fallback (specifically 6 digits)
        self.otp_standalone_regex = re.compile(r'\b\d{6}\b')

    def scrub(self, text: str) -> str:
        if not text:
            return ""
            
        # 1. Scrub Email
        text = self.email_regex.sub("[REDACTED_EMAIL]", text)
        
        # 2. Scrub Aadhaar
        text = self.aadhaar_regex.sub("[REDACTED_AADHAAR]", text)
        
        # 3. Scrub PAN (case-insensitive)
        text = re.sub(self.pan_regex, "[REDACTED_PAN]", text)
        
        # 4. Scrub Contextual OTP (e.g. "OTP: 1234" -> "OTP: [REDACTED_OTP]")
        def _repl_otp(match):
            val = match.group(0)
            # Find the actual 4-6 digit sequence inside the match and replace it
            digits = re.search(r'\d{4,6}', val)
            if digits:
                return val.replace(digits.group(0), "[REDACTED_OTP]")
            return val
            
        text = self.otp_context_regex.sub(_repl_otp, text)
        
        # 5. Scrub Standalone 6-digit OTP (common verification pins)
        text = self.otp_standalone_regex.sub("[REDACTED_OTP]", text)
        
        # 6. Scrub Bank Account numbers (9 to 18 digits)
        # Check that we aren't redacting parts of already redacted placeholders like [REDACTED_AADHAAR]
        def _repl_account(match):
            # Verify it's not preceded by [REDACTED_
            start = match.start()
            if start >= 10:
                left_context = text[start-10:start]
                if "REDACTED_" in left_context:
                    return match.group(0)
            return "[REDACTED_ACCOUNT]"
            
        text = self.account_regex.sub(_repl_account, text)
        
        return text
