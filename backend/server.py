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
        """More flexible scraping that actually finds business data"""
        session = await self.create_session()
        businesses = []
        
        try:
            logging.info(f"🔍 Starting flexible scrape of {directory_url}")
            
            # Step 1: Try to find business directory pages
            directory_pages = await self._find_directory_pages_flexible(directory_url, session)
            
            # Step 2: If no specific directory pages found, scrape the main page
            if not directory_pages:
                logging.info("📄 No specific directory pages found, trying main page")
                directory_pages = [directory_url]
            
            # Step 3: Extract businesses from all pages
            for page_url in directory_pages:
                logging.info(f"📋 Scraping businesses from: {page_url}")
                page_businesses = await self._scrape_businesses_flexible(page_url, session)
                businesses.extend(page_businesses)
                logging.info(f"   Found {len(page_businesses)} businesses on this page")
            
            # Step 4: Clean and validate (less strict)
            clean_businesses = self._clean_businesses_flexible(businesses)
            
            logging.info(f"✅ Final result: {len(clean_businesses)} businesses extracted")
            return clean_businesses
                
        except Exception as e:
            logging.error(f"❌ Error in flexible scraping {directory_url}: {str(e)}")
            return businesses
    
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