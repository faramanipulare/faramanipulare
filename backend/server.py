diff --git a/backend/server.py b/backend/server.py
index b0106ecae8e0de620cff567d1431e1bee4baa0d9..cc8aec6d2be2946770966a98135f2f2fa3ac04c9 100644
--- a/backend/server.py
+++ b/backend/server.py
@@ -1,65 +1,118 @@
 from fastapi import FastAPI, APIRouter, HTTPException, Query
 from dotenv import load_dotenv
 from starlette.middleware.cors import CORSMiddleware
 from motor.motor_asyncio import AsyncIOMotorClient
 import os
 import logging
 from pathlib import Path
 from pydantic import BaseModel, Field, ConfigDict
 from typing import List, Optional, Dict, Any
 import uuid
 from datetime import datetime, timezone, timedelta
 import httpx
 from bs4 import BeautifulSoup
 import asyncio
 from groq import Groq
 import json
+import investpy
+from zoneinfo import ZoneInfo
 
 ROOT_DIR = Path(__file__).parent
 load_dotenv(ROOT_DIR / '.env')
 
 # MongoDB connection
 mongo_url = os.environ['MONGO_URL']
 client = AsyncIOMotorClient(mongo_url)
 db = client[os.environ['DB_NAME']]
 
 # Create the main app without a prefix
 app = FastAPI()
 
 # Create a router with the /api prefix
 api_router = APIRouter(prefix="/api")
 
 # Simple in-memory cache for calendar data
 calendar_cache: Dict[str, Any] = {
     "data": [],
     "last_fetch": None,
-    "cache_duration": 60,  # 1 minute cache - refreshes frequently
+    "cache_duration": int(os.environ.get("CALENDAR_CACHE_SECONDS", "900")),
     "data_source": "sample",
-    "week_start": None  # Track which week the cache is for
+    "week_start": None,  # Track which week the cache is for
+    "last_source_refresh": {}
 }
 
+AUTO_REFRESH_MINUTES = int(os.environ.get("AUTO_REFRESH_MINUTES", "30"))
+refresh_task: Optional[asyncio.Task] = None
+ROMANIA_TZ = ZoneInfo("Europe/Bucharest")
+
+
+def normalize_event_to_romania_time(date_str: str, time_str: str, assume_utc: bool = True) -> tuple[str, str]:
+    """Normalize event date/time to Europe/Bucharest timezone when a parseable clock time exists."""
+    if not date_str or not time_str:
+        return date_str, time_str
+
+    clean_time = str(time_str).strip()
+    if clean_time.lower() in {"all day", "tentative", "", "-"}:
+        return date_str, time_str
+
+    parsed_time = None
+    time_candidates = [clean_time.upper(), clean_time.upper().replace(" ", "")]
+    for candidate in time_candidates:
+        for fmt in ("%H:%M", "%H:%M:%S", "%I:%M%p", "%I:%M %p"):
+            try:
+                parsed_time = datetime.strptime(candidate, fmt)
+                break
+            except Exception:
+                continue
+        if parsed_time is not None:
+            break
+
+    if parsed_time is None:
+        return date_str, time_str
+
+    try:
+        base_date = datetime.strptime(date_str, "%Y-%m-%d")
+    except ValueError:
+        return date_str, time_str
+
+    if assume_utc:
+        source_dt = datetime(
+            base_date.year, base_date.month, base_date.day,
+            parsed_time.hour, parsed_time.minute, parsed_time.second,
+            tzinfo=timezone.utc
+        )
+    else:
+        source_dt = datetime(
+            base_date.year, base_date.month, base_date.day,
+            parsed_time.hour, parsed_time.minute, parsed_time.second,
+            tzinfo=ROMANIA_TZ
+        )
+
+    ro_dt = source_dt.astimezone(ROMANIA_TZ)
+    return ro_dt.strftime("%Y-%m-%d"), ro_dt.strftime("%H:%M")
+
 # Configure logging
 logging.basicConfig(
     level=logging.INFO,
     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
 )
 logger = logging.getLogger(__name__)
 
 # Models
 class EconomicEvent(BaseModel):
     model_config = ConfigDict(extra="ignore")
     id: str = Field(default_factory=lambda: str(uuid.uuid4()))
     date: str
     time: str
     currency: str
     impact: str  # high, medium, low
     event: str
     actual: Optional[str] = None
     forecast: Optional[str] = None
     previous: Optional[str] = None
     source: str  # forexfactory or investing
 
 class TradingSignal(BaseModel):
     date: str
     signal: str  # trade, caution, avoid
     probability: int  # 0-100
