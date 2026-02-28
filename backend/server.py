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
from emergentintegrations.llm.chat import LlmChat, UserMessage

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
    "cache_duration": 300,  # 5 minutes
    "data_source": "sample"  # "live" or "sample"
}

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
    summary: str
    reasoning: List[str]
    high_impact_events: List[str]
    recommended_action: str

class DayAnalysis(BaseModel):
    date: str
    day_name: str
    signal: str
    probability: int
    event_count: int
    high_impact_count: int

class WeekOverview(BaseModel):
    week_start: str
    week_end: str
    days: List[DayAnalysis]
    overall_signal: str
    best_trading_days: List[str]
    avoid_days: List[str]

# Currency mapping for filtering
RELEVANT_CURRENCIES = {
    "indices": ["USD", "US", "DJI", "SPX", "NDX", "DAX", "FTSE", "CAC", "ALL"],
    "gbpusd": ["GBP", "USD"],
    "eurusd": ["EUR", "USD"]
}

async def fetch_forexfactory_events(date_from: str, date_to: str) -> List[dict]:
    """Fetch economic calendar from ForexFactory via FairEconomy API with caching"""
    global calendar_cache
    
    # Check cache validity
    now = datetime.now(timezone.utc)
    if (calendar_cache["last_fetch"] and 
        calendar_cache["data"] and
        (now - calendar_cache["last_fetch"]).total_seconds() < calendar_cache["cache_duration"]):
        # Use cached data
        all_data = calendar_cache["data"]
        logger.info(f"Using cached data: {len(all_data)} events")
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
                    for item in raw_data:
                        event_date = item.get("date", "")
                        if event_date:
                            try:
                                from datetime import datetime as dt
                                parsed_date = dt.fromisoformat(event_date.replace('Z', '+00:00'))
                                date_str = parsed_date.strftime("%Y-%m-%d")
                                time_str = parsed_date.strftime("%H:%M")
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
                            "source": "forexfactory"
                        })
                    
                    # Update cache
                    calendar_cache["data"] = all_data
                    calendar_cache["last_fetch"] = now
                    calendar_cache["data_source"] = "live"
                    logger.info(f"Fetched and cached {len(all_data)} events from ForexFactory")
                else:
                    logger.warning(f"ForexFactory API returned {response.status_code}, using sample data")
                    # Provide sample economic calendar data when API is rate-limited
                    all_data = generate_sample_calendar_data()
                    calendar_cache["data"] = all_data
                    calendar_cache["last_fetch"] = now
                    calendar_cache["data_source"] = "sample"
        except Exception as e:
            logger.error(f"Error fetching ForexFactory: {e}")
            # Fallback to sample data
            all_data = generate_sample_calendar_data()
            calendar_cache["data"] = all_data
            calendar_cache["last_fetch"] = now
            calendar_cache["data_source"] = "sample"
    
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


