from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin, urlparse
import time
import random
from playwright.async_api import async_playwright


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


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

class DirectorySearchRequest(BaseModel):
    location: str
    directory_types: List[str] = ["chamber of commerce", "business directory", "better business bureau"]
    max_results: int = 20

class DiscoveredDirectory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    url: str
    directory_type: str
    location: str
    description: Optional[str] = None
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    scrape_status: str = "pending"  # pending, scraped, failed
    business_count: int = 0

class BusinessContact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    directory_id: str
    business_name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    socials: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

class ScrapeDirectoryRequest(BaseModel):
    directory_id: str


# Web scraping utilities
class DirectoryDiscoverer:
    def __init__(self):
        self.session = None
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
        
        # Pre-built database of known chambers for major cities
        self.known_chambers = {
            'tampa bay': [
                {'name': 'Tampa Bay Chamber', 'url': 'https://tampabay.com'},
                {'name': 'Greater Tampa Chamber of Commerce', 'url': 'https://tampachamber.com'},
                {'name': 'Hillsborough Chamber', 'url': 'https://hillschamber.com'},
                {'name': 'Pinellas County Chamber', 'url': 'https://pinellaschamber.org'},
                {'name': 'Clearwater Chamber', 'url': 'https://clearwaterchamber.org'},
                {'name': 'St. Petersburg Chamber', 'url': 'https://stpete.org'},
                {'name': 'Brandon Chamber', 'url': 'https://brandonchamber.com'},
                {'name': 'Westshore Chamber', 'url': 'https://westshorealliance.org'},
                {'name': 'South Tampa Chamber', 'url': 'https://southtampachamber.org'},
                {'name': 'Plant City Chamber', 'url': 'https://plantcitychamber.com'},
                {'name': 'Lutz-Land O Lakes Chamber', 'url': 'https://lutzchamber.com'},
                {'name': 'Ruskin Chamber', 'url': 'https://ruskinchamber.org'},
                {'name': 'Riverview Chamber', 'url': 'https://riverviewchamber.com'},
                {'name': 'Carrollwood Chamber', 'url': 'https://carrollwoodchamber.com'},
                {'name': 'Westchase Chamber', 'url': 'https://westchasechamber.com'},
                {'name': 'New Tampa Chamber', 'url': 'https://newtampachamber.org'},
                {'name': 'Hyde Park Chamber', 'url': 'https://hydeparkchamber.com'},
                {'name': 'Seminole Chamber', 'url': 'https://seminolechamber.com'},
                {'name': 'Largo Chamber', 'url': 'https://largochamber.com'},
                {'name': 'Dunedin Chamber', 'url': 'https://dunedinchamber.com'},
                {'name': 'Belcher Chamber', 'url': 'https://belcherchamber.org'},
                {'name': 'Tarpon Springs Chamber', 'url': 'https://tarponspringschamber.com'},
                {'name': 'Safety Harbor Chamber', 'url': 'https://safetyharborchamber.com'},
                {'name': 'Oldsmar Chamber', 'url': 'https://oldsmarchamber.com'},
                {'name': 'Palm Harbor Chamber', 'url': 'https://palmharborchamber.com'},
                {'name': 'Countryside Chamber', 'url': 'https://countrysidechamber.com'},
                {'name': 'Indian Rocks Beach Chamber', 'url': 'https://indianrockschamber.com'},
                {'name': 'Redington Beach Chamber', 'url': 'https://redingtonbeachchamber.com'},
                {'name': 'Madeira Beach Chamber', 'url': 'https://madeirabeachchamber.com'},
                {'name': 'Treasure Island Chamber', 'url': 'https://treasureislandchamber.org'},
                {'name': 'St. Pete Beach Chamber', 'url': 'https://stpetebeachchamber.com'},
                {'name': 'Gulfport Chamber', 'url': 'https://gulfportchamber.com'},
                {'name': 'Kenneth City Chamber', 'url': 'https://kennethcitychamber.com'},
                {'name': 'Pinellas Park Chamber', 'url': 'https://pinellasparkchamber.com'},
                {'name': 'Bay Pines Chamber', 'url': 'https://baypineschamber.com'}
            ],
            'miami': [
                {'name': 'Miami Chamber of Commerce', 'url': 'https://miamichamber.com'},
                {'name': 'Greater Miami Chamber', 'url': 'https://greatermiami.com'},
                {'name': 'Miami-Dade Chamber', 'url': 'https://miamidade.com'},
                {'name': 'Coral Gables Chamber', 'url': 'https://coralgableschamber.org'},
                {'name': 'Miami Beach Chamber', 'url': 'https://miamibeachchamber.com'},
                {'name': 'Aventura Chamber', 'url': 'https://aventurachamber.org'},
                {'name': 'Homestead Chamber', 'url': 'https://homesteadchamber.com'},
                {'name': 'Kendall Chamber', 'url': 'https://kendallchamber.com'},
                {'name': 'Doral Chamber', 'url': 'https://doralchamber.org'},
                {'name': 'Hialeah Chamber', 'url': 'https://hialeahchamber.org'}
            ],
            'orlando': [
                {'name': 'Orlando Chamber of Commerce', 'url': 'https://orlandochamber.org'},
                {'name': 'Greater Orlando Chamber', 'url': 'https://greaterorldo.com'},
                {'name': 'Orange County Chamber', 'url': 'https://orangechamber.org'},
                {'name': 'Winter Park Chamber', 'url': 'https://winterparkchamber.com'},
                {'name': 'Kissimmee Chamber', 'url': 'https://kissimmeechamber.com'},
                {'name': 'Oviedo Chamber', 'url': 'https://oviedochamber.org'},
                {'name': 'Altamonte Springs Chamber', 'url': 'https://altamontechamber.com'},
                {'name': 'Apopka Chamber', 'url': 'https://apopkachamber.org'},
                {'name': 'Maitland Chamber', 'url': 'https://maitlandchamber.com'},
                {'name': 'Windermere Chamber', 'url': 'https://windermerechamber.com'}
            ]
        }
    
    async def create_session(self):
        if not self.session:
            connector = aiohttp.TCPConnector(limit=10)
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={'User-Agent': random.choice(self.user_agents)}
            )
        return self.session
    
    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None
    

    async def search_directories(self, location: str, directory_types: List[str], max_results: int = 20, progress_callback=None) -> List[Dict]:
        """Enhanced search combining known chambers with web search"""
        session = await self.create_session()
        discovered = []
        
        def log(message):
            if progress_callback:
                progress_callback(message)
            else:
                logging.info(message)
        
        # First, add known chambers for this location
        log(f"🔍 Checking known chambers database for {location}")
        location_lower = location.lower()
        known_count = 0
        for known_location, chambers in self.known_chambers.items():
            if known_location in location_lower or location_lower in known_location:
                log(f"📍 Found {len(chambers)} known chambers for {known_location}")
                for chamber in chambers:
                    if 'chamber of commerce' in directory_types:
                        discovered.append({
                            'name': chamber['name'],
                            'url': chamber['url'],
                            'directory_type': 'chamber of commerce',
                            'location': location,
                            'description': f"Known chamber in {location}"
                        })
                        known_count += 1
        
        log(f"✅ Added {known_count} known chambers")
        
        # Then perform web search for additional directories
        log(f"🌐 Starting web search for additional directories")
        web_results = await self._perform_web_search(session, location, directory_types, max_results, log)
        discovered.extend(web_results)
        
        # Remove duplicates and validate URLs
        log(f"🔄 Validating and removing duplicates from {len(discovered)} results")
        validated_results = await self._validate_and_deduplicate(session, discovered, log)
        
        log(f"🎯 Final result: {len(validated_results)} validated directories")
        
        return validated_results[:max_results]
    
    async def _perform_web_search(self, session, location: str, directory_types: List[str], max_results: int, log_func) -> List[Dict]:
        """Perform comprehensive web search"""
        discovered = []
        
        # Enhanced search patterns
        search_patterns = {
            'chamber of commerce': [
                f"{location} chamber of commerce",
                f"chamber of commerce {location}",
                f"{location} chamber",
                f"chambers {location}",
                f"business chamber {location}",
                f"{location} county chamber",
                f"{location} area chamber",
                f"{location} regional chamber",
                f"{location} local chamber",
                f"{location} business association",
                f"{location} economic development"
            ],
            'business directory': [
                f"{location} business directory",
                f"business listing {location}",
                f"{location} business guide",
                f"local business {location}",
                f"{location} yellow pages",
                f"business association {location}",
                f"{location} trade directory",
                f"{location} company directory"
            ],
            'better business bureau': [
                f"better business bureau {location}",
                f"BBB {location}",
                f"{location} BBB",
                f"better business {location}"
            ]
        }
        
        for directory_type in directory_types:
            log_func(f"🔍 Searching for {directory_type} in {location}")
            patterns = search_patterns.get(directory_type, [f"{directory_type} {location}"])
            
            for i, pattern in enumerate(patterns[:6]):  # Limit patterns to avoid too many requests
                try:
                    log_func(f"   🔎 Pattern {i+1}/6: '{pattern}'")
                    results = await self._search_with_duckduckgo(session, pattern, directory_type, location)
                    discovered.extend(results)
                    log_func(f"   ✅ Found {len(results)} results for '{pattern}'")
                    
                    # Add delay between searches
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    
                except Exception as e:
                    log_func(f"   ❌ Error searching '{pattern}': {str(e)}")
                    continue
        
        return discovered
    
    async def _search_with_duckduckgo(self, session, query: str, directory_type: str, location: str) -> List[Dict]:
        """Search with DuckDuckGo"""
        results = []
        
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            
            async with session.get(search_url) as response:
                if response.status == 200:
                    content = await response.text()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    result_links = soup.find_all('a', {'class': 'result__a'})
                    
                    for link in result_links[:8]:  # Top 8 results per search
                        href = link.get('href')
                        title = link.get_text(strip=True)
                        
                        if href and title and self._is_valid_directory_url(href, directory_type, location):
                            results.append({
                                'name': title[:150],
                                'url': href,
                                'directory_type': directory_type,
                                'location': location,
                                'description': title[:200]
                            })
        
        except Exception as e:
            logging.error(f"Error searching DuckDuckGo for {query}: {str(e)}")
        
        return results
    
    def _is_valid_directory_url(self, url: str, directory_type: str, location: str) -> bool:
        """Enhanced validation for directory URLs"""
        url_lower = url.lower()
        location_lower = location.lower()
        
        # Filter out unwanted domains
        excluded_domains = [
            'facebook.com', 'linkedin.com', 'twitter.com', 'instagram.com', 
            'youtube.com', 'pinterest.com', 'reddit.com', 'wikipedia.org',
            'google.com', 'bing.com', 'yahoo.com', 'duckduckgo.com',
            'yelp.com', 'foursquare.com', 'zillow.com', 'realtor.com'
        ]
        
        if any(domain in url_lower for domain in excluded_domains):
            return False
        
        # Look for directory-specific keywords
        directory_keywords = {
            'chamber of commerce': ['chamber', 'commerce', 'business', 'economic', 'development'],
            'business directory': ['directory', 'business', 'listing', 'guide', 'yellowpages', 'companies'],
            'better business bureau': ['bbb', 'bureau', 'better', 'business']
        }
        
        keywords = directory_keywords.get(directory_type, [])
        keyword_match = any(keyword in url_lower for keyword in keywords)
        
        # Check for location relevance
        location_words = location_lower.replace(' bay', '').replace(' county', '').split()
        location_match = any(word in url_lower for word in location_words if len(word) > 2)
        
        return keyword_match and (location_match or directory_type == 'chamber of commerce')
    
    async def _validate_and_deduplicate(self, session, discovered: List[Dict], log_func) -> List[Dict]:
        """Validate URLs and remove duplicates"""
        seen_urls = set()
        seen_names = set()
        validated = []
        
        log_func(f"🔄 Validating {len(discovered)} discovered directories")
        
        for i, directory in enumerate(discovered):
            url = directory['url']
            name = directory['name'].lower()
            
            # Skip duplicates
            if url in seen_urls or name in seen_names:
                continue
                
            # Quick validation - try to access URL
            try:
                async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status < 400:  # Valid response
                        seen_urls.add(url)
                        seen_names.add(name)
                        validated.append(directory)
                        log_func(f"   ✅ {i+1}: {directory['name']} - Valid")
                    else:
                        log_func(f"   ❌ {i+1}: {directory['name']} - HTTP {response.status}")
            except:
                # If head request fails, still include it (might be valid)
                if url not in seen_urls:
                    seen_urls.add(url)
                    seen_names.add(name)
                    validated.append(directory)
                    log_func(f"   ⚠️ {i+1}: {directory['name']} - Validation failed but included")
        
        log_func(f"✅ Validation complete: {len(validated)} valid directories")
        return validated
    
    async def scrape_directory_listings(self, directory_url: str) -> List[Dict]:
        """Enhanced scraping that handles both static and JavaScript-heavy sites"""
        session = await self.create_session()
        businesses = []
        
        try:
            logging.info(f"🔍 Starting enhanced scrape of {directory_url}")
            
            # Step 1: Try basic scraping first (faster)
            logging.info("📄 Attempting basic scraping...")
            businesses = await self._basic_scrape_directory(directory_url, session)
            
            # Step 2: If basic scraping finds few/no businesses, try enhanced Playwright scraping
            if len(businesses) < 3:
                logging.info(f"⚡ Basic scraping found only {len(businesses)} businesses. Trying enhanced Playwright scraping...")
                playwright_businesses = await self._enhanced_playwright_scrape(directory_url)
                
                # Use Playwright results if significantly better
                if len(playwright_businesses) > len(businesses):
                    logging.info(f"✅ Enhanced scraping found {len(playwright_businesses)} businesses (better than {len(businesses)})")
                    businesses = playwright_businesses
                else:
                    logging.info(f"📊 Enhanced scraping found {len(playwright_businesses)} businesses (keeping basic results)")
            
            # Step 3: Clean and validate
            clean_businesses = self._clean_businesses_flexible(businesses)
            
            # Additional validation for enhanced scraper
            validated_businesses = []
            for business in clean_businesses:
                if self._is_valid_business_record(business):
                    validated_businesses.append(business)
                else:
                    logging.info(f"❌ Filtered out invalid business: {business.get('business_name', 'N/A')}")
            
            logging.info(f"✅ Final result: {len(validated_businesses)} validated businesses extracted")
            return validated_businesses
                
        except Exception as e:
            logging.error(f"❌ Error in enhanced scraping {directory_url}: {str(e)}")
            return businesses
    
    async def _basic_scrape_directory(self, directory_url: str, session) -> List[Dict]:
        """Basic scraping using BeautifulSoup (original method)"""
        businesses = []
        
        try:
            # Step 1: Try to find business directory pages
            directory_pages = await self._find_directory_pages_flexible(directory_url, session)
            
            # Step 2: If no specific directory pages found, scrape the main page
            if not directory_pages:
                logging.info("📄 No specific directory pages found, trying main page")
                directory_pages = [directory_url]
            
            # Step 3: Extract businesses from all pages
            for page_url in directory_pages:
                logging.info(f"📋 Basic scraping businesses from: {page_url}")
                page_businesses = await self._scrape_businesses_flexible(page_url, session)
                businesses.extend(page_businesses)
                logging.info(f"   Found {len(page_businesses)} businesses on this page")
            
            return businesses
                
        except Exception as e:
            logging.error(f"❌ Error in basic scraping {directory_url}: {str(e)}")
            return businesses
    
    async def _enhanced_playwright_scrape(self, directory_url: str) -> List[Dict]:
        """Enhanced scraping using Playwright for JavaScript-heavy sites"""
        businesses = []
        
        try:
            logging.info(f"🎭 Starting Playwright scraping of {directory_url}")
            
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
                page = await context.new_page()
                
                # Navigate to the main page
                await page.goto(directory_url, wait_until="networkidle", timeout=60000)
                logging.info("🌐 Page loaded, looking for business directory links...")
                
                # Step 1: Find business directory links on the page
                directory_links = await self._find_directory_links_playwright(page, directory_url)
                
                # Step 2: If no directory links found, scrape the current page
                if not directory_links:
                    logging.info("📄 No directory links found, scraping current page...")
                    directory_links = [directory_url]
                
                # Step 3: Scrape businesses from each directory page
                for link in directory_links:
                    try:
                        if link != directory_url:
                            await page.goto(link, wait_until="networkidle", timeout=60000)
                            await asyncio.sleep(2)  # Wait for dynamic content
                        
                        logging.info(f"📋 Playwright scraping businesses from: {link}")
                        page_businesses = await self._scrape_businesses_playwright(page, link)
                        businesses.extend(page_businesses)
                        logging.info(f"   Found {len(page_businesses)} businesses on this page")
                        
                    except Exception as e:
                        logging.error(f"❌ Error scraping page {link}: {str(e)}")
                        continue
                
                await browser.close()
                
            # Apply final validation to Playwright results  
            validated_businesses = []
            for business in businesses:
                if self._is_valid_business_record(business):
                    validated_businesses.append(business)
                else:
                    logging.info(f"❌ Filtered out invalid Playwright business: {business.get('business_name', 'N/A')}")
            
            businesses = validated_businesses
                
        except Exception as e:
            logging.error(f"❌ Error in Playwright scraping {directory_url}: {str(e)}")
        
        return businesses
    
    async def _find_directory_links_playwright(self, page, base_url: str) -> List[str]:
        """Universal directory finder that works with any website technology"""
        directory_links = []
        
        try:
            # Wait for page to be fully loaded
            await page.wait_for_load_state('networkidle')
            
            logging.info("🌍 Starting universal directory discovery...")
            
            # Strategy 1: Comprehensive Link Analysis
            logging.info("🔍 Strategy 1: Comprehensive Link Analysis")
            link_directories = await self._strategy_comprehensive_links(page, base_url)
            directory_links.extend(link_directories)
            
            # Strategy 2: URL Pattern Testing
            logging.info("🔍 Strategy 2: URL Pattern Testing")
            pattern_directories = await self._strategy_url_patterns(page, base_url)
            directory_links.extend(pattern_directories)
            
            # Strategy 3: Navigation Menu Analysis
            logging.info("🔍 Strategy 3: Navigation Menu Analysis")
            nav_directories = await self._strategy_navigation_analysis(page, base_url)
            directory_links.extend(nav_directories)
            
            # Strategy 4: Content Pattern Recognition
            logging.info("🔍 Strategy 4: Content Pattern Recognition")
            content_directories = await self._strategy_content_patterns(page, base_url)
            directory_links.extend(content_directories)
            
            # Remove duplicates and validate
            unique_directories = list(set(directory_links))
            validated_directories = []
            
            for directory_url in unique_directories:
                if await self._validate_directory_page(page, directory_url):
                    validated_directories.append(directory_url)
                    logging.info(f"✅ Validated directory: {directory_url}")
                else:
                    logging.info(f"❌ Invalid directory: {directory_url}")
            
            # Return the best validated directories
            return validated_directories[:3]  # Top 3 validated directories
            
        except Exception as e:
            logging.error(f"❌ Error in universal directory discovery: {str(e)}")
            return []
    
    async def _strategy_comprehensive_links(self, page, base_url: str) -> List[str]:
        """Comprehensive link analysis for any CMS type"""
        
        # Expanded keyword sets for different CMS types and languages
        all_keywords = [
            # Primary directory terms
            'business directory', 'member directory', 'business listing', 'member listing',
            'business search', 'member search', 'find businesses', 'find members',
            
            # Secondary terms
            'directory', 'businesses', 'members', 'companies', 'organizations',
            'roster', 'listings', 'membership', 'business guide', 'member guide',
            
            # Navigation terms
            'our businesses', 'our members', 'local businesses', 'browse businesses',
            'browse members', 'search businesses', 'business database', 'member database',
            
            # CMS-specific terms
            'business profiles', 'member profiles', 'company profiles', 'organization profiles',
            'business cards', 'member cards', 'company cards', 'organization cards',
            
            # Action-based terms
            'explore businesses', 'explore members', 'discover businesses', 'discover members',
            'view businesses', 'view members', 'list businesses', 'list members',
            
            # Common variations
            'biz directory', 'biz listing', 'business list', 'member list', 'company list',
            'organization list', 'business index', 'member index', 'company index'
        ]
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        found_links = []
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            text = link.get_text().lower().strip()
            
            if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
                
            full_url = urljoin(base_url, href)
            
            # Skip obvious non-directory links
            skip_terms = ['application', 'form', 'join', 'register', 'login', 'contact', 'about', 'news', 'events']
            if any(skip in text for skip in skip_terms):
                continue
            
            # Check against all keywords
            for keyword in all_keywords:
                if keyword in text or keyword in href.lower():
                    found_links.append(full_url)
                    logging.info(f"🔗 Found link-based directory: {text} -> {full_url}")
                    break
        
        return found_links
    
    async def _strategy_url_patterns(self, page, base_url: str) -> List[str]:
        """Test common URL patterns for any CMS"""
        
        from urllib.parse import urlparse
        
        parsed_url = urlparse(base_url)
        base_domain = f'{parsed_url.scheme}://{parsed_url.netloc}'
        
        # Comprehensive URL patterns for any CMS
        url_patterns = [
            # Standard directory paths
            '/directory', '/directories', '/business-directory', '/member-directory',
            '/businesses', '/members', '/companies', '/organizations', '/roster',
            '/business-listing', '/member-listing', '/business-search', '/member-search',
            '/find-businesses', '/find-members', '/business-guide', '/member-guide',
            '/listings', '/database', '/search', '/browse', '/business', '/member',
            '/membership', '/company', '/profiles', '/list', '/business-list',
            '/member-list', '/company-list', '/organization-list',
            
            # CMS-specific patterns
            '/business-profiles', '/member-profiles', '/company-profiles',
            '/business-cards', '/member-cards', '/company-cards',
            '/biz-directory', '/biz-listing', '/business-index', '/member-index',
            
            # WordPress-specific patterns
            '/business-directory-plugin', '/member-directory-plugin',
            '/wp-business-directory', '/wp-member-directory',
            
            # Custom CMS patterns
            '/portal/businesses', '/portal/members', '/portal/directory',
            '/site/businesses', '/site/members', '/site/directory'
        ]
        
        # Test subdomain patterns
        subdomain_patterns = [
            'business', 'members', 'directory', 'member', 'companies', 'portal',
            'businesses', 'biz', 'dir', 'listing', 'listings'
        ]
        
        working_patterns = []
        
        # Test URL patterns with timeout
        for pattern in url_patterns:
            test_url = base_domain + pattern
            try:
                response = await page.goto(test_url, wait_until='networkidle', timeout=15000)
                if response.status == 200:
                    working_patterns.append(test_url)
                    logging.info(f"✅ Working URL pattern: {test_url}")
            except Exception as e:
                continue
        
        # Test subdomain patterns
        for subdomain in subdomain_patterns:
            domain_parts = parsed_url.netloc.split('.')
            if len(domain_parts) >= 2:
                test_domain = f'{subdomain}.{".".join(domain_parts[-2:])}'
                test_url = f'{parsed_url.scheme}://{test_domain}'
                try:
                    response = await page.goto(test_url, wait_until='networkidle', timeout=15000)
                    if response.status == 200:
                        working_patterns.append(test_url)
                        logging.info(f"✅ Working subdomain: {test_url}")
                except Exception as e:
                    continue
        
        return working_patterns
    
    async def _strategy_navigation_analysis(self, page, base_url: str) -> List[str]:
        """Analyze navigation menus for any CMS"""
        
        # Look for navigation elements across different CMS types
        nav_selectors = [
            'nav', '.navigation', '.nav', '.menu', '.main-menu', '.primary-menu',
            '.header-menu', '.top-menu', '.site-nav', '.navbar', '.nav-menu',
            '.main-nav', '.primary-nav', '.top-nav', '.header-nav', '.site-menu',
            '.navigation-menu', '.menu-main', '.menu-primary', '.menu-header',
            '.wp-nav-menu', '.genesis-nav-menu', '.nav-primary', '.nav-secondary'
        ]
        
        found_directories = []
        
        for selector in nav_selectors:
            try:
                nav_elements = await page.locator(selector).all()
                
                for nav in nav_elements:
                    nav_content = await nav.inner_html()
                    soup = BeautifulSoup(nav_content, 'html.parser')
                    
                    for link in soup.find_all('a', href=True):
                        href = link.get('href')
                        text = link.get_text().lower().strip()
                        
                        if not href:
                            continue
                            
                        full_url = urljoin(base_url, href)
                        
                        # Navigation-specific directory indicators
                        nav_keywords = [
                            'directory', 'members', 'businesses', 'membership',
                            'business', 'member', 'company', 'organization',
                            'roster', 'listings', 'companies', 'profiles'
                        ]
                        
                        for keyword in nav_keywords:
                            if keyword in text or keyword in href.lower():
                                found_directories.append(full_url)
                                logging.info(f"🔗 Found nav directory: {text} -> {full_url}")
                                break
                                
            except Exception as e:
                continue
        
        return found_directories
    
    async def _strategy_content_patterns(self, page, base_url: str) -> List[str]:
        """Content pattern recognition for any CMS"""
        
        content = await page.content()
        
        # Look for patterns that suggest directory functionality
        patterns = [
            r'search\s+(?:for\s+)?(?:businesses|members|companies)',
            r'browse\s+(?:our\s+)?(?:businesses|members|companies)',
            r'find\s+(?:local\s+)?(?:businesses|members|companies)',
            r'(?:business|member)\s+(?:directory|listing|database)',
            r'(?:our|local)\s+(?:businesses|members|companies)',
            r'explore\s+(?:businesses|members|companies)',
            r'discover\s+(?:businesses|members|companies)',
            r'view\s+(?:all\s+)?(?:businesses|members|companies)',
            r'(?:business|member|company)\s+(?:profiles|cards|index)'
        ]
        
        pattern_links = []
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.I)
            for match in matches:
                # Look for nearby links
                start_pos = max(0, match.start() - 500)
                end_pos = min(len(content), match.end() + 500)
                context = content[start_pos:end_pos]
                
                # Find links in the context
                link_matches = re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', context, re.I)
                
                for link_match in link_matches:
                    href = link_match.group(1)
                    text = link_match.group(2)
                    
                    if not href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                        full_url = urljoin(base_url, href)
                        pattern_links.append(full_url)
                        logging.info(f"🔗 Found pattern directory: {text} -> {full_url}")
        
        return pattern_links
    
    async def _validate_directory_page(self, page, url: str) -> bool:
        """Universal validation for any CMS directory page"""
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)
            
            content = await page.content()
            
            # Enhanced validation criteria
            score = 0
            
            # Phone numbers (strong indicator)
            phone_count = len(re.findall(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', content))
            score += phone_count * 5
            
            # Email addresses (strong indicator)
            email_count = len(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content))
            score += email_count * 5
            
            # Business profile links (very strong indicator)
            profile_patterns = [
                r'href=["\'][^"\']*(?:detail|profile|member|business|company)[^"\']*["\']',
                r'href=["\'][^"\']*\/(?:business|member|company)\/[^"\']*["\']',
                r'href=["\'][^"\']*(?:listing|directory|roster)[^"\']*["\']'
            ]
            
            profile_links = 0
            for pattern in profile_patterns:
                profile_links += len(re.findall(pattern, content, re.I))
            
            score += profile_links * 10
            
            # Directory-specific words
            directory_words = [
                'business', 'member', 'company', 'organization', 'contact',
                'phone', 'email', 'website', 'address', 'category', 'type',
                'profile', 'listing', 'directory', 'roster', 'database'
            ]
            
            for word in directory_words:
                word_count = content.lower().count(word)
                score += min(word_count, 10) * 1  # Cap at 10 occurrences per word
            
            # Search/filter functionality (strong indicator)
            search_patterns = [
                r'<(?:form|input|select)[^>]*(?:search|filter|category)',
                r'<(?:button|input)[^>]*(?:search|filter|find)',
                r'class=["\'][^"\']*(?:search|filter|directory)[^"\']*["\']'
            ]
            
            for pattern in search_patterns:
                if re.search(pattern, content, re.I):
                    score += 50
                    break
            
            # Pagination (moderate indicator)
            pagination_patterns = [
                r'<[^>]*(?:pagination|pager|load-more)',
                r'<(?:button|a)[^>]*(?:next|previous|more|load)',
                r'class=["\'][^"\']*(?:pagination|pager|load-more)[^"\']*["\']'
            ]
            
            for pattern in pagination_patterns:
                if re.search(pattern, content, re.I):
                    score += 25
                    break
            
            # Multiple contact blocks (strong indicator)
            contact_blocks = len(re.findall(r'<[^>]*(?:contact|business|member|company)[^>]*>.*?(?:phone|email|website).*?</[^>]*>', content, re.I | re.S))
            score += contact_blocks * 20
            
            logging.info(f"📊 Directory validation score: {score} (threshold: 100)")
            
            return score >= 100
            
        except Exception as e:
            logging.error(f"❌ Error validating directory page {url}: {str(e)}")
            return False
    
    async def _scrape_businesses_playwright(self, page, page_url: str) -> List[Dict]:
        """Scrape businesses from a page using Playwright"""
        businesses = []
        
        try:
            # Wait for content to load
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)  # Additional wait for dynamic content
            
            # Try to find and interact with search/directory elements
            await self._interact_with_directory_elements(page)
            
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Check if this looks like a business directory listing page with profile links
            profile_links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and ('/list/detail/' in href or '/list/member/' in href or '/list/ql/' in href or '/profile/' in href or '/business/' in href):
                    # Fix URL construction - check if already full URL
                    if href.startswith('http'):
                        full_url = href
                    elif href.startswith('/'):
                        from urllib.parse import urlparse
                        parsed_url = urlparse(page_url)
                        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
                        full_url = base_domain + href
                    else:
                        full_url = urljoin(page_url, href)
                    profile_links.append(full_url)
            
            profile_links = list(set(profile_links))
            logging.info(f"🔗 Found {len(profile_links)} business profile links")
            
            # If we have profile links, extract businesses from individual profiles
            if len(profile_links) > 0:
                logging.info("🧪 Using profile-based extraction method")
                businesses = await self._extract_from_business_profiles(page, profile_links[:25])  # Limit to 25 for performance
            else:
                logging.info("📄 Using page-based extraction method")
                # Fall back to page-based extraction
                businesses = await self._extract_from_current_page(page, page_url, soup)
            
            # Remove duplicates
            businesses = self._remove_duplicate_businesses(businesses)
            
            logging.info(f"📋 Extracted {len(businesses)} businesses from Playwright scraping")
            
        except Exception as e:
            logging.error(f"❌ Error in Playwright business scraping: {str(e)}")
        
        return businesses
    
    async def _extract_from_business_profiles(self, page, profile_links: List[str]) -> List[Dict]:
        """Extract businesses from individual profile pages"""
        businesses = []
        
        for i, business_url in enumerate(profile_links):
            try:
                logging.info(f"📋 Processing profile {i+1}/{len(profile_links)}: {business_url}")
                
                # Navigate to business profile
                await page.goto(business_url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(1500)  # Wait for dynamic content
                
                # Get profile content
                profile_content = await page.content()
                profile_soup = BeautifulSoup(profile_content, 'html.parser')
                
                # Extract business information
                business = {}
                page_text = profile_soup.get_text()
                
                # Enhanced business name extraction for GrowthZone
                business_name = None
                
                # Strategy 1: From page title
                title_tag = profile_soup.find('title')
                if title_tag:
                    title = title_tag.get_text().strip()
                    if ' - ' in title and 'South Tampa Chamber' in title:
                        business_name = title.split(' - ')[0].strip()
                    elif '|' in title:
                        business_name = title.split('|')[0].strip()
                    elif title and len(title) < 100 and 'South Tampa Chamber' not in title:
                        business_name = title.strip()
                
                # Strategy 2: From h1/h2 elements
                if not business_name:
                    for heading in profile_soup.find_all(['h1', 'h2', 'h3']):
                        heading_text = heading.get_text().strip()
                        if heading_text and len(heading_text) < 100 and self._is_valid_business_name(heading_text):
                            business_name = heading_text
                            break
                
                # Strategy 3: From structured data or specific containers
                if not business_name:
                    # Look for business name in common GrowthZone patterns
                    name_containers = profile_soup.find_all(['div', 'span'], class_=re.compile(r'name|title|business|company', re.I))
                    for container in name_containers:
                        container_text = container.get_text().strip()
                        if container_text and len(container_text) < 100 and self._is_valid_business_name(container_text):
                            business_name = container_text
                            break
                
                # Strategy 4: Extract from URL if possible
                if not business_name:
                    # Some URLs contain business names
                    url_parts = business_url.split('/')
                    for part in url_parts:
                        if part and '-' in part and len(part) > 5:
                            # Convert URL slug to business name
                            potential_name = part.replace('-', ' ').title()
                            if self._is_valid_business_name(potential_name):
                                business_name = potential_name
                                break
                
                if business_name:
                    business['business_name'] = business_name
                    logging.info(f"✅ Extracted business name: {business_name}")
                else:
                    logging.info(f"❌ Could not extract business name from profile")
                    continue  # Skip if no business name
                
                # Extract phone number
                phone_patterns = [
                    r'\((\d{3})\)\s*(\d{3})-(\d{4})',
                    r'(\d{3})-(\d{3})-(\d{4})',
                    r'(\d{3})\.(\d{3})\.(\d{4})',
                    r'(\d{3})\s+(\d{3})\s+(\d{4})'
                ]
                
                for pattern in phone_patterns:
                    phone_match = re.search(pattern, page_text)
                    if phone_match:
                        # Format phone number consistently
                        if len(phone_match.groups()) == 3:
                            phone = f"({phone_match.group(1)}) {phone_match.group(2)}-{phone_match.group(3)}"
                        else:
                            phone = phone_match.group(0)
                        business['phone'] = phone
                        logging.info(f"📞 Extracted phone: {phone}")
                        break
                
                # Extract email address
                email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', page_text)
                if email_match:
                    business['email'] = email_match.group(1)
                    logging.info(f"📧 Extracted email: {business['email']}")
                
                # Extract website
                website_links = profile_soup.find_all('a', href=re.compile(r'http'))
                for link in website_links:
                    href = link.get('href')
                    # Skip social media and chamber links
                    skip_domains = ['facebook', 'twitter', 'instagram', 'linkedin', 'southtampachamber', 'youtube']
                    if href and not any(domain in href.lower() for domain in skip_domains):
                        business['website'] = href
                        logging.info(f"🌐 Extracted website: {href}")
                        break
                
                # Extract address
                address_patterns = [
                    r'(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Circle|Cir|Place|Pl)[A-Za-z\s,]*\d{5})',
                    r'(\d+\s+[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s*\d{5})'
                ]
                
                for pattern in address_patterns:
                    address_match = re.search(pattern, page_text)
                    if address_match:
                        business['address'] = address_match.group(1).strip()
                        logging.info(f"📍 Extracted address: {business['address']}")
                        break
                
                # Only add if we have a name and at least one contact method
                if business.get('business_name') and (business.get('phone') or business.get('email') or business.get('website')):
                    businesses.append(business)
                    logging.info(f"✅ Successfully extracted business")
                else:
                    logging.info(f"❌ Business rejected - insufficient data")
                    
            except Exception as e:
                logging.error(f"❌ Error processing profile {business_url}: {str(e)}")
                continue
        
        return businesses
    
    async def _extract_from_current_page(self, page, page_url: str, soup) -> List[Dict]:
        """Extract businesses from current page content (fallback method)"""
        businesses = []
        
        # Strategy 1: Look for GrowthZone-specific business containers
        business_containers = soup.find_all(['div', 'article', 'section'], 
                                          class_=re.compile(r'business|member|company|listing|card|item|entry|gz-'))
        
        # Strategy 2: Look for any div with contact information
        contact_divs = soup.find_all('div', string=re.compile(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}'))
        business_containers.extend(contact_divs)
        
        # Strategy 3: Look for parent elements of phone/email links
        phone_links = soup.find_all('a', href=re.compile(r'tel:'))
        email_links = soup.find_all('a', href=re.compile(r'mailto:'))
        
        for link in phone_links + email_links:
            parent = link.parent
            if parent:
                business_containers.append(parent)
        
        logging.info(f"📊 Found {len(business_containers)} potential business containers")
        
        # Extract businesses from containers
        for container in business_containers:
            business = self._extract_business_from_container_playwright(container, page_url)
            if business and self._is_valid_business_record(business):
                businesses.append(business)
        
        # Strategy 4: Look for table-based listings
        tables = soup.find_all('table')
        for table in tables:
            table_businesses = self._extract_businesses_from_table_playwright(table, page_url)
            for business in table_businesses:
                if self._is_valid_business_record(business):
                    businesses.append(business)
        
        return businesses
    
    async def _interact_with_directory_elements(self, page):
        """Interact with directory elements to load more content"""
        try:
            # Try to find a search button or "load more" button
            search_selectors = [
                'button:has-text("Search")',
                'input[type="submit"][value*="Search"]',
                'button:has-text("Load")',
                'button:has-text("More")',
                'button:has-text("Show All")',
                'button:has-text("View All")',
                'a:has-text("Directory")',
                'a:has-text("Members")',
                'a:has-text("Businesses")'
            ]
            
            for selector in search_selectors:
                try:
                    if await page.locator(selector).count() > 0:
                        await page.locator(selector).first.click()
                        await page.wait_for_timeout(3000)  # Wait for results
                        logging.info(f"📋 Clicked element: {selector}")
                        break
                except Exception as e:
                    continue
            
            # Try to find dropdown menus or select elements that might filter businesses
            select_elements = await page.locator('select').all()
            for select in select_elements:
                try:
                    options = await select.locator('option').all()
                    if len(options) > 1:
                        # Try selecting "All" or first non-empty option
                        for option in options:
                            option_text = await option.inner_text()
                            if any(keyword in option_text.lower() for keyword in ['all', 'show', 'view']):
                                await select.select_option(value=await option.get_attribute('value'))
                                await page.wait_for_timeout(2000)
                                logging.info(f"📋 Selected option: {option_text}")
                                break
                        break
                except Exception as e:
                    continue
            
        except Exception as e:
            logging.error(f"❌ Error interacting with directory elements: {str(e)}")
    
    def _is_valid_business_record(self, business: Dict) -> bool:
        """Check if a business record is valid"""
        if not business or not business.get('business_name'):
            return False
        
        name = business.get('business_name', '').strip()
        
        # Must have valid business name
        if not self._is_valid_business_name(name):
            return False
        
        # Must have at least one contact method
        phone = business.get('phone', '').strip()
        email = business.get('email', '').strip()
        website = business.get('website', '').strip()
        
        if not any([phone, email, website]):
            return False
        
        # Phone validation - must be real phone, not placeholder
        if phone:
            if not re.match(r'^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$', phone):
                return False
            # Check for placeholder numbers
            if phone in ['(000) 000-0000', '000-000-0000', '(123) 456-7890', '123-456-7890']:
                return False
        
        # Email validation - must be real email, not placeholder
        if email:
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return False
            # Check for generic/placeholder emails
            if any(generic in email.lower() for generic in ['example.com', 'test.com', 'placeholder']):
                return False
        
        # Website validation - must be real website
        if website:
            if any(invalid in website.lower() for invalid in ['example.com', 'test.com', 'placeholder']):
                return False
        
        # Final check: business name must not be a sentence or description
        if len(name.split()) > 8:  # Too many words for a business name
            return False
        
        # Must not contain email addresses or phone numbers in the name
        if '@' in name or re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', name):
            return False
        
        return True
    
    def _remove_duplicate_businesses(self, businesses: List[Dict]) -> List[Dict]:
        """Remove duplicate businesses"""
        seen = set()
        unique_businesses = []
        
        for business in businesses:
            # Create a unique identifier
            name = business.get('business_name', '').strip().lower()
            phone = business.get('phone', '').strip()
            email = business.get('email', '').strip()
            
            identifier = f"{name}|{phone}|{email}"
            
            if identifier not in seen:
                seen.add(identifier)
                unique_businesses.append(business)
        
        return unique_businesses
    
    def _extract_business_from_container_playwright(self, container, base_url: str) -> Optional[Dict]:
        """Extract business info from a container using Playwright results"""
        try:
            business = {}
            text = container.get_text().strip()
            
            # Skip if container has too little content
            if len(text) < 10:
                return None
            
            # Enhanced business name extraction for GrowthZone CMS
            name_element = None
            
            # Strategy 1: Look for heading elements
            name_element = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            
            # Strategy 2: Look for elements with specific classes
            if not name_element:
                name_element = container.find(['div', 'span', 'a'], class_=re.compile(r'name|title|business|company', re.I))
            
            # Strategy 3: Look for strong/bold elements
            if not name_element:
                name_element = container.find(['strong', 'b'])
            
            # Strategy 4: Look for the first link in the container (often the business name)
            if not name_element:
                name_element = container.find('a', href=True)
            
            # Strategy 5: Try to extract from structured data or specific patterns
            if not name_element:
                # Look for patterns like "Business Name | Category" or "Business Name - Description"
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                if lines:
                    first_line = lines[0]
                    # Remove common prefixes/suffixes
                    if '|' in first_line:
                        potential_name = first_line.split('|')[0].strip()
                    elif ' - ' in first_line:
                        potential_name = first_line.split(' - ')[0].strip()
                    elif len(first_line) < 100:  # Reasonable length for business name
                        potential_name = first_line
                    else:
                        potential_name = None
                    
                    if potential_name and self._is_valid_business_name(potential_name):
                        business['business_name'] = potential_name
            
            # Extract name from element if found
            if name_element and not business.get('business_name'):
                name = name_element.get_text().strip()
                # Clean up the name
                if '|' in name:
                    name = name.split('|')[0].strip()
                elif ' - ' in name:
                    name = name.split(' - ')[0].strip()
                
                if self._is_valid_business_name(name):
                    business['business_name'] = name
            
            # If still no name, try more aggressive extraction
            if not business.get('business_name'):
                # Look for any text that might be a business name
                for line in text.split('\n')[:10]:  # Check first 10 lines
                    line = line.strip()
                    if len(line) > 3 and len(line) < 100:
                        # Skip lines that are obviously not business names
                        skip_patterns = [
                            'phone', 'email', 'website', 'address', 'contact',
                            'description', 'category', 'type', 'location',
                            'hours', 'open', 'closed', 'monday', 'tuesday',
                            'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
                        ]
                        
                        line_lower = line.lower()
                        if not any(pattern in line_lower for pattern in skip_patterns):
                            if self._is_valid_business_name(line):
                                business['business_name'] = line
                                break
            
            # Extract contact information (existing logic)
            phone_match = re.search(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', text)
            if phone_match:
                business['phone'] = self._clean_phone_number(phone_match.group(1))
            
            email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
            if email_match:
                business['email'] = email_match.group(1)
            
            # Look for website links
            links = container.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                if href and ('http' in href or 'www' in href):
                    if not any(social in href.lower() for social in ['facebook', 'twitter', 'instagram', 'linkedin']):
                        business['website'] = href
                        break
            
            # Look for social media links
            social_links = []
            for link in links:
                href = link.get('href')
                if href and any(social in href.lower() for social in ['facebook', 'twitter', 'instagram', 'linkedin']):
                    social_links.append(href)
            
            if social_links:
                business['socials'] = ', '.join(social_links)
            
            # Extract address (look for common address patterns)
            address_match = re.search(r'(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Circle|Cir|Place|Pl)[A-Za-z\s,]*\d{5})', text)
            if address_match:
                business['address'] = address_match.group(1)
            
            return business if business.get('business_name') else None
            
        except Exception as e:
            logging.error(f"❌ Error extracting business from container: {str(e)}")
            return None
    
    def _extract_businesses_from_table_playwright(self, table, base_url: str) -> List[Dict]:
        """Extract businesses from table using Playwright results"""
        businesses = []
        
        try:
            rows = table.find_all('tr')
            if len(rows) < 2:  # Need at least header and one data row
                return businesses
            
            # Get headers
            headers = [th.get_text().strip().lower() for th in rows[0].find_all(['th', 'td'])]
            
            # Process data rows
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:  # Need at least 2 cells for meaningful data
                    business = self._extract_business_from_table_row_playwright(cells, headers, base_url)
                    if business:
                        businesses.append(business)
            
        except Exception as e:
            logging.error(f"❌ Error extracting businesses from table: {str(e)}")
        
        return businesses
    
    def _extract_business_from_table_row_playwright(self, cells, headers, base_url: str) -> Optional[Dict]:
        """Extract business info from table row using Playwright results"""
        try:
            business = {}
            
            # Map cells to business fields based on headers
            for i, cell in enumerate(cells):
                cell_text = cell.get_text().strip()
                if not cell_text or len(cell_text) < 2:
                    continue
                
                header = headers[i] if i < len(headers) else ""
                
                # Map based on header content
                if any(keyword in header for keyword in ['name', 'business', 'company']) and not business.get('business_name'):
                    if self._is_valid_business_name(cell_text):
                        business['business_name'] = cell_text
                elif any(keyword in header for keyword in ['phone', 'tel']) and not business.get('phone'):
                    business['phone'] = self._clean_phone_number(cell_text)
                elif any(keyword in header for keyword in ['email', 'mail']) and not business.get('email'):
                    email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', cell_text)
                    if email_match:
                        business['email'] = email_match.group(1)
                elif any(keyword in header for keyword in ['website', 'web', 'url']) and not business.get('website'):
                    if 'http' in cell_text or 'www' in cell_text:
                        business['website'] = cell_text
                elif any(keyword in header for keyword in ['address', 'location']) and not business.get('address'):
                    business['address'] = cell_text
            
            # If no header mapping worked, use positional logic
            if not business.get('business_name') and len(cells) >= 2:
                first_cell = cells[0].get_text().strip()
                if self._is_valid_business_name(first_cell):
                    business['business_name'] = first_cell
            
            return business if business.get('business_name') else None
            
        except Exception as e:
            logging.error(f"❌ Error extracting business from table row: {str(e)}")
            return None
    
    def _extract_business_from_element_playwright(self, element, base_url: str) -> Optional[Dict]:
        """Extract business info from any element using Playwright results"""
        try:
            business = {}
            text = element.get_text().strip()
            
            # Skip if element has too little content
            if len(text) < 10:
                return None
            
            # Find business name
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines:
                first_line = lines[0]
                if self._is_valid_business_name(first_line):
                    business['business_name'] = first_line
            
            # Extract contact info
            phone_match = re.search(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', text)
            if phone_match:
                business['phone'] = self._clean_phone_number(phone_match.group(1))
            
            email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
            if email_match:
                business['email'] = email_match.group(1)
            
            return business if business.get('business_name') else None
            
        except Exception as e:
            logging.error(f"❌ Error extracting business from element: {str(e)}")
            return None
    
    def _is_valid_business_name(self, name: str) -> bool:
        """Check if name is likely a real business name"""
        if not name or len(name) < 3 or len(name) > 100:
            return False
        
        # Skip obvious junk and form elements
        junk_patterns = [
            'home', 'about', 'contact', 'services', 'news', 'events',
            'login', 'register', 'search', 'navigation', 'menu',
            'header', 'footer', 'privacy', 'terms', 'copyright',
            'click here', 'read more', 'learn more', 'view all',
            'member application', 'application', 'form', 'submit',
            'required field', 'span', 'div', 'class', 'title',
            'register now', 'sign up', 'membership', 'join',
            'form-req', 'gz-form', 'required', 'field', 'select',
            'please enter', 'enter your', 'your name', 'your email',
            'your phone', 'your address', 'contact information',
            'member login', 'password', 'username', 'email address',
            'phone number', 'first name', 'last name', 'company name',
            'business name', 'street address', 'city', 'state', 'zip',
            'country', 'website url', 'fax number', 'mobile number'
        ]
        
        name_lower = name.lower()
        if any(junk in name_lower for junk in junk_patterns):
            return False
        
        # Skip HTML-like content
        if '<' in name or '>' in name or name.startswith('*') or 'class=' in name:
            return False
        
        # Skip if it's mostly symbols or numbers
        if len(re.sub(r'[A-Za-z\s]', '', name)) > len(name) * 0.3:
            return False
        
        # Skip if it starts with common form field indicators
        if name.startswith(('*', '(', '[', '{', '<')):
            return False
        
        # Business indicators
        business_indicators = [
            'llc', 'inc', 'corp', 'company', 'co.', 'ltd', 'limited',
            'group', 'associates', 'partners', 'services', 'solutions',
            'consulting', 'restaurant', 'store', 'shop', 'clinic',
            'center', 'law', 'legal', 'medical', 'dental', 'insurance',
            'real estate', 'accounting', 'construction', 'design',
            'engineering', 'technology', 'management', 'agency', 'firm',
            'studio', 'gallery', 'market', 'trading', 'supply', 'equipment',
            'repair', 'maintenance', 'cleaning', 'security', 'transport',
            'logistics', 'hotel', 'motel', 'inn', 'resort', 'cafe',
            'bar', 'grill', 'deli', 'bakery', 'pharmacy', 'bank',
            'auto', 'automotive', 'dealership', 'salon', 'spa', 'fitness'
        ]
        
        # If it has clear business indicators, it's likely a business
        if any(indicator in name_lower for indicator in business_indicators):
            return True
        
        # If it's properly capitalized and not all caps, might be a business
        if not name.isupper() and any(word[0].isupper() for word in name.split()):
            # Additional check: must not be a single word unless it's clearly a business name
            words = name.split()
            if len(words) == 1:
                return any(indicator in name_lower for indicator in business_indicators)
            # Must be at least 2 words and not contain form-related words
            return len(words) >= 2 and not any(form_word in name_lower for form_word in ['application', 'form', 'login', 'register'])
        
        return False
    
    async def _find_directory_pages_flexible(self, base_url: str, session) -> List[str]:
        """Find business directory pages with more flexible matching"""
        directory_pages = []
        
        try:
            async with session.get(base_url) as response:
                if response.status != 200:
                    return directory_pages
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
            
            # Look for any links that might lead to business listings
            potential_links = []
            
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                text = link.get_text().lower().strip()
                
                if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                    continue
                
                # More flexible matching - any of these words might indicate a directory
                directory_words = [
                    'member', 'business', 'directory', 'listing', 'company', 'organization',
                    'roster', 'search', 'browse', 'find', 'businesses', 'members',
                    'companies', 'organizations', 'list', 'database'
                ]
                
                if any(word in text for word in directory_words) or any(word in href.lower() for word in directory_words):
                    full_url = urljoin(base_url, href)
                    potential_links.append((full_url, text))
                    logging.info(f"🔗 Found potential directory link: {text} -> {full_url}")
            
            # Test the most promising links
            for url, text in potential_links[:5]:  # Test top 5 links
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                        if response.status == 200:
                            content = await response.text()
                            if self._looks_like_business_directory(content):
                                directory_pages.append(url)
                                logging.info(f"✅ Confirmed business directory: {url}")
                except:
                    continue
            
            return directory_pages
            
        except Exception as e:
            logging.error(f"❌ Error finding directory pages: {str(e)}")
            return directory_pages
    
    def _looks_like_business_directory(self, content: str) -> bool:
        """More flexible check for business directory content"""
        # Count basic indicators (much more flexible)
        phone_count = len(re.findall(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', content))
        email_count = len(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content))
        
        # Very low threshold - even 2 contacts might indicate a directory
        return phone_count >= 2 or email_count >= 2
    
    async def _scrape_businesses_flexible(self, url: str, session) -> List[Dict]:
        """Flexible business extraction"""
        businesses = []
        
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return businesses
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                logging.info(f"📄 Page content length: {len(content)} chars")
            
            # Strategy 1: Look for any structured data (tables, lists, divs)
            businesses.extend(self._extract_from_any_structure(soup, url))
            
            # Strategy 2: Extract from any element that has contact info
            businesses.extend(self._extract_from_contact_elements(soup, url))
            
            # Strategy 3: Pattern matching across the entire page
            businesses.extend(self._extract_from_page_patterns(content, url))
            
            logging.info(f"📊 Raw extraction: {len(businesses)} potential businesses")
            return businesses
            
        except Exception as e:
            logging.error(f"❌ Error scraping {url}: {str(e)}")
            return businesses
    
    def _extract_from_any_structure(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract from any structural element that might contain business data"""
        businesses = []
        
        # Look at ALL tables, lists, and divs
        elements = soup.find_all(['table', 'ul', 'ol', 'div', 'article', 'section'])
        
        for element in elements:
            element_text = element.get_text()
            
            # If element contains phone or email, it might have business data
            if (re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', element_text) or 
                re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', element_text)):
                
                business = self._extract_business_from_element(element, base_url)
                if business:
                    businesses.append(business)
        
        return businesses
    
    def _extract_from_contact_elements(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract from any element that has contact information"""
        businesses = []
        
        # Find all elements with phone or email links
        phone_elements = soup.find_all('a', href=re.compile(r'tel:'))
        email_elements = soup.find_all('a', href=re.compile(r'mailto:'))
        
        # Process phone elements
        for phone_element in phone_elements:
            parent = phone_element.parent
            if parent:
                business = self._extract_business_from_element(parent, base_url)
                if business:
                    businesses.append(business)
        
        # Process email elements
        for email_element in email_elements:
            parent = email_element.parent
            if parent:
                business = self._extract_business_from_element(parent, base_url)
                if business:
                    businesses.append(business)
        
        return businesses
    
    def _extract_from_page_patterns(self, content: str, base_url: str) -> List[Dict]:
        """Extract businesses using pattern matching on the entire page"""
        businesses = []
        
        # Find all phone numbers and try to extract business info around them
        phone_matches = re.finditer(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', content)
        
        for match in phone_matches:
            phone = match.group(1)
            start_pos = max(0, match.start() - 200)  # Look 200 chars before
            end_pos = min(len(content), match.end() + 200)  # Look 200 chars after
            
            context = content[start_pos:end_pos]
            
            # Try to find a business name in the context
            lines = context.split('\n')
            business_name = None
            
            for line in lines:
                line = line.strip()
                if line and len(line) > 3 and len(line) < 80:
                    # This might be a business name
                    if not any(junk in line.lower() for junk in ['phone', 'email', 'contact', 'address']):
                        business_name = line
                        break
            
            if business_name:
                business = {
                    'business_name': business_name,
                    'phone': self._clean_phone_number(phone)
                }
                
                # Try to find email in the same context
                email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', context)
                if email_match:
                    business['email'] = email_match.group(1)
                
                businesses.append(business)
        
        return businesses
    
    def _extract_business_from_element(self, element, base_url: str) -> Optional[Dict]:
        """Extract business info from any element - more flexible"""
        business = {}
        text = element.get_text()
        
        # Find potential business name (any text that looks like a name)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        for line in lines:
            if (len(line) > 3 and len(line) < 100 and 
                not any(junk in line.lower() for junk in ['phone:', 'email:', 'website:', 'address:', 'contact:'])):
                business['business_name'] = line
                break
        
        # Extract contact info
        phone_match = re.search(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', text)
        if phone_match:
            business['phone'] = self._clean_phone_number(phone_match.group(1))
        
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
        if email_match:
            business['email'] = email_match.group(1)
        
        # Look for website links
        links = element.find_all('a', href=True)
        for link in links:
            href = link.get('href')
            if href and ('http' in href or 'www' in href):
                if not any(social in href.lower() for social in ['facebook', 'twitter', 'instagram', 'linkedin']):
                    business['website'] = href
                    break
        
        return business if business.get('business_name') else None
    
    def _clean_businesses_flexible(self, businesses: List[Dict]) -> List[Dict]:
        """Clean businesses with strict quality filtering"""
        clean_businesses = []
        seen_names = set()
        seen_phones = set()
        seen_emails = set()
        
        for business in businesses:
            # Basic cleaning
            name = business.get('business_name', '').strip()
            if not name or len(name) < 3:
                continue
            
            # STRICT junk filtering - only allow business-like names
            name_lower = name.lower()
            
            # Must NOT contain navigation/website content
            navigation_junk = [
                'membership', 'join now', 'member benefits', 'networking programs',
                'member news', 'member spotlight', 'home', 'about', 'contact',
                'services', 'news', 'events', 'login', 'register', 'search',
                'navigation', 'menu', 'header', 'footer', 'privacy', 'terms',
                'cookie', 'copyright', 'rights reserved', 'quick links',
                'our vision', 'our mission', 'board of directors', 'staff',
                'leadership', 'awards', 'recognition', 'testimonial', 'blog',
                'resources', 'programs', 'directory', 'listing', 'spotlight',
                'ribbon cutting', 'chamber', 'read more', 'learn more',
                'click here', 'view all', 'see all', 'welcome', 'thank you'
            ]
            
            if any(junk in name_lower for junk in navigation_junk):
                continue
            
            # Must have at least one contact method
            phone = business.get('phone', '').strip()
            email = business.get('email', '').strip()
            website = business.get('website', '').strip()
            
            if not any([phone, email, website]):
                continue
            
            # Additional business name validation
            if not self._is_likely_business_name(name):
                continue
            
            # Clean the data
            cleaned_business = {
                'business_name': name,
                'phone': self._clean_phone_number(phone) if phone else '',
                'email': email.lower() if email else '',
                'website': website if website else '',
                'address': business.get('address', '').strip(),
                'contact_person': business.get('contact_person', '').strip(),
                'socials': business.get('socials', '').strip()
            }
            
            # Check for duplicates
            if (name not in seen_names and 
                cleaned_business.get('phone') not in seen_phones and 
                cleaned_business.get('email') not in seen_emails):
                
                seen_names.add(name)
                if cleaned_business.get('phone'):
                    seen_phones.add(cleaned_business['phone'])
                if cleaned_business.get('email'):
                    seen_emails.add(cleaned_business['email'])
                
                clean_businesses.append(cleaned_business)
        
        return clean_businesses
    
    def _is_likely_business_name(self, name: str) -> bool:
        """Check if name is likely a real business name"""
        if not name or len(name) < 3 or len(name) > 100:
            return False
        
        # Business indicators
        business_indicators = [
            'llc', 'inc', 'corp', 'company', 'co.', 'ltd', 'limited',
            'group', 'associates', 'partners', 'services', 'solutions',
            'consulting', 'consultants', 'marketing', 'restaurant',
            'store', 'shop', 'clinic', 'office', 'center', 'centre',
            'law', 'legal', 'medical', 'dental', 'health', 'care',
            'real estate', 'realty', 'insurance', 'financial',
            'accounting', 'construction', 'building', 'design',
            'engineering', 'technology', 'tech', 'systems',
            'management', 'development', 'enterprises', 'industries',
            'manufacturing', 'agency', 'firm', 'studio', 'gallery',
            'market', 'trading', 'supply', 'equipment', 'repair',
            'maintenance', 'cleaning', 'security', 'transport',
            'logistics', 'hotel', 'motel', 'inn', 'resort',
            'restaurant', 'cafe', 'bar', 'grill', 'deli', 'bakery',
            'pharmacy', 'bank', 'credit union', 'auto', 'automotive',
            'dealership', 'salon', 'spa', 'fitness', 'gym'
        ]
        
        name_lower = name.lower()
        
        # If it has clear business indicators, it's likely a business
        if any(indicator in name_lower for indicator in business_indicators):
            return True
        
        # If it's a proper name format (Title Case), it might be a business
        words = name.split()
        if len(words) >= 2:
            # Check if it looks like a business name (not all caps, has capital letters)
            if not name.isupper() and any(word[0].isupper() for word in words):
                return True
        
        return False
    
    async def _intelligent_directory_discovery(self, base_url: str, session) -> List[str]:
        """Deep crawl to find actual business directory pages"""
        directory_pages = []
        
        try:
            # Get main page
            async with session.get(base_url) as response:
                if response.status != 200:
                    return directory_pages
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
            
            # Strategy 1: Look for direct member directory links
            directory_links = await self._find_member_directory_links(soup, base_url, session)
            directory_pages.extend(directory_links)
            
            # Strategy 2: Look for search/browse business functionality
            search_pages = await self._find_business_search_pages(soup, base_url, session)
            directory_pages.extend(search_pages)
            
            # Strategy 3: Look for category-based listings
            category_pages = await self._find_category_listings(soup, base_url, session)
            directory_pages.extend(category_pages)
            
            # Remove duplicates
            directory_pages = list(set(directory_pages))
            logging.info(f"📂 Found {len(directory_pages)} business directory pages")
            
            return directory_pages
            
        except Exception as e:
            logging.error(f"❌ Error in directory discovery: {str(e)}")
            return directory_pages
    
    async def _find_member_directory_links(self, soup: BeautifulSoup, base_url: str, session) -> List[str]:
        """Find direct member directory links"""
        directory_links = []
        
        # High-priority member directory patterns
        member_patterns = [
            r'member.*directory',
            r'business.*directory', 
            r'member.*listing',
            r'business.*listing',
            r'company.*directory',
            r'directory.*member',
            r'member.*search',
            r'business.*search',
            r'find.*member',
            r'member.*roster',
            r'business.*roster'
        ]
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            text = link.get_text().lower().strip()
            
            if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
            
            # Check if this looks like a member directory
            for pattern in member_patterns:
                if re.search(pattern, text, re.IGNORECASE) or re.search(pattern, href, re.IGNORECASE):
                    full_url = urljoin(base_url, href)
                    if await self._validate_business_directory_page(full_url, session):
                        directory_links.append(full_url)
                        logging.info(f"✅ Found member directory: {text} -> {full_url}")
                    break
        
        return directory_links
    
    async def _find_business_search_pages(self, soup: BeautifulSoup, base_url: str, session) -> List[str]:
        """Find business search/browse pages"""
        search_pages = []
        
        # Look for search forms or browse links
        search_forms = soup.find_all('form')
        for form in search_forms:
            form_text = form.get_text().lower()
            if any(keyword in form_text for keyword in ['business', 'member', 'company', 'search', 'find']):
                action = form.get('action')
                if action:
                    search_url = urljoin(base_url, action)
                    # Try to submit the form to get business listings
                    try:
                        async with session.post(search_url, data={}) as response:
                            if response.status == 200:
                                content = await response.text()
                                if self._has_business_listings(content):
                                    search_pages.append(search_url)
                                    logging.info(f"✅ Found business search page: {search_url}")
                    except:
                        pass
        
        return search_pages
    
    async def _find_category_listings(self, soup: BeautifulSoup, base_url: str, session) -> List[str]:
        """Find category-based business listings"""
        category_pages = []
        
        # Look for category links that might lead to business listings
        category_keywords = ['category', 'industry', 'sector', 'type', 'browse']
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            text = link.get_text().lower().strip()
            
            if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
            
            # Check if this looks like a category page
            if any(keyword in text for keyword in category_keywords):
                full_url = urljoin(base_url, href)
                if await self._validate_business_directory_page(full_url, session):
                    category_pages.append(full_url)
                    logging.info(f"✅ Found category page: {text} -> {full_url}")
        
        return category_pages
    
    async def _validate_business_directory_page(self, url: str, session) -> bool:
        """Validate if page contains real business listings"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status != 200:
                    return False
                
                content = await response.text()
                return self._has_business_listings(content)
                
        except Exception:
            return False
    
    def _has_business_listings(self, content: str) -> bool:
        """Check if content has real business listings"""
        # Count business indicators
        business_score = 0
        
        # Phone numbers (strong indicator)
        phone_count = len(re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', content))
        business_score += min(phone_count, 10) * 3
        
        # Email addresses (strong indicator)
        email_count = len(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content))
        business_score += min(email_count, 10) * 3
        
        # Business-like patterns
        business_patterns = [
            r'(?:LLC|Inc|Corp|Company|Business|Enterprise|Group|Associates|Partners)',
            r'(?:Restaurant|Store|Shop|Service|Consulting|Marketing|Real Estate|Law|Medical)',
            r'(?:Main Street|Business Park|Industrial|Commercial|Office|Suite)'
        ]
        
        for pattern in business_patterns:
            matches = len(re.findall(pattern, content, re.IGNORECASE))
            business_score += min(matches, 5) * 2
        
        # Table or list structures (good indicator)
        soup = BeautifulSoup(content, 'html.parser')
        tables = soup.find_all('table')
        lists = soup.find_all(['ul', 'ol'])
        
        for table in tables:
            if any(header in table.get_text().lower() for header in ['business', 'company', 'name', 'contact', 'phone']):
                business_score += 10
        
        for list_elem in lists:
            if len(list_elem.find_all('li')) > 5:  # Long lists might be business listings
                business_score += 5
        
        logging.info(f"📊 Business listing score: {business_score}")
        return business_score > 15
    
    async def _extract_businesses_intelligent(self, url: str, session) -> List[Dict]:
        """Extract businesses using intelligent methods"""
        businesses = []
        
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return businesses
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
            
            # Strategy 1: Extract from structured tables
            table_businesses = self._extract_from_structured_tables(soup, url)
            businesses.extend(table_businesses)
            
            # Strategy 2: Extract from business cards/containers
            card_businesses = self._extract_from_business_containers(soup, url)
            businesses.extend(card_businesses)
            
            # Strategy 3: Extract from contact lists
            list_businesses = self._extract_from_contact_lists(soup, url)
            businesses.extend(list_businesses)
            
            logging.info(f"📋 Extracted {len(businesses)} raw businesses from {url}")
            return businesses
            
        except Exception as e:
            logging.error(f"❌ Error extracting from {url}: {str(e)}")
            return businesses
    
    def _extract_from_structured_tables(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract from well-structured tables"""
        businesses = []
        
        tables = soup.find_all('table')
        for table in tables:
            # Check if table has business-like headers
            headers = []
            header_row = table.find('tr')
            if header_row:
                headers = [th.get_text().strip().lower() for th in header_row.find_all(['th', 'td'])]
            
            # Skip if no relevant headers
            if not any(keyword in ' '.join(headers) for keyword in ['business', 'company', 'name', 'contact', 'phone', 'email']):
                continue
            
            # Extract business data from each row
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                
                business = self._extract_business_from_table_row_intelligent(cells, headers, base_url)
                if business:
                    businesses.append(business)
        
        return businesses
    
    def _extract_from_business_containers(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract from business card-style containers"""
        businesses = []
        
        # Look for containers with business-like class names
        containers = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'business|member|company|listing|card|contact'))
        
        for container in containers:
            # Must have contact info to be considered a business
            text = container.get_text()
            if not (re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', text) or 
                   re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)):
                continue
            
            business = self._extract_business_from_container_intelligent(container, base_url)
            if business:
                businesses.append(business)
        
        return businesses
    
    def _extract_from_contact_lists(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract from contact lists"""
        businesses = []
        
        lists = soup.find_all(['ul', 'ol'])
        for list_elem in lists:
            items = list_elem.find_all('li')
            if len(items) < 3:  # Need multiple items
                continue
            
            # Check if list contains business-like content
            list_text = list_elem.get_text().lower()
            if not any(keyword in list_text for keyword in ['phone', 'email', 'contact', 'business', 'company']):
                continue
            
            for item in items:
                business = self._extract_business_from_list_item_intelligent(item, base_url)
                if business:
                    businesses.append(business)
        
        return businesses
    
    async def _find_business_directory_page(self, soup: BeautifulSoup, base_url: str, session) -> Optional[str]:
        """Find the actual business directory page URL with improved detection"""
        
        # More specific business directory keywords and patterns
        directory_patterns = [
            # Direct member directory links
            (r'member.*directory', 'member directory'),
            (r'business.*directory', 'business directory'),
            (r'company.*directory', 'company directory'),
            (r'member.*listing', 'member listing'),
            (r'business.*listing', 'business listing'),
            (r'member.*search', 'member search'),
            (r'directory.*search', 'directory search'),
            (r'find.*member', 'find member'),
            (r'find.*business', 'find business'),
            (r'member.*roster', 'member roster'),
            (r'business.*roster', 'business roster'),
            # Common directory page names
            (r'members', 'members'),
            (r'businesses', 'businesses'),
            (r'directory', 'directory'),
            (r'listings', 'listings'),
            (r'roster', 'roster'),
            (r'search', 'search'),
        ]
        
        # Look for links with high-priority patterns first
        high_priority_links = []
        medium_priority_links = []
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            link_text = link.get_text().lower().strip()
            
            if not href:
                continue
                
            # Skip external links, mailto, tel, etc.
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
            
            # Convert relative URLs to absolute
            full_url = urljoin(base_url, href)
            href_lower = href.lower()
            
            # Check for high-priority directory patterns
            for pattern, description in directory_patterns[:8]:  # First 8 are high priority
                if re.search(pattern, link_text, re.IGNORECASE) or re.search(pattern, href_lower, re.IGNORECASE):
                    high_priority_links.append((full_url, description, link_text))
                    break
            else:
                # Check for medium-priority patterns
                for pattern, description in directory_patterns[8:]:
                    if re.search(pattern, link_text, re.IGNORECASE) or re.search(pattern, href_lower, re.IGNORECASE):
                        medium_priority_links.append((full_url, description, link_text))
                        break
        
        # Try high-priority links first
        for url, description, link_text in high_priority_links:
            logging.info(f"🔍 Testing high-priority directory link: {link_text} -> {url}")
            if await self._validate_directory_page(url, session):
                logging.info(f"✅ Found business directory: {url}")
                return url
        
        # Try medium-priority links
        for url, description, link_text in medium_priority_links:
            logging.info(f"🔍 Testing medium-priority directory link: {link_text} -> {url}")
            if await self._validate_directory_page(url, session):
                logging.info(f"✅ Found business directory: {url}")
                return url
        
        logging.warning("⚠️ No business directory page found")
        return None
    
    async def _validate_directory_page(self, url: str, session) -> bool:
        """Validate if a page actually contains business listings"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    return False
                    
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Count indicators of business listings
                business_indicators = 0
                
                # Look for multiple phone numbers or email addresses
                phone_count = len(re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', content))
                email_count = len(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content))
                
                if phone_count > 2:
                    business_indicators += phone_count
                if email_count > 2:
                    business_indicators += email_count
                
                # Look for business-like structures
                business_cards = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'business|member|company|listing|card'))
                if len(business_cards) > 3:
                    business_indicators += len(business_cards)
                
                # Look for tables with business data
                tables = soup.find_all('table')
                for table in tables:
                    if any(header in table.get_text().lower() for header in ['business', 'company', 'member', 'contact', 'phone', 'email']):
                        business_indicators += 10
                
                # Look for lists with business data
                lists = soup.find_all(['ul', 'ol'])
                for list_elem in lists:
                    list_text = list_elem.get_text().lower()
                    if any(keyword in list_text for keyword in ['phone', 'email', '@', 'contact']):
                        business_indicators += 5
                
                logging.info(f"📊 Business indicators score: {business_indicators} for {url}")
                return business_indicators > 5
                
        except Exception as e:
            logging.error(f"❌ Error validating directory page {url}: {str(e)}")
            return False
    
    def _extract_business_from_table_row_intelligent(self, cells, headers, base_url: str) -> Optional[Dict]:
        """Intelligently extract business data from table row"""
        business = {}
        
        # Try to map cells to business fields based on headers
        for i, cell in enumerate(cells):
            cell_text = cell.get_text().strip()
            if not cell_text or len(cell_text) < 2:
                continue
                
            header = headers[i] if i < len(headers) else ""
            cell_lower = cell_text.lower()
            
            # Skip obvious junk
            if any(junk in cell_lower for junk in ['home', 'about', 'contact us', 'services', 'login', 'menu']):
                continue
            
            # Map based on header content
            if any(keyword in header for keyword in ['name', 'business', 'company']) and not business.get('business_name'):
                business['business_name'] = cell_text
            elif any(keyword in header for keyword in ['contact', 'person', 'owner', 'manager']) and not business.get('contact_person'):
                business['contact_person'] = cell_text
            elif any(keyword in header for keyword in ['phone', 'tel']) and not business.get('phone'):
                business['phone'] = self._clean_phone_number(cell_text)
            elif any(keyword in header for keyword in ['email', 'mail']) and not business.get('email'):
                business['email'] = self._extract_email_from_text(cell_text)
            elif any(keyword in header for keyword in ['website', 'web', 'url']) and not business.get('website'):
                business['website'] = self._extract_website_from_text(cell_text)
            elif any(keyword in header for keyword in ['address', 'location']) and not business.get('address'):
                business['address'] = cell_text
        
        # If no header mapping worked, use positional logic
        if not business and len(cells) >= 2:
            # First cell is usually business name
            business['business_name'] = cells[0].get_text().strip()
            
            # Look for contact info in remaining cells
            for cell in cells[1:]:
                cell_text = cell.get_text().strip()
                if not business.get('phone') and re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', cell_text):
                    business['phone'] = self._clean_phone_number(cell_text)
                elif not business.get('email') and '@' in cell_text:
                    business['email'] = self._extract_email_from_text(cell_text)
                elif not business.get('website') and ('http' in cell_text or 'www' in cell_text):
                    business['website'] = self._extract_website_from_text(cell_text)
        
        # Extract additional info from cell links
        self._extract_links_from_cells(cells, business, base_url)
        
        return business if self._is_valid_business_record(business) else None
    
    def _extract_business_from_container_intelligent(self, container, base_url: str) -> Optional[Dict]:
        """Intelligently extract business data from container"""
        business = {}
        text = container.get_text()
        
        # Find business name (usually in heading or first strong element)
        name_element = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b'])
        if name_element:
            name = name_element.get_text().strip()
            if self._is_valid_business_name(name):
                business['business_name'] = name
        
        # If no name found, use first line
        if not business.get('business_name'):
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines:
                first_line = lines[0]
                if self._is_valid_business_name(first_line):
                    business['business_name'] = first_line
        
        # Extract contact information
        business['phone'] = self._clean_phone_number(self._extract_phone_from_text(text))
        business['email'] = self._extract_email_from_text(text)
        business['address'] = self._extract_address_from_text(text)
        business['contact_person'] = self._extract_contact_person_from_text(text)
        
        # Extract links
        self._extract_links_from_element(container, business, base_url)
        
        return business if self._is_valid_business_record(business) else None
    
    def _extract_business_from_list_item_intelligent(self, item, base_url: str) -> Optional[Dict]:
        """Intelligently extract business data from list item"""
        business = {}
        text = item.get_text()
        
        # Must have contact info to be valid
        if not (re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', text) or '@' in text):
            return None
        
        # Extract business name
        name_element = item.find(['strong', 'b', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if name_element:
            name = name_element.get_text().strip()
            if self._is_valid_business_name(name):
                business['business_name'] = name
        
        if not business.get('business_name'):
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines:
                first_line = lines[0]
                if self._is_valid_business_name(first_line):
                    business['business_name'] = first_line
        
        # Extract contact information
        business['phone'] = self._clean_phone_number(self._extract_phone_from_text(text))
        business['email'] = self._extract_email_from_text(text)
        business['address'] = self._extract_address_from_text(text)
        business['contact_person'] = self._extract_contact_person_from_text(text)
        
        # Extract links
        self._extract_links_from_element(item, business, base_url)
        
        return business if self._is_valid_business_record(business) else None
    
    def _is_valid_business_name(self, name: str) -> bool:
        """Check if text is a valid business name"""
        if not name or len(name) < 3 or len(name) > 100:
            return False
        
        name_lower = name.lower().strip()
        
        # Extensive junk filter
        junk_patterns = [
            # Navigation and UI elements
            'home', 'about', 'contact', 'services', 'products', 'news', 'events', 'blog',
            'login', 'register', 'search', 'menu', 'navigation', 'header', 'footer',
            # Chamber content
            'membership', 'join', 'member', 'benefits', 'programs', 'networking',
            'directory', 'listing', 'spotlight', 'ribbon cutting', 'chamber',
            # Generic content
            'privacy', 'terms', 'cookie', 'accessibility', 'disclaimer', 'copyright',
            'read more', 'learn more', 'click here', 'view all', 'see all',
            # Social media
            'facebook', 'twitter', 'instagram', 'linkedin', 'youtube',
            # Common words that shouldn't be business names
            'welcome', 'thank you', 'overview', 'mission', 'vision', 'history',
            'board', 'staff', 'leadership', 'awards', 'recognition', 'testimonial'
        ]
        
        # Check for junk patterns
        for pattern in junk_patterns:
            if pattern in name_lower:
                return False
        
        # Check for business-like indicators
        business_indicators = [
            'llc', 'inc', 'corp', 'company', 'business', 'group', 'associates',
            'partners', 'services', 'solutions', 'consulting', 'marketing',
            'restaurant', 'store', 'shop', 'clinic', 'law', 'medical', 'dental',
            'real estate', 'insurance', 'financial', 'accounting', 'construction'
        ]
        
        # Business name should either have business indicators or not be obviously junk
        has_business_indicator = any(indicator in name_lower for indicator in business_indicators)
        
        # If it has business indicators, it's likely valid
        if has_business_indicator:
            return True
        
        # Otherwise, it should at least look like a proper name (capital letters, etc.)
        return name[0].isupper() and not name.isupper() and ' ' in name
    
    def _extract_phone_from_text(self, text: str) -> str:
        """Extract phone number from text"""
        phone_patterns = [
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}'
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return ""
    
    def _clean_phone_number(self, phone: str) -> str:
        """Clean and format phone number"""
        if not phone:
            return ""
        
        # Remove everything except digits
        digits = re.sub(r'[^\d]', '', phone)
        
        # Format as (XXX) XXX-XXXX if 10 digits
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        
        return phone  # Return original if can't format
    
    def _extract_email_from_text(self, text: str) -> str:
        """Extract email from text"""
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
        return email_match.group(1) if email_match else ""
    
    def _extract_website_from_text(self, text: str) -> str:
        """Extract website from text"""
        # Look for URLs
        url_patterns = [
            r'https?://[^\s]+',
            r'www\.[^\s]+',
            r'[a-zA-Z0-9.-]+\.(com|org|net|edu|gov|biz|info)[^\s]*'
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                url = match.group(0)
                # Clean up the URL
                if not url.startswith('http'):
                    url = 'https://' + url
                return url
        
        return ""
    
    def _extract_address_from_text(self, text: str) -> str:
        """Extract address from text"""
        address_patterns = [
            r'\d+[^,\n]*(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|blvd|boulevard|way|place|pl|court|ct|circle|cir)[^,\n]*(?:,\s*[^,\n]*){0,3}',
            r'\d+[^,\n]*,\s*[^,\n]*,\s*[A-Z]{2}\s*\d{5}',
            r'[A-Z][^,\n]*,\s*[A-Z]{2}\s*\d{5}'
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        
        return ""
    
    def _extract_contact_person_from_text(self, text: str) -> str:
        """Extract contact person name from text"""
        contact_patterns = [
            r'(?:contact|manager|director|owner|president|ceo):?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*,\s*(?:manager|director|owner|president|ceo))',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*-\s*(?:manager|director|owner|president|ceo))'
        ]
        
        for pattern in contact_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _is_valid_business_record(self, business: Dict) -> bool:
        """Check if business record has valid data"""
        if not business or not business.get('business_name'):
            return False
        
        # Must have at least one contact method
        contact_methods = [
            business.get('phone'),
            business.get('email'),
            business.get('website')
        ]
        
        if not any(contact_methods):
            return False
        
        # Business name must be valid
        if not self._is_valid_business_name(business['business_name']):
            return False
        
        return True
    
    def _validate_and_clean_businesses(self, businesses: List[Dict]) -> List[Dict]:
        """Final validation and cleaning of business data"""
        clean_businesses = []
        
        for business in businesses:
            # Clean the data
            cleaned_business = self._clean_business_data(business)
            
            # Validate the cleaned data
            if self._is_valid_business_record(cleaned_business):
                clean_businesses.append(cleaned_business)
        
        # Remove duplicates
        final_businesses = self._deduplicate_businesses(clean_businesses)
        
        logging.info(f"🧹 Cleaned and validated: {len(final_businesses)} quality businesses")
        return final_businesses
    
    def _clean_business_data(self, business: Dict) -> Dict:
        """Clean individual business data"""
        cleaned = {}
        
        # Clean business name
        name = business.get('business_name', '').strip()
        if name:
            # Remove extra whitespace
            name = re.sub(r'\s+', ' ', name)
            # Remove leading/trailing punctuation
            name = name.strip('.,;:!?-')
            cleaned['business_name'] = name
        
        # Clean phone
        phone = business.get('phone', '').strip()
        if phone:
            cleaned['phone'] = self._clean_phone_number(phone)
        
        # Clean email
        email = business.get('email', '').strip().lower()
        if email and '@' in email:
            cleaned['email'] = email
        
        # Clean website
        website = business.get('website', '').strip()
        if website:
            if not website.startswith('http'):
                website = 'https://' + website
            cleaned['website'] = website
        
        # Clean address
        address = business.get('address', '').strip()
        if address:
            cleaned['address'] = re.sub(r'\s+', ' ', address)
        
        # Clean contact person
        contact_person = business.get('contact_person', '').strip()
        if contact_person:
            cleaned['contact_person'] = contact_person
        
        # Clean socials
        socials = business.get('socials', '').strip()
        if socials:
            cleaned['socials'] = socials
        
        return cleaned
    
    def _deduplicate_businesses(self, businesses: List[Dict]) -> List[Dict]:
        """Remove duplicate businesses"""
        seen_names = set()
        seen_phones = set()
        seen_emails = set()
        unique_businesses = []
        
        for business in businesses:
            name = business.get('business_name', '').lower().strip()
            phone = business.get('phone', '').strip()
            email = business.get('email', '').strip()
            
            # Check for duplicates
            is_duplicate = False
            if name and name in seen_names:
                is_duplicate = True
            if phone and phone in seen_phones:
                is_duplicate = True
            if email and email in seen_emails:
                is_duplicate = True
            
            if not is_duplicate:
                if name:
                    seen_names.add(name)
                if phone:
                    seen_phones.add(phone)
                if email:
                    seen_emails.add(email)
                unique_businesses.append(business)
        
        return unique_businesses

# Global discoverer instance
discoverer = DirectoryDiscoverer()


# API Routes
@api_router.get("/")
async def root():
    return {"message": "Chamber Directory Scraper API"}

@api_router.post("/discover-directories")
async def discover_directories(request: DirectorySearchRequest):
    """Discover business directories in a specific location with detailed logging"""
    try:
        # Create a progress tracking system
        progress_log = []
        
        def log_progress(message):
            progress_log.append(f"{datetime.utcnow().strftime('%H:%M:%S')} - {message}")
            logging.info(message)
        
        log_progress(f"🔍 Starting discovery for location: {request.location}")
        log_progress(f"📋 Directory types: {request.directory_types}")
        log_progress(f"🎯 Max results: {request.max_results}")
        
        # Search for directories
        discovered = await discoverer.search_directories(
            request.location, 
            request.directory_types, 
            request.max_results,
            progress_callback=log_progress
        )
        
        log_progress(f"✅ Discovery complete! Found {len(discovered)} directories")
        
        # Save discovered directories to database
        saved_directories = []
        for directory_data in discovered:
            directory = DiscoveredDirectory(**directory_data)
            await db.directories.insert_one(directory.dict())
            saved_directories.append(directory)
            log_progress(f"💾 Saved: {directory.name}")
        
        return {
            "success": True,
            "count": len(saved_directories),
            "directories": saved_directories,
            "progress_log": progress_log
        }
        
    except Exception as e:
        logging.error(f"Error discovering directories: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/directories")
async def get_directories():
    """Get all discovered directories"""
    try:
        directories = await db.directories.find().to_list(1000)
        return [DiscoveredDirectory(**directory) for directory in directories]
    except Exception as e:
        logging.error(f"Error fetching directories: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/scrape-directory")
async def scrape_directory(request: ScrapeDirectoryRequest):
    """Scrape business listings from a specific directory with detailed logging"""
    try:
        # Find the directory
        directory = await db.directories.find_one({"id": request.directory_id})
        if not directory:
            raise HTTPException(status_code=404, detail="Directory not found")
        
        progress_log = []
        
        def log_progress(message):
            progress_log.append(f"{datetime.utcnow().strftime('%H:%M:%S')} - {message}")
            logging.info(message)
        
        log_progress(f"🚀 Starting scrape of: {directory['name']}")
        log_progress(f"🔗 URL: {directory['url']}")
        log_progress(f"📍 Location: {directory['location']}")
        log_progress(f"🏢 Type: {directory['directory_type']}")
        
        # Scrape businesses from the directory
        businesses = await discoverer.scrape_directory_listings(directory['url'])
        
        log_progress(f"📊 Found {len(businesses)} businesses")
        
        # Save businesses to database
        saved_businesses = []
        for business_data in businesses:
            business_data['directory_id'] = request.directory_id
            business = BusinessContact(**business_data)
            await db.businesses.insert_one(business.dict())
            saved_businesses.append(business)
            log_progress(f"💾 Saved: {business.business_name}")
        
        # Update directory status
        await db.directories.update_one(
            {"id": request.directory_id},
            {"$set": {
                "scrape_status": "scraped",
                "business_count": len(saved_businesses)
            }}
        )
        
        log_progress(f"✅ Scraping complete! Saved {len(saved_businesses)} businesses")
        
        return {
            "success": True,
            "directory_id": request.directory_id,
            "businesses_found": len(saved_businesses),
            "businesses": saved_businesses,
            "progress_log": progress_log
        }
        
    except Exception as e:
        logging.error(f"Error scraping directory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/businesses")
async def get_businesses(directory_id: Optional[str] = None):
    """Get all scraped businesses, optionally filtered by directory"""
    try:
        query = {}
        if directory_id:
            query["directory_id"] = directory_id
        
        businesses = await db.businesses.find(query).to_list(1000)
        return [BusinessContact(**business) for business in businesses]
    except Exception as e:
        logging.error(f"Error fetching businesses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/delete-all-data")
async def delete_all_data():
    """Delete all directories and businesses data"""
    try:
        logging.info("🗑️ Starting delete all data operation...")
        
        # Get counts before deletion
        directories_count = await db.directories.count_documents({})
        businesses_count = await db.businesses.count_documents({})
        
        # Delete all businesses
        businesses_result = await db.businesses.delete_many({})
        logging.info(f"🗑️ Deleted {businesses_result.deleted_count} businesses")
        
        # Delete all directories
        directories_result = await db.directories.delete_many({})
        logging.info(f"🗑️ Deleted {directories_result.deleted_count} directories")
        
        return {
            "success": True,
            "message": f"Successfully deleted all data: {directories_count} directories and {businesses_count} businesses",
            "directories_deleted": directories_result.deleted_count,
            "businesses_deleted": businesses_result.deleted_count
        }
        
    except Exception as e:
        logging.error(f"❌ Error deleting all data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting data: {str(e)}")

@api_router.get("/export-businesses")
async def export_businesses(directory_id: Optional[str] = None):
    """Export businesses to CSV"""
    try:
        import io
        import csv
        
        # Build query
        query = {}
        if directory_id:
            query["directory_id"] = directory_id
        
        # Fetch businesses
        businesses = await db.businesses.find(query).to_list(None)
        
        if not businesses:
            raise HTTPException(status_code=404, detail="No businesses found")
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'business_name', 'contact_person', 'phone', 'email', 
            'website', 'address', 'socials', 'directory_name'
        ])
        
        writer.writeheader()
        for business in businesses:
            # Get directory name
            directory = await db.directories.find_one({"id": business.get("directory_id")})
            directory_name = directory.get("name", "Unknown") if directory else "Unknown"
            
            writer.writerow({
                'business_name': business.get('business_name', ''),
                'contact_person': business.get('contact_person', ''),
                'phone': business.get('phone', ''),
                'email': business.get('email', ''),
                'website': business.get('website', ''),
                'address': business.get('address', ''),
                'socials': business.get('socials', ''),
                'directory_name': directory_name
            })
        
        # Return CSV response
        from fastapi.responses import Response
        
        filename = f"businesses_{directory_id if directory_id else 'all'}.csv"
        
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logging.error(f"Error exporting businesses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/test-scrape")
async def test_scrape(request: dict):
    """Test scraping a specific URL"""
    try:
        url = request.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL required")
        
        # Add to database temporarily
        test_directory = {
            "id": str(uuid.uuid4()),
            "name": "Test Chamber",
            "url": url,
            "directory_type": "chamber of commerce",
            "location": "Test Location",
            "description": "Test chamber for direct scraping",
            "discovered_at": datetime.utcnow(),
            "scrape_status": "pending",
            "business_count": 0
        }
        
        await db.directories.insert_one(test_directory)
        
        # Scrape the businesses
        businesses = await discoverer.scrape_directory_listings(url)
        
        # Save businesses to database
        saved_businesses = []
        for business_data in businesses:
            business_data['directory_id'] = test_directory['id']
            business = BusinessContact(**business_data)
            await db.businesses.insert_one(business.dict())
            saved_businesses.append(business)
        
        # Update directory status
        await db.directories.update_one(
            {"id": test_directory['id']},
            {"$set": {
                "scrape_status": "scraped",
                "business_count": len(saved_businesses)
            }}
        )
        
        return {
            "success": True,
            "url": url,
            "businesses_found": len(saved_businesses),
            "businesses": saved_businesses[:10],  # Show first 10
            "directory_id": test_directory['id']
        }
        
    except Exception as e:
        logging.error(f"Error in test scraping: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Legacy routes
@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    logger.info("Starting Chamber Directory Scraper API")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await discoverer.close_session()
    client.close()
    logger.info("Shutting down Chamber Directory Scraper API")