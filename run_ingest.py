import os
import asyncio
import json
import logging
from typing import List
from src.ingestion.scraper import ResilientScraper
from src.ingestion.parser import ResilientParser, SemanticChunker

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("IngestionPipeline")

GROWW_URLS = [
    "https://groww.in/mutual-funds/icici-prudential-large-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/icici-prudential-commodities-fund-direct-growth",
    "https://groww.in/mutual-funds/icici-prudential-balanced-direct-growth",
    "https://groww.in/mutual-funds/icici-prudential-liquid-fund-direct-plan-growth",
    "https://groww.in/mutual-funds/icici-prudential-flexicap-fund-direct-growth",
    "https://groww.in/mutual-funds/icici-prudential-value-direct-growth",
    "https://groww.in/mutual-funds/icici-prudential-retirement-fund-pure-equity-plan-direct-growth",
    "https://groww.in/mutual-funds/icici-prudential-multicap-fund-direct-growth",
    "https://groww.in/mutual-funds/icici-prudential-indo-asia-equity-fund-direct-growth",
    "https://groww.in/mutual-funds/icici-prudential-silver-etf-fof-direct-growth"
]

class IngestionPipeline:
    """
    Orchestrates the entire Ingestion Phase:
    Crawls Groww, extracts fund metadata & metrics, chunks semantically, and logs results.
    """
    def __init__(self, output_dir: str = "data/parsed"):
        self.output_dir = output_dir
        self.scraper = ResilientScraper(headless=True, max_retries=3, min_delay=2.0, max_delay=5.0)
        os.makedirs(self.output_dir, exist_ok=True)

    async def run_one(self, url: str) -> bool:
        logger.info(f"Starting ingestion for: {url}")
        html = await self.scraper.scrape_url(url)
        
        if not html:
            logger.error(f"Failed to scrape HTML content for: {url}")
            return False
        
        parser = ResilientParser(source_url=url)
        profile = parser.parse(html)
        
        if not profile or not profile.fund_name:
            logger.error(f"Failed to parse fund profile for: {url}")
            return False
        
        # Save structured fund profile to JSON
        sanitized_name = "".join(c if c.isalnum() else "_" for c in profile.fund_name)
        output_file = os.path.join(self.output_dir, f"{sanitized_name}.json")
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(profile.dict(), f, indent=4, default=str)
        logger.info(f"Saved structured JSON profile to: {output_file}")
        
        # Perform Semantic Chunking
        chunker = SemanticChunker()
        chunks = chunker.chunk(profile)
        logger.info(f"Generated {len(chunks)} semantic chunks for {profile.fund_name}:")
        
        for i, chunk in enumerate(chunks):
            logger.info(f"  [Chunk {i+1}] ({chunk.metadata['data_type']}) length: {len(chunk.content)} chars")
            
        return True

    async def run_all(self, urls: List[str]):
        logger.info(f"Launching batch ingestion for {len(urls)} target schemes...")
        success_count = 0
        
        for i, url in enumerate(urls):
            logger.info(f"\nProcessing scheme {i+1} of {len(urls)}")
            success = await self.run_one(url)
            if success:
                success_count += 1
            # Brief pause between sequential tasks to be extremely polite
            await asyncio.sleep(2.0)
            
        logger.info(f"\nBatch Ingestion Completed. Successfully processed {success_count}/{len(urls)} schemes.")

if __name__ == "__main__":
    pipeline = IngestionPipeline()
    asyncio.run(pipeline.run_all(GROWW_URLS))