def generate_sample_calendar_data() -> List[dict]:
    """Generate realistic sample economic calendar data for demonstration"""
    today = datetime.now(timezone.utc)
    week_start = today - timedelta(days=today.weekday())
    
    # Major economic events that affect indices and forex
    sample_events = [
        # Monday
        {"day": 0, "time": "09:00", "currency": "EUR", "event": "German Ifo Business Climate", "impact": "high", "forecast": "87.5", "previous": "87.0"},
        {"day": 0, "time": "14:30", "currency": "USD", "event": "Chicago Fed National Activity Index", "impact": "low", "forecast": "0.15", "previous": "0.12"},
        {"day": 0, "time": "15:00", "currency": "EUR", "event": "Consumer Confidence", "impact": "medium", "forecast": "-14.2", "previous": "-14.5"},
        
        # Tuesday  
        {"day": 1, "time": "07:00", "currency": "GBP", "event": "BRC Retail Sales Monitor y/y", "impact": "low", "forecast": "2.1%", "previous": "1.9%"},
        {"day": 1, "time": "10:00", "currency": "USD", "event": "S&P/CS Composite-20 HPI y/y", "impact": "medium", "forecast": "4.5%", "previous": "4.3%"},
        {"day": 1, "time": "15:00", "currency": "USD", "event": "CB Consumer Confidence", "impact": "high", "forecast": "105.0", "previous": "104.1"},
        {"day": 1, "time": "15:00", "currency": "USD", "event": "New Home Sales", "impact": "medium", "forecast": "680K", "previous": "664K"},
        
        # Wednesday
        {"day": 2, "time": "07:00", "currency": "EUR", "event": "German GfK Consumer Climate", "impact": "medium", "forecast": "-22.5", "previous": "-22.4"},
        {"day": 2, "time": "09:30", "currency": "GBP", "event": "MPC Member Speaks", "impact": "medium", "forecast": "", "previous": ""},
        {"day": 2, "time": "13:30", "currency": "USD", "event": "Core Durable Goods Orders m/m", "impact": "high", "forecast": "0.2%", "previous": "0.1%"},
        {"day": 2, "time": "13:30", "currency": "USD", "event": "Durable Goods Orders m/m", "impact": "high", "forecast": "-0.8%", "previous": "0.3%"},
        {"day": 2, "time": "15:30", "currency": "USD", "event": "Crude Oil Inventories", "impact": "low", "forecast": "-2.1M", "previous": "-3.0M"},
        
        # Thursday
        {"day": 3, "time": "07:00", "currency": "EUR", "event": "Spanish Flash CPI y/y", "impact": "medium", "forecast": "2.9%", "previous": "3.0%"},
        {"day": 3, "time": "09:00", "currency": "EUR", "event": "ECB Economic Bulletin", "impact": "medium", "forecast": "", "previous": ""},
        {"day": 3, "time": "13:30", "currency": "USD", "event": "GDP q/q", "impact": "high", "forecast": "3.3%", "previous": "3.2%"},
        {"day": 3, "time": "13:30", "currency": "USD", "event": "Unemployment Claims", "impact": "high", "forecast": "210K", "previous": "213K"},
        {"day": 3, "time": "13:30", "currency": "USD", "event": "Core PCE Price Index q/q", "impact": "high", "forecast": "2.2%", "previous": "2.1%"},
        {"day": 3, "time": "15:00", "currency": "USD", "event": "Pending Home Sales m/m", "impact": "medium", "forecast": "1.5%", "previous": "-4.3%"},
        
        # Friday
        {"day": 4, "time": "00:30", "currency": "JPY", "event": "Tokyo Core CPI y/y", "impact": "high", "forecast": "2.0%", "previous": "1.9%"},
        {"day": 4, "time": "07:00", "currency": "GBP", "event": "Nationwide HPI m/m", "impact": "low", "forecast": "0.3%", "previous": "0.2%"},
        {"day": 4, "time": "09:00", "currency": "EUR", "event": "German Prelim CPI m/m", "impact": "high", "forecast": "0.4%", "previous": "-0.2%"},
        {"day": 4, "time": "10:00", "currency": "EUR", "event": "CPI Flash Estimate y/y", "impact": "high", "forecast": "2.5%", "previous": "2.4%"},
        {"day": 4, "time": "10:00", "currency": "EUR", "event": "Core CPI Flash Estimate y/y", "impact": "high", "forecast": "2.7%", "previous": "2.6%"},
        {"day": 4, "time": "13:30", "currency": "USD", "event": "Core PCE Price Index m/m", "impact": "high", "forecast": "0.3%", "previous": "0.2%"},
        {"day": 4, "time": "13:30", "currency": "USD", "event": "Personal Spending m/m", "impact": "medium", "forecast": "0.5%", "previous": "0.7%"},
        {"day": 4, "time": "13:30", "currency": "USD", "event": "Personal Income m/m", "impact": "medium", "forecast": "0.4%", "previous": "0.3%"},
        {"day": 4, "time": "14:45", "currency": "USD", "event": "Chicago PMI", "impact": "medium", "forecast": "46.5", "previous": "46.0"},
    ]
    
    events = []
    for item in sample_events:
        event_date = (week_start + timedelta(days=item["day"])).strftime("%Y-%m-%d")
        events.append({
            "id": str(uuid.uuid4()),
            "date": event_date,
            "time": item["time"],
            "currency": item["currency"],
            "impact": item["impact"],
            "event": item["event"],
            "actual": None,
            "forecast": item.get("forecast"),
            "previous": item.get("previous"),
            "source": "forexfactory"
        })
    
    logger.info(f"Generated {len(events)} sample calendar events")
    return events

