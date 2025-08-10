"""FreshRSS MCP Server implementation."""

import asyncio
import logging
import os
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from .client import FreshRSSClient, FreshRSSError, AuthenticationError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("FreshRSS MCP Server")

# Global client instance
client: Optional[FreshRSSClient] = None


class AuthenticateParams(BaseModel):
    """Parameters for authentication."""
    base_url: Optional[str] = Field(None, description="FreshRSS instance URL (uses env if not provided)")
    email: Optional[str] = Field(None, description="User email (uses env if not provided)")
    api_password: Optional[str] = Field(None, description="API password (uses env if not provided)")


class GetArticlesParams(BaseModel):
    """Parameters for fetching articles."""
    folder: Optional[str] = Field(None, description="Folder/label name to filter by")
    feed_url: Optional[str] = Field(None, description="Feed URL to filter by")
    show_read: bool = Field(False, description="Include read articles")
    starred_only: bool = Field(False, description="Show only starred articles")
    count: int = Field(50, description="Number of articles to fetch (max ~1000)")
    order: str = Field("newest", description="Sort order: 'newest' or 'oldest'")
    continuation: Optional[str] = Field(None, description="Continuation token for pagination")


class MarkArticlesParams(BaseModel):
    """Parameters for marking articles."""
    article_ids: List[str] = Field(..., description="List of article IDs")


class AddLabelParams(BaseModel):
    """Parameters for adding labels."""
    article_ids: List[str] = Field(..., description="List of article IDs")
    label: str = Field(..., description="Label name to add")


class SubscribeParams(BaseModel):
    """Parameters for subscribing to a feed."""
    feed_url: str = Field(..., description="URL of the feed to subscribe to")
    title: Optional[str] = Field(None, description="Custom title for the feed")
    folder: Optional[str] = Field(None, description="Folder to add the feed to")


class UnsubscribeParams(BaseModel):
    """Parameters for unsubscribing from a feed."""
    feed_url: str = Field(..., description="URL of the feed to unsubscribe from")


async def ensure_authenticated():
    """Ensure the client is authenticated."""
    global client
    if client is None:
        # Try to create client from environment variables
        base_url = os.getenv("FRESHRSS_URL")
        email = os.getenv("FRESHRSS_EMAIL")
        api_password = os.getenv("FRESHRSS_API_PASSWORD")
        
        if not all([base_url, email, api_password]):
            raise AuthenticationError(
                "Not authenticated. Please call freshrss_authenticate first or set environment variables."
            )
        
        client = FreshRSSClient(base_url, email, api_password)
        await client.authenticate()
    return client


