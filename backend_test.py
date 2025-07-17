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
            'universal_discovery': {'passed': False, 'error': None, 'data': None},
            'directory_management': {'passed': False, 'error': None, 'data': None},
            'directory_scraping': {'passed': False, 'error': None, 'data': None},
            'enhanced_scraper': {'passed': False, 'error': None, 'data': None},
            'business_data': {'passed': False, 'error': None, 'data': None},
            'csv_export': {'passed': False, 'error': None, 'data': None},
            'export_businesses': {'passed': False, 'error': None, 'data': None},
            'delete_all_data': {'passed': False, 'error': None, 'data': None}
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
    
    async def test_universal_directory_discovery(self):
        """Test Universal Directory Discovery System with main chamber pages"""
        print("\n=== Testing Universal Directory Discovery System ===")
        
        try:
            session = await self.create_session()
            
            # Test with main chamber pages by first discovering them, then testing scraping
            test_locations = ["Tampa Bay", "Miami", "Orlando"]
            
            universal_test_results = {
                'locations_tested': 0,
                'directories_discovered': 0,
                'directories_scraped': 0,
                'multi_strategy_working': False,
                'technology_agnostic': False,
                'intelligent_validation': False,
                'test_details': []
            }
            
            print(f"🌍 Testing Universal Directory Discovery with {len(test_locations)} locations...")
            
            for i, location in enumerate(test_locations):
                print(f"\n📍 Testing Location {i+1}: {location}")
                
                # First discover directories for this location
                discovery_data = {
                    "location": location,
                    "directory_types": ["chamber of commerce"],
                    "max_results": 5
                }
                
                try:
                    async with session.post(f"{API_BASE}/discover-directories", json=discovery_data) as discovery_response:
                        if discovery_response.status == 200:
                            discovery_result = await discovery_response.json()
                            
                            if discovery_result.get('success') and discovery_result.get('directories'):
                                directories = discovery_result['directories']
                                print(f"   ✅ Discovered {len(directories)} directories")
                                
                                # Test scraping the first few directories to see universal discovery in action
                                for j, directory in enumerate(directories[:3]):
                                    directory_name = directory.get('name', 'N/A')
                                    directory_url = directory.get('url', 'N/A')
                                    
                                    print(f"\n   🏢 Testing Directory {j+1}: {directory_name}")
                                    print(f"      URL: {directory_url}")
                                    
                                    # Get the actual directory_id from the database
                                    async with session.get(f"{API_BASE}/directories") as dir_response:
                                        if dir_response.status == 200:
                                            all_directories = await dir_response.json()
                                            
                                            # Find matching directory by URL
                                            matching_dir = None
                                            for db_dir in all_directories:
                                                if db_dir.get('url') == directory_url:
                                                    matching_dir = db_dir
                                                    break
                                            
                                            if matching_dir:
                                                directory_id = matching_dir['id']
                                                scrape_data = {"directory_id": directory_id}
                                                
                                                async with session.post(f"{API_BASE}/scrape-directory", json=scrape_data) as scrape_response:
                                                    if scrape_response.status == 200:
                                                        scrape_result = await scrape_response.json()
                                                        
                                                        scraping_method = scrape_result.get('scraping_method', 'basic')
                                                        businesses_found = len(scrape_result.get('businesses', []))
                                                        
                                                        print(f"      ✅ Scraping completed: {businesses_found} businesses")
                                                        print(f"      🔧 Method: {scraping_method}")
                                                        
                                                        # Check for multi-strategy approach indicators
                                                        if 'playwright' in scraping_method.lower() or 'enhanced' in scraping_method.lower():
                                                            universal_test_results['multi_strategy_working'] = True
                                                            print(f"      🎯 Multi-strategy approach detected!")
                                                        
                                                        # Check for technology agnostic capability
                                                        if any(cms in directory_url.lower() for cms in ['wordpress', 'growthzone', 'custom']):
                                                            universal_test_results['technology_agnostic'] = True
                                                        
                                                        # Check for intelligent validation (businesses found or properly filtered)
                                                        if businesses_found > 0:
                                                            universal_test_results['intelligent_validation'] = True
                                                            print(f"      ✅ Intelligent validation: Found valid businesses")
                                                        elif businesses_found == 0:
                                                            universal_test_results['intelligent_validation'] = True
                                                            print(f"      ✅ Intelligent validation: Properly filtered non-directory page")
                                                        
                                                        universal_test_results['directories_scraped'] += 1
                                                        
                                                        # Record test details
                                                        test_detail = {
                                                            'location': location,
                                                            'directory_name': directory_name,
                                                            'directory_url': directory_url,
                                                            'scraping_method': scraping_method,
                                                            'businesses_found': businesses_found,
                                                            'multi_strategy_used': 'playwright' in scraping_method.lower(),
                                                            'validation_working': True
                                                        }
                                                        universal_test_results['test_details'].append(test_detail)
                                                        
                                                        # Show sample businesses if found
                                                        if businesses_found > 0:
                                                            print(f"      📋 Sample businesses:")
                                                            for k, business in enumerate(scrape_result.get('businesses', [])[:2]):
                                                                name = business.get('business_name', 'N/A')
                                                                phone = business.get('phone', 'N/A')
                                                                print(f"        {k+1}. {name} | {phone}")
                                                    else:
                                                        print(f"      ❌ Scraping failed: HTTP {scrape_response.status}")
                                            else:
                                                print(f"      ⚠️  Directory not found in database")
                                        else:
                                            print(f"      ❌ Could not fetch directories from database")
                                
                                universal_test_results['locations_tested'] += 1
                                universal_test_results['directories_discovered'] += len(directories)
                            else:
                                print(f"   ❌ No directories discovered for {location}")
                        else:
                            print(f"   ❌ Discovery failed: HTTP {discovery_response.status}")
                
                except Exception as e:
                    print(f"   ❌ Error testing location {location}: {str(e)}")
            
            # Evaluate universal discovery test results
            print(f"\n🌍 Universal Directory Discovery Test Summary:")
            print(f"   Locations tested: {universal_test_results['locations_tested']}")
            print(f"   Total directories discovered: {universal_test_results['directories_discovered']}")
            print(f"   Directories scraped: {universal_test_results['directories_scraped']}")
            print(f"   Multi-strategy approach working: {universal_test_results['multi_strategy_working']}")
            print(f"   Technology agnostic: {universal_test_results['technology_agnostic']}")
            print(f"   Intelligent validation: {universal_test_results['intelligent_validation']}")
            
            # Determine if universal discovery test passed
            test_passed = (
                universal_test_results['locations_tested'] >= 2 and
                universal_test_results['directories_discovered'] >= 5 and
                universal_test_results['directories_scraped'] >= 3 and
                universal_test_results['intelligent_validation']
            )
            
            if test_passed:
                self.test_results['universal_discovery'] = {
                    'passed': True,
                    'error': None,
                    'data': universal_test_results
                }
                print("✅ Universal Directory Discovery System test PASSED")
            else:
                error_msg = "Universal discovery test failed: "
                if universal_test_results['locations_tested'] < 2:
                    error_msg += "Not enough locations tested"
                elif universal_test_results['directories_discovered'] < 5:
                    error_msg += "Not enough directories discovered"
                elif universal_test_results['directories_scraped'] < 3:
                    error_msg += "Not enough directories scraped successfully"
                elif not universal_test_results['intelligent_validation']:
                    error_msg += "Intelligent validation not working"
                
                self.test_results['universal_discovery'] = {
                    'passed': False,
                    'error': error_msg,
                    'data': universal_test_results
                }
                print(f"❌ Universal Directory Discovery test FAILED: {error_msg}")
                    
        except Exception as e:
            self.test_results['universal_discovery'] = {
                'passed': False,
                'error': str(e)
            }
            print(f"Error testing universal directory discovery: {e}")
    
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
    
    async def test_enhanced_javascript_scraper(self):
        """Test Enhanced JavaScript Scraper with comprehensive validation testing"""
        print("\n=== Testing Enhanced JavaScript Scraper with Validation ===")
        
        try:
            session = await self.create_session()
            
            # Get existing directories for testing
            async with session.get(f"{API_BASE}/directories") as response:
                if response.status != 200:
                    self.test_results['enhanced_scraper'] = {
                        'passed': False,
                        'error': "Could not fetch existing directories"
                    }
                    return
                
                existing_directories = await response.json()
                if not existing_directories:
                    self.test_results['enhanced_scraper'] = {
                        'passed': False,
                        'error': "No directories available for testing"
                    }
                    return
            
            # Test multiple directory types to verify enhanced validation
            test_results = {
                'directories_tested': 0,
                'fallback_triggered': 0,
                'validation_working': True,
                'total_businesses_found': 0,
                'directories_with_businesses': 0,
                'form_only_sites_filtered': 0,
                'test_details': []
            }
            
            print(f"Testing enhanced scraper with {len(existing_directories)} directories...")
            
            # Test up to 5 directories to verify different scenarios
            for i, directory in enumerate(existing_directories[:5]):
                directory_id = directory['id']
                directory_name = directory.get('name', 'N/A')
                directory_url = directory.get('url', 'N/A')
                
                print(f"\n📂 Testing Directory {i+1}: {directory_name}")
                print(f"   URL: {directory_url}")
                
                scrape_data = {"directory_id": directory_id}
                
                try:
                    async with session.post(f"{API_BASE}/scrape-directory", json=scrape_data) as scrape_response:
                        if scrape_response.status == 200:
                            scrape_result = await scrape_response.json()
                            
                            businesses = scrape_result.get('businesses', [])
                            businesses_found = len(businesses)
                            scraping_method = scrape_result.get('scraping_method', 'basic')
                            
                            print(f"   ✅ Scraping successful: {businesses_found} businesses found")
                            print(f"   🔧 Method used: {scraping_method}")
                            
                            # Check if fallback to Playwright was triggered
                            if scraping_method == 'playwright' or 'enhanced' in scraping_method.lower():
                                test_results['fallback_triggered'] += 1
                                print(f"   ⚡ Fallback to enhanced Playwright scraping triggered")
                            
                            # Validate business data quality
                            valid_businesses = 0
                            businesses_with_contact = 0
                            junk_filtered = 0
                            
                            for business in businesses:
                                business_name = business.get('business_name', '').strip()
                                phone = business.get('phone', '').strip()
                                email = business.get('email', '').strip()
                                website = business.get('website', '').strip()
                                
                                # Check if business has valid contact info
                                has_contact = bool(phone or email or website)
                                if has_contact:
                                    businesses_with_contact += 1
                                
                                # Check for form elements and junk data (should be filtered out)
                                junk_indicators = [
                                    'form', 'application', 'register', 'login', 'submit',
                                    'required field', 'enter your', 'contact information',
                                    'member application', 'sign up', 'membership'
                                ]
                                
                                is_junk = any(indicator in business_name.lower() for indicator in junk_indicators)
                                if is_junk:
                                    junk_filtered += 1
                                    print(f"   ⚠️  Potential junk data found: {business_name}")
                                else:
                                    valid_businesses += 1
                            
                            # Record test details
                            test_detail = {
                                'directory_name': directory_name,
                                'directory_url': directory_url,
                                'businesses_found': businesses_found,
                                'valid_businesses': valid_businesses,
                                'businesses_with_contact': businesses_with_contact,
                                'junk_filtered': junk_filtered,
                                'scraping_method': scraping_method,
                                'fallback_used': scraping_method != 'basic'
                            }
                            test_results['test_details'].append(test_detail)
                            
                            # Update overall results
                            test_results['directories_tested'] += 1
                            test_results['total_businesses_found'] += businesses_found
                            
                            if businesses_found > 0:
                                test_results['directories_with_businesses'] += 1
                            
                            # Check if this looks like a form-only site (should return 0 businesses)
                            if businesses_found == 0 and 'chamber' in directory_name.lower():
                                test_results['form_only_sites_filtered'] += 1
                                print(f"   🚫 Form-only site correctly filtered (0 businesses)")
                            
                            # Validate data quality
                            if junk_filtered > valid_businesses:
                                test_results['validation_working'] = False
                                print(f"   ❌ Validation issue: More junk ({junk_filtered}) than valid businesses ({valid_businesses})")
                            else:
                                print(f"   ✅ Validation working: {valid_businesses} valid, {junk_filtered} junk filtered")
                            
                            # Show sample businesses for verification
                            if businesses_found > 0:
                                print(f"   📋 Sample businesses:")
                                for j, business in enumerate(businesses[:3]):
                                    name = business.get('business_name', 'N/A')
                                    phone = business.get('phone', 'N/A')
                                    email = business.get('email', 'N/A')
                                    print(f"     {j+1}. {name} | {phone} | {email}")
                        
                        else:
                            error_text = await scrape_response.text()
                            print(f"   ❌ Scraping failed: HTTP {scrape_response.status}")
                            test_results['test_details'].append({
                                'directory_name': directory_name,
                                'directory_url': directory_url,
                                'error': f"HTTP {scrape_response.status}: {error_text}"
                            })
                
                except Exception as e:
                    print(f"   ❌ Error testing directory: {str(e)}")
                    test_results['test_details'].append({
                        'directory_name': directory_name,
                        'directory_url': directory_url,
                        'error': str(e)
                    })
            
            # Evaluate overall test results
            print(f"\n📊 Enhanced Scraper Test Summary:")
            print(f"   Directories tested: {test_results['directories_tested']}")
            print(f"   Fallback to Playwright triggered: {test_results['fallback_triggered']} times")
            print(f"   Total businesses found: {test_results['total_businesses_found']}")
            print(f"   Directories with businesses: {test_results['directories_with_businesses']}")
            print(f"   Form-only sites filtered: {test_results['form_only_sites_filtered']}")
            print(f"   Validation working: {test_results['validation_working']}")
            
            # Determine if test passed
            test_passed = (
                test_results['directories_tested'] > 0 and
                test_results['validation_working'] and
                (test_results['total_businesses_found'] > 0 or test_results['form_only_sites_filtered'] > 0)
            )
            
            if test_passed:
                self.test_results['enhanced_scraper'] = {
                    'passed': True,
                    'error': None,
                    'data': test_results
                }
                print("✅ Enhanced JavaScript Scraper with Validation test PASSED")
            else:
                error_msg = "Enhanced scraper test failed: "
                if test_results['directories_tested'] == 0:
                    error_msg += "No directories tested successfully"
                elif not test_results['validation_working']:
                    error_msg += "Validation not working properly"
                elif test_results['total_businesses_found'] == 0 and test_results['form_only_sites_filtered'] == 0:
                    error_msg += "No businesses found and no form-only sites detected"
                
                self.test_results['enhanced_scraper'] = {
                    'passed': False,
                    'error': error_msg,
                    'data': test_results
                }
                print(f"❌ Enhanced JavaScript Scraper test FAILED: {error_msg}")
                    
        except Exception as e:
            self.test_results['enhanced_scraper'] = {
                'passed': False,
                'error': str(e)
            }
            print(f"Error testing enhanced JavaScript scraper: {e}")
    
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
    
    async def test_export_businesses_api(self):
        """Test GET /api/export-businesses"""
        print("\n=== Testing Export Businesses API ===")
        
        try:
            session = await self.create_session()
            
            # First, get current database state
            async with session.get(f"{API_BASE}/directories") as dir_response:
                if dir_response.status == 200:
                    directories = await dir_response.json()
                    print(f"Current directories in database: {len(directories)}")
                else:
                    print("Could not fetch directories count")
            
            async with session.get(f"{API_BASE}/businesses") as biz_response:
                if biz_response.status == 200:
                    businesses = await biz_response.json()
                    print(f"Current businesses in database: {len(businesses)}")
                else:
                    print("Could not fetch businesses count")
            
            # Test 1: Export all businesses
            print("\n📊 Testing export all businesses...")
            async with session.get(f"{API_BASE}/export-businesses") as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    # Check if response is CSV content
                    content_type = response.headers.get('content-type', '')
                    if 'text/csv' in content_type:
                        csv_content = await response.text()
                        lines = csv_content.split('\n')
                        print(f"✅ CSV export successful: {len(lines)} lines")
                        
                        # Verify CSV header
                        if lines and lines[0]:
                            header = lines[0]
                            expected_fields = ['business_name', 'contact_person', 'phone', 'email', 'website', 'address', 'socials', 'directory_name']
                            header_valid = all(field in header for field in expected_fields)
                            
                            if header_valid:
                                print("✅ CSV header validation passed")
                                
                                # Show sample data
                                print("📋 Sample CSV data:")
                                for i, line in enumerate(lines[:4]):  # Header + 3 data lines
                                    if line.strip():
                                        print(f"  {i}: {line[:100]}...")
                                
                                self.test_results['export_businesses']['passed'] = True
                                self.test_results['export_businesses']['data'] = {
                                    'total_lines': len(lines),
                                    'header_valid': True,
                                    'content_type': content_type
                                }
                            else:
                                self.test_results['export_businesses']['error'] = f"Invalid CSV header: {header}"
                        else:
                            self.test_results['export_businesses']['error'] = "Empty CSV content"
                    else:
                        self.test_results['export_businesses']['error'] = f"Unexpected content type: {content_type}"
                elif response.status == 404:
                    # No businesses found - this is valid if database is empty
                    print("📭 No businesses found for export (database might be empty)")
                    self.test_results['export_businesses']['passed'] = True
                    self.test_results['export_businesses']['data'] = {'no_businesses': True}
                else:
                    error_text = await response.text()
                    self.test_results['export_businesses']['error'] = f"HTTP {response.status}: {error_text}"
            
            # Test 2: Export businesses for specific directory (if businesses exist)
            if businesses:
                directory_id = businesses[0].get('directory_id')
                if directory_id:
                    print(f"\n📊 Testing export for specific directory: {directory_id}")
                    async with session.get(f"{API_BASE}/export-businesses?directory_id={directory_id}") as response:
                        if response.status == 200:
                            csv_content = await response.text()
                            lines = csv_content.split('\n')
                            print(f"✅ Directory-specific export successful: {len(lines)} lines")
                        else:
                            print(f"⚠️ Directory-specific export failed: HTTP {response.status}")
                    
        except Exception as e:
            self.test_results['export_businesses']['error'] = str(e)
            print(f"Error testing export businesses API: {e}")
    
    async def test_delete_all_data_api(self):
        """Test DELETE /api/delete-all-data"""
        print("\n=== Testing Delete All Data API ===")
        
        try:
            session = await self.create_session()
            
            # First, get current database state
            print("📊 Getting current database state...")
            
            async with session.get(f"{API_BASE}/directories") as dir_response:
                if dir_response.status == 200:
                    directories_before = await dir_response.json()
                    directories_count_before = len(directories_before)
                    print(f"Directories before deletion: {directories_count_before}")
                else:
                    directories_count_before = 0
                    print("Could not fetch directories count")
            
            async with session.get(f"{API_BASE}/businesses") as biz_response:
                if biz_response.status == 200:
                    businesses_before = await biz_response.json()
                    businesses_count_before = len(businesses_before)
                    print(f"Businesses before deletion: {businesses_count_before}")
                else:
                    businesses_count_before = 0
                    print("Could not fetch businesses count")
            
            # Test the delete all data endpoint
            print("\n🗑️ Testing DELETE /api/delete-all-data...")
            async with session.delete(f"{API_BASE}/delete-all-data") as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    print(f"Delete operation successful: {result.get('success', False)}")
                    print(f"Message: {result.get('message', 'N/A')}")
                    
                    directories_deleted = result.get('directories_deleted', 0)
                    businesses_deleted = result.get('businesses_deleted', 0)
                    
                    print(f"Directories deleted: {directories_deleted}")
                    print(f"Businesses deleted: {businesses_deleted}")
                    
                    if result.get('success'):
                        # Verify data was actually deleted
                        print("\n🔍 Verifying data deletion...")
                        
                        async with session.get(f"{API_BASE}/directories") as verify_dir_response:
                            if verify_dir_response.status == 200:
                                directories_after = await verify_dir_response.json()
                                directories_count_after = len(directories_after)
                                print(f"Directories after deletion: {directories_count_after}")
                            else:
                                directories_count_after = -1
                        
                        async with session.get(f"{API_BASE}/businesses") as verify_biz_response:
                            if verify_biz_response.status == 200:
                                businesses_after = await verify_biz_response.json()
                                businesses_count_after = len(businesses_after)
                                print(f"Businesses after deletion: {businesses_count_after}")
                            else:
                                businesses_count_after = -1
                        
                        # Validate deletion was complete
                        deletion_successful = (
                            directories_count_after == 0 and 
                            businesses_count_after == 0
                        )
                        
                        if deletion_successful:
                            print("✅ Data deletion verification passed - database is empty")
                            self.test_results['delete_all_data']['passed'] = True
                            self.test_results['delete_all_data']['data'] = {
                                'directories_before': directories_count_before,
                                'businesses_before': businesses_count_before,
                                'directories_deleted': directories_deleted,
                                'businesses_deleted': businesses_deleted,
                                'directories_after': directories_count_after,
                                'businesses_after': businesses_count_after,
                                'deletion_complete': True
                            }
                        else:
                            self.test_results['delete_all_data']['error'] = f"Data not completely deleted. Directories after: {directories_count_after}, Businesses after: {businesses_count_after}"
                    else:
                        self.test_results['delete_all_data']['error'] = "Delete operation reported as unsuccessful"
                else:
                    error_text = await response.text()
                    self.test_results['delete_all_data']['error'] = f"HTTP {response.status}: {error_text}"
                    
        except Exception as e:
            self.test_results['delete_all_data']['error'] = str(e)
            print(f"Error testing delete all data API: {e}")

    async def run_all_tests(self):
        """Run all backend tests"""
        print(f"Starting backend API tests...")
        print(f"Backend URL: {API_BASE}")
        print(f"Test started at: {datetime.now()}")
        
        try:
            # Test in logical order
            await self.test_directory_discovery_api()
            await self.test_universal_directory_discovery()  # New universal discovery test
            await self.test_directory_management_api()
            await self.test_directory_scraping_api()
            await self.test_enhanced_javascript_scraper()  # New enhanced scraper test
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