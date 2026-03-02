import { useState, useEffect, useCallback } from "react";
import "@/App.css";
import axios from "axios";
import { format, addDays, startOfWeek, parseISO, formatDistanceToNow } from "date-fns";
import { 
  TrendingUp, 
  AlertTriangle, 
  XCircle, 
  Calendar as CalendarIcon, 
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Activity,
  Target,
  Zap,
  Clock,
  Globe,
  BarChart3,
  Brain,
  Newspaper,
  ExternalLink
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";

const RAW_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const BACKEND_URL = (
  RAW_BACKEND_URL &&
  !["undefined", "null", ""].includes(String(RAW_BACKEND_URL).toLowerCase())
)
  ? String(RAW_BACKEND_URL).replace(/\/$/, "")
  : (typeof window !== "undefined" ? window.location.origin : "");
const API = `${BACKEND_URL}/api`;

// Signal Icon Component
const SignalIcon = ({ signal, size = 20 }) => {
  if (signal === "trade") return <TrendingUp size={size} className="text-emerald-400" />;
  if (signal === "caution") return <AlertTriangle size={size} className="text-amber-400" />;
  return <XCircle size={size} className="text-red-400" />;
};

// Impact Badge Component
const ImpactBadge = ({ impact }) => {
  const classes = {
    high: "impact-high",
    medium: "impact-medium",
    low: "impact-low"
  };
  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${classes[impact] || classes.low}`}>
      {impact?.toUpperCase() || "LOW"}
    </span>
  );
};

// Source Badge Component
const SourceBadge = ({ source }) => {
  const isFF = source === "forexfactory";
  const isTE = source === "tradingeconomics" || source === "tradingeconomics_fallback";
  
  let className = "source-ff";  // Default ForexFactory orange
  let label = "FF";
  
  if (isTE) {
    className = "source-te";
    label = "TE";
  } else if (!isFF) {
    className = "source-inv";
    label = "INV";
  }
  
  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${className}`}>
      {label}
    </span>
  );
};

