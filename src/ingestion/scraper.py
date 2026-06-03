import asyncio
import random
import logging
from typing import Dict, List, Optional
from playwright.async_api import async_playwright

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15"
]

class ResilientScraper:
    """
    A highly resilient web crawler utilizing Playwright to scrape dynamic content.
    Includes rate limiting, randomized user agents, and exponential backoff retry logic.
    """
    def __init__(self, headless: bool = True, max_retries: int = 5, min_delay: float = 2.0, max_delay: float = 7.0):
        self.headless = headless
        self.max_retries = max_retries
        self.min_delay = min_delay
        self.max_delay = max_delay

    async def scrape_url(self, url: str) -> Optional[str]:
        """
        Scrapes a single URL with exponential backoff retries.
        """
        retry_count = 0
        backoff_base = 2.0

        while retry_count < self.max_retries:
            try:
                # Add a randomized delay before the request to prevent rate-limiting (politeness delay)
                delay = random.uniform(self.min_delay, self.max_delay)
                logger.info(f"Applying politeness delay of {delay:.2f} seconds before scraping: {url}")
                await asyncio.sleep(delay)

                async with async_playwright() as p:
                    # Select a random User-Agent
                    user_agent = random.choice(USER_AGENTS)
                    logger.info(f"Launching browser with User-Agent: {user_agent}")
                    
                    browser = await p.chromium.launch(
                        headless=self.headless,
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                    
                    # Create isolated context
                    context = await browser.new_context(
                        user_agent=user_agent,
                        viewport={"width": 1920, "height": 1080},
                        extra_http_headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.9",
                            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24"',
                            "Sec-Ch-Ua-Mobile": "?0",
                            "Sec-Ch-Ua-Platform": '"Windows"',
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "none",
                            "Sec-Fetch-User": "?1",
                            "Upgrade-Insecure-Requests": "1"
                        }
                    )
                    
                    page = await context.new_page()
                    
                    # Prevent webdriver detection
                    await page.evaluate("() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }) }")
                    
                    logger.info(f"Navigating to: {url} (Attempt {retry_count + 1}/{self.max_retries})")
                    response = await page.goto(url, wait_until="networkidle", timeout=30000)
                    
                    if not response:
                        raise ValueError("No response received from target URL.")
                    
                    status = response.status
                    logger.info(f"Received response with status code: {status} for {url}")
                    
                    # Handle typical client/server error codes
                    if status == 429:
                        raise RuntimeError("HTTP 429: Too Many Requests / Rate Limited.")
                    elif status >= 400:
                        raise RuntimeError(f"HTTP {status}: Client or Server Error.")
                    
                    # Extract raw HTML content
                    html_content = await page.content()
                    await browser.close()
                    return html_content

            except Exception as e:
                retry_count += 1
                logger.warning(f"Error scraping {url} on attempt {retry_count}: {str(e)}")
                
                if retry_count < self.max_retries:
                    # Calculate exponential backoff: base * (2 ^ (retry - 1)) + jitter
                    sleep_time = (backoff_base ** retry_count) + random.uniform(0, 1)
                    logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.error(f"Max retries reached for URL: {url}. Ingestion failed.")
                    
        return None

    async def scrape_multiple(self, urls: List[str]) -> Dict[str, str]:
        """
        Scrapes a batch of URLs sequentially to respect rate limits.
        """
        results = {}
        for url in urls:
            html = await self.scrape_url(url)
            if html:
                results[url] = html
        return results

if __name__ == "__main__":
    # Quick visual check of crawler capabilities
    async def main():
        scraper = ResilientScraper(headless=True)
        url = "https://groww.in/mutual-funds/icici-prudential-liquid-fund-direct-plan-growth"
        content = await scraper.scrape_url(url)
        if content:
            print(f"Successfully scraped {len(content)} bytes of HTML content.")
        else:
            print("Failed to scrape content.")
            
    asyncio.run(main())
