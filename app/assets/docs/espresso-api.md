# Espresso News API & MCP

Espresso News API is an intelligent news aggregation and search service that curates fresh content from RSS feeds using AI-powered natural language queries and filters. It provides fast JSON responses, making it ideal for developers building news apps or integrating smart content discovery.

## Key Features

- **Natural Language Search**: Query articles using semantic (vector) or keyword (BM25) searches with adjustable accuracy thresholds for precise results.
- **Advanced Filtering**: Filter by categories, entities, regions, sources, authors, publication dates, and more to tailor content to specific needs.
- **Latest Articles Endpoint**: Retrieve the newest news and blogs sorted by publication date, with pagination support.
- **Publisher and Metadata Access**: Fetch publisher details, unique categories, entities, and regions for comprehensive content exploration.
- **High-Performance Aggregation**: Daily scraping of RSS feeds ensures up-to-date, cross-referenced content influenced by social media trends for relevance.
- **API Key Authentication**: Secure access with customizable headers for protected endpoints.

## Benefits

- **Scalable and Reliable**: Built on FastAPI for low-latency responses, with free tiers for testing and paid options for high-volume usage.
- **Interconnected Ecosystem**: Powers Espresso Beans (the user-facing aggregator) and complements Espresso Publications (AI-generated insights).
- **Developer-Friendly**: JSON-based responses, comprehensive query parameters, and clear documentation make integration straightforward.
- **Use Cases**: Ideal for news apps, content recommendation systems, research tools, or any platform needing curated, AI-enhanced news feeds.

## Endpoints

### Health Check
- **GET /health**
  - Description: Performs a health check on the API service.
  - Response: `{ "status": "alive" }`

### Categories
- **GET /categories**
  - Description: Retrieves a list of unique content categories.
  - Query Parameters:
    - `offset` (int): Number of items to skip (default: 0).
    - `limit` (int): Maximum number of items to return (default: 16).

### Entities
- **GET /entities**
  - Description: Retrieves a list of unique named entities (e.g., people, organizations, products).
  - Query Parameters:
    - `offset` (int): Number of items to skip (default: 0).
    - `limit` (int): Maximum number of items to return (default: 16).

### Regions
- **GET /regions**
  - Description: Retrieves a list of unique geographic regions.
  - Query Parameters:
    - `offset` (int): Number of items to skip (default: 0).
    - `limit` (int): Maximum number of items to return (default: 16).

### Latest Articles
- **GET /articles/latest**
  - Description: Searches for the latest articles sorted by publication date.
  - Query Parameters:
    - `q` (str): Search query string (min length: 3).
    - `acc` (float): Minimum cosine similarity score (default: 0.75).
    - `kind` (str): Type of content (`news` or `blog`).
    - `categories`, `entities`, `regions`, `sources` (list[str]): Filters.
    - `published_since` (datetime): Filter by publication date.
    - `offset` (int): Number of items to skip (default: 0).
    - `limit` (int): Maximum number of items to return (default: 16).

### Publishers
- **GET /publishers**
  - Description: Retrieves metadata about publishers filtered by source IDs.
  - Query Parameters:
    - `sources` (list[str]): Source IDs to filter publishers.
    - `offset` (int): Number of items to skip (default: 0).
    - `limit` (int): Maximum number of items to return (default: 16).

- **GET /publishers/sources**
  - Description: Retrieves a list of unique publisher IDs.
  - Query Parameters:
    - `offset` (int): Number of items to skip (default: 0).
    - `limit` (int): Maximum number of items to return (default: 16).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
