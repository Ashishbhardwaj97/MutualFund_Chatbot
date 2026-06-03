import re
import os
import logging
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


logger = logging.getLogger("FactualGenerator")

class FactualGenerator:
    """
    RAG-based response generator that constructs strict prompts, interacts with the 
    Groq API, supports a robust offline mock mode fallback, and executes up to 3 
    retries with a final static fallback upon validation failures.
    """
    def __init__(self, model_name: str = "llama-3.1-8b-instant", timeout_seconds: float = 10.0):
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def _build_prompt(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """
        Constructs the strict facts-only RAG prompt matching the technical architecture contract.
        """
        context_str = ""
        for idx, chunk in enumerate(context_chunks):
            content = chunk["content"]
            meta = chunk["metadata"]
            context_str += f"Context Block {idx+1}:\n"
            context_str += f"Fund Name: {meta.get('fund_name')}\n"
            context_str += f"Source URL: {meta.get('source_url')}\n"
            context_str += f"Last Scraped Date: {meta.get('last_scraped_date')}\n"
            context_str += f"Content: {content}\n\n"

        prompt = f"""System Role:
You are a highly precise, facts-only mutual fund assistant. You answer questions using ONLY the provided context. If the answer cannot be found in the context, politely state that you do not have that information.

Strict Output Rules:
1. Maximum length: 3 sentences. No exceptions.
2. Do not offer opinions, projections, or advice.
3. You must include exactly one citation link. Use the 'source_url' from the context.
4. Keep the response objective, neutral, and clear.
5. Do not calculate returns or make performance comparisons.
6. The footer must state: "Last updated from sources: <date>" where <date> is extracted from the context.

Context:
{context_str}

User Query:
{query}
"""
        return prompt

    def _call_groq_api(self, prompt: str) -> str:
        """
        Executes standard HTTP POST query to Groq Chat Completion endpoint.
        """
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not configured.")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 300
        }

        logger.info(f"Sending prompt to Groq API endpoint ({self.model_name})")
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        
        if response.status_code != 200:
            logger.error(f"Groq API error (status {response.status_code}): {response.text}")
            raise RuntimeError(f"Groq API returned status code {response.status_code}")

        result = response.json()
        return result["choices"][0]["message"]["content"]

    def _ensure_footer(self, text: str, date: str) -> str:
        """
        Guarantees that the last scraped date footer is appended correctly 
        and clean from LLM variations.
        """
        if not text:
            return ""
        
        text = text.strip()
        # Remove any existing footer line to avoid double-footers
        text = re.sub(r'Last updated from sources:.*', '', text, flags=re.IGNORECASE).strip()
        
        # Ensure it has trailing punctuation or spacing
        return f"{text}\nLast updated from sources: {date}"

    def _mock_generate(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """
        Deterministic mock generator for offline local testing.
        Fulfills all validation constraints (<=3 sentences, exact citation matching source, and date footer).
        """
        if not context_chunks:
            return "I do not have that information based on the official sources provided."

        first_chunk = context_chunks[0]
        metadata = first_chunk["metadata"]
        url = metadata.get("source_url", "")
        date = metadata.get("last_scraped_date", "")

        # Search for patterns across all chunks for complete coverage
        full_content = "\n\n".join([c["content"] for c in context_chunks])

        # Simple context-matching extraction
        if "exit load" in query.lower() or "exit" in query.lower():
            match = re.search(r'Exit Load Details: ([^\n]+)', full_content, re.IGNORECASE)
            if match:
                answer = f"The exit load details for this scheme are: {match.group(1).strip()}"
            else:
                sentence_match = re.search(r'[^.]*exit load[^.]*\.', full_content, re.IGNORECASE)
                answer = sentence_match.group(0).strip() if sentence_match else "The exit load details for this scheme are specified in the official documentation."
        elif "manager" in query.lower() or "managed" in query.lower() or "run by" in query.lower():
            mgr_matches = re.findall(r'Manager \d+: ([^\n]+)', full_content)
            if mgr_matches:
                answer = f"The fund is managed by {', '.join(mgr_matches)}."
            else:
                sentence_match = re.search(r'[^.]*manager[^.]*\.', full_content, re.IGNORECASE)
                answer = sentence_match.group(0).strip() if sentence_match else "The fund is managed by an experienced team of investment professionals."
        elif "objective" in query.lower() or "aim" in query.lower() or "invests" in query.lower():
            match = re.search(r'Investment Objective:\n([^\n]+)', full_content, re.IGNORECASE)
            if match:
                answer = f"The investment objective is: {match.group(1).strip()}"
            else:
                sentence_match = re.search(r'[^.]*objective[^.]*\.', full_content, re.IGNORECASE)
                answer = sentence_match.group(0).strip() if sentence_match else "The scheme seeks to generate long-term growth and capital appreciation."
        elif "expense" in query.lower() or "ratio" in query.lower():
            match = re.search(r'Expense Ratio: ([^\n]+)', full_content, re.IGNORECASE)
            answer = f"The expense ratio of the scheme is {match.group(1).strip()}." if match else "The fund maintains a low expense ratio to optimize retail investor returns."
        elif "nav" in query.lower() or "net asset value" in query.lower():
            match = re.search(r'Latest Net Asset Value \(NAV\): ([^\n]+)', full_content, re.IGNORECASE)
            answer = f"The latest Net Asset Value (NAV) of the scheme is {match.group(1).strip()}." if match else "The NAV details for this scheme are specified in the official documentation."
        elif "aum" in query.lower() or "size" in query.lower():
            match = re.search(r'Fund Size \(AUM\): ([^\n]+)', full_content, re.IGNORECASE)
            answer = f"The fund size (AUM) of the scheme is {match.group(1).strip()}." if match else "The fund size details for this scheme are specified in the official documentation."
        elif "sip" in query.lower() or "minimum" in query.lower():
            match = re.search(r'Minimum SIP Investment: ([^\n]+)', full_content, re.IGNORECASE)
            answer = f"The minimum SIP investment for the scheme is {match.group(1).strip()}." if match else "The minimum investment details for this scheme are specified in the official documentation."
        elif "lock-in" in query.lower() or "lock in" in query.lower():
            match = re.search(r'Lock-in Period: ([^\n]+)', full_content, re.IGNORECASE)
            answer = f"The lock-in period of the scheme is {match.group(1).strip()}." if match else "The lock-in details for this scheme are specified in the official documentation."
        elif "benchmark" in query.lower():
            match = re.search(r'Benchmark Index: ([^\n]+)', full_content, re.IGNORECASE)
            answer = f"The benchmark index of the scheme is {match.group(1).strip()}." if match else "The benchmark details for this scheme are specified in the official documentation."
        elif "riskometer" in query.lower() or "risk" in query.lower():
            match = re.search(r'Riskometer Classification: ([^\n]+)', full_content, re.IGNORECASE)
            answer = f"The risk classification of the scheme is {match.group(1).strip()}." if match else "The risk classification details for this scheme are specified in the official documentation."
        else:
            # Fallback: Clean out the Source URL line to avoid splitting inside the URL at periods
            cleaned_content = re.sub(r'(?i)Source URL: [^\n]+', '', full_content)
            sentences = re.split(r'[.!?]+', cleaned_content)
            sentences = [s.strip() for s in sentences if s.strip()]
            answer = sentences[0] + "." if sentences else "Here is the verified factual information about the mutual fund."

        # Keep output answer extremely short and factual. Adding citation and footer.
        response = f"{answer} For verified Groww metrics, view: {url}"
        return self._ensure_footer(response, date)

    def generate(self, query: str, context_chunks: List[Dict[str, Any]], mock: bool = False) -> str:
        """
        Orchestrates full factual generation: validates context, checks offline/mock settings,
        runs up to 3 API attempts with programmatic validation, and triggers a clean fallback response.
        """
        if not context_chunks:
            return "I do not have that information based on the official sources provided."

        first_chunk = context_chunks[0]
        target_url = first_chunk["metadata"].get("source_url", "")
        last_scraped_date = first_chunk["metadata"].get("last_scraped_date", "")

        # Check environment API key presence to automatically toggle mock mode
        api_key = os.environ.get("GROQ_API_KEY")
        use_mock = mock or not api_key

        if use_mock:
            logger.info("Executing under Offline Mock Mode.")
            mock_response = self._mock_generate(query, context_chunks)
            return mock_response

        # REAL Groq API Generation Loop (Up to 3 Attempts)
        from src.generation.validator import OutputValidator
        validator = OutputValidator(target_url=target_url, last_scraped_date=last_scraped_date)
        prompt = self._build_prompt(query, context_chunks)

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                raw_response = self._call_groq_api(prompt)
                formatted_response = self._ensure_footer(raw_response, last_scraped_date)
                
                # Perform strict post-validation checks
                is_valid, errors = validator.validate(formatted_response)
                if is_valid:
                    logger.info(f"Validation passed successfully on attempt {attempt}.")
                    return formatted_response
                    
                logger.warning(f"Validation failed on attempt {attempt}. Errors: {errors}")
            except Exception as e:
                logger.error(f"Error during generation attempt {attempt}: {str(e)}")

        # Hard Fallback in case all attempts violate constraints or throw errors
        logger.error(f"Bypassing LLM. All {max_attempts} attempts failed. Returning safe static fallback.")
        fallback_msg = f"I am unable to format a compliant response at this time. Please refer directly to the official source: {target_url}"
        return self._ensure_footer(fallback_msg, last_scraped_date)
