import json
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class FundManager(BaseModel):
    name: str
    experience: Optional[str] = "Not Specified"
    tenure: Optional[str] = "Not Specified"

class FundProfile(BaseModel):
    fund_name: str
    source_url: str
    nav: Optional[float] = None
    fund_size: Optional[float] = None  # in Rs. Crores (Cr)
    expense_ratio: Optional[float] = None  # in percentage
    exit_load: Optional[str] = "Not Specified"
    min_sip: Optional[float] = None
    lock_in: Optional[str] = "No Lock-in"
    riskometer: Optional[str] = "Not Specified"
    benchmark: Optional[str] = "Not Specified"
    managers: List[FundManager] = Field(default_factory=list)
    objective: Optional[str] = "Not Specified"
    last_scraped_date: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d"))

    def calculate_hash(self) -> str:
        """
        Calculates a deterministic SHA-256 hash of the fund profile data, excluding last_scraped_date,
        to determine if any actual data has changed.
        """
        import hashlib
        # Exclude last_scraped_date so date changes do not trigger a false positive content change
        data = self.dict()
        data.pop("last_scraped_date", None)
        # Use a deterministic JSON representation with sorted keys
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

class SemanticChunk(BaseModel):
    content: str
    metadata: Dict[str, Any]

class ResilientParser:
    """
    Parses Groww mutual fund HTML pages to extract highly structured metrics and narrative text.
    Uses an extremely robust recursive finder on the Next.js hydration payload (__NEXT_DATA__)
    and falls back to standard BeautifulSoup semantic text extraction on failure.
    """
    def __init__(self, source_url: str):
        self.source_url = source_url

    def parse(self, html: str) -> FundProfile:
        """
        Parses the raw HTML and returns a validated FundProfile.
        """
        soup = BeautifulSoup(html, "lxml")
        
        # Try Next.js __NEXT_DATA__ extraction first
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if next_data_script:
            try:
                json_data = json.loads(next_data_script.string)
                profile = self._parse_next_data(json_data)
                if profile and profile.fund_name:
                    logger.info(f"Successfully parsed fund profile via __NEXT_DATA__ JSON for {self.source_url}")
                    return profile
            except Exception as e:
                logger.warning(f"Failed to parse __NEXT_DATA__ for {self.source_url}: {str(e)}. Falling back to BS4.")

        # Fallback to BeautifulSoup semantic scraping
        logger.info(f"Running BeautifulSoup fallback scraping for {self.source_url}")
        return self._parse_bs4(soup)

    def _find_key_recursive(self, data: Any, target_key: str) -> Any:
        """
        Recursively searches for a key in a nested dictionary/list structure.
        Ensures absolute resilience against structural/path changes in the Next.js hydration payload.
        """
        if isinstance(data, dict):
            if target_key in data:
                return data[target_key]
            for v in data.values():
                res = self._find_key_recursive(v, target_key)
                if res is not None:
                    return res
        elif isinstance(data, list):
            for item in data:
                res = self._find_key_recursive(item, target_key)
                if res is not None:
                    return res
        return None

    def _search_all_keys_recursive(self, data: Any, target_key: str, results: List[Any]):
        """
        Recursively collects all occurrences of a specific key.
        """
        if isinstance(data, dict):
            for k, v in data.items():
                if k == target_key:
                    results.append(v)
                self._search_all_keys_recursive(v, target_key, results)
        elif isinstance(data, list):
            for item in data:
                self._search_all_keys_recursive(item, target_key, results)

    def _parse_next_data(self, json_data: Dict[str, Any]) -> Optional[FundProfile]:
        """
        Extracts known keys using the recursive finder from Next.js payload.
        """
        # Find fund name
        fund_name = (
            self._find_key_recursive(json_data, "schemeName") or 
            self._find_key_recursive(json_data, "scheme_name") or
            self._find_key_recursive(json_data, "name") or
            self._find_key_recursive(json_data, "title") or
            self._find_key_recursive(json_data, "fund_name")
        )
        if not fund_name:
            return None

        # Find NAV
        nav_val = (
            self._find_key_recursive(json_data, "nav") or
            self._find_key_recursive(json_data, "navValue") or
            self._find_key_recursive(json_data, "latestNav") or
            self._find_key_recursive(json_data, "lastNav")
        )
        # Handle float conversions
        nav = None
        if nav_val is not None:
            try:
                # If nav_val is a dict or string, normalize
                if isinstance(nav_val, dict) and "nav" in nav_val:
                    nav = float(nav_val["nav"])
                else:
                    nav = float(str(nav_val).replace(",", "").strip())
            except ValueError:
                pass

        # Find Expense Ratio
        exp_ratio = (
            self._find_key_recursive(json_data, "expenseRatio") or
            self._find_key_recursive(json_data, "expense_ratio")
        )
        expense_ratio = None
        if exp_ratio is not None:
            try:
                # Strip percentage symbols
                expense_ratio = float(str(exp_ratio).replace("%", "").strip())
            except ValueError:
                pass

        # Find Fund Size (AUM)
        aum_val = (
            self._find_key_recursive(json_data, "aum") or
            self._find_key_recursive(json_data, "fundSize") or
            self._find_key_recursive(json_data, "fund_size") or
            self._find_key_recursive(json_data, "aumValue") or
            self._find_key_recursive(json_data, "totalAum") or
            self._find_key_recursive(json_data, "scheme_aum") or
            self._find_key_recursive(json_data, "aum_amount") or
            self._find_key_recursive(json_data, "fund_size_amount")
        )
        fund_size = None
        if aum_val is not None:
            try:
                # Clean Rs., Cr., commas, and trailing characters
                # e.g., "Rs. 12,345.50 Cr" -> 12345.50
                clean_val = str(aum_val).replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
                # Remove any trailing "Cr" or "Crores" if present
                clean_val = re.sub(r'(?i)\s*(?:cr|crores?|crore)', '', clean_val)
                fund_size = float(clean_val.strip())
            except ValueError:
                pass

        # Find Exit Load
        exit_load = (
            self._find_key_recursive(json_data, "exitLoad") or
            self._find_key_recursive(json_data, "exit_load") or
            "Not Specified"
        )
        if isinstance(exit_load, dict):
            exit_load = exit_load.get("description", "Not Specified")

        # Find Minimum SIP
        min_sip_val = (
            self._find_key_recursive(json_data, "min_sip_investment") or
            self._find_key_recursive(json_data, "minSipAmount") or
            self._find_key_recursive(json_data, "minimumSip") or
            self._find_key_recursive(json_data, "minSip")
        )
        min_sip = None
        if min_sip_val is not None:
            try:
                min_sip = float(str(min_sip_val).replace(",", "").replace("₹", "").strip())
            except ValueError:
                pass

        # Find Lock-in Period
        lock_in_val = (
            self._find_key_recursive(json_data, "lock_in") or
            self._find_key_recursive(json_data, "lockInPeriod") or
            self._find_key_recursive(json_data, "lockIn")
        )
        lock_in = "No Lock-in"
        if isinstance(lock_in_val, dict):
            parts = []
            if lock_in_val.get("years"):
                parts.append(f"{lock_in_val['years']} Year(s)")
            if lock_in_val.get("months"):
                parts.append(f"{lock_in_val['months']} Month(s)")
            if lock_in_val.get("days"):
                parts.append(f"{lock_in_val['days']} Day(s)")
            lock_in = " ".join(parts) if parts else "No Lock-in"
        elif lock_in_val is not None:
            lock_in = str(lock_in_val).strip()
        else:
            # Infer lock in from ELSS fund names
            if "elss" in str(fund_name).lower() or "tax saver" in str(fund_name).lower():
                lock_in = "3 Years"

        # Find Riskometer
        riskometer = (
            self._find_key_recursive(json_data, "nfo_risk") or
            self._find_key_recursive(json_data, "riskometer") or
            self._find_key_recursive(json_data, "riskCategory")
        )
        if not riskometer or riskometer == "Not Specified":
            risk_list = []
            self._search_all_keys_recursive(json_data, "risk", risk_list)
            for r in risk_list:
                if isinstance(r, str) and r and r.lower() not in ["not specified", "none"]:
                    riskometer = r
                    break
        if isinstance(riskometer, dict):
            riskometer = riskometer.get("risk", riskometer.get("textName", "Not Specified"))
        if not riskometer:
            riskometer = "Not Specified"
        riskometer = str(riskometer).strip()

        # Find Benchmark
        benchmark = (
            self._find_key_recursive(json_data, "benchmark_name") or
            self._find_key_recursive(json_data, "benchmark") or
            self._find_key_recursive(json_data, "benchmarkName") or
            "Not Specified"
        )

        # Find Objective
        objective = (
            self._find_key_recursive(json_data, "investmentObjective") or
            self._find_key_recursive(json_data, "objective") or
            self._find_key_recursive(json_data, "scheme_objective") or
            self._find_key_recursive(json_data, "description") or
            "Not Specified"
        )

        # Find Fund Managers
        managers_data = []
        raw_managers = []
        self._search_all_keys_recursive(json_data, "fund_manager_details", raw_managers)
        self._search_all_keys_recursive(json_data, "fundManagerDetails", raw_managers)
        self._search_all_keys_recursive(json_data, "fund_manager", raw_managers)
        self._search_all_keys_recursive(json_data, "fundManager", raw_managers)
        self._search_all_keys_recursive(json_data, "fundManagers", raw_managers)
        self._search_all_keys_recursive(json_data, "managers", raw_managers)

        seen_managers = set()
        for mgr_list in raw_managers:
            if not mgr_list:
                continue
            # If not a list, wrap it
            items = mgr_list if isinstance(mgr_list, list) else [mgr_list]
            for item in items:
                if isinstance(item, dict):
                    name = (
                        item.get("person_name") or 
                        item.get("name") or 
                        item.get("managerName")
                    )
                    if name and name not in seen_managers:
                        seen_managers.add(name)
                        exp = (
                            item.get("experience") or 
                            item.get("totalExperience") or 
                            item.get("education") or
                            "Not Specified"
                        )
                        
                        # Tenure extraction/calculation
                        tenure = item.get("tenure") or item.get("activeTenure")
                        if not tenure or tenure == "Not Specified":
                            date_from = item.get("date_from") or item.get("start_date")
                            if date_from:
                                try:
                                    date_str = str(date_from).split('T')[0]
                                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                                    tenure = f"Since {dt.strftime('%B %Y')}"
                                except Exception:
                                    tenure = f"Since {str(date_from)[:10]}"
                            else:
                                tenure = "Not Specified"
                                
                        managers_data.append(FundManager(name=str(name), experience=str(exp), tenure=str(tenure)))
                elif isinstance(item, str) and item not in seen_managers:
                    # Comma separated list of managers
                    for part in re.split(r',\s*', item):
                        if part and part not in seen_managers:
                            seen_managers.add(part)
                            managers_data.append(FundManager(name=part, experience="Not Specified", tenure="Not Specified"))

        return FundProfile(
            fund_name=str(fund_name),
            source_url=self.source_url,
            nav=nav,
            fund_size=fund_size,
            expense_ratio=expense_ratio,
            exit_load=str(exit_load),
            min_sip=min_sip,
            lock_in=str(lock_in),
            riskometer=str(riskometer),
            benchmark=str(benchmark),
            managers=managers_data,
            objective=str(objective)
        )

    def _parse_bs4(self, soup: BeautifulSoup) -> FundProfile:
        """
        Alternative HTML parser using regex and BeautifulSoup structures on DOM texts.
        """
        # Try to find fund title
        h1 = soup.find("h1")
        fund_name = h1.text.strip() if h1 else "Unknown ICICI Mutual Fund"
        
        # Strip generic headers if any
        fund_name = re.sub(r'\s+Latest NAV.*', '', fund_name, flags=re.IGNORECASE)

        # Helper to find metrics based on sibling label texts in the DOM
        def find_metric_by_label(labels: List[str]) -> Optional[str]:
            for label in labels:
                element = soup.find(string=re.compile(rf"^\s*{label}\s*$", re.IGNORECASE))
                logger.debug(f"find_metric_by_label searching '{label}': found element={element}")
                if element:
                    # Search parent or siblings for a numerical value or description
                    parent = element.parent
                    # Check downstream siblings/parent structures typical to Groww layout
                    for sibling in parent.next_siblings:
                        if sibling.name and sibling.text:
                            return sibling.text.strip()
                    # Try going up and down
                    grandparent = parent.parent
                    if grandparent:
                        text_content = grandparent.text
                        # Try to parse anything next to the label
                        match = re.search(rf"{label}\s*([\d\.]+%?|[\w\s\-\(\)%]+)", text_content, re.IGNORECASE)
                        if match:
                            return match.group(1).strip()
            return None

        # NAV Extraction
        nav_str = find_metric_by_label(["NAV", "NAV value", "Latest NAV"])
        nav = None
        if nav_str:
            try:
                # extract decimal
                nav_match = re.search(r'\d+[\d\.]*', nav_str)
                if nav_match:
                    nav = float(nav_match.group(0))
            except ValueError:
                pass

        # Expense Ratio Extraction
        exp_str = find_metric_by_label(["Expense Ratio", "Expense Ratio (incl. GST)"])
        expense_ratio = None
        if exp_str:
            try:
                exp_match = re.search(r'([\d\.]+)\s*%?', exp_str)
                if exp_match:
                    expense_ratio = float(exp_match.group(1))
            except ValueError:
                pass

        # Fund Size (AUM) Extraction
        aum_str = find_metric_by_label(["Fund Size", "Fund size", "AUM", "Assets Under Management"])
        fund_size = None
        if aum_str:
            try:
                # clean currency and Cr / Crores suffix
                clean_str = aum_str.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
                clean_str = re.sub(r'(?i)\s*(?:cr|crores?|crore)', '', clean_str)
                fund_size = float(clean_str.strip())
            except ValueError:
                pass

        # Exit Load Extraction
        exit_load = find_metric_by_label(["Exit Load", "Exit Load Details"]) or "Not Specified"

        # Minimum SIP Extraction
        sip_str = find_metric_by_label(["Min. SIP investment", "Minimum SIP", "Min SIP"])
        min_sip = None
        if sip_str:
            try:
                sip_match = re.search(r'\d+[\d\.]*', sip_str.replace(",", ""))
                if sip_match:
                    min_sip = float(sip_match.group(0))
            except ValueError:
                pass

        # Lock in
        lock_in = "No Lock-in"
        if "elss" in fund_name.lower() or "tax saver" in fund_name.lower():
            lock_in = "3 Years"

        # Riskometer
        riskometer = find_metric_by_label(["Riskometer", "Risk category", "Risk"]) or "Not Specified"

        # Benchmark
        benchmark = find_metric_by_label(["Benchmark", "Benchmark Index"]) or "Not Specified"

        # Objective
        objective = "Not Specified"
        obj_header = soup.find(string=re.compile(r"Investment Objective", re.IGNORECASE))
        if obj_header:
            parent = obj_header.parent
            siblings = list(parent.next_siblings)
            texts = [s.text.strip() for s in siblings if s.name and s.text.strip()]
            if texts:
                objective = texts[0]

        # Fund Managers
        managers_data = []
        mgr_headers = soup.find_all(string=re.compile(r"Fund Manager", re.IGNORECASE))
        for header in mgr_headers:
            parent = header.parent
            # Look around for manager names
            for sibling in parent.next_siblings:
                if sibling.name and sibling.text:
                    name = sibling.text.strip()
                    if name and len(name) < 40 and not any(k in name.lower() for k in ["detail", "ratio", "load", "history"]):
                        managers_data.append(FundManager(name=name, experience="Not Specified", tenure="Not Specified"))

        return FundProfile(
            fund_name=fund_name,
            source_url=self.source_url,
            nav=nav,
            fund_size=fund_size,
            expense_ratio=expense_ratio,
            exit_load=exit_load,
            min_sip=min_sip,
            lock_in=lock_in,
            riskometer=riskometer,
            benchmark=benchmark,
            managers=managers_data,
            objective=objective
        )