// Header Component
const Header = ({ dataStatus, roNow }) => {
  const lastFetchText = (() => {
    if (!dataStatus?.last_fetch) return "never";
    try {
      return formatDistanceToNow(parseISO(dataStatus.last_fetch), { addSuffix: true });
    } catch {
      return "invalid";
    }
  })();

  const roTimeNow = new Intl.DateTimeFormat("ro-RO", {
    timeZone: "Europe/Bucharest",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(roNow);

  const lastFetchRoTime = (() => {
    if (!dataStatus?.last_fetch) return "n/a";
    try {
      return new Intl.DateTimeFormat("ro-RO", {
        timeZone: "Europe/Bucharest",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
      }).format(parseISO(dataStatus.last_fetch));
    } catch {
      return "n/a";
    }
  })();

  return (
    <header className="header-glass px-6 py-4" data-testid="header">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center signal-trade">
          <BarChart3 size={22} className="text-white" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-zinc-50 tracking-tight">TradeSignal AI</h1>
          <p className="text-xs text-zinc-500">Forex & Indices Intelligence</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {/* Data source indicator */}
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${
          dataStatus?.is_live 
            ? "bg-emerald-500/10 border-emerald-500/30" 
            : "bg-amber-500/10 border-amber-500/30"
        }`}>
          <span className={`w-2 h-2 rounded-full ${dataStatus?.is_live ? "bg-emerald-500" : "bg-amber-500"} pulse-glow`}></span>
          <span className={`text-xs font-medium ${dataStatus?.is_live ? "text-emerald-400" : "text-amber-400"}`}>
            {dataStatus?.is_live ? "Live Data" : "Sample Data"}
          </span>
        </div>
        <div className="text-right">
          <p className="text-[11px] text-zinc-500">RO {roTimeNow}</p>
          <p className="text-[11px] text-zinc-500">Last calendar update {lastFetchText}</p>
          <p className="text-[10px] text-zinc-600">{lastFetchRoTime} (Europe/Bucharest)</p>
          <p className="text-[10px] text-zinc-600">Auto refresh {dataStatus?.refresh_interval_minutes || 30}m</p>
        </div>
      </div>
    </div>
    </header>
  );
};

// AI Analysis Card Component
const AIAnalysisCard = ({ analysis, loading, onRefresh }) => {
  if (loading) {
    return (
      <div className="ai-card rounded-xl border border-zinc-800 bg-zinc-900/50 p-6" data-testid="ai-analysis-loading">
        <div className="flex items-center justify-center h-64">
          <div className="spinner"></div>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="ai-card rounded-xl border border-zinc-800 bg-zinc-900/50 p-6" data-testid="ai-analysis-empty">
        <div className="text-center py-12">
          <Brain className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
          <p className="text-zinc-400">Select a date to get AI analysis</p>
        </div>
      </div>
    );
  }

  const signalColors = {
    trade: "text-emerald-400 border-emerald-500/30",
    caution: "text-amber-400 border-amber-500/30",
    avoid: "text-red-400 border-red-500/30"
  };

  const signalBg = {
    trade: "bg-emerald-500/10",
    caution: "bg-amber-500/10",
    avoid: "bg-red-500/10"
  };

  // Format date for display
  const getFormattedDate = () => {
    try {
      const date = parseISO(analysis.date);
      return format(date, "EEEE, MMMM d, yyyy");
    } catch {
      return analysis.date;
    }
  };

  return (
    <div className={`ai-card rounded-xl border bg-zinc-900/50 p-6 ${signalColors[analysis.signal]} signal-${analysis.signal}`} data-testid="ai-analysis-card">
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-xl ${signalBg[analysis.signal]}`}>
            <Brain size={24} className={signalColors[analysis.signal].split(" ")[0]} />
          </div>
          <div>
            <h2 className="font-heading text-lg font-bold text-zinc-100">AI Analysis</h2>
            <p className="text-sm text-indigo-400 font-medium">{getFormattedDate()}</p>
          </div>
        </div>
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={onRefresh}
          className="text-zinc-400 hover:text-zinc-100"
          data-testid="refresh-analysis-btn"
        >
          <RefreshCw size={18} />
        </Button>
      </div>

      {/* Signal Status */}
      <div className={`rounded-lg p-4 mb-6 ${signalBg[analysis.signal]}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`signal-indicator ${analysis.signal}`}></div>
            <span className={`font-heading text-2xl font-bold uppercase ${signalColors[analysis.signal].split(" ")[0]}`}>
              {analysis.signal}
            </span>
          </div>
          <div className="text-right">
            <span className="font-mono text-3xl font-bold text-zinc-100">{analysis.probability}%</span>
            <p className="text-xs text-zinc-500">Success Probability</p>
          </div>
        </div>
        <div className="probability-bar">
          <div 
            className={`probability-fill ${analysis.signal}`} 
            style={{ width: `${analysis.probability}%` }}
          ></div>
        </div>
      </div>

      {/* Summary */}
      <div className="mb-6">
        <h3 className="text-sm font-medium text-zinc-400 mb-2">Market Outlook</h3>
        <p className="text-zinc-200 leading-relaxed">{analysis.summary}</p>
      </div>

      {/* Reasoning */}
      <div className="mb-6">
        <h3 className="text-sm font-medium text-zinc-400 mb-3">Key Factors</h3>
        <ul className="space-y-2">
          {analysis.reasoning?.map((reason, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-zinc-300">
              <Zap size={14} className="text-indigo-400 mt-1 flex-shrink-0" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* High Impact Events */}
      {analysis.high_impact_events?.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-zinc-400 mb-3">High Impact Events</h3>
          <div className="flex flex-wrap gap-2">
            {analysis.high_impact_events.map((event, idx) => (
              <Badge key={idx} variant="outline" className="border-red-500/30 text-red-400 bg-red-500/10">
                {event}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Recommended Action */}
      <div className="p-4 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
        <div className="flex items-center gap-2 mb-2">
          <Target size={16} className="text-indigo-400" />
          <h3 className="text-sm font-medium text-zinc-300">Recommended Action</h3>
        </div>
        <p className="text-zinc-100 font-medium">{analysis.recommended_action}</p>
      </div>
    </div>
  );
};

// Week Overview Component
const WeekOverview = ({ weekData, loading, onDaySelect }) => {
  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6" data-testid="week-overview-loading">
        <div className="h-32 flex items-center justify-center">
          <div className="spinner"></div>
        </div>
      </div>
    );
  }

  if (!weekData) return null;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6" data-testid="week-overview">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-heading text-lg font-bold text-zinc-100">Week Overview</h2>
        <Badge 
          variant="outline" 
          className={`
            ${weekData.overall_signal === "trade" ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10" : ""}
            ${weekData.overall_signal === "caution" ? "border-amber-500/30 text-amber-400 bg-amber-500/10" : ""}
            ${weekData.overall_signal === "avoid" ? "border-red-500/30 text-red-400 bg-red-500/10" : ""}
          `}
        >
          {weekData.overall_signal?.toUpperCase()}
        </Badge>
      </div>

      <div className="grid grid-cols-5 gap-3">
        {weekData.days?.map((day) => (
          <button
            key={day.date}
            onClick={() => onDaySelect(day.date)}
            className={`day-card ${day.signal} p-3 rounded-lg border border-zinc-700/50 bg-zinc-800/30 text-left`}
            data-testid={`day-card-${day.day_name.toLowerCase()}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <SignalIcon signal={day.signal} size={14} />
              <span className="text-xs font-medium text-zinc-300">{day.day_name?.substring(0, 3)}</span>
            </div>
            <div className="font-mono text-lg font-bold text-zinc-100">{day.probability}%</div>
            <div className="flex items-center gap-1 mt-1">
              <span className="text-xs text-zinc-500">{day.high_impact_count}</span>
              <AlertTriangle size={10} className="text-red-400" />
            </div>
          </button>
        ))}
      </div>

      {weekData.best_trading_days?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-zinc-800">
          <div className="flex items-center gap-2 text-sm">
            <TrendingUp size={14} className="text-emerald-400" />
            <span className="text-zinc-400">Best days:</span>
            <span className="text-emerald-400 font-medium">{weekData.best_trading_days.join(", ")}</span>
          </div>
        </div>
      )}
    </div>
  );
};

