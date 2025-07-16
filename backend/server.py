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
        """Scrape business listings from a directory page by finding the actual business directory"""
        session = await self.create_session()
        businesses = []
        
        try:
            logging.info(f"🔍 Starting scrape of {directory_url}")
            
            # Step 1: Get the main chamber page
            async with session.get(directory_url) as response:
                if response.status != 200:
                    logging.error(f"❌ Failed to access {directory_url} - Status {response.status}")
                    return businesses
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Step 2: Find the business directory page
                directory_page_url = await self._find_business_directory_page(soup, directory_url, session)
                
                if not directory_page_url:
                    logging.info(f"⚠️ No business directory page found, scraping main page")
                    directory_page_url = directory_url
                
                # Step 3: Scrape the business directory page
                if directory_page_url != directory_url:
                    logging.info(f"📂 Found business directory at: {directory_page_url}")
                    async with session.get(directory_page_url) as dir_response:
                        if dir_response.status == 200:
                            dir_content = await dir_response.text()
                            dir_soup = BeautifulSoup(dir_content, 'html.parser')
                            businesses = await self._extract_business_contacts(dir_soup, directory_page_url, session)
                        else:
                            logging.error(f"❌ Failed to access directory page - Status {dir_response.status}")
                else:
                    businesses = await self._extract_business_contacts(soup, directory_url, session)
                
                logging.info(f"✅ Scraped {len(businesses)} business contacts")
                
        except Exception as e:
            logging.error(f"❌ Error scraping directory {directory_url}: {str(e)}")
        
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
    
    async def _extract_business_contacts(self, soup: BeautifulSoup, base_url: str, session) -> List[Dict]:
        """Extract business contacts focusing on structured business data"""
        businesses = []
        
        logging.info("🔍 Looking for structured business listings...")
        
        # Strategy 1: Look for tables with business data
        businesses.extend(self._extract_from_tables(soup, base_url))
        
        # Strategy 2: Look for structured business cards/listings
        businesses.extend(self._extract_from_business_cards(soup, base_url))
        
        # Strategy 3: Look for directory-style lists
        businesses.extend(self._extract_from_directory_lists(soup, base_url))
        
        # Filter out junk and deduplicate
        valid_businesses = []
        for business in businesses:
            if self._is_valid_business_data(business):
                valid_businesses.append(business)
        
        final_businesses = self._deduplicate_businesses(valid_businesses)
        
        logging.info(f"✅ Extracted {len(final_businesses)} valid businesses")
        return final_businesses
    
    def _extract_from_tables(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract business data from tables"""
        businesses = []
        
        tables = soup.find_all('table')
        for table in tables:
            table_text = table.get_text().lower()
            
            # Check if this table contains business data
            if not any(keyword in table_text for keyword in ['business', 'company', 'member', 'contact', 'phone', 'email']):
                continue
                
            logging.info(f"📊 Found business table with {len(table.find_all('tr'))} rows")
            
            # Find header row to understand column structure
            headers = []
            header_row = table.find('tr')
            if header_row:
                for th in header_row.find_all(['th', 'td']):
                    headers.append(th.get_text().strip().lower())
            
            # Process data rows
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:  # Need at least 2 cells for business data
                    continue
                
                business = self._extract_business_from_table_row(cells, headers, base_url)
                if business:
                    businesses.append(business)
        
        return businesses
    
    def _extract_from_business_cards(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract business data from business card-style elements"""
        businesses = []
        
        # Look for business card containers
        selectors = [
            '.business-card', '.member-card', '.company-card',
            '.business-listing', '.member-listing', '.company-listing',
            '.business-item', '.member-item', '.company-item',
            '[class*="business-"]', '[class*="member-"]', '[class*="company-"]'
        ]
        
        for selector in selectors:
            try:
                cards = soup.select(selector)
                if cards:
                    logging.info(f"🎴 Found {len(cards)} business cards with selector: {selector}")
                    for card in cards:
                        business = self._extract_business_from_card(card, base_url)
                        if business:
                            businesses.append(business)
            except:
                continue
        
        return businesses
    
    def _extract_from_directory_lists(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract business data from directory-style lists"""
        businesses = []
        
        # Look for lists that contain business information
        lists = soup.find_all(['ul', 'ol', 'dl'])
        for list_elem in lists:
            list_text = list_elem.get_text().lower()
            
            # Check if this list contains business data
            if not any(keyword in list_text for keyword in ['phone', 'email', '@', 'contact', 'website']):
                continue
            
            items = list_elem.find_all(['li', 'dt', 'dd'])
            if len(items) < 3:  # Need multiple items for a directory
                continue
                
            logging.info(f"📋 Found directory list with {len(items)} items")
            
            for item in items:
                business = self._extract_business_from_list_item(item, base_url)
                if business:
                    businesses.append(business)
        
        return businesses
    
    def _extract_business_from_table_row(self, cells, headers, base_url: str) -> Optional[Dict]:
        """Extract business data from a table row"""
        if len(cells) < 2:
            return None
        
        business = {}
        row_text = ' '.join(cell.get_text() for cell in cells)
        
        # Try to map cells to business fields based on headers
        for i, cell in enumerate(cells):
            cell_text = cell.get_text().strip()
            if not cell_text or len(cell_text) < 2:
                continue
                
            header = headers[i] if i < len(headers) else ""
            
            # Map based on header content
            if any(keyword in header for keyword in ['name', 'business', 'company']):
                business['business_name'] = cell_text
            elif any(keyword in header for keyword in ['contact', 'person', 'owner']):
                business['contact_person'] = cell_text
            elif any(keyword in header for keyword in ['phone', 'tel']):
                business['phone'] = cell_text
            elif any(keyword in header for keyword in ['email', 'mail']):
                business['email'] = cell_text
            elif any(keyword in header for keyword in ['website', 'web', 'url']):
                business['website'] = cell_text
            elif any(keyword in header for keyword in ['address', 'location']):
                business['address'] = cell_text
        
        # If no headers matched, try to extract from first few cells
        if not business.get('business_name') and len(cells) > 0:
            business['business_name'] = cells[0].get_text().strip()
        
        # Extract additional data from cell content
        self._extract_contact_info_from_text(row_text, business)
        self._extract_links_from_cells(cells, business, base_url)
        
        return business if business.get('business_name') else None
    
    def _extract_business_from_card(self, card, base_url: str) -> Optional[Dict]:
        """Extract business data from a business card element"""
        business = {}
        card_text = card.get_text()
        
        # Look for business name in headings
        name_element = card.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if name_element:
            business['business_name'] = name_element.get_text().strip()
        
        # Extract contact information
        self._extract_contact_info_from_text(card_text, business)
        self._extract_links_from_element(card, business, base_url)
        
        return business if business.get('business_name') else None
    
    def _extract_business_from_list_item(self, item, base_url: str) -> Optional[Dict]:
        """Extract business data from a list item"""
        business = {}
        item_text = item.get_text()
        
        # Look for business name (usually first line or in strong/bold)
        name_element = item.find(['strong', 'b', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if name_element:
            business['business_name'] = name_element.get_text().strip()
        else:
            # Use first line as business name
            lines = [line.strip() for line in item_text.split('\n') if line.strip()]
            if lines:
                business['business_name'] = lines[0]
        
        # Extract contact information
        self._extract_contact_info_from_text(item_text, business)
        self._extract_links_from_element(item, business, base_url)
        
        return business if business.get('business_name') else None
    
    def _extract_contact_info_from_text(self, text: str, business: Dict):
        """Extract phone, email, and address from text"""
        # Extract phone number
        if not business.get('phone'):
            phone_patterns = [
                r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})',
                r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})',
                r'(\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4})'
            ]
            for pattern in phone_patterns:
                match = re.search(pattern, text)
                if match:
                    business['phone'] = match.group(1).strip()
                    break
        
        # Extract email
        if not business.get('email'):
            email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
            if email_match:
                business['email'] = email_match.group(1).strip()
        
        # Extract address
        if not business.get('address'):
            address_patterns = [
                r'(\d+[^,\n]*(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|blvd|boulevard|way|place|pl|court|ct|circle|cir)[^,\n]*(?:,\s*[^,\n]*){0,3})',
                r'(\d+[^,\n]*,\s*[^,\n]*,\s*[A-Z]{2}\s*\d{5})',
                r'([A-Z][^,\n]*,\s*[A-Z]{2}\s*\d{5})'
            ]
            for pattern in address_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    business['address'] = match.group(1).strip()
                    break
    
    def _extract_links_from_element(self, element, business: Dict, base_url: str):
        """Extract website and social media links from an element"""
        links = element.find_all('a', href=True)
        
        for link in links:
            href = link.get('href')
            if not href:
                continue
                
            # Skip internal navigation links
            if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                if href.startswith('mailto:') and not business.get('email'):
                    business['email'] = href.replace('mailto:', '').strip()
                elif href.startswith('tel:') and not business.get('phone'):
                    business['phone'] = href.replace('tel:', '').strip()
                continue
            
            # Convert relative URLs to absolute
            full_url = urljoin(base_url, href)
            
            # Categorize the link
            if not business.get('website'):
                # Check if this is likely a business website (not social media)
                if not any(social in full_url.lower() for social in ['facebook', 'twitter', 'instagram', 'linkedin']):
                    business['website'] = full_url
            
            # Extract social media links
            social_links = business.get('socials', '').split('; ') if business.get('socials') else []
            
            if 'facebook.com' in full_url.lower():
                social_links.append(f"Facebook: {full_url}")
            elif 'linkedin.com' in full_url.lower():
                social_links.append(f"LinkedIn: {full_url}")
            elif 'twitter.com' in full_url.lower():
                social_links.append(f"Twitter: {full_url}")
            elif 'instagram.com' in full_url.lower():
                social_links.append(f"Instagram: {full_url}")
            
            if social_links:
                business['socials'] = '; '.join(social_links)
    
    def _extract_links_from_cells(self, cells, business: Dict, base_url: str):
        """Extract links from table cells"""
        for cell in cells:
            self._extract_links_from_element(cell, business, base_url)
    
    def _is_valid_business_data(self, business: Dict) -> bool:
        """Enhanced validation for business data"""
        if not business or not business.get('business_name'):
            return False
            
        name = business.get('business_name', '').strip().lower()
        
        # More comprehensive junk filter
        junk_patterns = [
            # Website navigation and content
            'home', 'about', 'contact', 'services', 'products', 'news', 'events',
            'blog', 'resources', 'login', 'register', 'search', 'menu', 'navigation',
            # Chamber-specific content
            'membership', 'join now', 'member benefits', 'networking programs',
            'member spotlight', 'ribbon cutting', 'member login', 'member directory',
            'business directory', 'member news', 'member tutorials', 'quick links',
            # Generic content
            'privacy policy', 'terms of service', 'cookie policy', 'sitemap',
            'accessibility', 'disclaimer', 'copyright', 'all rights reserved',
            # Social media
            'facebook', 'twitter', 'instagram', 'linkedin', 'youtube',
            # Chamber organization content
            'mission', 'vision', 'our vision', 'our mission', 'about us',
            'board of directors', 'staff', 'history', 'awards', 'recognitions',
            # Page elements
            'pages', 'page', 'directory', 'welcome to', 'thank you',
            'click here', 'read more', 'learn more', 'view all', 'see all',
            # Program names
            'competitive edge', 'leadership', 'emerging leaders', 'workforce development',
            'minority business accelerator', 'return on', 'collegiate leadership'
        ]
        
        # Check if name contains junk patterns
        for pattern in junk_patterns:
            if pattern in name:
                return False
        
        # Check name length
        if len(name) < 3 or len(name) > 100:
            return False
        
        # Must have at least one contact method
        has_contact = any([
            business.get('phone'),
            business.get('email'),
            business.get('website')
        ])
        
        return has_contact
    
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

@api_router.get("/export-csv/{directory_id}")
async def export_csv(directory_id: str):
    """Export businesses to CSV format with improved fields"""
    try:
        businesses = await db.businesses.find({"directory_id": directory_id}).to_list(1000)
        
        # Create CSV content with improved headers
        csv_content = "Business Name,Contact Person,Phone,Email,Website,Socials,Address,Description\n"
        for business in businesses:
            # Escape quotes in CSV fields
            def escape_csv(value):
                if not value:
                    return ""
                return str(value).replace('"', '""')
            
            csv_content += f'"{escape_csv(business.get("business_name", ""))}","{escape_csv(business.get("contact_person", ""))}","{escape_csv(business.get("phone", ""))}","{escape_csv(business.get("email", ""))}","{escape_csv(business.get("website", ""))}","{escape_csv(business.get("socials", ""))}","{escape_csv(business.get("address", ""))}","{escape_csv(business.get("description", ""))}"\n'
        
        return {
            "success": True,
            "csv_content": csv_content,
            "filename": f"businesses_{directory_id}.csv"
        }
    except Exception as e:
        logging.error(f"Error exporting CSV: {str(e)}")
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