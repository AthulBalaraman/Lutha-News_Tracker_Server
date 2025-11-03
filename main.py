import os
import requests
from fastapi import FastAPI, Query
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI()

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
    """
    Fetches news articles from the NewsAPI.org service.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("ERROR: NEWS_API_KEY not found in .env file.")
        return []

    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        
        articles = []
        for i, item in enumerate(data.get("articles", [])):
            article = NewsArticle(
                id=i + 1,
                title=item.get("title", "No Title"),
                summary=item.get("description"),
                source=item.get("source", {}).get("name", "Unknown Source"),
                timestamp=datetime.fromisoformat(item.get("publishedAt").replace("Z", "+00:00")),
                imageUrl=item.get("urlToImage"),
                # The following fields are not directly available in NewsAPI
                # and are set to default values.
                country="USA", 
                category="General",
                relevance_score=item.get("relevance", 0.0)
            )
            articles.append(article)
        return articles

    except requests.exceptions.RequestException as e:
        print(f"Error fetching news from NewsAPI: {e}")
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
    """
    Provides a filterable and sortable list of news articles.
    """
    results = news_data

    # 1. Filtering and Searching
    if q:
        results = [
            article for article in results 
            if q.lower() in article.title.lower() or (article.summary and q.lower() in article.summary.lower())
        ]

    if country:
        results = [article for article in results if article.country and article.country.lower() == country.lower()]

    if category:
        results = [article for article in results if article.category and article.category.lower() == category.lower()]

    # 2. Sorting
    if sort_by == 'newest':
        results.sort(key=lambda x: x.timestamp, reverse=True)
    elif sort_by == 'oldest':
        results.sort(key=lambda x: x.timestamp)
    elif sort_by == 'source':
        results.sort(key=lambda x: x.source)
    elif sort_by == 'relevance':
        # Ensure relevance_score is not None before sorting
        results.sort(key=lambda x: x.relevance_score if x.relevance_score is not None else 0.0, reverse=True)

    return results

@app.get("/")
def read_root():
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
