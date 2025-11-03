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

# II. Data Structure and Pydantic Model
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

# III. Core Functions and Real Data Fetching
def scrape_real_news() -> List[NewsArticle]:
    logger.info("Attempting to scrape real news from newsapi.ai...")
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        logger.error("NEWS_API_KEY not found or is default in .env file. Please set your actual API key.")
        return []

    url = "http://eventregistry.org/api/v1/article/getArticles"
    
    payload = {
        "action": "getArticles",
        "keyword": "business",
        "articlesPage": 1,
        "articlesCount": 20,
        "articlesSortBy": "date",
        "articlesSortByAsc": False,
        "articlesArticleBodyLen": -1,
        "resultType": "articles",
        "dataType": [
            "news",
            "blog"
        ],
        "apiKey": api_key,
        "forceMaxDataTimeWindow": 31
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        
        articles = []
        for i, item in enumerate(data.get("articles", {}).get("results", [])):
            # Ensure 'dateTimePub' is not None before processing
            published_at = item.get("dateTimePub")
            if published_at:
                try:
                    timestamp = datetime.fromisoformat(published_at)
                except ValueError:
                    logger.warning(f"Could not parse timestamp for article: {item.get('title')}. Using current time.")
                    timestamp = datetime.now()
            else:
                logger.warning(f"'dateTimePub' is missing for article: {item.get('title')}. Using current time.")
                timestamp = datetime.now()

            article = NewsArticle(
                id=i + 1,
                title=item.get("title", "No Title"),
                summary=item.get("body"),
                source=item.get("source", {}).get("title", "Unknown Source"),
                timestamp=timestamp,
                imageUrl=item.get("image"),
                country=item.get("location", {}).get("country", {}).get("label"),
                category=item.get("concepts")[0].get("label") if item.get("concepts") else "General",
                relevance_score=item.get("relevance", 0.0)
            )
            articles.append(article)
        logger.info(f"Successfully fetched {len(articles)} articles from newsapi.ai.")
        return articles

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching news from newsapi.ai: {e}")
        return []

news_data = scrape_real_news()

# IV. API Endpoint: /news
@app.get("/news", response_model=List[NewsArticle])
async def get_news(
    q: Optional[str] = Query(None, description="Global search term for title and summary"),
    country: Optional[str] = Query(None, description="Filter by country"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by: str = Query('newest', description="Sort by: 'newest', 'oldest', 'source', 'relevance'")
):
    logger.info(f"GET /news endpoint accessed with params: q={q}, country={country}, category={category}, sort_by={sort_by}")
    """
    Provides a filterable and sortable list of news articles.
    """
    results = news_data

    # 1. Filtering and Searching
    if q:
        initial_count = len(results)
        results = [
            article for article in results 
            if q.lower() in article.title.lower() or (article.summary and q.lower() in article.summary.lower())
        ]
        logger.info(f"Filtered by search term '{q}': {initial_count} -> {len(results)} articles.")

    if country:
        initial_count = len(results)
        results = [article for article in results if article.country and article.country.lower() == country.lower()]
        logger.info(f"Filtered by country '{country}': {initial_count} -> {len(results)} articles.")

    if category:
        initial_count = len(results)
        results = [article for article in results if article.category and article.category.lower() == category.lower()]
        logger.info(f"Filtered by category '{category}': {initial_count} -> {len(results)} articles.")

    # 2. Sorting
    if sort_by == 'newest':
        results.sort(key=lambda x: x.timestamp, reverse=True)
        logger.info("Sorted by 'newest'.")
    elif sort_by == 'oldest':
        results.sort(key=lambda x: x.timestamp)
        logger.info("Sorted by 'oldest'.")
    elif sort_by == 'source':
        results.sort(key=lambda x: x.source)
        logger.info("Sorted by 'source'.")
    elif sort_by == 'relevance':
        # Ensure relevance_score is not None before sorting
        results.sort(key=lambda x: x.relevance_score if x.relevance_score is not None else 0.0, reverse=True)
        logger.info("Sorted by 'relevance'.")
    else:
        logger.warning(f"Unknown sort_by parameter: {sort_by}. No sorting applied.")

    logger.info(f"Returning {len(results)} articles.")
    return results

@app.get("/")
def read_root():
    logger.info("GET / root endpoint accessed.")
    return {"message": "Welcome to the Global News Tracker API"}

# To run this application:
# 1. Create a virtual environment:
#    python -m venv venv
#    source venv/bin/activate  (or venv\Scripts\activate on Windows)
# 2. Install dependencies:
#    pip install -r requirements.txt
# 3. Create a .env file in the same directory and add your NewsAPI.org key:
#    NEWS_API_KEY=your_actual_api_key
# 4. Run the server:
#    uvicorn main:app --reload


# curl "http://127.0.0.1:8000/news"
# curl "http://127.0.0.1:8000/news?q=tech"
# curl "http://127.0.0.1:8000/news?country=uk&sort_by=oldest"
