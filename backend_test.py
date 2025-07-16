#!/usr/bin/env python3
"""
Backend API Testing for Chamber Directory Scraper
Tests all backend endpoints with realistic data
"""

import asyncio
import aiohttp
import json
import os
from datetime import datetime
import sys

# Get backend URL from frontend .env file
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"Error reading backend URL: {e}")
        return None

BACKEND_URL = get_backend_url()
if not BACKEND_URL:
    print("ERROR: Could not get backend URL from frontend/.env")
    sys.exit(1)

API_BASE = f"{BACKEND_URL}/api"

class BackendTester:
    def __init__(self):
        self.session = None
        self.test_results = {
            'directory_discovery': {'passed': False, 'error': None, 'data': None},
            'directory_management': {'passed': False, 'error': None, 'data': None},
            'directory_scraping': {'passed': False, 'error': None, 'data': None},
            'business_data': {'passed': False, 'error': None, 'data': None},
            'csv_export': {'passed': False, 'error': None, 'data': None}
        }
        self.discovered_directories = []
        
    async def create_session(self):
        """Create aiohttp session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def test_directory_discovery_api(self):
        """Test POST /api/discover-directories"""
        print("\n=== Testing Directory Discovery API ===")
        
        try:
            session = await self.create_session()
            
            # Test with Tampa Bay location as specified
            test_data = {
                "location": "Tampa Bay",
                "directory_types": ["chamber of commerce", "business directory", "better business bureau"],
                "max_results": 10
            }
            
            print(f"Testing discovery with location: {test_data['location']}")
            
            async with session.post(f"{API_BASE}/discover-directories", json=test_data) as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    print(f"Discovery successful: {result.get('success', False)}")
                    print(f"Directories found: {result.get('count', 0)}")
                    
                    if result.get('success') and result.get('directories'):
                        self.discovered_directories = result['directories']
                        self.test_results['directory_discovery']['passed'] = True
                        self.test_results['directory_discovery']['data'] = result
                        
                        # Print sample directory info
                        for i, directory in enumerate(result['directories'][:3]):
                            print(f"  Directory {i+1}: {directory.get('name', 'N/A')}")
                            print(f"    URL: {directory.get('url', 'N/A')}")
                            print(f"    Type: {directory.get('directory_type', 'N/A')}")
                    else:
                        self.test_results['directory_discovery']['error'] = "No directories discovered"
                else:
                    error_text = await response.text()
                    self.test_results['directory_discovery']['error'] = f"HTTP {response.status}: {error_text}"
                    
        except Exception as e:
            self.test_results['directory_discovery']['error'] = str(e)
            print(f"Error testing directory discovery: {e}")
    
    async def test_directory_management_api(self):
        """Test GET /api/directories"""
        print("\n=== Testing Directory Management API ===")
        
        try:
            session = await self.create_session()
            
            async with session.get(f"{API_BASE}/directories") as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    directories = await response.json()
                    print(f"Retrieved {len(directories)} directories")
                    
                    if directories:
                        self.test_results['directory_management']['passed'] = True
                        self.test_results['directory_management']['data'] = directories
                        
                        # Verify directory structure
                        sample_dir = directories[0]
                        required_fields = ['id', 'name', 'url', 'directory_type', 'location']
                        missing_fields = [field for field in required_fields if field not in sample_dir]
                        
                        if missing_fields:
                            print(f"Warning: Missing fields in directory: {missing_fields}")
                        else:
                            print("Directory structure validation passed")
                            
                        # Print sample directories
                        for i, directory in enumerate(directories[:3]):
                            print(f"  Directory {i+1}: {directory.get('name', 'N/A')}")
                            print(f"    Status: {directory.get('scrape_status', 'N/A')}")
                            print(f"    Business count: {directory.get('business_count', 0)}")
                    else:
                        self.test_results['directory_management']['error'] = "No directories found in database"
                else:
                    error_text = await response.text()
                    self.test_results['directory_management']['error'] = f"HTTP {response.status}: {error_text}"
                    
        except Exception as e:
            self.test_results['directory_management']['error'] = str(e)
            print(f"Error testing directory management: {e}")
    
    async def test_directory_scraping_api(self):
        """Test POST /api/scrape-directory"""
        print("\n=== Testing Directory Scraping API ===")
        
        try:
            session = await self.create_session()
            
            # Get directories to scrape
            async with session.get(f"{API_BASE}/directories") as response:
                if response.status == 200:
                    directories = await response.json()
                    if not directories:
                        self.test_results['directory_scraping']['error'] = "No directories available to scrape"
                        return
                else:
                    self.test_results['directory_scraping']['error'] = "Could not fetch directories for scraping"
                    return
            
            # Test scraping with first directory
            test_directory = directories[0]
            directory_id = test_directory['id']
            
            print(f"Testing scraping for directory: {test_directory.get('name', 'N/A')}")
            print(f"Directory URL: {test_directory.get('url', 'N/A')}")
            
            scrape_data = {"directory_id": directory_id}
            
            async with session.post(f"{API_BASE}/scrape-directory", json=scrape_data) as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    print(f"Scraping successful: {result.get('success', False)}")
                    print(f"Businesses found: {result.get('businesses_found', 0)}")
                    
                    if result.get('success'):
                        self.test_results['directory_scraping']['passed'] = True
                        self.test_results['directory_scraping']['data'] = result
                        
                        # Print sample business info
                        businesses = result.get('businesses', [])
                        for i, business in enumerate(businesses[:3]):
                            print(f"  Business {i+1}: {business.get('business_name', 'N/A')}")
                            print(f"    Phone: {business.get('phone', 'N/A')}")
                            print(f"    Email: {business.get('email', 'N/A')}")
                    else:
                        self.test_results['directory_scraping']['error'] = "Scraping reported as unsuccessful"
                else:
                    error_text = await response.text()
                    self.test_results['directory_scraping']['error'] = f"HTTP {response.status}: {error_text}"
                    
        except Exception as e:
            self.test_results['directory_scraping']['error'] = str(e)
            print(f"Error testing directory scraping: {e}")
    
    async def test_business_data_api(self):
        """Test GET /api/businesses"""
        print("\n=== Testing Business Data API ===")
        
        try:
            session = await self.create_session()
            
            # Test getting all businesses
            print("Testing GET /api/businesses (all businesses)")
            async with session.get(f"{API_BASE}/businesses") as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    businesses = await response.json()
                    print(f"Retrieved {len(businesses)} businesses")
                    
                    if businesses:
                        # Verify business structure
                        sample_business = businesses[0]
                        required_fields = ['id', 'directory_id', 'business_name']
                        missing_fields = [field for field in required_fields if field not in sample_business]
                        
                        if missing_fields:
                            print(f"Warning: Missing fields in business: {missing_fields}")
                        else:
                            print("Business structure validation passed")
                        
                        # Test filtering by directory_id
                        directory_id = sample_business.get('directory_id')
                        if directory_id:
                            print(f"\nTesting GET /api/businesses?directory_id={directory_id}")
                            async with session.get(f"{API_BASE}/businesses?directory_id={directory_id}") as filter_response:
                                if filter_response.status == 200:
                                    filtered_businesses = await filter_response.json()
                                    print(f"Filtered businesses: {len(filtered_businesses)}")
                                    
                                    # Verify all businesses have the same directory_id
                                    all_same_directory = all(b.get('directory_id') == directory_id for b in filtered_businesses)
                                    if all_same_directory:
                                        print("Directory filtering validation passed")
                                        self.test_results['business_data']['passed'] = True
                                        self.test_results['business_data']['data'] = {
                                            'total_businesses': len(businesses),
                                            'filtered_businesses': len(filtered_businesses)
                                        }
                                    else:
                                        self.test_results['business_data']['error'] = "Directory filtering not working correctly"
                                else:
                                    self.test_results['business_data']['error'] = f"Filtering failed: HTTP {filter_response.status}"
                        else:
                            self.test_results['business_data']['passed'] = True
                            self.test_results['business_data']['data'] = {'total_businesses': len(businesses)}
                    else:
                        self.test_results['business_data']['error'] = "No businesses found in database"
                else:
                    error_text = await response.text()
                    self.test_results['business_data']['error'] = f"HTTP {response.status}: {error_text}"
                    
        except Exception as e:
            self.test_results['business_data']['error'] = str(e)
            print(f"Error testing business data API: {e}")
    
    async def test_csv_export_api(self):
        """Test GET /api/export-csv/{directory_id}"""
        print("\n=== Testing CSV Export API ===")
        
        try:
            session = await self.create_session()
            
            # Get a directory with businesses
            async with session.get(f"{API_BASE}/businesses") as response:
                if response.status == 200:
                    businesses = await response.json()
                    if not businesses:
                        self.test_results['csv_export']['error'] = "No businesses available for CSV export"
                        return
                    
                    directory_id = businesses[0].get('directory_id')
                    if not directory_id:
                        self.test_results['csv_export']['error'] = "No directory_id found in business data"
                        return
                else:
                    self.test_results['csv_export']['error'] = "Could not fetch businesses for CSV export test"
                    return
            
            print(f"Testing CSV export for directory_id: {directory_id}")
            
            async with session.get(f"{API_BASE}/export-csv/{directory_id}") as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    print(f"Export successful: {result.get('success', False)}")
                    
                    if result.get('success') and result.get('csv_content'):
                        csv_content = result['csv_content']
                        lines = csv_content.split('\n')
                        print(f"CSV lines generated: {len(lines)}")
                        
                        # Verify CSV header
                        expected_header = "Business Name,Contact Person,Phone,Email,Address,Website,Category,Description"
                        if lines[0] == expected_header:
                            print("CSV header validation passed")
                            self.test_results['csv_export']['passed'] = True
                            self.test_results['csv_export']['data'] = {
                                'filename': result.get('filename'),
                                'lines_count': len(lines),
                                'sample_header': lines[0]
                            }
                        else:
                            self.test_results['csv_export']['error'] = f"Invalid CSV header: {lines[0]}"
                    else:
                        self.test_results['csv_export']['error'] = "CSV export reported as unsuccessful or no content"
                else:
                    error_text = await response.text()
                    self.test_results['csv_export']['error'] = f"HTTP {response.status}: {error_text}"
                    
        except Exception as e:
            self.test_results['csv_export']['error'] = str(e)
            print(f"Error testing CSV export: {e}")
    
    async def run_all_tests(self):
        """Run all backend tests"""
        print(f"Starting backend API tests...")
        print(f"Backend URL: {API_BASE}")
        print(f"Test started at: {datetime.now()}")
        
        try:
            # Test in logical order
            await self.test_directory_discovery_api()
            await self.test_directory_management_api()
            await self.test_directory_scraping_api()
            await self.test_business_data_api()
            await self.test_csv_export_api()
            
        finally:
            await self.close_session()
        
        # Print summary
        self.print_test_summary()
    
    def print_test_summary(self):
        """Print test results summary"""
        print("\n" + "="*60)
        print("BACKEND API TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['passed'])
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print()
        
        for test_name, result in self.test_results.items():
            status = "✅ PASSED" if result['passed'] else "❌ FAILED"
            print(f"{test_name.replace('_', ' ').title()}: {status}")
            if result['error']:
                print(f"  Error: {result['error']}")
            print()
        
        if passed_tests == total_tests:
            print("🎉 ALL BACKEND TESTS PASSED!")
        else:
            print(f"⚠️  {total_tests - passed_tests} test(s) failed. Check errors above.")

async def main():
    """Main test runner"""
    tester = BackendTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())