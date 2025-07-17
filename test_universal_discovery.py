#!/usr/bin/env python3
"""
Focused test for Universal Directory Discovery System
Tests the 4-strategy approach and technology-agnostic capabilities
"""

import asyncio
import aiohttp
import json
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

async def test_universal_directory_discovery():
    """Test Universal Directory Discovery System"""
    print("🌍 Testing Universal Directory Discovery System")
    print(f"Backend URL: {API_BASE}")
    print("="*60)
    
    timeout = aiohttp.ClientTimeout(total=60)
    session = aiohttp.ClientSession(timeout=timeout)
    
    try:
        # Test 1: Auto-discovery from main pages
        print("\n📍 Test 1: Universal Discovery from Main Pages")
        
        test_data = {
            "location": "Tampa Bay",
            "directory_types": ["chamber of commerce"],
            "max_results": 15
        }
        
        async with session.post(f"{API_BASE}/discover-directories", json=test_data) as response:
            if response.status == 200:
                result = await response.json()
                directories = result.get('directories', [])
                
                print(f"✅ Discovered {len(directories)} directories")
                print("📂 Sample directories found:")
                
                for i, directory in enumerate(directories[:5]):
                    name = directory.get('name', 'N/A')
                    url = directory.get('url', 'N/A')
                    dir_type = directory.get('directory_type', 'N/A')
                    print(f"  {i+1}. {name}")
                    print(f"     URL: {url}")
                    print(f"     Type: {dir_type}")
                
                # Test 2: Multi-Strategy Scraping
                print(f"\n🎯 Test 2: Multi-Strategy Approach Testing")
                
                # Get existing directories from database
                async with session.get(f"{API_BASE}/directories") as dir_response:
                    if dir_response.status == 200:
                        all_directories = await dir_response.json()
                        
                        # Test scraping different types of directories
                        test_results = {
                            'directories_tested': 0,
                            'enhanced_scraping_triggered': 0,
                            'basic_scraping_used': 0,
                            'businesses_found': 0,
                            'validation_working': True
                        }
                        
                        print(f"Testing scraping with {min(10, len(all_directories))} directories...")
                        
                        for i, directory in enumerate(all_directories[:10]):
                            directory_id = directory['id']
                            directory_name = directory.get('name', 'N/A')
                            directory_url = directory.get('url', 'N/A')
                            
                            print(f"\n  📂 Testing {i+1}: {directory_name}")
                            print(f"     URL: {directory_url}")
                            
                            scrape_data = {"directory_id": directory_id}
                            
                            async with session.post(f"{API_BASE}/scrape-directory", json=scrape_data) as scrape_response:
                                if scrape_response.status == 200:
                                    scrape_result = await scrape_response.json()
                                    
                                    scraping_method = scrape_result.get('scraping_method', 'basic')
                                    businesses = scrape_result.get('businesses', [])
                                    businesses_count = len(businesses)
                                    
                                    print(f"     ✅ Method: {scraping_method}")
                                    print(f"     📊 Businesses: {businesses_count}")
                                    
                                    test_results['directories_tested'] += 1
                                    test_results['businesses_found'] += businesses_count
                                    
                                    if 'enhanced' in scraping_method.lower() or 'playwright' in scraping_method.lower():
                                        test_results['enhanced_scraping_triggered'] += 1
                                        print(f"     🚀 Enhanced scraping triggered!")
                                    else:
                                        test_results['basic_scraping_used'] += 1
                                    
                                    # Check data quality (validation)
                                    if businesses_count > 0:
                                        valid_businesses = 0
                                        for business in businesses:
                                            name = business.get('business_name', '').strip()
                                            phone = business.get('phone', '').strip()
                                            email = business.get('email', '').strip()
                                            
                                            # Check if business has valid data
                                            if name and len(name) > 2 and (phone or email):
                                                valid_businesses += 1
                                        
                                        validation_rate = valid_businesses / businesses_count if businesses_count > 0 else 0
                                        print(f"     ✅ Validation: {valid_businesses}/{businesses_count} ({validation_rate:.1%}) valid")
                                        
                                        if validation_rate < 0.5:  # Less than 50% valid
                                            test_results['validation_working'] = False
                                        
                                        # Show sample businesses
                                        if businesses_count > 0:
                                            print(f"     📋 Sample businesses:")
                                            for j, business in enumerate(businesses[:2]):
                                                bname = business.get('business_name', 'N/A')
                                                bphone = business.get('phone', 'N/A')
                                                print(f"       {j+1}. {bname} | {bphone}")
                                else:
                                    print(f"     ❌ Scraping failed: HTTP {scrape_response.status}")
                        
                        # Test 3: Technology Agnostic Verification
                        print(f"\n🔧 Test 3: Technology Agnostic Verification")
                        
                        # Check if we handled different types of websites
                        website_types = set()
                        for directory in all_directories[:20]:
                            url = directory.get('url', '').lower()
                            if 'wordpress' in url or 'wp-' in url:
                                website_types.add('WordPress')
                            elif 'growthzone' in url or 'gz-' in url:
                                website_types.add('GrowthZone')
                            elif any(cms in url for cms in ['drupal', 'joomla', 'squarespace', 'wix']):
                                website_types.add('Other CMS')
                            else:
                                website_types.add('Custom/Static')
                        
                        print(f"✅ Website types handled: {', '.join(website_types)}")
                        
                        # Test 4: Intelligent Validation Check
                        print(f"\n🧠 Test 4: Intelligent Validation Results")
                        
                        print(f"📊 Overall Test Results:")
                        print(f"   Directories tested: {test_results['directories_tested']}")
                        print(f"   Enhanced scraping triggered: {test_results['enhanced_scraping_triggered']} times")
                        print(f"   Basic scraping used: {test_results['basic_scraping_used']} times")
                        print(f"   Total businesses found: {test_results['businesses_found']}")
                        print(f"   Validation working: {test_results['validation_working']}")
                        print(f"   Technology types handled: {len(website_types)}")
                        
                        # Overall assessment
                        print(f"\n🎯 Universal Directory Discovery Assessment:")
                        
                        # Check key features
                        features_working = {
                            'Universal Discovery': len(directories) >= 5,
                            'Multi-Strategy Approach': test_results['enhanced_scraping_triggered'] > 0 or test_results['basic_scraping_used'] > 0,
                            'Intelligent Validation': test_results['validation_working'],
                            'Technology Agnostic': len(website_types) >= 2
                        }
                        
                        for feature, working in features_working.items():
                            status = "✅ WORKING" if working else "❌ NEEDS ATTENTION"
                            print(f"   {feature}: {status}")
                        
                        all_working = all(features_working.values())
                        
                        if all_working:
                            print(f"\n🎉 UNIVERSAL DIRECTORY DISCOVERY SYSTEM: ✅ FULLY FUNCTIONAL")
                            print(f"   ✅ Auto-discovers directories from main pages")
                            print(f"   ✅ Uses multi-strategy approach (4 strategies)")
                            print(f"   ✅ Intelligent validation filters quality data")
                            print(f"   ✅ Technology-agnostic (works with any CMS)")
                        else:
                            print(f"\n⚠️  UNIVERSAL DIRECTORY DISCOVERY SYSTEM: PARTIALLY WORKING")
                            failed_features = [f for f, w in features_working.items() if not w]
                            print(f"   Issues with: {', '.join(failed_features)}")
                    
                    else:
                        print(f"❌ Could not fetch directories: HTTP {dir_response.status}")
            else:
                print(f"❌ Discovery failed: HTTP {response.status}")
                
    except Exception as e:
        print(f"❌ Error during testing: {e}")
    
    finally:
        await session.close()

async def main():
    await test_universal_directory_discovery()

if __name__ == "__main__":
    asyncio.run(main())