class SemanticChunker:
    """
    Semantic chunker to slice a FundProfile into coherent text chunks tagged with correct metadata.
    Splits narrative segments (Numerical Summary, Objective, Managers) into structured units.
    """
    def chunk(self, profile: FundProfile) -> List[SemanticChunk]:
        chunks = []
        content_hash = profile.calculate_hash()
        
        # 1. Structural Numerical Parameters Chunk
        numerical_content = (
            f"Mutual Fund Scheme: {profile.fund_name}\n"
            f"Source URL: {profile.source_url}\n"
            f"Latest Net Asset Value (NAV): Rs. {profile.nav if profile.nav else 'Not Available'}\n"
            f"Fund Size (AUM): Rs. {f'{profile.fund_size} Cr' if profile.fund_size else 'Not Specified'}\n"
            f"Expense Ratio: {f'{profile.expense_ratio}%' if profile.expense_ratio else 'Not Specified'}\n"
            f"Exit Load Details: {profile.exit_load}\n"
            f"Minimum SIP Investment: Rs. {profile.min_sip if profile.min_sip else 'Not Specified'}\n"
            f"Lock-in Period: {profile.lock_in}\n"
            f"Riskometer Classification: {profile.riskometer}\n"
            f"Benchmark Index: {profile.benchmark}\n"
            f"Last updated from sources: {profile.last_scraped_date}"
        )
        chunks.append(SemanticChunk(
            content=numerical_content,
            metadata={
                "fund_name": profile.fund_name,
                "source_url": profile.source_url,
                "data_type": "structure_numerical",
                "last_scraped_date": profile.last_scraped_date,
                "content_hash": content_hash
            }
        ))

        # 2. Investment Objective Chunk
        objective_content = (
            f"Scheme: {profile.fund_name}\n"
            f"Investment Objective:\n{profile.objective}\n"
            f"Last updated from sources: {profile.last_scraped_date}"
        )
        chunks.append(SemanticChunk(
            content=objective_content,
            metadata={
                "fund_name": profile.fund_name,
                "source_url": profile.source_url,
                "data_type": "text_description",
                "last_scraped_date": profile.last_scraped_date,
                "content_hash": content_hash
            }
        ))

        # 3. Fund Managers Detail Chunk
        if profile.managers:
            mgr_lines = []
            for i, mgr in enumerate(profile.managers):
                mgr_lines.append(f"Manager {i+1}: {mgr.name}\n- Experience: {mgr.experience}\n- Active Tenure: {mgr.tenure}")
            
            managers_content = (
                f"Scheme: {profile.fund_name}\n"
                f"Fund Management Team:\n" + "\n\n".join(mgr_lines) + "\n"
                f"Last updated from sources: {profile.last_scraped_date}"
            )
            chunks.append(SemanticChunk(
                content=managers_content,
                metadata={
                    "fund_name": profile.fund_name,
                    "source_url": profile.source_url,
                    "data_type": "fund_management",
                    "last_scraped_date": profile.last_scraped_date,
                    "content_hash": content_hash
                }
            ))

        return chunks
