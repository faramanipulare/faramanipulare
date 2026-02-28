import requests
import sys
import json
from datetime import datetime, timedelta

class TradeSignalAPITester:
    def __init__(self, base_url="https://ai-trade-guard.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, params=None, data=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        if params:
            print(f"   Params: {params}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)

            print(f"   Status Code: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - {name}")
                
                # Try to parse JSON response
                try:
                    response_data = response.json()
                    print(f"   Response type: {type(response_data)}")
                    if isinstance(response_data, list):
                        print(f"   Response length: {len(response_data)}")
                    elif isinstance(response_data, dict):
                        print(f"   Response keys: {list(response_data.keys())}")
                    return True, response_data
                except:
                    print(f"   Response: {response.text[:100]}...")
                    return True, {}
            else:
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ FAILED - Request timeout")
            return False, {}
        except Exception as e:
            print(f"❌ FAILED - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200
        )

    def test_health_check(self):
        """Test health check endpoint"""
        return self.run_test(
            "Health Check",
            "GET",
            "health",
            200
        )

    def test_calendar_basic(self):
        """Test calendar endpoint without filters"""
        return self.run_test(
            "Economic Calendar - Basic",
            "GET",
            "calendar",
            200
        )

    def test_calendar_with_filters(self):
        """Test calendar endpoint with various filters"""
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=4)
        
        date_from = week_start.strftime("%Y-%m-%d")
        date_to = week_end.strftime("%Y-%m-%d")
        
        # Test with date range
        success1, _ = self.run_test(
            "Calendar - Date Range",
            "GET",
            "calendar",
            200,
            params={
                "date_from": date_from,
                "date_to": date_to
            }
        )
        
        # Test with market filter
        success2, _ = self.run_test(
            "Calendar - Indices Filter",
            "GET",
            "calendar",
            200,
            params={
                "market": "indices",
                "date_from": date_from,
                "date_to": date_to
            }
        )
        
        # Test with impact filter
        success3, _ = self.run_test(
            "Calendar - High Impact Filter",
            "GET",
            "calendar",
            200,
            params={
                "impact": "high",
                "date_from": date_from,
                "date_to": date_to
            }
        )
        
        # Test GBP/USD filter
        success4, _ = self.run_test(
            "Calendar - GBP/USD Filter",
            "GET",
            "calendar",
            200,
            params={
                "market": "gbpusd",
                "date_from": date_from,
                "date_to": date_to
            }
        )
        
        # Test EUR/USD filter
        success5, _ = self.run_test(
            "Calendar - EUR/USD Filter",
            "GET",
            "calendar",
            200,
            params={
                "market": "eurusd",
                "date_from": date_from,
                "date_to": date_to
            }
        )
        
        return all([success1, success2, success3, success4, success5])

    def test_analyze_endpoint(self):
        """Test AI analysis endpoint"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Test without date (should use today)
        success1, response1 = self.run_test(
            "AI Analysis - Default Date",
            "GET",
            "analyze",
            200
        )
        
        # Test with specific date
        success2, response2 = self.run_test(
            "AI Analysis - Specific Date",
            "GET",
            "analyze",
            200,
            params={"date": today}
        )
        
        # Validate response structure for AI analysis
        if success2 and response2:
            required_fields = ["date", "signal", "probability", "summary", "reasoning", "recommended_action"]
            missing_fields = [field for field in required_fields if field not in response2]
            if missing_fields:
                print(f"⚠️  WARNING: Missing AI analysis fields: {missing_fields}")
            else:
                print(f"✅ AI Analysis response has all required fields")
                
                # Validate signal values
                if response2.get("signal") in ["trade", "caution", "avoid"]:
                    print(f"✅ Valid signal value: {response2.get('signal')}")
                else:
                    print(f"⚠️  WARNING: Invalid signal value: {response2.get('signal')}")
                
                # Validate probability range
                prob = response2.get("probability")
                if isinstance(prob, int) and 0 <= prob <= 100:
                    print(f"✅ Valid probability: {prob}%")
                else:
                    print(f"⚠️  WARNING: Invalid probability: {prob}")
        
        return success1 and success2

    def test_week_overview(self):
        """Test week overview endpoint"""
        # Test current week
        success1, response1 = self.run_test(
            "Week Overview - Current Week",
            "GET",
            "week-overview",
            200
        )
        
        # Test previous week
        success2, response2 = self.run_test(
            "Week Overview - Previous Week",
            "GET",
            "week-overview",
            200,
            params={"week_offset": -1}
        )
        
        # Test next week
        success3, response3 = self.run_test(
            "Week Overview - Next Week",
            "GET",
            "week-overview",
            200,
            params={"week_offset": 1}
        )
        
        # Validate response structure for week overview
        if success1 and response1:
            required_fields = ["week_start", "week_end", "days", "overall_signal"]
            missing_fields = [field for field in required_fields if field not in response1]
            if missing_fields:
                print(f"⚠️  WARNING: Missing week overview fields: {missing_fields}")
            else:
                print(f"✅ Week Overview response has all required fields")
                
                # Check days array
                days = response1.get("days", [])
                if len(days) == 5:
                    print(f"✅ Correct number of days: {len(days)}")
                    
                    # Check each day structure
                    day_fields = ["date", "day_name", "signal", "probability", "event_count"]
                    for i, day in enumerate(days):
                        missing_day_fields = [field for field in day_fields if field not in day]
                        if missing_day_fields:
                            print(f"⚠️  WARNING: Day {i} missing fields: {missing_day_fields}")
                else:
                    print(f"⚠️  WARNING: Expected 5 days, got {len(days)}")
        
        return success1 and success2 and success3

    def test_data_status(self):
        """Test data status endpoint"""
        success, response = self.run_test(
            "Data Status Endpoint",
            "GET",
            "data-status",
            200
        )
        
        # Validate response structure
        if success and response:
            required_fields = ["data_source", "is_live", "event_count"]
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                print(f"⚠️  WARNING: Missing data status fields: {missing_fields}")
            else:
                print(f"✅ Data Status response has all required fields")
                
                # Validate data_source values
                data_source = response.get("data_source")
                if data_source in ["live", "sample"]:
                    print(f"✅ Valid data source: {data_source}")
                else:
                    print(f"⚠️  WARNING: Invalid data source: {data_source}")
                
                # Validate is_live is boolean
                is_live = response.get("is_live")
                if isinstance(is_live, bool):
                    print(f"✅ Valid is_live boolean: {is_live}")
                else:
                    print(f"⚠️  WARNING: is_live should be boolean: {is_live}")
                
                # Check event count
                event_count = response.get("event_count")
                if isinstance(event_count, int) and event_count >= 0:
                    print(f"✅ Valid event count: {event_count}")
                else:
                    print(f"⚠️  WARNING: Invalid event count: {event_count}")
        
        return success

    def test_market_news(self):
        """Test market news endpoint (Finnhub integration)"""
        # Test default category
        success1, response1 = self.run_test(
            "Market News - Default Category",
            "GET",
            "market-news",
            200
        )
        
        # Test specific category
        success2, response2 = self.run_test(
            "Market News - General Category",
            "GET",
            "market-news",
            200,
            params={"category": "general"}
        )
        
        # Test forex category
        success3, response3 = self.run_test(
            "Market News - Forex Category",
            "GET",
            "market-news",
            200,
            params={"category": "forex"}
        )
        
        # Validate response structure for market news
        if success1 and isinstance(response1, list):
            print(f"✅ Market News returns array with {len(response1)} items")
            
            if len(response1) > 0:
                # Check first news item structure
                news_item = response1[0]
                required_fields = ["id", "headline", "source", "url", "datetime", "category"]
                missing_fields = [field for field in required_fields if field not in news_item]
                if missing_fields:
                    print(f"⚠️  WARNING: Missing news item fields: {missing_fields}")
                else:
                    print(f"✅ News item has all required fields")
                    
                    # Validate URL format
                    url = news_item.get("url", "")
                    if url and (url.startswith("http://") or url.startswith("https://")):
                        print(f"✅ Valid news URL format")
                    else:
                        print(f"⚠️  WARNING: Invalid or missing URL: {url[:50]}...")
                    
                    # Check headline is not empty
                    headline = news_item.get("headline", "")
                    if headline and len(headline.strip()) > 0:
                        print(f"✅ News headline present: {headline[:50]}...")
                    else:
                        print(f"⚠️  WARNING: Empty or missing headline")
                        
                    # Check source is present
                    source = news_item.get("source", "")
                    if source and len(source.strip()) > 0:
                        print(f"✅ News source present: {source}")
                    else:
                        print(f"⚠️  WARNING: Empty or missing source")
            else:
                print(f"ℹ️  No news items returned (might be due to API limits or no news available)")
        elif success1:
            print(f"⚠️  WARNING: Expected array response, got: {type(response1)}")
        
        return success1 and success2 and success3

    def run_all_tests(self):
        """Run all API tests"""
        print("=" * 60)
        print("🚀 Starting TradeSignal AI Backend API Tests")
        print("=" * 60)
        
        # Basic connectivity tests
        print("\n📡 Testing Basic Connectivity...")
        self.test_root_endpoint()
        self.test_health_check()
        
        # Calendar tests
        print("\n📅 Testing Calendar API...")
        self.test_calendar_basic()
        self.test_calendar_with_filters()
        
        # AI Analysis tests
        print("\n🧠 Testing AI Analysis API...")
        self.test_analyze_endpoint()
        
        # Week Overview tests
        print("\n📊 Testing Week Overview API...")
        self.test_week_overview()
        
        # Data Status tests
        print("\n📊 Testing Data Status API...")
        self.test_data_status()
        
        # Print final results
        print("\n" + "=" * 60)
        print("📊 FINAL TEST RESULTS")
        print("=" * 60)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL TESTS PASSED!")
            return 0
        else:
            print("❌ SOME TESTS FAILED!")
            return 1

def main():
    tester = TradeSignalAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())