async def fetch_trading_economics_events(date_from: str, date_to: str) -> List[dict]:
    """Fetch economic calendar from Trading Economics via web scraping"""
    events = []
    try:
        url = "https://tradingeconomics.com/calendar"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http_client:
            response = await http_client.get(url, headers=headers)
            logger.info(f"Trading Economics response: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                table = soup.find('table', id='calendar')
                
                if table:
                    rows = table.find_all('tr')
                    current_date = ""
                    
                    for row in rows[1:100]:  # Skip header, limit to 100 rows
                        cells = row.find_all('td')
                        if len(cells) >= 5:
                            # Extract date from first column if present
                            date_cell = cells[0].get_text(strip=True)
                            if date_cell and len(date_cell) > 3:
                                # Try to parse date
                                try:
                                    # Trading Economics format varies
                                    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                                except:
                                    pass
                            
                            time_text = cells[0].get_text(strip=True)[:8]
                            country = cells[1].get_text(strip=True)[:3].upper()
                            event_name = cells[2].get_text(strip=True)
                            
                            # Determine impact based on importance column or styling
                            impact = "medium"
                            importance_cell = cells[3] if len(cells) > 3 else None
                            if importance_cell:
                                imp_text = importance_cell.get_text(strip=True).lower()
                                if 'high' in imp_text or '***' in str(importance_cell):
                                    impact = "high"
                                elif 'low' in imp_text or '*' in str(importance_cell):
                                    impact = "low"
                            
                            # Filter for relevant currencies (USD, EUR, GBP for indices focus)
                            if country in ['USD', 'EUR', 'GBP', 'US', 'EU', 'UK', 'DE', 'FR']:
                                events.append({
                                    "id": str(uuid.uuid4()),
                                    "date": current_date or date_from,
                                    "time": time_text,
                                    "currency": country,
                                    "impact": impact,
                                    "event": event_name,
                                    "actual": None,
                                    "forecast": cells[4].get_text(strip=True) if len(cells) > 4 else None,
                                    "previous": cells[5].get_text(strip=True) if len(cells) > 5 else None,
                                    "source": "tradingeconomics"
                                })
                    
                    logger.info(f"Got {len(events)} events from Trading Economics")
                else:
                    logger.warning("Trading Economics calendar table not found")
                    
    except Exception as e:
        logger.error(f"Error fetching Trading Economics: {e}")
    
    return events

async def get_ai_analysis(events: List[dict], target_date: str) -> TradingSignal:
    """Use GPT-5.2 to analyze trading conditions for a given date"""
    api_key = os.environ.get('EMERGENT_LLM_KEY')
    
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
{event_summary if event_summary else "No events scheduled"}

High Impact Events Count: {len(high_impact)}

Based on these events, provide:
1. Overall trading signal: TRADE (green - good day to trade), CAUTION (yellow - trade with reduced risk), or AVOID (red - stay out)
2. Probability score (0-100) for successful trading
3. Brief summary (1-2 sentences)
4. 3 key reasoning points
5. Recommended action

Respond in this exact JSON format:
{{
    "signal": "trade|caution|avoid",
    "probability": 75,
    "summary": "Brief market outlook",
    "reasoning": ["point 1", "point 2", "point 3"],
    "recommended_action": "Specific recommendation"
}}"""

        chat = LlmChat(
            api_key=api_key,
            session_id=f"analysis-{target_date}-{uuid.uuid4()}",
            system_message="You are a professional forex and indices trading analyst. Provide concise, actionable analysis based on economic calendar events. Always respond in valid JSON format."
        ).with_model("openai", "gpt-5.2")
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse the JSON response
        import json
        # Clean up response - find JSON in the response
        response_text = response.strip()
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        analysis = json.loads(response_text)
        
        return TradingSignal(
            date=target_date,
            signal=analysis.get("signal", "caution"),
            probability=min(100, max(0, int(analysis.get("probability", 50)))),
            summary=analysis.get("summary", "Analysis unavailable"),
            reasoning=analysis.get("reasoning", [])[:3],
            high_impact_events=[e.get("event", "") for e in high_impact[:5]],
            recommended_action=analysis.get("recommended_action", "Trade with caution")
        )
        
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return generate_rule_based_analysis(events, target_date)

def generate_rule_based_analysis(events: List[dict], target_date: str) -> TradingSignal:
    """Fallback rule-based analysis when AI is unavailable"""
    date_events = [e for e in events if target_date in e.get("date", "")]
    high_impact = [e for e in date_events if e.get("impact") == "high"]
    medium_impact = [e for e in date_events if e.get("impact") == "medium"]
    
    # Simple rule-based scoring
    high_count = len(high_impact)
    
    if high_count >= 4:
        signal = "avoid"
        probability = 25
        summary = f"High volatility expected with {high_count} major economic releases. Consider staying out of the market."
        action = "Avoid trading or significantly reduce position sizes"
    elif high_count >= 2:
        signal = "caution"
        probability = 55
        summary = f"Moderate volatility expected with {high_count} high-impact events. Trade with reduced risk."
        action = "Trade with smaller position sizes and wider stops"
    else:
        signal = "trade"
        probability = 80 - (len(medium_impact) * 5)
        summary = "Low volatility day with minimal high-impact news. Good conditions for trading."
        action = "Normal trading with standard risk management"
    
    reasoning = []
    if high_count > 0:
        reasoning.append(f"{high_count} high-impact economic event(s) scheduled")
    if len(medium_impact) > 0:
        reasoning.append(f"{len(medium_impact)} medium-impact event(s) may cause price fluctuations")
    if len(date_events) == 0:
        reasoning.append("No major economic events scheduled - lower volatility expected")
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
    """Get combined economic calendar from ForexFactory and Investing.com"""
    # Default to current week
    today = datetime.now(timezone.utc)
    if not date_from:
        # Start from Monday of current week
        start_of_week = today - timedelta(days=today.weekday())
        date_from = start_of_week.strftime("%Y-%m-%d")
    if not date_to:
        # End on Friday of current week
        end_of_week = today + timedelta(days=(4 - today.weekday()))
        date_to = end_of_week.strftime("%Y-%m-%d")
    
    # Fetch from both sources concurrently
    ff_events, inv_events = await asyncio.gather(
        fetch_forexfactory_events(date_from, date_to),
        fetch_investing_events(date_from, date_to)
    )
    
    all_events = ff_events + inv_events
    
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
    
    # Fetch events for the date
    events = await fetch_forexfactory_events(date, date)
    inv_events = await fetch_investing_events(date, date)
    all_events = events + inv_events
    
    # Get AI analysis
    analysis = await get_ai_analysis(all_events, date)
    
    return analysis

@api_router.get("/week-overview", response_model=WeekOverview)
async def get_week_overview(
    week_offset: int = Query(default=0, description="Week offset from current week")
):
    """Get trading overview for an entire week"""
    today = datetime.now(timezone.utc)
    
    # Calculate week start (Monday)
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=4)  # Friday
    
    date_from = week_start.strftime("%Y-%m-%d")
    date_to = week_end.strftime("%Y-%m-%d")
    
    # Fetch all events for the week
    ff_events, inv_events = await asyncio.gather(
        fetch_forexfactory_events(date_from, date_to),
        fetch_investing_events(date_from, date_to)
    )
    all_events = ff_events + inv_events
    
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
                best_days.append(day_names[i])
        
        days.append(DayAnalysis(
            date=day_date,
            day_name=day_names[i],
            signal=signal,
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
        "is_live": calendar_cache.get("data_source") == "live"
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
