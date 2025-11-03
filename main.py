import os
import requests
import logging
from fastapi import FastAPI, Query
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()
logger.info("FastAPI application initialized.")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# II. Data Structure and Pydantic Models
class NewsArticle(BaseModel):
    id: Optional[int] = None
    title: str
    summary: Optional[str] = None
    source: str
    country: Optional[str] = None
    category: Optional[str] = None
    timestamp: datetime
    imageUrl: Optional[str] = None
    relevance_score: Optional[float] = None

class Trend(BaseModel):
    uri: str
    label: str
    score: float

class TrendsResponse(BaseModel):
    trends: List[Trend]

# Mappings for newsapi.ai
COUNTRY_URIS = {
    "USA": "http://en.wikipedia.org/wiki/United_States",
    "UK": "http://en.wikipedia.org/wiki/United_Kingdom",
    "Japan": "http://en.wikipedia.org/wiki/Japan",
    "Germany": "http://en.wikipedia.org/wiki/Germany",
}

CATEGORY_URIS = {
    "Business": "dmoz/Business",
    "Tech": "dmoz/Computers/Technology",
    "Politics": "dmoz/Society/Politics",
    "Science": "dmoz/Science",
    "Health": "dmoz/Health",
}

SORT_BY_MAP = {
    "newest": "date",
    "relevance": "rel",
    "source": "sourceImportance",
}

# III. Core Functions and Real Data Fetching
def scrape_real_news(q: Optional[str], country: Optional[str], category: Optional[str], sort_by: str) -> List[NewsArticle]:
    logger.info(f"Attempting to scrape real news from newsapi.ai with params: q={q}, country={country}, category={category}, sort_by={sort_by}")
    api_key = os.getenv("NEWS_API_KEY")
    base_url = os.getenv("NEWS_API_AI_BASE_URL")
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        logger.error("NEWS_API_KEY not found or is default in .env file.")
        return []
    if not base_url:
        logger.error("NEWS_API_AI_BASE_URL not found in .env file.")
        return []

    url = f"{base_url}/article/getArticles"
    
    payload = {
        "action": "getArticles",
        "articlesPage": 1,
        "articlesCount": 20,
        "articlesSortBy": SORT_BY_MAP.get(sort_by, "date"),
        "articlesSortByAsc": False,
        "articlesArticleBodyLen": -1,
        "resultType": "articles",
        "dataType": ["news", "blog"],
        "apiKey": api_key,
        "forceMaxDataTimeWindow": 31
    }

    # Add conditional parameters
    if q:
        payload["keyword"] = q
    else:
        payload["keyword"] = "business" # Default keyword if none provided
    
    if country and country in COUNTRY_URIS:
        payload["sourceLocationUri"] = COUNTRY_URIS[country]
        
    if category and category in CATEGORY_URIS:
        payload["categoryUri"] = CATEGORY_URIS[category]

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        articles = []
        for i, item in enumerate(data.get("articles", {}).get("results", [])):
            published_at = item.get("dateTimePub")
            timestamp = datetime.now()
            if published_at:
                try:
                    timestamp = datetime.fromisoformat(published_at)
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse timestamp for article: {item.get('title')}. Using current time.")

            article = NewsArticle(
                id=i + 1,
                title=item.get("title", "No Title"),
                summary=item.get("body"),
                source=item.get("source", {}).get("title", "Unknown Source"),
                timestamp=timestamp,
                imageUrl=item.get("image"),
                country=next((k for k, v in COUNTRY_URIS.items() if v == item.get("location", {}).get("country", {}).get("uri")), None),
                category=next((k for k, v in CATEGORY_URIS.items() if v in item.get("categories", [])), "General"),
                relevance_score=item.get("relevance", 0.0)
            )
            articles.append(article)
        logger.info(f"Successfully fetched {len(articles)} articles from newsapi.ai.")
        return articles

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching news from newsapi.ai: {e}")
        return []

# IV. API Endpoints
@app.get("/news", response_model=List[NewsArticle])
async def get_news(
    q: Optional[str] = Query(None, description="Global search term for title and summary"),
    country: Optional[str] = Query(None, description="Filter by country"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by: str = Query('newest', description="Sort by: 'newest', 'oldest', 'source', 'relevance'")
):
    return scrape_real_news(q, country, category, sort_by)

@app.get("/trends", response_model=TrendsResponse)
async def get_trends():
    logger.info("Attempting to fetch trends from newsapi.ai...")
    api_key = os.getenv("NEWS_API_KEY")
    base_url = os.getenv("NEWS_API_AI_BASE_URL")
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        logger.error("NEWS_API_KEY not found or is default in .env file.")
        return {"trends": []}
    if not base_url:
        logger.error("NEWS_API_AI_BASE_URL not found in .env file.")
        return {"trends": []}

    url = f"{base_url}/trends/getTrends"
    # Added source to get more relevant trends
    payload = {"apiKey": api_key, "source": "news"} 

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Correctly access the nested 'results' array
        trends_data = data.get("trends", {}).get("trends", {}).get("results", [])
        trends = [Trend(uri=t.get("uri"), label=t.get("label"), score=t.get("score")) for t in trends_data]
        
        logger.info(f"Successfully fetched {len(trends)} trends.")
        return {"trends": trends}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching trends from newsapi.ai: {e}")
        return {"trends": []}

@app.get("/")
def read_root():
    logger.info("GET / root endpoint accessed.")
    return {"message": "Welcome to the Global News Tracker API"}

# To run this application:
# 1. Create a virtual environment and activate it.
# 2. Install dependencies: pip install -r requirements.txt
# 3. Create a .env file and add your NEWS_API_KEY.
# 4. Run the server: uvicorn main:app --reload