@@ -107,79 +160,80 @@ async def fetch_forexfactory_events(date_from: str, date_to: str) -> List[dict]:
     
     # Check cache validity
     now = datetime.now(timezone.utc)
     
     # Calculate current/next trading week dates for validation
     # If weekend, use next week; otherwise current week
     if now.weekday() >= 5:  # Weekend
         days_until_monday = 7 - now.weekday()
         week_monday = now + timedelta(days=days_until_monday)
     else:
         week_monday = now - timedelta(days=now.weekday())
     
     current_week_start = week_monday.strftime("%Y-%m-%d")
     current_week_end = (week_monday + timedelta(days=4)).strftime("%Y-%m-%d")
     
     # Check if cache is valid: not expired AND same week
     cache_valid = (
         calendar_cache["last_fetch"] and 
         calendar_cache["data"] and
         (now - calendar_cache["last_fetch"]).total_seconds() < calendar_cache["cache_duration"] and
         calendar_cache.get("week_start") == current_week_start
     )
     
     if cache_valid:
         # Use cached data
-        all_data = calendar_cache["data"]
+        all_data = [e for e in calendar_cache["data"] if e.get("source") == "forexfactory"]
         logger.info(f"Using cached data: {len(all_data)} events for week {current_week_start}")
     else:
         # Fetch fresh data
         all_data = []
         try:
             url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
             
             headers = {
                 "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                 "Accept": "application/json",
             }
             
             async with httpx.AsyncClient(timeout=30.0) as http_client:
                 response = await http_client.get(url, headers=headers)
                 logger.info(f"ForexFactory API response: {response.status_code}")
                 
                 if response.status_code == 200:
                     raw_data = response.json()
                     api_dates = set()
                     
                     for item in raw_data:
                         event_date = item.get("date", "")
                         if event_date:
                             try:
                                 from datetime import datetime as dt
                                 parsed_date = dt.fromisoformat(event_date.replace('Z', '+00:00'))
                                 date_str = parsed_date.strftime("%Y-%m-%d")
                                 time_str = parsed_date.strftime("%H:%M")
