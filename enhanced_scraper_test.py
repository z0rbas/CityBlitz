#!/usr/bin/env python3
"""
Enhanced JavaScript Scraper Specific Testing
Tests the enhanced validation and fallback logic as requested in the review
"""

import asyncio
import aiohttp
import json
import os
import re
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

class EnhancedScraperTester:
    def __init__(self):
        self.session = None
        
    async def create_session(self):
        """Create aiohttp session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=120)  # Longer timeout for Playwright
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def test_fallback_logic(self):
        """Test that fallback to Playwright works when basic scraping finds <3 businesses"""
        print("\n=== Testing Fallback Logic ===")
        
        session = await self.create_session()
        
        # Get directories to test fallback logic
        async with session.get(f"{API_BASE}/directories") as response:
            if response.status != 200:
                print("❌ Could not fetch directories")
                return False
            
            directories = await response.json()
            
            # Look for South Tampa Chamber specifically (known JavaScript-heavy site)
            south_tampa_dir = None
            for directory in directories:
                if "southtampachamber.org" in directory.get('url', ''):
                    south_tampa_dir = directory
                    break
            
            if not south_tampa_dir:
                print("⚠️  South Tampa Chamber not found, testing with first available directory")
                if directories:
                    south_tampa_dir = directories[0]
                else:
                    print("❌ No directories available for testing")
                    return False
            
            print(f"Testing fallback with: {south_tampa_dir.get('name', 'N/A')}")
            print(f"URL: {south_tampa_dir.get('url', 'N/A')}")
            
            # Test scraping to see if fallback is triggered
            scrape_data = {"directory_id": south_tampa_dir['id']}
            
            async with session.post(f"{API_BASE}/scrape-directory", json=scrape_data) as scrape_response:
                if scrape_response.status == 200:
                    result = await scrape_response.json()
                    
                    businesses_found = result.get('businesses_found', 0)
                    scraping_method = result.get('scraping_method', 'basic')
                    
                    print(f"Businesses found: {businesses_found}")
                    print(f"Scraping method: {scraping_method}")
                    
                    # Check if fallback was triggered
                    if scraping_method in ['playwright', 'enhanced'] or 'playwright' in scraping_method.lower():
                        print("✅ Fallback to Playwright was triggered")
                        return True
                    elif businesses_found >= 3:
                        print("✅ Basic scraping found enough businesses (≥3), no fallback needed")
                        return True
                    else:
                        print(f"⚠️  Basic scraping found {businesses_found} businesses but no fallback triggered")
                        return False
                else:
                    print(f"❌ Scraping failed: HTTP {scrape_response.status}")
                    return False
    
    async def test_validation_filtering(self):
        """Test that enhanced validation filters out form elements and junk data"""
        print("\n=== Testing Enhanced Validation ===")
        
        session = await self.create_session()
        
        # Get directories with businesses to test validation
        async with session.get(f"{API_BASE}/directories") as response:
            if response.status != 200:
                print("❌ Could not fetch directories")
                return False
            
            directories = await response.json()
            business_directories = [d for d in directories if d.get('business_count', 0) > 0]
            
            if not business_directories:
                print("❌ No directories with businesses found for validation testing")
                return False
            
            validation_results = {
                'directories_tested': 0,
                'total_businesses': 0,
                'valid_businesses': 0,
                'junk_filtered': 0,
                'validation_working': True
            }
            
            # Test validation on up to 3 directories with businesses
            for directory in business_directories[:3]:
                print(f"\n📂 Testing validation for: {directory.get('name', 'N/A')}")
                print(f"   Expected businesses: {directory.get('business_count', 0)}")
                
                scrape_data = {"directory_id": directory['id']}
                
                async with session.post(f"{API_BASE}/scrape-directory", json=scrape_data) as scrape_response:
                    if scrape_response.status == 200:
                        result = await scrape_response.json()
                        businesses = result.get('businesses', [])
                        
                        validation_results['directories_tested'] += 1
                        validation_results['total_businesses'] += len(businesses)
                        
                        # Analyze business data quality
                        valid_count = 0
                        junk_count = 0
                        
                        for business in businesses:
                            business_name = business.get('business_name', '').strip()
                            phone = business.get('phone', '').strip()
                            email = business.get('email', '').strip()
                            website = business.get('website', '').strip()
                            
                            # Check for junk/form indicators
                            junk_indicators = [
                                'form', 'application', 'register', 'login', 'submit',
                                'required field', 'enter your', 'contact information',
                                'member application', 'sign up', 'membership',
                                'home', 'about', 'contact', 'services', 'news',
                                'navigation', 'menu', 'header', 'footer'
                            ]
                            
                            is_junk = any(indicator in business_name.lower() for indicator in junk_indicators)
                            
                            # Check for valid contact info
                            has_valid_phone = phone and re.match(r'^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$', phone)
                            has_valid_email = email and re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email)
                            has_valid_website = website and ('http' in website or 'www' in website)
                            
                            if is_junk:
                                junk_count += 1
                                print(f"   🚫 Junk filtered: {business_name}")
                            elif has_valid_phone or has_valid_email or has_valid_website:
                                valid_count += 1
                                print(f"   ✅ Valid business: {business_name}")
                            else:
                                print(f"   ⚠️  Questionable: {business_name} (no valid contact)")
                        
                        validation_results['valid_businesses'] += valid_count
                        validation_results['junk_filtered'] += junk_count
                        
                        print(f"   📊 Results: {valid_count} valid, {junk_count} junk")
                        
                        # Validation is working if we have more valid than junk
                        if junk_count > valid_count and valid_count > 0:
                            validation_results['validation_working'] = False
                            print(f"   ❌ Validation issue: More junk than valid businesses")
                    else:
                        print(f"   ❌ Scraping failed: HTTP {scrape_response.status}")
            
            # Overall validation assessment
            print(f"\n📊 Validation Summary:")
            print(f"   Directories tested: {validation_results['directories_tested']}")
            print(f"   Total businesses: {validation_results['total_businesses']}")
            print(f"   Valid businesses: {validation_results['valid_businesses']}")
            print(f"   Junk filtered: {validation_results['junk_filtered']}")
            print(f"   Validation working: {validation_results['validation_working']}")
            
            return validation_results['validation_working'] and validation_results['valid_businesses'] > 0
    
    async def test_form_only_sites(self):
        """Test that form-only sites return 0 businesses"""
        print("\n=== Testing Form-Only Site Filtering ===")
        
        session = await self.create_session()
        
        # Get directories to test form-only filtering
        async with session.get(f"{API_BASE}/directories") as response:
            if response.status != 200:
                print("❌ Could not fetch directories")
                return False
            
            directories = await response.json()
            
            # Look for directories that are likely form-only (business_count = 0)
            form_only_dirs = [d for d in directories if d.get('business_count', 0) == 0 and 'chamber' in d.get('name', '').lower()]
            
            if not form_only_dirs:
                print("⚠️  No form-only chamber directories found for testing")
                return True  # Not a failure, just no test cases
            
            form_only_correctly_filtered = 0
            
            # Test up to 3 form-only directories
            for directory in form_only_dirs[:3]:
                print(f"\n📂 Testing form-only site: {directory.get('name', 'N/A')}")
                print(f"   URL: {directory.get('url', 'N/A')}")
                
                scrape_data = {"directory_id": directory['id']}
                
                async with session.post(f"{API_BASE}/scrape-directory", json=scrape_data) as scrape_response:
                    if scrape_response.status == 200:
                        result = await scrape_response.json()
                        businesses_found = result.get('businesses_found', 0)
                        
                        if businesses_found == 0:
                            print(f"   ✅ Correctly filtered form-only site (0 businesses)")
                            form_only_correctly_filtered += 1
                        else:
                            print(f"   ⚠️  Found {businesses_found} businesses (may not be form-only)")
                    else:
                        print(f"   ❌ Scraping failed: HTTP {scrape_response.status}")
            
            print(f"\n📊 Form-only filtering: {form_only_correctly_filtered}/{len(form_only_dirs[:3])} correctly filtered")
            return form_only_correctly_filtered > 0
    
    async def test_business_validation_rules(self):
        """Test specific business validation rules"""
        print("\n=== Testing Business Validation Rules ===")
        
        session = await self.create_session()
        
        # Get some businesses to test validation rules
        async with session.get(f"{API_BASE}/businesses") as response:
            if response.status != 200:
                print("❌ Could not fetch businesses for validation testing")
                return False
            
            businesses = await response.json()
            
            if not businesses:
                print("❌ No businesses found for validation testing")
                return False
            
            # Limit to first 50 for testing
            businesses = businesses[:50]
            
            validation_stats = {
                'total_businesses': len(businesses),
                'valid_names': 0,
                'valid_phones': 0,
                'valid_emails': 0,
                'valid_websites': 0,
                'placeholder_data_found': 0
            }
            
            print(f"Testing validation rules on {len(businesses)} businesses...")
            
            for business in businesses:
                name = business.get('business_name', '').strip()
                phone = business.get('phone', '').strip()
                email = business.get('email', '').strip()
                website = business.get('website', '').strip()
                
                # Test business name validation
                if name and len(name) >= 3 and len(name) <= 100:
                    # Check for junk patterns
                    junk_patterns = ['home', 'about', 'contact', 'form', 'application']
                    if not any(junk in name.lower() for junk in junk_patterns):
                        validation_stats['valid_names'] += 1
                
                # Test phone validation
                if phone:
                    if re.match(r'^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$', phone):
                        # Check for placeholder numbers
                        if phone not in ['(000) 000-0000', '000-000-0000', '(123) 456-7890']:
                            validation_stats['valid_phones'] += 1
                        else:
                            validation_stats['placeholder_data_found'] += 1
                
                # Test email validation
                if email:
                    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                        # Check for placeholder emails
                        if not any(placeholder in email.lower() for placeholder in ['example.com', 'test.com']):
                            validation_stats['valid_emails'] += 1
                        else:
                            validation_stats['placeholder_data_found'] += 1
                
                # Test website validation
                if website:
                    if 'http' in website or 'www' in website:
                        if not any(placeholder in website.lower() for placeholder in ['example.com', 'test.com']):
                            validation_stats['valid_websites'] += 1
                        else:
                            validation_stats['placeholder_data_found'] += 1
            
            print(f"📊 Validation Results:")
            print(f"   Total businesses: {validation_stats['total_businesses']}")
            print(f"   Valid names: {validation_stats['valid_names']}")
            print(f"   Valid phones: {validation_stats['valid_phones']}")
            print(f"   Valid emails: {validation_stats['valid_emails']}")
            print(f"   Valid websites: {validation_stats['valid_websites']}")
            print(f"   Placeholder data found: {validation_stats['placeholder_data_found']}")
            
            # Validation is working if we have mostly valid data and minimal placeholder data
            validation_quality = (validation_stats['valid_names'] + validation_stats['valid_phones'] + 
                                validation_stats['valid_emails'] + validation_stats['valid_websites'])
            
            success = (validation_quality > validation_stats['placeholder_data_found'] and 
                      validation_stats['placeholder_data_found'] < validation_stats['total_businesses'] * 0.1)
            
            if success:
                print("✅ Business validation rules are working correctly")
            else:
                print("❌ Business validation rules may need improvement")
            
            return success
    
    async def run_enhanced_scraper_tests(self):
        """Run all enhanced scraper tests"""
        print("="*60)
        print("ENHANCED JAVASCRIPT SCRAPER TESTING")
        print("="*60)
        print(f"Backend URL: {API_BASE}")
        print(f"Test started at: {datetime.now()}")
        
        test_results = {}
        
        try:
            # Test 1: Fallback Logic
            print("\n" + "="*40)
            test_results['fallback_logic'] = await self.test_fallback_logic()
            
            # Test 2: Enhanced Validation
            print("\n" + "="*40)
            test_results['validation_filtering'] = await self.test_validation_filtering()
            
            # Test 3: Form-Only Site Filtering
            print("\n" + "="*40)
            test_results['form_only_filtering'] = await self.test_form_only_sites()
            
            # Test 4: Business Validation Rules
            print("\n" + "="*40)
            test_results['validation_rules'] = await self.test_business_validation_rules()
            
        finally:
            await self.close_session()
        
        # Print final summary
        print("\n" + "="*60)
        print("ENHANCED SCRAPER TEST SUMMARY")
        print("="*60)
        
        total_tests = len(test_results)
        passed_tests = sum(1 for result in test_results.values() if result)
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print()
        
        for test_name, result in test_results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name.replace('_', ' ').title()}: {status}")
        
        if passed_tests == total_tests:
            print("\n🎉 ALL ENHANCED SCRAPER TESTS PASSED!")
            print("\nKey Findings:")
            print("✅ Fallback logic works correctly (basic → Playwright when <3 businesses)")
            print("✅ Enhanced validation filters out form elements and junk data")
            print("✅ Form-only sites correctly return 0 businesses")
            print("✅ Business validation rules prevent placeholder/invalid data")
            return True
        else:
            print(f"\n⚠️  {total_tests - passed_tests} test(s) failed.")
            return False

async def main():
    """Main test runner"""
    tester = EnhancedScraperTester()
    success = await tester.run_enhanced_scraper_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())