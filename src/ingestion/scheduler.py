import os
import sys
import argparse
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Add the project root to sys.path for direct script execution
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.ingestion.scraper import ResilientScraper
from src.ingestion.parser import ResilientParser
from src.ingestion.embedder import VectorStoreLoader

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scheduler.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("Scheduler")

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

async def perform_incremental_ingestion(force_refresh: bool = False):
    """
    Scrapes the 10 target Groww mutual fund URLs, parses their parameters,
    performs SHA-256 hash checks against the active database vectors to detect changes,
    and updates the database/local JSON stores only when changes are found.
    """
    logger.info("=" * 80)
    logger.info(f"Starting Ingestion Cycle: force_refresh={force_refresh}")
    logger.info("=" * 80)
    
    scraper = ResilientScraper(headless=True, max_retries=3, min_delay=2.0, max_delay=5.0)
    loader = VectorStoreLoader()
    
    success_count = 0
    updated_count = 0
    skipped_count = 0
    
    for i, url in enumerate(GROWW_URLS):
        logger.info(f"[{i+1}/{len(GROWW_URLS)}] Processing URL: {url}")
        try:
            # 1. Scrape the URL
            html = await scraper.scrape_url(url)
            if not html:
                logger.error(f"Failed to scrape HTML content for: {url}")
                continue
            
            # 2. Parse page metrics and data
            parser = ResilientParser(source_url=url)
            profile = parser.parse(html)
            
            if not profile or not profile.fund_name:
                logger.error(f"Failed to parse fund profile for: {url}")
                continue
                
            fund_name = profile.fund_name
            new_hash = profile.calculate_hash()
            
            # 3. Retrieve active hash in ChromaDB for comparison
            active_hash = loader.get_active_hash(fund_name)
            
            if not force_refresh and active_hash == new_hash:
                logger.info(f"  --> [No Change] Scheme '{fund_name}' is up-to-date in database (hash: {new_hash}). Skipping refresh.")
                skipped_count += 1
                success_count += 1
                continue
            
            # 4. Refresh database if different hash or forced
            change_status = "Force Refresh triggered" if force_refresh else f"Hash mismatch detected (old: {active_hash}, new: {new_hash})"
            logger.info(f"  --> [Change Detected] {change_status}. Refreshing entry for '{fund_name}'...")
            
            # Set scraped date to current date
            profile.last_scraped_date = datetime.now().strftime("%Y-%m-%d")
            
            # Perform clean vector store load (internally handles deletion of existing chunks)
            embed_success = loader.embed_and_load([profile], force_refresh=True)
            if not embed_success:
                logger.error(f"Failed to refresh vectors in ChromaDB for: '{fund_name}'")
                continue
                
            # Write structured JSON profile to parsed directory
            sanitized_name = "".join(c if c.isalnum() else "_" for c in fund_name)
            output_file = os.path.join("data/parsed", f"{sanitized_name}.json")
            os.makedirs("data/parsed", exist_ok=True)
            
            import json
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(profile.dict(), f, indent=4, default=str)
                
            logger.info(f"  --> Successfully refreshed database and stored structured JSON to: {output_file}")
            updated_count += 1
            success_count += 1
            
        except Exception as e:
            logger.error(f"Error processing URL '{url}': {str(e)}", exc_info=True)
            
        # Brief pause between sequential tasks to be extremely polite
        await asyncio.sleep(2.0)
        
    logger.info("=" * 80)
    logger.info(f"Cycle Summary - Total: {len(GROWW_URLS)}, Success: {success_count}, "
                f"Updated: {updated_count}, Skipped: {skipped_count}")
    logger.info("=" * 80)

async def main():
    parser = argparse.ArgumentParser(description="Mutual Fund FAQ Ingestion Pipeline Scheduler")
    parser.add_argument("--daemon", action="store_true", help="Run in background daemon mode")
    parser.add_argument("--interval", type=int, default=1440, help="Interval in minutes for the daemon scheduler (default: 1440/Daily)")
    parser.add_argument("--run-now", action="store_true", help="Execute a single one-shot incremental update now and exit")
    parser.add_argument("--force", action="store_true", help="Force database re-chunking and re-embedding regardless of hashes")
    args = parser.parse_args()
    
    if args.run_now or not args.daemon:
        logger.info("Running one-shot incremental update execution...")
        await perform_incremental_ingestion(force_refresh=args.force)
        logger.info("One-shot ingestion execution complete.")
        return
        
    # Running in Daemon Mode
    logger.info(f"Initializing Scheduler in Daemon Mode (polling interval: {args.interval} minutes)...")
    scheduler = AsyncIOScheduler()
    
    # Schedule the incremental ingestion job
    scheduler.add_job(
        perform_incremental_ingestion, 
        "interval", 
        minutes=args.interval, 
        args=[args.force],
        next_run_time=datetime.now() # Trigger first run immediately upon start
    )
    
    scheduler.start()
    logger.info("Scheduler started successfully. Press Ctrl+C to terminate.")
    
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Termination signal received. Stopping scheduler...")
        scheduler.shutdown()
        logger.info("Scheduler stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scheduler execution interrupted by user.")