// Calendar Events Table Component - Now grouped by date
const EventsTable = ({ events, loading }) => {
  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6" data-testid="events-loading">
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 skeleton rounded-lg"></div>
          ))}
        </div>
      </div>
    );
  }

  // Group events by date
  const groupedEvents = {};
  events?.forEach(event => {
    const date = event.date || "Unknown";
    if (!groupedEvents[date]) {
      groupedEvents[date] = [];
    }
    groupedEvents[date].push(event);
  });

  // Sort dates and events within each date by time
  const sortedDates = Object.keys(groupedEvents).sort();
  sortedDates.forEach(date => {
    groupedEvents[date].sort((a, b) => (a.time || "").localeCompare(b.time || ""));
  });

  // Format date for display
  const formatDateDisplay = (dateStr) => {
    try {
      const date = parseISO(dateStr);
      return format(date, "EEE, MMM d");
    } catch {
      return dateStr;
    }
  };

  // Get day name
  const getDayName = (dateStr) => {
    try {
      const date = parseISO(dateStr);
      return format(date, "EEEE");
    } catch {
      return "";
    }
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50" data-testid="events-table">
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-lg font-bold text-zinc-100">Economic Calendar</h2>
          <Badge variant="outline" className="border-zinc-700 text-zinc-400">
            {events?.length || 0} Events
          </Badge>
        </div>
      </div>

      <ScrollArea className="h-[400px]">
        <div className="p-2">
          {events?.length === 0 ? (
            <div className="text-center py-12">
              <CalendarIcon className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <p className="text-zinc-400">No events found</p>
            </div>
          ) : (
            <div className="space-y-4">
              {sortedDates.map((date) => (
                <div key={date} className="space-y-1">
                  {/* Date Header */}
                  <div className="sticky top-0 z-10 bg-zinc-900/95 backdrop-blur-sm py-2 px-3 rounded-lg border border-zinc-800/50 mb-2">
                    <div className="flex items-center gap-3">
                      <CalendarIcon size={14} className="text-indigo-400" />
                      <span className="font-heading font-semibold text-zinc-100">{formatDateDisplay(date)}</span>
                      <span className="text-xs text-zinc-500">({getDayName(date)})</span>
                      <Badge variant="outline" className="ml-auto border-zinc-700 text-zinc-500 text-xs">
                        {groupedEvents[date].length} events
                      </Badge>
                    </div>
                  </div>
                  
                  {/* Events for this date */}
                  <table className="w-full">
                    <thead>
                      <tr className="text-xs text-zinc-500 border-b border-zinc-800">
                        <th className="text-left py-2 px-3 font-medium w-20">Time</th>
                        <th className="text-left py-2 px-3 font-medium w-20">Currency</th>
                        <th className="text-left py-2 px-3 font-medium">Event</th>
                        <th className="text-center py-2 px-3 font-medium w-20">Impact</th>
                        <th className="text-center py-2 px-3 font-medium w-16">Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {groupedEvents[date].map((event) => (
                        <tr 
                          key={event.id} 
                          className="table-row-hover border-b border-zinc-800/30 last:border-0"
                          data-testid={`event-row-${event.id}`}
                        >
                          <td className="py-2.5 px-3">
                            <div className="flex items-center gap-1.5">
                              <Clock size={11} className="text-zinc-500" />
                              <span className="font-mono text-sm text-zinc-300">{event.time || "TBA"}</span>
                            </div>
                          </td>
                          <td className="py-2.5 px-3">
                            <div className="flex items-center gap-1.5">
                              <Globe size={11} className="text-zinc-500" />
                              <span className="text-sm font-medium text-zinc-200">{event.currency}</span>
                            </div>
                          </td>
                          <td className="py-2.5 px-3">
                            <span className="text-sm text-zinc-300 line-clamp-1">{event.event}</span>
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            <ImpactBadge impact={event.impact} />
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            <SourceBadge source={event.source} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

// Market News Component
const MarketNews = ({ news, loading }) => {
  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6" data-testid="news-loading">
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 skeleton rounded-lg"></div>
          ))}
        </div>
      </div>
    );
  }

  const formatNewsTime = (isoString) => {
    try {
      const date = parseISO(isoString);
      return formatDistanceToNow(date, { addSuffix: true });
    } catch {
      return "";
    }
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50" data-testid="market-news">
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Newspaper size={18} className="text-indigo-400" />
            <h2 className="font-heading text-lg font-bold text-zinc-100">Market News</h2>
          </div>
          <Badge variant="outline" className="border-indigo-500/30 text-indigo-400 bg-indigo-500/10">
            Finnhub
          </Badge>
        </div>
      </div>

      <ScrollArea className="h-[280px]">
        <div className="p-3 space-y-3">
          {news?.length === 0 ? (
            <div className="text-center py-8">
              <Newspaper className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-400 text-sm">No news available</p>
            </div>
          ) : (
            news?.map((item) => (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-3 rounded-lg bg-zinc-800/30 border border-zinc-700/30 hover:border-zinc-600/50 hover:bg-zinc-800/50 transition-all group"
                data-testid={`news-item-${item.id}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-medium text-zinc-200 line-clamp-2 group-hover:text-zinc-50">
                    {item.headline}
                  </h3>
                  <ExternalLink size={14} className="text-zinc-500 flex-shrink-0 mt-0.5 group-hover:text-indigo-400" />
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-xs text-indigo-400 font-medium">{item.source}</span>
                  <span className="text-xs text-zinc-500">{formatNewsTime(item.datetime)}</span>
                </div>
              </a>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

// Market Filter Component
const MarketFilter = ({ selected, onChange }) => {
  const markets = [
    { id: "all", label: "All Markets", icon: Globe },
    { id: "indices", label: "Indices", icon: BarChart3 },
    { id: "gbpusd", label: "GBP/USD", icon: Activity },
    { id: "eurusd", label: "EUR/USD", icon: Activity }
  ];

  return (
    <div className="flex flex-wrap gap-2" data-testid="market-filter">
      {markets.map((market) => {
        const Icon = market.icon;
        return (
          <button
            key={market.id}
            onClick={() => onChange(market.id)}
            className={`filter-btn flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium
              ${selected === market.id 
                ? "active border-indigo-500/40" 
                : "border-zinc-700/50 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600"
              }`}
            data-testid={`filter-${market.id}`}
          >
            <Icon size={14} />
            {market.label}
          </button>
        );
      })}
    </div>
  );
};

// Main App Component
function App() {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [weekOffset, setWeekOffset] = useState(0);
  const [marketFilter, setMarketFilter] = useState("all");
  const [impactFilter, setImpactFilter] = useState("all");
  
  const [analysis, setAnalysis] = useState(null);
  const [weekData, setWeekData] = useState(null);
  const [events, setEvents] = useState([]);
  const [news, setNews] = useState([]);
  const [dataStatus, setDataStatus] = useState({ is_live: false, data_source: "loading" });
  const [roNow, setRoNow] = useState(new Date());
  
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [loadingWeek, setLoadingWeek] = useState(false);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [loadingNews, setLoadingNews] = useState(false);

  const formatDateParam = (date) => format(date, "yyyy-MM-dd");

  const fetchDataStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/data-status`);
      setDataStatus(response.data);
    } catch (error) {
      console.error("Error fetching data status:", error);
    }
  }, []);

  const fetchNews = useCallback(async () => {
    setLoadingNews(true);
    try {
      const response = await axios.get(`${API}/market-news`, {
        params: { category: "general" }
      });
      setNews(response.data);
    } catch (error) {
      console.error("Error fetching news:", error);
    } finally {
      setLoadingNews(false);
    }
  }, []);

  const fetchAnalysis = useCallback(async (date) => {
    setLoadingAnalysis(true);
    try {
      const response = await axios.get(`${API}/analyze`, {
        params: { date: formatDateParam(date) }
      });
      setAnalysis(response.data);
    } catch (error) {
      console.error("Error fetching analysis:", error);
      toast.error("Failed to fetch AI analysis");
    } finally {
      setLoadingAnalysis(false);
    }
  }, []);

  const fetchWeekOverview = useCallback(async (offset) => {
    setLoadingWeek(true);
    try {
      const response = await axios.get(`${API}/week-overview`, {
        params: { week_offset: offset }
      });
      setWeekData(response.data);
    } catch (error) {
      console.error("Error fetching week overview:", error);
      toast.error("Failed to fetch week overview");
    } finally {
      setLoadingWeek(false);
    }
  }, []);

  const fetchEvents = useCallback(async (dateFrom, dateTo, market, impact) => {
    setLoadingEvents(true);
    try {
      const response = await axios.get(`${API}/calendar`, {
        params: {
          date_from: dateFrom,
          date_to: dateTo,
          market,
          impact
        }
      });
      setEvents(response.data);
    } catch (error) {
      console.error("Error fetching events:", error);
      toast.error("Failed to fetch calendar events");
    } finally {
      setLoadingEvents(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchAnalysis(selectedDate);
    fetchWeekOverview(weekOffset);
    fetchDataStatus();
    fetchNews();
  }, []);

  // Keep status fresh in UI (for "last update" timer text)
  useEffect(() => {
    const intervalId = setInterval(() => {
      fetchDataStatus();
    }, 60 * 1000);

    return () => clearInterval(intervalId);
  }, [fetchDataStatus]);



  // RO clock in header
  useEffect(() => {
    const clockId = setInterval(() => {
      setRoNow(new Date());
    }, 1000);

    return () => clearInterval(clockId);
  }, []);
  // Fetch events when filters change
  useEffect(() => {
    // If weekend (Sat=6, Sun=0), use next week's Monday
    const today = new Date();
    const dayOfWeek = today.getDay(); // 0=Sun, 6=Sat
    
    let baseMonday;
    if (dayOfWeek === 0 || dayOfWeek === 6) {
      // Weekend - use next Monday
      const daysUntilMonday = dayOfWeek === 0 ? 1 : 8 - dayOfWeek;
      baseMonday = addDays(today, daysUntilMonday);
    } else {
      // Weekday - use this week's Monday
      baseMonday = startOfWeek(today, { weekStartsOn: 1 });
    }
    
    const offsetWeekStart = addDays(baseMonday, weekOffset * 7);
    const weekEnd = addDays(offsetWeekStart, 4);
    
    fetchEvents(
      formatDateParam(offsetWeekStart),
      formatDateParam(weekEnd),
      marketFilter,
      impactFilter
    );
    // Also update data status when events change
    fetchDataStatus();
  }, [weekOffset, marketFilter, impactFilter, fetchEvents, fetchDataStatus]);

  const handleDateSelect = (date) => {
    if (date) {
      setSelectedDate(date);
      fetchAnalysis(date);
    }
  };

  const handleDayCardSelect = (dateStr) => {
    const date = parseISO(dateStr);
    setSelectedDate(date);
    fetchAnalysis(date);
  };

  const handleWeekChange = (direction) => {
    const newOffset = weekOffset + direction;
    setWeekOffset(newOffset);
    fetchWeekOverview(newOffset);
  };

  const handleRefreshAnalysis = () => {
    fetchAnalysis(selectedDate);
  };

  return (
    <div className="min-h-screen bg-zinc-950 grid-texture" data-testid="app-container">
      <Header dataStatus={dataStatus} roNow={roNow} />
      <Toaster position="top-right" />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Top Controls */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-8 fade-in">
          <div className="flex items-center gap-4">
            <Popover>
              <PopoverTrigger asChild>
                <Button 
                  variant="outline" 
                  className="bg-zinc-800/50 border-zinc-700 hover:bg-zinc-700/50 hover:border-zinc-600"
                  data-testid="date-picker-btn"
                >
                  <CalendarIcon size={16} className="mr-2" />
                  {format(selectedDate, "MMM d, yyyy")}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0 bg-zinc-900 border-zinc-700" align="start">
                <Calendar
                  mode="single"
                  selected={selectedDate}
                  onSelect={handleDateSelect}
                  initialFocus
                  className="bg-zinc-900"
                />
              </PopoverContent>
            </Popover>

            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleWeekChange(-1)}
                className="text-zinc-400 hover:text-zinc-100"
                data-testid="prev-week-btn"
              >
                <ChevronLeft size={20} />
              </Button>
              <span className="text-sm text-zinc-400 min-w-[100px] text-center">
                {weekOffset === 0 ? "This Week" : weekOffset > 0 ? `+${weekOffset} Week` : `${weekOffset} Week`}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleWeekChange(1)}
                className="text-zinc-400 hover:text-zinc-100"
                data-testid="next-week-btn"
              >
                <ChevronRight size={20} />
              </Button>
            </div>
          </div>

          <MarketFilter selected={marketFilter} onChange={setMarketFilter} />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* AI Analysis - Left Column */}
          <div className="lg:col-span-5 space-y-6 fade-in stagger-1">
            <AIAnalysisCard 
              analysis={analysis} 
              loading={loadingAnalysis} 
              onRefresh={handleRefreshAnalysis}
            />
          </div>

          {/* Right Column */}
          <div className="lg:col-span-7 space-y-6 fade-in stagger-2">
            {/* Week Overview */}
            <WeekOverview 
              weekData={weekData} 
              loading={loadingWeek}
              onDaySelect={handleDayCardSelect}
            />

            {/* Impact Filter Tabs */}
            <Tabs defaultValue="all" value={impactFilter} onValueChange={setImpactFilter}>
              <TabsList className="bg-zinc-800/50 border border-zinc-700/50">
                <TabsTrigger value="all" className="data-[state=active]:bg-zinc-700" data-testid="impact-all">All</TabsTrigger>
                <TabsTrigger value="high" className="data-[state=active]:bg-red-500/20 data-[state=active]:text-red-400" data-testid="impact-high">High</TabsTrigger>
                <TabsTrigger value="medium" className="data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400" data-testid="impact-medium">Medium</TabsTrigger>
                <TabsTrigger value="low" className="data-[state=active]:bg-emerald-500/20 data-[state=active]:text-emerald-400" data-testid="impact-low">Low</TabsTrigger>
              </TabsList>
            </Tabs>

            {/* Events Table */}
            <EventsTable events={events} loading={loadingEvents} />
          </div>
        </div>

        {/* Market News Section - Full Width */}
        <div className="mt-6 fade-in stagger-3">
          <MarketNews news={news} loading={loadingNews} />
        </div>

        {/* Footer */}
        <footer className="mt-12 pt-8 border-t border-zinc-800">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-zinc-500">
            <p>Data sources: ForexFactory, Trading Economics, Finnhub</p>
            <p className="flex items-center gap-2">
              <Brain size={14} />
              AI powered by Groq (Llama 3.3)
            </p>
          </div>
        </footer>
      </main>
    </div>
  );
}

export default App;
diff --git a/frontend/src/App.js b/frontend/src/App.js
index 0e2e5b85671938797981b253aeb1ac9093b25bab..10507b49b0453b9ccf242ec56b0019c8396d0bc7 100644
--- a/frontend/src/App.js
+++ b/frontend/src/App.js
@@ -34,99 +34,132 @@ const API = `${BACKEND_URL}/api`;
 
 // Signal Icon Component
 const SignalIcon = ({ signal, size = 20 }) => {
   if (signal === "trade") return <TrendingUp size={size} className="text-emerald-400" />;
   if (signal === "caution") return <AlertTriangle size={size} className="text-amber-400" />;
   return <XCircle size={size} className="text-red-400" />;
 };
 
 // Impact Badge Component
 const ImpactBadge = ({ impact }) => {
   const classes = {
     high: "impact-high",
     medium: "impact-medium",
     low: "impact-low"
   };
   return (
     <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${classes[impact] || classes.low}`}>
       {impact?.toUpperCase() || "LOW"}
     </span>
   );
 };
 
 // Source Badge Component
 const SourceBadge = ({ source }) => {
   const isFF = source === "forexfactory";
-  const isTE = source === "tradingeconomics";
+  const isTE = source === "tradingeconomics" || source === "tradingeconomics_fallback";
   
   let className = "source-ff";  // Default ForexFactory orange
   let label = "FF";
   
   if (isTE) {
     className = "source-te";
     label = "TE";
   } else if (!isFF) {
     className = "source-inv";
     label = "INV";
   }
   
   return (
     <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${className}`}>
       {label}
     </span>
   );
 };
 
 // Header Component
-const Header = ({ dataStatus }) => (
-  <header className="header-glass px-6 py-4" data-testid="header">
-    <div className="max-w-7xl mx-auto flex items-center justify-between">
+const Header = ({ dataStatus, roNow }) => {
+  const lastFetchText = dataStatus?.last_fetch
+    ? formatDistanceToNow(parseISO(dataStatus.last_fetch), { addSuffix: true })
+    : "never";
+
+  const roTimeNow = new Intl.DateTimeFormat("ro-RO", {
+    timeZone: "Europe/Bucharest",
+    hour: "2-digit",
+    minute: "2-digit",
+    second: "2-digit",
+    hour12: false
+  }).format(roNow);
+
+  const lastFetchRoTime = dataStatus?.last_fetch
+    ? new Intl.DateTimeFormat("ro-RO", {
+        timeZone: "Europe/Bucharest",
+        day: "2-digit",
+        month: "2-digit",
+        year: "numeric",
+        hour: "2-digit",
+        minute: "2-digit",
+        second: "2-digit",
+        hour12: false
+      }).format(parseISO(dataStatus.last_fetch))
+    : "n/a";
+
+  return (
+    <header className="header-glass px-6 py-4" data-testid="header">
+      <div className="max-w-7xl mx-auto flex items-center justify-between">
       <div className="flex items-center gap-3">
         <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center signal-trade">
           <BarChart3 size={22} className="text-white" />
         </div>
         <div>
           <h1 className="font-heading text-xl font-bold text-zinc-50 tracking-tight">TradeSignal AI</h1>
           <p className="text-xs text-zinc-500">Forex & Indices Intelligence</p>
         </div>
       </div>
       <div className="flex items-center gap-3">
         {/* Data source indicator */}
         <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${
           dataStatus?.is_live 
             ? "bg-emerald-500/10 border-emerald-500/30" 
             : "bg-amber-500/10 border-amber-500/30"
         }`}>
           <span className={`w-2 h-2 rounded-full ${dataStatus?.is_live ? "bg-emerald-500" : "bg-amber-500"} pulse-glow`}></span>
           <span className={`text-xs font-medium ${dataStatus?.is_live ? "text-emerald-400" : "text-amber-400"}`}>
             {dataStatus?.is_live ? "Live Data" : "Sample Data"}
           </span>
         </div>
+        <div className="text-right">
+          <p className="text-[11px] text-zinc-500">RO {roTimeNow}</p>
+          <p className="text-[11px] text-zinc-500">Last calendar update {lastFetchText}</p>
+          <p className="text-[10px] text-zinc-600">{lastFetchRoTime} (Europe/Bucharest)</p>
+          <p className="text-[10px] text-zinc-600">Auto refresh {dataStatus?.refresh_interval_minutes || 30}m</p>
+        </div>
       </div>
     </div>
-  </header>
-);
+    </header>
+  );
+};
 
 // AI Analysis Card Component
 const AIAnalysisCard = ({ analysis, loading, onRefresh }) => {
   if (loading) {
     return (
       <div className="ai-card rounded-xl border border-zinc-800 bg-zinc-900/50 p-6" data-testid="ai-analysis-loading">
         <div className="flex items-center justify-center h-64">
           <div className="spinner"></div>
         </div>
       </div>
     );
   }
 
   if (!analysis) {
     return (
       <div className="ai-card rounded-xl border border-zinc-800 bg-zinc-900/50 p-6" data-testid="ai-analysis-empty">
         <div className="text-center py-12">
           <Brain className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
           <p className="text-zinc-400">Select a date to get AI analysis</p>
         </div>
       </div>
     );
   }
 
   const signalColors = {
@@ -538,50 +571,51 @@ const MarketFilter = ({ selected, onChange }) => {
                 : "border-zinc-700/50 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600"
               }`}
             data-testid={`filter-${market.id}`}
           >
             <Icon size={14} />
             {market.label}
           </button>
         );
       })}
     </div>
   );
 };
 
 // Main App Component
 function App() {
   const [selectedDate, setSelectedDate] = useState(new Date());
   const [weekOffset, setWeekOffset] = useState(0);
   const [marketFilter, setMarketFilter] = useState("all");
   const [impactFilter, setImpactFilter] = useState("all");
   
   const [analysis, setAnalysis] = useState(null);
   const [weekData, setWeekData] = useState(null);
   const [events, setEvents] = useState([]);
   const [news, setNews] = useState([]);
   const [dataStatus, setDataStatus] = useState({ is_live: false, data_source: "loading" });
+  const [roNow, setRoNow] = useState(new Date());
   
   const [loadingAnalysis, setLoadingAnalysis] = useState(false);
   const [loadingWeek, setLoadingWeek] = useState(false);
   const [loadingEvents, setLoadingEvents] = useState(false);
   const [loadingNews, setLoadingNews] = useState(false);
 
   const formatDateParam = (date) => format(date, "yyyy-MM-dd");
 
   const fetchDataStatus = useCallback(async () => {
     try {
       const response = await axios.get(`${API}/data-status`);
       setDataStatus(response.data);
     } catch (error) {
       console.error("Error fetching data status:", error);
     }
   }, []);
 
   const fetchNews = useCallback(async () => {
     setLoadingNews(true);
     try {
       const response = await axios.get(`${API}/market-news`, {
         params: { category: "general" }
       });
       setNews(response.data);
     } catch (error) {
@@ -627,50 +661,69 @@ function App() {
       const response = await axios.get(`${API}/calendar`, {
         params: {
           date_from: dateFrom,
           date_to: dateTo,
           market,
           impact
         }
       });
       setEvents(response.data);
     } catch (error) {
       console.error("Error fetching events:", error);
       toast.error("Failed to fetch calendar events");
     } finally {
       setLoadingEvents(false);
     }
   }, []);
 
   // Initial load
   useEffect(() => {
     fetchAnalysis(selectedDate);
     fetchWeekOverview(weekOffset);
     fetchDataStatus();
     fetchNews();
   }, []);
 
+  // Keep status fresh in UI (for "last update" timer text)
+  useEffect(() => {
+    const intervalId = setInterval(() => {
+      fetchDataStatus();
+    }, 60 * 1000);
+
+    return () => clearInterval(intervalId);
+  }, [fetchDataStatus]);
+
+
+
+  // RO clock in header
+  useEffect(() => {
+    const clockId = setInterval(() => {
+      setRoNow(new Date());
+    }, 1000);
+
+    return () => clearInterval(clockId);
+  }, []);
   // Fetch events when filters change
   useEffect(() => {
     // If weekend (Sat=6, Sun=0), use next week's Monday
     const today = new Date();
     const dayOfWeek = today.getDay(); // 0=Sun, 6=Sat
     
     let baseMonday;
     if (dayOfWeek === 0 || dayOfWeek === 6) {
       // Weekend - use next Monday
       const daysUntilMonday = dayOfWeek === 0 ? 1 : 8 - dayOfWeek;
       baseMonday = addDays(today, daysUntilMonday);
     } else {
       // Weekday - use this week's Monday
       baseMonday = startOfWeek(today, { weekStartsOn: 1 });
     }
     
     const offsetWeekStart = addDays(baseMonday, weekOffset * 7);
     const weekEnd = addDays(offsetWeekStart, 4);
     
     fetchEvents(
       formatDateParam(offsetWeekStart),
       formatDateParam(weekEnd),
       marketFilter,
       impactFilter
     );
@@ -681,51 +734,51 @@ function App() {
   const handleDateSelect = (date) => {
     if (date) {
       setSelectedDate(date);
       fetchAnalysis(date);
     }
   };
 
   const handleDayCardSelect = (dateStr) => {
     const date = parseISO(dateStr);
     setSelectedDate(date);
     fetchAnalysis(date);
   };
 
   const handleWeekChange = (direction) => {
     const newOffset = weekOffset + direction;
     setWeekOffset(newOffset);
     fetchWeekOverview(newOffset);
   };
 
   const handleRefreshAnalysis = () => {
     fetchAnalysis(selectedDate);
   };
 
   return (
     <div className="min-h-screen bg-zinc-950 grid-texture" data-testid="app-container">
-      <Header dataStatus={dataStatus} />
+      <Header dataStatus={dataStatus} roNow={roNow} />
       <Toaster position="top-right" />
       
       <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
         {/* Top Controls */}
         <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-8 fade-in">
           <div className="flex items-center gap-4">
             <Popover>
               <PopoverTrigger asChild>
                 <Button 
                   variant="outline" 
                   className="bg-zinc-800/50 border-zinc-700 hover:bg-zinc-700/50 hover:border-zinc-600"
                   data-testid="date-picker-btn"
                 >
                   <CalendarIcon size={16} className="mr-2" />
                   {format(selectedDate, "MMM d, yyyy")}
                 </Button>
               </PopoverTrigger>
               <PopoverContent className="w-auto p-0 bg-zinc-900 border-zinc-700" align="start">
                 <Calendar
                   mode="single"
                   selected={selectedDate}
                   onSelect={handleDateSelect}
                   initialFocus
                   className="bg-zinc-900"
                 />
