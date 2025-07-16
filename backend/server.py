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
    
    async def search_directories(self, location: str, directory_types: List[str], max_results: int = 20) -> List[Dict]:
        """Search for business directories in a specific location"""
        session = await self.create_session()
        discovered = []
        
        for directory_type in directory_types:
            search_query = f"{directory_type} {location}"
            # We'll use DuckDuckGo as it's more scraping-friendly than Google
            search_url = f"https://html.duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
            
            try:
                async with session.get(search_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        # Parse DuckDuckGo results
                        results = soup.find_all('a', {'class': 'result__a'})
                        
                        for result in results[:max_results//len(directory_types)]:
                            href = result.get('href')
                            title = result.get_text(strip=True)
                            
                            if href and self._is_valid_directory_url(href, directory_type):
                                discovered.append({
                                    'name': title,
                                    'url': href,
                                    'directory_type': directory_type,
                                    'location': location,
                                    'description': title
                                })
                
                # Add delay between searches
                await asyncio.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logging.error(f"Error searching for {directory_type} in {location}: {str(e)}")
                continue
        
        return discovered
    
    def _is_valid_directory_url(self, url: str, directory_type: str) -> bool:
        """Check if URL is likely a valid directory"""
        url_lower = url.lower()
        
        # Filter out unwanted domains
        excluded_domains = ['facebook.com', 'linkedin.com', 'twitter.com', 'instagram.com', 'youtube.com', 'yelp.com']
        if any(domain in url_lower for domain in excluded_domains):
            return False
        
        # Look for directory-specific keywords
        directory_keywords = {
            'chamber of commerce': ['chamber', 'commerce'],
            'business directory': ['directory', 'business', 'listing'],
            'better business bureau': ['bbb', 'bureau', 'better']
        }
        
        keywords = directory_keywords.get(directory_type, [])
        return any(keyword in url_lower for keyword in keywords)
    
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
    """Discover business directories in a specific location"""
    try:
        # Search for directories
        discovered = await discoverer.search_directories(
            request.location, 
            request.directory_types, 
            request.max_results
        )
        
        # Save discovered directories to database
        saved_directories = []
        for directory_data in discovered:
            directory = DiscoveredDirectory(**directory_data)
            await db.directories.insert_one(directory.dict())
            saved_directories.append(directory)
        
        return {
            "success": True,
            "count": len(saved_directories),
            "directories": saved_directories
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