+                                date_str, time_str = normalize_event_to_romania_time(date_str, time_str, assume_utc=True)
                                 api_dates.add(date_str)
                             except Exception:
                                 date_str = event_date[:10] if len(event_date) >= 10 else event_date
                                 time_str = ""
                         else:
                             date_str = ""
                             time_str = ""
                         
                         impact = "low"
                         impact_raw = item.get("impact", "").lower()
                         if impact_raw in ["high", "red"]:
                             impact = "high"
                         elif impact_raw in ["medium", "orange"]:
                             impact = "medium"
                         
                         all_data.append({
                             "id": str(uuid.uuid4()),
                             "date": date_str,
                             "time": time_str,
                             "currency": item.get("country", ""),
                             "impact": impact,
                             "event": item.get("title", ""),
                             "actual": item.get("actual"),
                             "forecast": item.get("forecast"),
                             "previous": item.get("previous"),
@@ -214,50 +268,118 @@ async def fetch_forexfactory_events(date_from: str, date_to: str) -> List[dict]:
                     calendar_cache["week_start"] = current_week_start
         except Exception as e:
             logger.error(f"Error fetching ForexFactory: {e}")
             # Fallback to sample data
             all_data = generate_sample_calendar_data()
             calendar_cache["data"] = all_data
             calendar_cache["last_fetch"] = now
             calendar_cache["data_source"] = "sample"
             calendar_cache["week_start"] = current_week_start
     
     # Filter by date range if specified
     events = []
     for item in all_data:
         date_str = item.get("date", "")
         if date_from and date_to:
             if date_str and date_from <= date_str <= date_to:
                 events.append(item.copy())
                 events[-1]["id"] = str(uuid.uuid4())  # New ID for each response
         else:
             events.append(item.copy())
             events[-1]["id"] = str(uuid.uuid4())
     
     return events
 
 
+async def fetch_investing_events(date_from: str, date_to: str) -> List[dict]:
+    """Fetch economic calendar events from Investing.com through investpy."""
+    try:
+        from_date = datetime.strptime(date_from, "%Y-%m-%d").strftime("%d/%m/%Y")
+        to_date = datetime.strptime(date_to, "%Y-%m-%d").strftime("%d/%m/%Y")
+    except ValueError:
+        logger.warning("Invalid date format for investing fetch: %s - %s", date_from, date_to)
+        return []
+
+    def _fetch_in_thread() -> List[dict]:
+        try:
+            frame = investpy.economic_calendar(
+                from_date=from_date,
+                to_date=to_date
+            )
+            if frame is None or frame.empty:
+                return []
+
+            records = frame.to_dict("records")
+            events: List[dict] = []
+
+            for row in records:
+                event_date = row.get("date")
+                if not event_date:
+                    continue
+
+                date_str = ""
+                try:
+                    parsed_date = datetime.strptime(str(event_date), "%d/%m/%Y")
+                    date_str = parsed_date.strftime("%Y-%m-%d")
+                except Exception:
+                    date_str = str(event_date)
+
+                impact_raw = str(row.get("importance", "")).lower()
+                if "high" in impact_raw or impact_raw.count("bull") >= 3:
+                    impact = "high"
+                elif "medium" in impact_raw or impact_raw.count("bull") == 2:
+                    impact = "medium"
+                else:
+                    impact = "low"
+
+                ro_date, ro_time = normalize_event_to_romania_time(
+                    date_str,
+                    str(row.get("time", "")),
+                    assume_utc=True
+                )
+
+                events.append({
+                    "id": str(uuid.uuid4()),
+                    "date": ro_date,
+                    "time": ro_time,
+                    "currency": str(row.get("currency", "")),
+                    "impact": impact,
+                    "event": str(row.get("event", "")),
+                    "actual": row.get("actual"),
+                    "forecast": row.get("forecast"),
+                    "previous": row.get("previous"),
+                    "source": "investing"
+                })
+
+            return events
+        except Exception as err:
+            logger.error("Error fetching Investing.com calendar: %s", err)
+            return []
+
+    return await asyncio.to_thread(_fetch_in_thread)
+
+
 def generate_sample_calendar_data() -> List[dict]:
     """Generate dynamic economic calendar data that changes each week"""
     today = datetime.now(timezone.utc)
     
     # If it's Saturday (5) or Sunday (6), use next week's Monday
     if today.weekday() >= 5:  # Weekend
         days_until_monday = 7 - today.weekday()
         week_start = today + timedelta(days=days_until_monday)
     else:
         week_start = today - timedelta(days=today.weekday())
     
     week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
     
     # Calculate week number for rotation (different events each week)
     week_number = int(week_start.strftime("%W"))
     
     # Large pool of realistic economic events organized by day type
     # These rotate based on week number so each week looks different
     
     monday_events_pool = [
         [
             {"time": "09:00", "currency": "EUR", "event": "German Ifo Business Climate", "impact": "high"},
             {"time": "14:30", "currency": "USD", "event": "Chicago Fed National Activity Index", "impact": "low"},
             {"time": "15:00", "currency": "EUR", "event": "Consumer Confidence", "impact": "medium"},
         ],
@@ -420,124 +542,169 @@ def generate_sample_calendar_data() -> List[dict]:
         (2, wednesday_events),
         (3, thursday_events),
         (4, friday_events),
     ]
     
     events = []
     for day_offset, day_events in all_day_events:
         event_date = (week_start + timedelta(days=day_offset)).strftime("%Y-%m-%d")
         for item in day_events:
             events.append({
                 "id": str(uuid.uuid4()),
                 "date": event_date,
                 "time": item["time"],
                 "currency": item["currency"],
                 "impact": item["impact"],
                 "event": item["event"],
                 "actual": None,
                 "forecast": None,
                 "previous": None,
                 "source": "forexfactory"
             })
     
     logger.info(f"Generated {len(events)} dynamic calendar events for week {week_number} starting {week_start.strftime('%Y-%m-%d')}")
     return events
 
-async def fetch_trading_economics_events(date_from: str, date_to: str) -> List[dict]:
-    """Fetch economic calendar from Trading Economics via web scraping"""
-    events = []
+async def fetch_tradingeconomics_fallback_events(date_from: str, date_to: str) -> List[dict]:
+    """Secondary fallback source when Investing.com is unavailable."""
+    events: List[dict] = []
+    url = "https://tradingeconomics.com/calendar"
+    headers = {
+        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
+        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
+    }
+
     try:
-        url = "https://tradingeconomics.com/calendar"
-        headers = {
-            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
-            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
-            "Accept-Language": "en-US,en;q=0.5"
-        }
-        
-        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http_client:
+        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as http_client:
             response = await http_client.get(url, headers=headers)
-            logger.info(f"Trading Economics response: {response.status_code}")
-            
-            if response.status_code == 200:
-                soup = BeautifulSoup(response.text, 'lxml')
-                table = soup.find('table', id='calendar')
-                
-                if table:
-                    rows = table.find_all('tr')
-                    current_date = ""
-                    
-                    for row in rows[1:100]:  # Skip header, limit to 100 rows
-                        cells = row.find_all('td')
-                        if len(cells) >= 5:
-                            # Extract date from first column if present
-                            date_cell = cells[0].get_text(strip=True)
-                            if date_cell and len(date_cell) > 3:
-                                # Try to parse date
-                                try:
-                                    # Trading Economics format varies
-                                    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
-                                except Exception:
-                                    pass
-                            
-                            time_text = cells[0].get_text(strip=True)[:8]
-                            country = cells[1].get_text(strip=True)[:3].upper()
-                            event_name = cells[2].get_text(strip=True)
-                            
-                            # Determine impact based on importance column or styling
-                            impact = "medium"
-                            importance_cell = cells[3] if len(cells) > 3 else None
-                            if importance_cell:
-                                imp_text = importance_cell.get_text(strip=True).lower()
-                                if 'high' in imp_text or '***' in str(importance_cell):
-                                    impact = "high"
-                                elif 'low' in imp_text or '*' in str(importance_cell):
-                                    impact = "low"
-                            
-                            # Filter for relevant currencies (USD, EUR, GBP for indices focus)
-                            if country in ['USD', 'EUR', 'GBP', 'US', 'EU', 'UK', 'DE', 'FR']:
-                                events.append({
-                                    "id": str(uuid.uuid4()),
-                                    "date": current_date or date_from,
-                                    "time": time_text,
-                                    "currency": country,
-                                    "impact": impact,
-                                    "event": event_name,
-                                    "actual": None,
-                                    "forecast": cells[4].get_text(strip=True) if len(cells) > 4 else None,
-                                    "previous": cells[5].get_text(strip=True) if len(cells) > 5 else None,
-                                    "source": "tradingeconomics"
-                                })
-                    
-                    logger.info(f"Got {len(events)} events from Trading Economics")
+            if response.status_code != 200:
+                return []
+
+            soup = BeautifulSoup(response.text, "lxml")
+            rows = soup.select("table#calendar tr")
+
+            current_date = date_from
+            for row in rows[:200]:
+                cells = row.find_all("td")
+                if len(cells) < 4:
+                    continue
+
+                event_name = cells[2].get_text(strip=True)
+                if not event_name:
+                    continue
+
+                time_raw = cells[0].get_text(strip=True)
+                currency = cells[1].get_text(strip=True)[:3].upper()
+
+                if not currency:
+                    continue
+
+                impact_text = cells[3].get_text(strip=True).lower()
+                if "high" in impact_text or "***" in str(cells[3]):
+                    impact = "high"
+                elif "low" in impact_text:
+                    impact = "low"
                 else:
-                    logger.warning("Trading Economics calendar table not found")
-                    
-    except Exception as e:
-        logger.error(f"Error fetching Trading Economics: {e}")
-    
+                    impact = "medium"
+
+                ro_date, ro_time = normalize_event_to_romania_time(current_date, time_raw, assume_utc=True)
+                if ro_date < date_from or ro_date > date_to:
+                    continue
+
+                events.append({
+                    "id": str(uuid.uuid4()),
+                    "date": ro_date,
+                    "time": ro_time,
+                    "currency": currency,
+                    "impact": impact,
+                    "event": event_name,
+                    "actual": None,
+                    "forecast": cells[4].get_text(strip=True) if len(cells) > 4 else None,
+                    "previous": cells[5].get_text(strip=True) if len(cells) > 5 else None,
+                    "source": "tradingeconomics_fallback"
+                })
+    except Exception as err:
+        logger.error("TradingEconomics fallback failed: %s", err)
+
     return events
 
+
+async def refresh_calendar_sources(date_from: str, date_to: str) -> List[dict]:
+    """Fetch and combine all calendar sources for a date range."""
+    refresh_ts = datetime.now(timezone.utc).isoformat()
+    ff_events, investing_events = await asyncio.gather(
+        fetch_forexfactory_events(date_from, date_to),
+        fetch_investing_events(date_from, date_to)
+    )
+
+    fallback_events: List[dict] = []
+    if not investing_events:
+        fallback_events = await fetch_tradingeconomics_fallback_events(date_from, date_to)
+
+    calendar_cache["last_source_refresh"] = {
+        "forexfactory": refresh_ts if ff_events else None,
+        "investing": refresh_ts if investing_events else None,
+        "fallback": refresh_ts if fallback_events else None
+    }
+    return ff_events + investing_events + fallback_events
+
+
+async def auto_refresh_calendar() -> None:
+    """Background task that periodically refreshes the active trading week cache."""
+    global calendar_cache
+    while True:
+        try:
+            now = datetime.now(timezone.utc)
+            if now.weekday() >= 5:
+                days_until_monday = 7 - now.weekday()
+                week_monday = now + timedelta(days=days_until_monday)
+            else:
+                week_monday = now - timedelta(days=now.weekday())
+
+            week_start = week_monday.strftime("%Y-%m-%d")
+            week_end = (week_monday + timedelta(days=4)).strftime("%Y-%m-%d")
+
+            events = await refresh_calendar_sources(week_start, week_end)
+            if events:
+                calendar_cache["data"] = events
+                calendar_cache["last_fetch"] = datetime.now(timezone.utc)
+                calendar_cache["week_start"] = week_start
+                if any(e.get("source") == "investing" for e in events):
+                    calendar_cache["data_source"] = "live_multi"
+                elif any(e.get("source") == "tradingeconomics_fallback" for e in events):
+                    calendar_cache["data_source"] = "live_fallback"
+                elif any(e.get("source") == "forexfactory" for e in events):
+                    calendar_cache["data_source"] = "live"
+
+                logger.info("Auto-refreshed calendar cache with %s events", len(events))
+            else:
+                logger.warning("Auto refresh ran but no events were returned")
+        except Exception as err:
+            logger.error("Auto refresh failed: %s", err)
+
+        await asyncio.sleep(max(60, AUTO_REFRESH_MINUTES * 60))
+
 async def get_ai_analysis(events: List[dict], target_date: str) -> TradingSignal:
     """Use Groq (Llama 3.3 70B) to analyze trading conditions for a given date"""
     api_key = os.environ.get('GROQ_API_KEY')
     
     if not api_key:
         # Return default analysis if no API key
         return generate_rule_based_analysis(events, target_date)
     
     try:
         # Filter events for the target date
         date_events = [e for e in events if target_date in e.get("date", "")]
         
         # Build context for AI
         high_impact = [e for e in date_events if e.get("impact") == "high"]
         
         event_summary = "\n".join([
             f"- {e.get('time', 'TBA')} | {e.get('currency', 'N/A')} | {e.get('event', 'Unknown')} | Impact: {e.get('impact', 'low')}"
             for e in date_events[:20]
         ])
         
         prompt = f"""You are a professional forex and indices trading analyst. Analyze the following economic calendar events for {target_date} and provide trading recommendations.
 
 Focus on: Indices (US30, NAS100, SPX500, DAX, FTSE), GBPUSD, and EURUSD.
 
 Economic Events for {target_date}:
@@ -639,146 +806,133 @@ def generate_rule_based_analysis(events: List[dict], target_date: str) -> Tradin
     else:
         reasoning.append(f"Total of {len(date_events)} events on the calendar")
     
     return TradingSignal(
         date=target_date,
         signal=signal,
         probability=max(0, min(100, probability)),
         summary=summary,
         reasoning=reasoning[:3],
         high_impact_events=[e.get("event", "") for e in high_impact[:5]],
         recommended_action=action
     )
 
 # API Routes
 @api_router.get("/")
 async def root():
     return {"message": "TradeSignal AI API", "status": "operational"}
 
 @api_router.get("/calendar", response_model=List[EconomicEvent])
 async def get_calendar(
     date_from: str = Query(default=None, description="Start date YYYY-MM-DD"),
     date_to: str = Query(default=None, description="End date YYYY-MM-DD"),
     market: str = Query(default="all", description="Market filter: all, indices, gbpusd, eurusd"),
     impact: str = Query(default="all", description="Impact filter: all, high, medium, low")
 ):
-    """Get combined economic calendar from ForexFactory and Trading Economics"""
+    """Get combined economic calendar from ForexFactory and Investing.com"""
     # Default to current/next trading week
     today = datetime.now(timezone.utc)
     
     if not date_from or not date_to:
         # If weekend, use next week; otherwise current week
         if today.weekday() >= 5:  # Weekend (Sat=5, Sun=6)
             days_until_monday = 7 - today.weekday()
             week_monday = today + timedelta(days=days_until_monday)
         else:
             week_monday = today - timedelta(days=today.weekday())
         
         if not date_from:
             date_from = week_monday.strftime("%Y-%m-%d")
         if not date_to:
             date_to = (week_monday + timedelta(days=4)).strftime("%Y-%m-%d")
     
     # Fetch from both sources concurrently
-    ff_events, te_events = await asyncio.gather(
-        fetch_forexfactory_events(date_from, date_to),
-        fetch_trading_economics_events(date_from, date_to)
-    )
-    
-    all_events = ff_events + te_events
+    all_events = await refresh_calendar_sources(date_from, date_to)
     
     # Filter by market/currency
     if market != "all" and market in RELEVANT_CURRENCIES:
         currencies = RELEVANT_CURRENCIES[market]
         all_events = [
             e for e in all_events 
             if any(c.lower() in e.get("currency", "").lower() for c in currencies)
         ]
     
     # Filter by impact
     if impact != "all":
         all_events = [e for e in all_events if e.get("impact") == impact]
     
     # Convert to EconomicEvent models
     events = []
     for e in all_events:
         try:
             events.append(EconomicEvent(**e))
         except Exception as err:
             logger.warning(f"Error parsing event: {err}")
     
     # Sort by date and time
     events.sort(key=lambda x: (x.date, x.time))
     
     return events
 
 @api_router.get("/analyze", response_model=TradingSignal)
 async def analyze_day(
     date: str = Query(default=None, description="Target date YYYY-MM-DD")
 ):
     """Get AI-powered trading analysis for a specific date"""
     if not date:
         date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
     
     # Fetch events for the date from both sources
-    ff_events, te_events = await asyncio.gather(
-        fetch_forexfactory_events(date, date),
-        fetch_trading_economics_events(date, date)
-    )
-    all_events = ff_events + te_events
+    all_events = await refresh_calendar_sources(date, date)
     
     # Get AI analysis
     analysis = await get_ai_analysis(all_events, date)
     
     return analysis
 
 @api_router.get("/week-overview", response_model=WeekOverview)
 async def get_week_overview(
     week_offset: int = Query(default=0, description="Week offset from current week")
 ):
     """Get trading overview for an entire week"""
     today = datetime.now(timezone.utc)
     
     # Calculate week start (Monday) - if weekend, start from next Monday
     if today.weekday() >= 5:  # Weekend
         days_until_monday = 7 - today.weekday()
         base_monday = today + timedelta(days=days_until_monday)
     else:
         base_monday = today - timedelta(days=today.weekday())
     
     week_start = base_monday + timedelta(weeks=week_offset)
     week_end = week_start + timedelta(days=4)  # Friday
     
     date_from = week_start.strftime("%Y-%m-%d")
     date_to = week_end.strftime("%Y-%m-%d")
     
     # Fetch all events for the week from both sources
-    ff_events, te_events = await asyncio.gather(
-        fetch_forexfactory_events(date_from, date_to),
-        fetch_trading_economics_events(date_from, date_to)
-    )
-    all_events = ff_events + te_events
+    all_events = await refresh_calendar_sources(date_from, date_to)
     
     # Analyze each day
     days = []
     best_days = []
     avoid_days = []
     day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
     
     for i in range(5):
         day_date = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")
         day_events = [e for e in all_events if day_date in e.get("date", "")]
         high_impact = [e for e in day_events if e.get("impact") == "high"]
         
         # Quick analysis without full AI call
         high_count = len(high_impact)
         if high_count >= 4:
             signal = "avoid"
             probability = 25
             avoid_days.append(day_names[i])
         elif high_count >= 2:
             signal = "caution"
             probability = 55
         else:
             signal = "trade"
             probability = 80 - (len([e for e in day_events if e.get("impact") == "medium"]) * 5)
             if probability >= 70:
@@ -791,62 +945,104 @@ async def get_week_overview(
             probability=max(0, min(100, probability)),
             event_count=len(day_events),
             high_impact_count=high_count
         ))
     
     # Calculate overall signal
     avoid_count = len([d for d in days if d.signal == "avoid"])
     caution_count = len([d for d in days if d.signal == "caution"])
     
     if avoid_count >= 3:
         overall = "avoid"
     elif avoid_count + caution_count >= 3:
         overall = "caution"
     else:
         overall = "trade"
     
     return WeekOverview(
         week_start=date_from,
         week_end=date_to,
         days=days,
         overall_signal=overall,
         best_trading_days=best_days[:3],
         avoid_days=avoid_days
     )
 
+
+
+@api_router.get("/ai-status")
+async def ai_status():
+    """Checks if Groq Llama 3.3 integration is configured and reachable."""
+    api_key = os.environ.get('GROQ_API_KEY')
+    if not api_key:
+        return {
+            "configured": False,
+            "provider": "groq",
+            "model": "llama-3.3-70b-versatile",
+            "working": False,
+            "message": "GROQ_API_KEY is not configured"
+        }
+
+    try:
+        groq_client = Groq(api_key=api_key)
+        completion = groq_client.chat.completions.create(
+            model="llama-3.3-70b-versatile",
+            messages=[{"role": "user", "content": "reply only with: ok"}],
+            temperature=0,
+            max_tokens=5
+        )
+        content = completion.choices[0].message.content if completion.choices else ""
+        return {
+            "configured": True,
+            "provider": "groq",
+            "model": "llama-3.3-70b-versatile",
+            "working": bool(content),
+            "sample_response": content
+        }
+    except Exception as err:
+        return {
+            "configured": True,
+            "provider": "groq",
+            "model": "llama-3.3-70b-versatile",
+            "working": False,
+            "message": str(err)
+        }
+
 @api_router.get("/health")
 async def health_check():
     return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
 
 @api_router.get("/data-status")
 async def data_status():
     """Get the current data source status"""
     return {
         "data_source": calendar_cache.get("data_source", "unknown"),
         "last_fetch": calendar_cache["last_fetch"].isoformat() if calendar_cache["last_fetch"] else None,
         "event_count": len(calendar_cache.get("data", [])),
-        "is_live": calendar_cache.get("data_source") == "live"
+        "is_live": calendar_cache.get("data_source") in {"live", "live_multi", "live_fallback"},
+        "refresh_interval_minutes": AUTO_REFRESH_MINUTES,
+        "source_refresh": calendar_cache.get("last_source_refresh", {})
     }
 
 @api_router.get("/market-news", response_model=List[MarketNews])
 async def get_market_news(
     category: str = Query(default="general", description="News category: general, forex, crypto, merger")
 ):
     """Get latest market news from Finnhub"""
     finnhub_key = os.environ.get("FINNHUB_API_KEY")
     if not finnhub_key:
         return []
     
     news_items = []
     try:
         url = "https://finnhub.io/api/v1/news"
         params = {
             "category": category,
             "token": finnhub_key
         }
         
         async with httpx.AsyncClient(timeout=30.0) as http_client:
             response = await http_client.get(url, params=params)
             
             if response.status_code == 200:
                 data = response.json()
                 
@@ -874,50 +1070,60 @@ async def get_market_news(
                 
                 logger.info(f"Got {len(news_items)} news items from Finnhub")
             else:
                 logger.warning(f"Finnhub news API returned {response.status_code}")
                 
     except Exception as e:
         logger.error(f"Error fetching Finnhub news: {e}")
     
     return news_items
 
 @api_router.post("/refresh-cache")
 async def refresh_cache():
     """Force refresh the calendar cache - clears cache and fetches fresh data"""
     global calendar_cache
     
     # Clear the cache
     calendar_cache["data"] = []
     calendar_cache["last_fetch"] = None
     calendar_cache["data_source"] = "refreshing"
     
     # Fetch fresh data
     today = datetime.now(timezone.utc)
     week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
     week_end = (today + timedelta(days=(4 - today.weekday()))).strftime("%Y-%m-%d")
     
-    events = await fetch_forexfactory_events(week_start, week_end)
+    events = await refresh_calendar_sources(week_start, week_end)
     
     return {
         "status": "refreshed",
         "data_source": calendar_cache.get("data_source", "unknown"),
         "event_count": len(events),
         "week_start": week_start,
         "week_end": week_end,
         "message": f"Cache refreshed with {len(events)} events for {week_start} to {week_end}"
     }
 
 # Include the router in the main app
 app.include_router(api_router)
 
 app.add_middleware(
     CORSMiddleware,
     allow_credentials=True,
     allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
     allow_methods=["*"],
     allow_headers=["*"],
 )
 
+@app.on_event("startup")
+async def start_refresh_scheduler():
+    global refresh_task
+    if refresh_task is None or refresh_task.done():
+        refresh_task = asyncio.create_task(auto_refresh_calendar())
+
+
 @app.on_event("shutdown")
 async def shutdown_db_client():
+    global refresh_task
+    if refresh_task and not refresh_task.done():
+        refresh_task.cancel()
     client.close()