@mcp.tool()
async def freshrss_authenticate(params: AuthenticateParams) -> Dict[str, Any]:
    """Authenticate with FreshRSS instance.
    
    Uses provided parameters or falls back to environment variables:
    - FRESHRSS_URL
    - FRESHRSS_EMAIL  
    - FRESHRSS_API_PASSWORD
    """
    global client
    
    # Get credentials
    base_url = params.base_url or os.getenv("FRESHRSS_URL")
    email = params.email or os.getenv("FRESHRSS_EMAIL")
    api_password = params.api_password or os.getenv("FRESHRSS_API_PASSWORD")
    
    if not all([base_url, email, api_password]):
        return {
            "success": False,
            "error": "Missing required credentials. Please provide base_url, email, and api_password."
        }
    
    try:
        # Close existing client if any
        if client:
            await client.close()
        
        # Create new client
        client = FreshRSSClient(base_url, email, api_password)
        auth_response = await client.authenticate()
        
        return {
            "success": True,
            "message": "Successfully authenticated with FreshRSS",
            "user": email,
            "instance": base_url
        }
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_get_token() -> Dict[str, Any]:
    """Get edit token for write operations. Usually called automatically when needed."""
    try:
        client = await ensure_authenticated()
        token = await client.get_token()
        return {
            "success": True,
            "token": token,
            "message": "Token retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Failed to get token: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_list_folders() -> Dict[str, Any]:
    """List all folders/categories/tags in FreshRSS."""
    try:
        client = await ensure_authenticated()
        tag_list = await client.get_tag_list()
        
        folders = []
        for tag in tag_list.folders:
            folders.append({
                "name": tag.label,
                "id": tag.id,
                "type": "folder"
            })
        
        return {
            "success": True,
            "folders": folders,
            "count": len(folders)
        }
    except Exception as e:
        logger.error(f"Failed to list folders: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_list_subscriptions() -> Dict[str, Any]:
    """List all subscribed feeds with their folders."""
    try:
        client = await ensure_authenticated()
        subscription_list = await client.get_subscription_list()
        
        subscriptions = []
        for sub in subscription_list.subscriptions:
            folders = [cat.label for cat in sub.categories if cat.is_label]
            subscriptions.append({
                "title": sub.title,
                "feed_url": sub.feed_id,
                "id": sub.id,
                "folders": folders,
                "url": sub.url,
                "html_url": sub.htmlUrl,
                "icon_url": sub.iconUrl
            })
        
        return {
            "success": True,
            "subscriptions": subscriptions,
            "count": len(subscriptions)
        }
    except Exception as e:
        logger.error(f"Failed to list subscriptions: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_get_unread_count() -> Dict[str, Any]:
    """Get unread counts by feed and folder."""
    try:
        client = await ensure_authenticated()
        unread_counts = await client.get_unread_counts()
        
        # Organize counts by type
        feeds = []
        folders = []
        total_unread = 0
        
        for count in unread_counts:
            if count.id.startswith("feed/"):
                feeds.append({
                    "feed_url": count.id[5:],
                    "count": count.count
                })
            elif count.id.startswith("user/-/label/"):
                folders.append({
                    "folder": count.id.split("/")[-1],
                    "count": count.count
                })
            elif count.id == "user/-/state/com.google/reading-list":
                total_unread = count.count
        
        return {
            "success": True,
            "total_unread": total_unread,
            "feeds": feeds,
            "folders": folders
        }
    except Exception as e:
        logger.error(f"Failed to get unread counts: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_get_articles(params: GetArticlesParams) -> Dict[str, Any]:
    """Fetch articles with various filters."""
    try:
        client = await ensure_authenticated()
        
        # Determine stream ID
        if params.starred_only:
            stream_id = "user/-/state/com.google/starred"
        elif params.folder:
            stream_id = f"user/-/label/{params.folder}"
        elif params.feed_url:
            stream_id = f"feed/{params.feed_url}"
        else:
            stream_id = "user/-/state/com.google/reading-list"
        
        # Set exclude target for unread only
        exclude_target = None if params.show_read else "user/-/state/com.google/read"
        
        # Fetch articles
        stream = await client.get_stream_contents(
            stream_id=stream_id,
            count=params.count,
            order="d" if params.order == "newest" else "o",
            exclude_target=exclude_target,
            continuation=params.continuation
        )
        
        # Format articles
        articles = []
        for article in stream.items:
            articles.append({
                "id": article.id,
                "title": article.title,
                "url": article.url,
                "content": article.content,
                "summary": article.summary,
                "author": article.author,
                "published": article.published.isoformat() if article.published else None,
                "feed_title": article.feed_title,
                "feed_url": article.feed_url,
                "is_read": article.is_read,
                "is_starred": article.is_starred,
                "labels": [cat for cat in article.categories if cat.startswith("user/-/label/")]
            })
        
        return {
            "success": True,
            "articles": articles,
            "count": len(articles),
            "has_more": stream.has_more,
            "continuation": stream.continuation
        }
    except Exception as e:
        logger.error(f"Failed to get articles: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_mark_read(params: MarkArticlesParams) -> Dict[str, Any]:
    """Mark articles as read."""
    try:
        client = await ensure_authenticated()
        response = await client.mark_as_read(params.article_ids)
        
        return {
            "success": True,
            "message": f"Marked {len(params.article_ids)} article(s) as read",
            "status": response.status
        }
    except Exception as e:
        logger.error(f"Failed to mark articles as read: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_mark_unread(params: MarkArticlesParams) -> Dict[str, Any]:
    """Mark articles as unread."""
    try:
        client = await ensure_authenticated()
        response = await client.mark_as_unread(params.article_ids)
        
        return {
            "success": True,
            "message": f"Marked {len(params.article_ids)} article(s) as unread",
            "status": response.status
        }
    except Exception as e:
        logger.error(f"Failed to mark articles as unread: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_star_article(params: MarkArticlesParams) -> Dict[str, Any]:
    """Star articles."""
    try:
        client = await ensure_authenticated()
        response = await client.star_article(params.article_ids)
        
        return {
            "success": True,
            "message": f"Starred {len(params.article_ids)} article(s)",
            "status": response.status
        }
    except Exception as e:
        logger.error(f"Failed to star articles: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_unstar_article(params: MarkArticlesParams) -> Dict[str, Any]:
    """Unstar articles."""
    try:
        client = await ensure_authenticated()
        response = await client.unstar_article(params.article_ids)
        
        return {
            "success": True,
            "message": f"Unstarred {len(params.article_ids)} article(s)",
            "status": response.status
        }
    except Exception as e:
        logger.error(f"Failed to unstar articles: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_add_label(params: AddLabelParams) -> Dict[str, Any]:
    """Add label to articles."""
    try:
        client = await ensure_authenticated()
        response = await client.add_label(params.article_ids, params.label)
        
        return {
            "success": True,
            "message": f"Added label '{params.label}' to {len(params.article_ids)} article(s)",
            "status": response.status
        }
    except Exception as e:
        logger.error(f"Failed to add label: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_subscribe(params: SubscribeParams) -> Dict[str, Any]:
    """Subscribe to a new feed."""
    try:
        client = await ensure_authenticated()
        response = await client.subscribe(
            feed_url=params.feed_url,
            title=params.title,
            folder=params.folder
        )
        
        return {
            "success": True,
            "message": f"Successfully subscribed to {params.feed_url}",
            "status": response.status
        }
    except Exception as e:
        logger.error(f"Failed to subscribe: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def freshrss_unsubscribe(params: UnsubscribeParams) -> Dict[str, Any]:
    """Unsubscribe from a feed."""
    try:
        client = await ensure_authenticated()
        response = await client.unsubscribe(params.feed_url)
        
        return {
            "success": True,
            "message": f"Successfully unsubscribed from {params.feed_url}",
            "status": response.status
        }
    except Exception as e:
        logger.error(f"Failed to unsubscribe: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def main():
    """Run the MCP server."""
    import sys
    
    # Check for transport argument
    transport = "stdio"  # default
    port = 8000  # default port for HTTP
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--http":
            transport = "streamable-http"
            print(f"🚀 Starting FreshRSS MCP Server on http://localhost:{port}")
            print("📡 Available endpoints:")
            print(f"   • WebSocket: ws://localhost:{port}/ws")
            print(f"   • Health: http://localhost:{port}/health")
            print("📋 MCP Tools: 13 tools available for FreshRSS management")
            print("🔧 Configure in Claude Desktop with WebSocket URL")
        elif sys.argv[1] == "--sse":
            transport = "sse"
            print(f"🚀 Starting FreshRSS MCP Server with SSE on port {port}")
        elif sys.argv[1] == "--stdio":
            transport = "stdio"
            print("🚀 Starting FreshRSS MCP Server with stdio transport")
        elif sys.argv[1] in ["-h", "--help"]:
            print("FreshRSS MCP Server")
            print("Usage:")
            print("  freshrss-mcp [--http|--sse|--stdio]")
            print("  freshrss-mcp --http    # HTTP transport on port 8000")
            print("  freshrss-mcp --sse     # Server-Sent Events transport")
            print("  freshrss-mcp --stdio   # Standard I/O transport (default)")
            return
    
    # Configure logging level
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))
    
    if transport == "streamable-http":
        # For HTTP transport, we need to set up the server differently
        import uvicorn
        
        # Create the HTTP app
        app = mcp.streamable_http_app()
        
        # Show startup logs
        logger.info(f"🚀 FreshRSS MCP Server starting on http://localhost:{port}")
        logger.info("📋 13 MCP tools loaded for FreshRSS management")
        
        # Use 0.0.0.0 when running in Docker to allow external connections
        host = "0.0.0.0" if os.getenv("DOCKER_CONTAINER", "").lower() == "true" else "localhost"
        
        uvicorn.run(
            app, 
            host=host, 
            port=port, 
            log_level=log_level.lower(),
            access_log=True
        )
    elif transport == "stdio":
        if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
            logger.info("🚀 FreshRSS MCP Server starting with stdio transport")
        mcp.run(transport=transport)
    else:
        logger.info(f"🚀 FreshRSS MCP Server starting with {transport} transport")
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()