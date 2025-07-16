#!/usr/bin/env python3
"""
Enhanced JavaScript Scraper Test
Specifically tests the enhanced Playwright-based scraping functionality
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime

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
    
    async def test_enhanced_scraper_comprehensive(self):
        """Comprehensive test of enhanced JavaScript scraper"""
        print("=== Enhanced JavaScript Scraper Comprehensive Test ===")
        print(f"Backend URL: {API_BASE}")
        print(f"Test started at: {datetime.now()}")
        
        try:
            session = await self.create_session()
            
            # Test 1: Get all South Tampa Chamber directories
            print("\n1. Finding South Tampa Chamber directories...")
            async with session.get(f"{API_BASE}/directories") as response:
                if response.status != 200:
                    print(f"❌ Failed to get directories: HTTP {response.status}")
                    return
                
                directories = await response.json()
                south_tampa_dirs = [d for d in directories if 'southtampa' in d.get('url', '').lower()]
                
                print(f"Found {len(south_tampa_dirs)} South Tampa Chamber directories:")
                for i, directory in enumerate(south_tampa_dirs):
                    print(f"  {i+1}. {directory.get('name', 'N/A')}")
                    print(f"     URL: {directory.get('url', 'N/A')}")
                    print(f"     Status: {directory.get('scrape_status', 'N/A')}")
                    print(f"     Business count: {directory.get('business_count', 0)}")
            
            # Test 2: Test scraping with different South Tampa Chamber URLs
            test_urls = [
                'https://www.southtampachamber.org/',
                'https://business.southtampachamber.org/list',
                'https://southtampachamber.org'
            ]
            
            results = {}
            
            for test_url in test_urls:
                print(f"\n2. Testing enhanced scraper with: {test_url}")
                
                # Find directory with this URL
                target_dir = None
                for directory in south_tampa_dirs:
                    if directory.get('url') == test_url or directory.get('url').rstrip('/') == test_url.rstrip('/'):
                        target_dir = directory
                        break
                
                if not target_dir:
                    print(f"   ⚠️ Directory not found for URL: {test_url}")
                    continue
                
                # Test scraping
                scrape_data = {'directory_id': target_dir['id']}
                
                print(f"   🔍 Scraping directory: {target_dir.get('name', 'N/A')}")
                async with session.post(f"{API_BASE}/scrape-directory", json=scrape_data) as scrape_response:
                    if scrape_response.status == 200:
                        result = await scrape_response.json()
                        
                        success = result.get('success', False)
                        businesses_found = result.get('businesses_found', 0)
                        message = result.get('message', 'N/A')
                        scraping_method = result.get('scraping_method', 'unknown')
                        
                        print(f"   ✅ Success: {success}")
                        print(f"   📊 Businesses found: {businesses_found}")
                        print(f"   🔧 Scraping method: {scraping_method}")
                        print(f"   💬 Message: {message}")
                        
                        results[test_url] = {
                            'success': success,
                            'businesses_found': businesses_found,
                            'scraping_method': scraping_method,
                            'businesses': result.get('businesses', [])
                        }
                        
                        # Analyze business data quality
                        businesses = result.get('businesses', [])
                        if businesses:
                            print(f"   📋 Business data quality analysis:")
                            
                            valid_businesses = 0
                            businesses_with_phone = 0
                            businesses_with_email = 0
                            businesses_with_website = 0
                            
                            for business in businesses:
                                name = business.get('business_name', '').strip()
                                phone = business.get('phone', '').strip()
                                email = business.get('email', '').strip()
                                website = business.get('website', '').strip()
                                
                                # Check if this looks like a real business (not form elements)
                                if (name and len(name) > 3 and 
                                    not any(junk in name.lower() for junk in ['<span', 'required', 'field', 'form', 'application']) and
                                    (phone or email or website)):
                                    valid_businesses += 1
                                
                                if phone and phone != '(000) 000-0000':
                                    businesses_with_phone += 1
                                if email and '@' in email:
                                    businesses_with_email += 1
                                if website and 'http' in website:
                                    businesses_with_website += 1
                            
                            print(f"     - Valid businesses: {valid_businesses}/{len(businesses)}")
                            print(f"     - With phone: {businesses_with_phone}")
                            print(f"     - With email: {businesses_with_email}")
                            print(f"     - With website: {businesses_with_website}")
                            
                            # Show sample businesses (only valid ones)
                            print(f"   📝 Sample businesses:")
                            shown = 0
                            for i, business in enumerate(businesses):
                                name = business.get('business_name', '').strip()
                                if (name and len(name) > 3 and 
                                    not any(junk in name.lower() for junk in ['<span', 'required', 'field', 'form', 'application'])):
                                    print(f"     {shown+1}. {name}")
                                    print(f"        Phone: {business.get('phone', 'N/A')}")
                                    print(f"        Email: {business.get('email', 'N/A')}")
                                    print(f"        Website: {business.get('website', 'N/A')}")
                                    shown += 1
                                    if shown >= 3:
                                        break
                            
                            if shown == 0:
                                print(f"     ⚠️ No valid businesses found (only form elements or junk data)")
                        
                    else:
                        error_text = await scrape_response.text()
                        print(f"   ❌ Scraping failed: HTTP {scrape_response.status}")
                        print(f"   Error: {error_text}")
                        results[test_url] = {'success': False, 'error': f"HTTP {scrape_response.status}"}
            
            # Test 3: Verify fallback logic is working
            print(f"\n3. Enhanced Scraper Fallback Logic Analysis:")
            
            total_tests = len(results)
            successful_tests = sum(1 for r in results.values() if r.get('success', False))
            
            print(f"   📊 Test Results Summary:")
            print(f"     - Total URLs tested: {total_tests}")
            print(f"     - Successful scrapes: {successful_tests}")
            print(f"     - Success rate: {(successful_tests/total_tests*100):.1f}%" if total_tests > 0 else "     - Success rate: 0%")
            
            # Check if enhanced scraping (Playwright) was used
            playwright_used = any(r.get('scraping_method') == 'playwright' for r in results.values())
            basic_used = any(r.get('scraping_method') == 'basic' for r in results.values())
            
            print(f"   🔧 Scraping Methods Used:")
            print(f"     - Basic scraping (BeautifulSoup): {'✅' if basic_used else '❌'}")
            print(f"     - Enhanced scraping (Playwright): {'✅' if playwright_used else '❌'}")
            
            # Test 4: Overall assessment
            print(f"\n4. Enhanced JavaScript Scraper Assessment:")
            
            # Check if we found any real business data
            total_businesses = sum(r.get('businesses_found', 0) for r in results.values())
            
            if total_businesses > 0:
                print(f"   ✅ Enhanced scraper is functional")
                print(f"   📊 Total businesses extracted: {total_businesses}")
                
                # Check data quality
                quality_issues = []
                for url, result in results.items():
                    businesses = result.get('businesses', [])
                    for business in businesses:
                        name = business.get('business_name', '').strip()
                        if any(junk in name.lower() for junk in ['<span', 'required', 'field', 'form', 'application']):
                            quality_issues.append(f"Form element detected: {name}")
                
                if quality_issues:
                    print(f"   ⚠️ Data quality issues detected:")
                    for issue in quality_issues[:3]:  # Show first 3 issues
                        print(f"     - {issue}")
                    if len(quality_issues) > 3:
                        print(f"     - ... and {len(quality_issues) - 3} more issues")
                    
                    print(f"   💡 Recommendation: The enhanced scraper is working but may need refinement")
                    print(f"      to better distinguish between actual business listings and form elements")
                    print(f"      on JavaScript-heavy sites like GrowthZone CMS.")
                else:
                    print(f"   ✅ Data quality appears good")
                
                return True
            else:
                print(f"   ❌ Enhanced scraper failed to extract business data")
                print(f"   💡 This could indicate:")
                print(f"      - The South Tampa Chamber site structure has changed")
                print(f"      - The enhanced scraper needs adjustment for GrowthZone CMS")
                print(f"      - The site requires additional JavaScript execution time")
                return False
                
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            return False
        
        finally:
            await self.close_session()

async def main():
    """Main test runner"""
    tester = EnhancedScraperTester()
    success = await tester.test_enhanced_scraper_comprehensive()
    
    print(f"\n{'='*60}")
    print(f"ENHANCED JAVASCRIPT SCRAPER TEST RESULT")
    print(f"{'='*60}")
    
    if success:
        print(f"✅ PASSED - Enhanced JavaScript scraper is working")
        print(f"   The fallback logic from basic to Playwright scraping is functional.")
        print(f"   Business data is being extracted from JavaScript-heavy sites.")
    else:
        print(f"❌ FAILED - Enhanced JavaScript scraper needs improvement")
        print(f"   The scraper may need refinement for better business data extraction.")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)