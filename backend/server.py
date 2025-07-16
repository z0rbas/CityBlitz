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
        """Find the actual business directory page URL"""
        
        # Common business directory keywords in links
        directory_keywords = [
            'member', 'business', 'directory', 'listing', 'companies', 'organizations',
            'members', 'businesses', 'directories', 'listings', 'roster', 'search'
        ]
        
        # Look for links that likely lead to business directories
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            link_text = link.get_text().lower().strip()
            
            # Check if this looks like a business directory link
            if any(keyword in link_text for keyword in directory_keywords):
                if any(keyword in href.lower() for keyword in directory_keywords):
                    # Convert relative URLs to absolute
                    full_url = urljoin(base_url, href)
                    
                    # Verify this page exists and likely contains business listings
                    try:
                        async with session.head(full_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status == 200:
                                return full_url
                    except:
                        continue
        
        return None
    
    async def _extract_business_contacts(self, soup: BeautifulSoup, base_url: str, session) -> List[Dict]:
        """Extract business contacts with proper data fields"""
        businesses = []
        
        # Look for structured business listings
        business_containers = []
        
        # Try multiple selectors to find business listings
        selectors = [
            # Common business listing selectors
            '.member-listing, .business-listing, .directory-item, .member-item',
            '[class*="member"], [class*="business"], [class*="directory"], [class*="listing"]',
            '.company, .organization, .firm, .business-card',
            # Table rows that might contain business info
            'tr:has(td:contains("phone")), tr:has(td:contains("email")), tr:has(td:contains("@"))',
            # Divs with business-like content
            'div:has(a[href*="tel:"]), div:has(a[href*="mailto:"]), div:has(a[href*="http"])'
        ]
        
        for selector in selectors:
            try:
                containers = soup.select(selector)
                if containers:
                    business_containers.extend(containers)
                    logging.info(f"📋 Found {len(containers)} potential business containers with selector: {selector}")
            except:
                continue
        
        # Remove duplicates
        unique_containers = []
        seen_texts = set()
        for container in business_containers:
            text = container.get_text()[:100]  # First 100 chars as identifier
            if text not in seen_texts:
                seen_texts.add(text)
                unique_containers.append(container)
        
        logging.info(f"🔍 Processing {len(unique_containers)} unique business containers")
        
        # Extract business information from each container
        for container in unique_containers:
            business = self._extract_business_from_container(container, base_url)
            if business and business.get('business_name') and len(business.get('business_name', '')) > 3:
                # Filter out junk data
                if not self._is_junk_business_data(business):
                    businesses.append(business)
        
        # Deduplicate businesses
        final_businesses = self._deduplicate_businesses(businesses)
        
        return final_businesses
    
    def _extract_business_from_container(self, container, base_url: str) -> Dict:
        """Extract business information from a single container"""
        business = {}
        
        # Get all text content
        text = container.get_text()
        
        # Extract business name - look for headings or strong text first
        name_element = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', '.name', '.title', '.company'])
        if name_element:
            business['business_name'] = name_element.get_text(strip=True)
        else:
            # Fallback: get first line of text
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines:
                business['business_name'] = lines[0][:100]
        
        # Extract phone number
        phone_patterns = [
            r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})',
            r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})',
            r'(\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4})'
        ]
        
        # Look for phone in links first
        phone_link = container.find('a', href=re.compile(r'tel:'))
        if phone_link:
            business['phone'] = phone_link.get('href').replace('tel:', '').strip()
        else:
            # Look for phone in text
            for pattern in phone_patterns:
                match = re.search(pattern, text)
                if match:
                    business['phone'] = match.group(1)
                    break
        
        # Extract email
        email_link = container.find('a', href=re.compile(r'mailto:'))
        if email_link:
            business['email'] = email_link.get('href').replace('mailto:', '').strip()
        else:
            # Look for email in text
            email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
            if email_match:
                business['email'] = email_match.group(1)
        
        # Extract website
        website_link = container.find('a', href=re.compile(r'https?://'))
        if website_link:
            href = website_link.get('href')
            if 'mailto:' not in href and 'tel:' not in href:
                business['website'] = href
        
        # Extract address - look for address patterns
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
        
        # Extract contact person name
        # Look for patterns like "Contact: John Smith" or "Manager: Jane Doe"
        contact_patterns = [
            r'(?:contact|manager|director|owner|president|ceo):?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*,\s*(?:manager|director|owner|president|ceo))'
        ]
        
        for pattern in contact_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                business['contact_person'] = match.group(1).strip()
                break
        
        # Extract social media links
        social_links = []
        social_patterns = {
            'facebook': r'facebook\.com/[^/\s]+',
            'linkedin': r'linkedin\.com/(?:in|company)/[^/\s]+',
            'twitter': r'twitter\.com/[^/\s]+',
            'instagram': r'instagram\.com/[^/\s]+'
        }
        
        for platform, pattern in social_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                social_links.append(f"{platform}: {match.group(0)}")
        
        if social_links:
            business['socials'] = '; '.join(social_links)
        
        return business
    
    def _is_junk_business_data(self, business: Dict) -> bool:
        """Check if the business data is junk/useless"""
        name = business.get('business_name', '').lower()
        
        # Filter out common junk patterns
        junk_patterns = [
            'membership', 'join now', 'member benefits', 'networking programs',
            'our vision', 'mission', 'about us', 'contact us', 'privacy policy',
            'terms of service', 'quick links', 'copyright', 'all rights reserved',
            'home', 'services', 'programs', 'events', 'news', 'blog', 'resources',
            'member login', 'business directory', 'member spotlight', 'ribbon cutting'
        ]
        
        if any(pattern in name for pattern in junk_patterns):
            return True
        
        # Check if name is too short or too long
        if len(name) < 3 or len(name) > 100:
            return True
        
        # Check if name contains mostly navigation text
        if any(nav in name for nav in ['click here', 'read more', 'learn more', 'view all']):
            return True
        
        return False
    
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
    
    def _extract_chamber_listings(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract business listings from common chamber website patterns"""
        businesses = []
        
        # Common chamber directory selectors
        selectors = [
            '.member-listing',
            '.business-listing',
            '.directory-item',
            '.member-item',
            '[class*="member"]',
            '[class*="business"]',
            '[class*="directory"]'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            for item in items:
                business = self._extract_business_info(item, base_url)
                if business and business.get('business_name'):
                    businesses.append(business)
        
        return businesses
    
    def _extract_generic_listings(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract business listings from generic directory patterns"""
        businesses = []
        
        # Look for lists of business information
        for container in soup.find_all(['div', 'article', 'section']):
            # Check if container likely contains business info
            text = container.get_text().lower()
            if any(keyword in text for keyword in ['phone', 'email', 'address', 'contact', 'business']):
                business = self._extract_business_info(container, base_url)
                if business and business.get('business_name'):
                    businesses.append(business)
        
        return businesses
    
    def _extract_business_info(self, element, base_url: str) -> Dict:
        """Extract business information from a DOM element"""
        business = {}
        
        # Extract business name - look for headings or strong text
        name_element = element.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b'])
        if name_element:
            business['business_name'] = name_element.get_text(strip=True)
        else:
            # Fallback to first text content
            text_content = element.get_text(strip=True)
            if text_content:
                business['business_name'] = text_content.split('\n')[0][:100]
        
        # Extract contact information using regex
        text = element.get_text()
        
        # Phone number
        phone_match = re.search(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', text)
        if phone_match:
            business['phone'] = phone_match.group(1)
        
        # Email
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
        if email_match:
            business['email'] = email_match.group(1)
        
        # Address - look for address-like patterns
        address_match = re.search(r'(\d+[^,\n]*(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|blvd|boulevard)[^,\n]*(?:,\s*[^,\n]*){0,2})', text, re.IGNORECASE)
        if address_match:
            business['address'] = address_match.group(1)
        
        # Website - look for links
        link_element = element.find('a', href=True)
        if link_element:
            href = link_element.get('href')
            if href:
                business['website'] = urljoin(base_url, href)
        
        # Category/description
        business['description'] = text[:200] if text else None
        
        return business


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
    """Scrape business listings from a specific directory"""
    try:
        # Find the directory
        directory = await db.directories.find_one({"id": request.directory_id})
        if not directory:
            raise HTTPException(status_code=404, detail="Directory not found")
        
        # Scrape businesses from the directory
        businesses = await discoverer.scrape_directory_listings(directory['url'])
        
        # Save businesses to database
        saved_businesses = []
        for business_data in businesses:
            business_data['directory_id'] = request.directory_id
            business = BusinessContact(**business_data)
            await db.businesses.insert_one(business.dict())
            saved_businesses.append(business)
        
        # Update directory status
        await db.directories.update_one(
            {"id": request.directory_id},
            {"$set": {
                "scrape_status": "scraped",
                "business_count": len(saved_businesses)
            }}
        )
        
        return {
            "success": True,
            "directory_id": request.directory_id,
            "businesses_found": len(saved_businesses),
            "businesses": saved_businesses
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
    """Export businesses to CSV format"""
    try:
        businesses = await db.businesses.find({"directory_id": directory_id}).to_list(1000)
        
        # Create CSV content
        csv_content = "Business Name,Contact Person,Phone,Email,Address,Website,Category,Description\n"
        for business in businesses:
            csv_content += f'"{business.get("business_name", "")}","{business.get("contact_person", "")}","{business.get("phone", "")}","{business.get("email", "")}","{business.get("address", "")}","{business.get("website", "")}","{business.get("category", "")}","{business.get("description", "")}"\n'
        
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