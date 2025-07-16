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
    
    async def _validate_and_deduplicate(self, session, discovered: List[Dict]) -> List[Dict]:
        """Validate URLs and remove duplicates"""
        seen_urls = set()
        seen_names = set()
        validated = []
        
        for directory in discovered:
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
            except:
                # If head request fails, still include it (might be valid)
                if url not in seen_urls:
                    seen_urls.add(url)
                    seen_names.add(name)
                    validated.append(directory)
        
        return validated
    
    async def scrape_directory_listings(self, directory_url: str) -> List[Dict]:
        """Scrape business listings from a directory page"""
        session = await self.create_session()
        businesses = []
        
        try:
            async with session.get(directory_url) as response:
                if response.status == 200:
                    content = await response.text()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Try multiple common patterns for business listings
                    businesses.extend(self._extract_chamber_listings(soup, directory_url))
                    businesses.extend(self._extract_generic_listings(soup, directory_url))
                    
        except Exception as e:
            logging.error(f"Error scraping directory {directory_url}: {str(e)}")
        
        return businesses
    
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