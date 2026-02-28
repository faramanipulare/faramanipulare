# TradeSignal AI - Product Requirements Document

## Original Problem Statement
Build a website that takes high impact news from investing.com and forexfactory economic calendar and integrate with AI robot that shows which days are ok/high probability to trade and which to avoid.

## User Choices
1. AI: Emergent LLM key (GPT-5.2, no API key needed)
2. Data: Both ForexFactory + Investing.com combined
3. Display: Color-coded signals + probability percentages
4. Focus: Indices + GBPUSD + EURUSD
5. Public dashboard (no authentication)

## User Personas
- **Primary**: Forex/Indices traders who want to optimize trading days based on economic events
- **Secondary**: New traders learning market impact of economic releases

## Core Requirements (Static)
- Economic calendar aggregation from multiple sources
- AI-powered trading day analysis with probability scores
- Color-coded signals (Green=Trade, Yellow=Caution, Red=Avoid)
- Daily/Weekly view of trading conditions
- Market/Currency filters

## Architecture
### Backend (FastAPI)
- `/api/calendar` - Economic events with filters
- `/api/analyze` - AI analysis for specific date
- `/api/week-overview` - Weekly trading overview
- Data source: FairEconomy API (ForexFactory) with sample data fallback
- AI: GPT-5.2 via Emergent integrations

### Frontend (React)
- Dark theme professional trading aesthetic
- Components: Header, AIAnalysisCard, WeekOverview, EventsTable, MarketFilter
- Libraries: Tailwind CSS, Shadcn UI, Lucide icons

## What's Been Implemented (Feb 28, 2026)
- [x] Backend API with 4 endpoints (calendar, analyze, week-overview, data-status)
- [x] AI integration with GPT-5.2 for trading analysis
- [x] Economic calendar with ForexFactory data + sample fallback
- [x] **Calendar grouped by date** with sticky date headers (e.g., "Mon, Feb 23 (Monday)")
- [x] Week overview with day-by-day signals
- [x] **Day card click updates AI Analysis** to show that specific day
- [x] **Data source indicator** in header (Live Data / Sample Data)
- [x] Market filters (All, Indices, GBP/USD, EUR/USD)
- [x] Impact filters (All, High, Medium, Low)
- [x] Professional dark theme UI with formatted dates
- [x] All tests passing (100% backend, 90%+ frontend)

## Prioritized Backlog
### P0 (Critical)
- [x] Core calendar display - DONE
- [x] AI analysis integration - DONE
- [x] Basic filtering - DONE

### P1 (Important)
- [ ] Real-time ForexFactory API integration (when rate limits allow)
- [ ] Investing.com data integration via investpy
- [ ] Push notifications for high-impact events

### P2 (Nice to Have)
- [ ] Historical analysis view
- [ ] Save favorite currencies
- [ ] Email alerts
- [ ] Mobile app

## Next Tasks
1. Monitor and implement real ForexFactory API when rate limits reset
2. Add Investing.com data source via investpy library
3. Add push notifications for upcoming high-impact events
4. Consider adding historical analysis and backtesting features
