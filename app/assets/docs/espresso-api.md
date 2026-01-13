# Espresso News API & MCP

Espresso News API & MCP serves as the robust backend engine for Project Cafecito's Espresso product suite, delivering AI-curated news and blog content aggregated from diverse RSS feeds. Designed for developers, it enables seamless integration of intelligent content discovery into applications, dashboards, or platforms.

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