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
