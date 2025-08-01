"""FreshRSS API client implementation."""

import json
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, quote
from datetime import datetime

import httpx
from httpx import Response

from .models import (
    Article,
    AuthResponse,
    Category,
    EditResponse,
    StreamContents,
    Subscription,
    SubscriptionList,
    TagList,
    UnreadCount,
)

logger = logging.getLogger(__name__)


class FreshRSSError(Exception):
    """Base exception for FreshRSS API errors."""
    pass


class AuthenticationError(FreshRSSError):
    """Authentication failed."""
    pass


class APIError(FreshRSSError):
    """API request failed."""
    pass


class FreshRSSClient:
    """Client for interacting with FreshRSS Google Reader API."""
    
    def __init__(
        self,
        base_url: str,
        email: str,
        api_password: str,
        timeout: float = 30.0,
    ):
        """Initialize FreshRSS client.
        
        Args:
            base_url: FreshRSS instance URL (e.g., https://freshrss.example.com)
            email: User email
            api_password: API password (not the main password)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/greader.php"
        self.email = email
        self.api_password = api_password
        self.timeout = timeout
        self.auth_token: Optional[str] = None
        self.edit_token: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=timeout)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
    
    def _build_url(self, endpoint: str) -> str:
        """Build full API URL."""
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]
        return f"{self.api_url}/{endpoint}"
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        auth_required: bool = True,
    ) -> Response:
        """Make an API request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Form data for POST requests
            auth_required: Whether authentication is required
            
        Returns:
            HTTP response
            
        Raises:
            AuthenticationError: If authentication is required but not available
            APIError: If the request fails
        """
        headers = {}
        if auth_required:
            if not self.auth_token:
                raise AuthenticationError("Not authenticated. Call authenticate() first.")
            headers["Authorization"] = f"GoogleLogin auth={self.auth_token}"
        
        url = self._build_url(endpoint)
        
        try:
            response = await self._client.request(
                method=method,
                url=url,
                params=params,
                data=data,
                headers=headers,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise APIError(f"HTTP {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise APIError(f"Request failed: {e}") from e
    
    async def authenticate(self) -> AuthResponse:
        """Authenticate with FreshRSS.
        
        Returns:
            Authentication response with tokens
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            response = await self._request(
                method="POST",
                endpoint="accounts/ClientLogin",
                data={
                    "Email": self.email,
                    "Passwd": self.api_password,
                },
                auth_required=False,
            )
            
            # Parse response (format: key=value per line)
            lines = response.text.strip().split("\n")
            auth_data = {}
            for line in lines:
                if "=" in line:
                    key, value = line.split("=", 1)
                    auth_data[key] = value
            
            if "Auth" not in auth_data:
                raise AuthenticationError("No auth token in response")
            
            auth_response = AuthResponse(
                SID=auth_data.get("SID", ""),
                Auth=auth_data["Auth"],
            )
            
            self.auth_token = auth_response.token
            logger.info("Successfully authenticated with FreshRSS")
            return auth_response
            
        except APIError as e:
            raise AuthenticationError(f"Authentication failed: {e}") from e
    
    async def get_token(self) -> str:
        """Get edit token for write operations.
        
        Returns:
            Edit token
            
        Raises:
            APIError: If token retrieval fails
        """
        response = await self._request("GET", "reader/api/0/token")
        self.edit_token = response.text.strip()
        return self.edit_token
    
    async def get_subscription_list(self) -> SubscriptionList:
        """Get list of subscribed feeds.
        
        Returns:
            List of subscriptions
        """
        response = await self._request("GET", "reader/api/0/subscription/list", params={"output": "json"})
        data = response.json()
        return SubscriptionList(subscriptions=[
            Subscription(**sub) for sub in data.get("subscriptions", [])
        ])
    
    async def get_tag_list(self) -> TagList:
        """Get list of tags/labels/folders.
        
        Returns:
            List of tags
        """
        response = await self._request("GET", "reader/api/0/tag/list", params={"output": "json"})
        data = response.json()
        tags = []
        for tag in data.get("tags", []):
            tags.append(Category(
                id=tag["id"],
                label=tag.get("sortid", tag["id"].split("/")[-1]),
                type="tag" if "label" in tag["id"] else "state"
            ))
        return TagList(tags=tags)
    
    async def get_unread_counts(self) -> List[UnreadCount]:
        """Get unread counts for all feeds and categories.
        
        Returns:
            List of unread counts
        """
        response = await self._request("GET", "reader/api/0/unread-count", params={"output": "json"})
        data = response.json()
        return [
            UnreadCount(**item) for item in data.get("unreadcounts", [])
        ]
    
    async def get_stream_contents(
        self,
        stream_id: str = "user/-/state/com.google/reading-list",
        count: int = 50,
        order: str = "d",  # d=descending (newest first), o=ascending
        start_time: Optional[int] = None,
        continuation: Optional[str] = None,
        exclude_target: Optional[str] = None,
        include_target: Optional[str] = None,
    ) -> StreamContents:
        """Get articles from a stream.
        
        Args:
            stream_id: Stream to fetch (reading-list, starred, or user/-/label/FolderName)
            count: Number of items to fetch (max ~1000)
            order: Sort order (d=descending, o=ascending)
            start_time: Unix timestamp to start from
            continuation: Continuation token for pagination
            exclude_target: Exclude articles with this state (e.g., user/-/state/com.google/read)
            include_target: Include only articles with this state
            
        Returns:
            Stream contents with articles
        """
        params = {
            "output": "json",
            "n": count,
            "r": order,
        }
        
        if start_time:
            params["ot"] = start_time
        if continuation:
            params["c"] = continuation
        if exclude_target:
            params["xt"] = exclude_target
        if include_target:
            params["it"] = include_target
        
        # URL encode the stream ID and append to endpoint
        encoded_stream = quote(stream_id, safe="")
        endpoint = f"reader/api/0/stream/contents/{encoded_stream}"
        
        response = await self._request("GET", endpoint, params=params)
        data = response.json()
        
        # Parse articles
        articles = []
        for item in data.get("items", []):
            # Convert timestamps
            published = None
            if "published" in item:
                published = datetime.fromtimestamp(item["published"])
            elif "crawlTimeMsec" in item:
                published = datetime.fromtimestamp(int(item["crawlTimeMsec"]) / 1000)
            
            article = Article(
                id=item["id"],
                title=item.get("title", ""),
                published=published or datetime.now(),
                updated=datetime.fromtimestamp(item["updated"]) if "updated" in item else None,
                author=item.get("author"),
                content=item.get("content", {}).get("content") if "content" in item else None,
                summary=item.get("summary", {}).get("content") if "summary" in item else None,
                categories=item.get("categories", []),
                origin=item.get("origin"),
                alternate=item.get("alternate", []),
                crawlTimeMsec=item.get("crawlTimeMsec"),
                timestampUsec=item.get("timestampUsec"),
            )
            articles.append(article)
        
        return StreamContents(
            id=data.get("id", stream_id),
            title=data.get("title"),
            items=articles,
            continuation=data.get("continuation"),
            updated=data.get("updated"),
        )
    
    async def mark_as_read(self, item_ids: List[str]) -> EditResponse:
        """Mark articles as read.
        
        Args:
            item_ids: List of article IDs to mark as read
            
        Returns:
            Edit response
        """
        if not self.edit_token:
            await self.get_token()
        
        data = {
            "T": self.edit_token,
            "a": "user/-/state/com.google/read",
        }
        
        # Add item IDs
        for item_id in item_ids:
            data[f"i"] = item_id
        
        response = await self._request("POST", "reader/api/0/edit-tag", data=data)
        return EditResponse(status=response.text.strip())
    
    async def mark_as_unread(self, item_ids: List[str]) -> EditResponse:
        """Mark articles as unread.
        
        Args:
            item_ids: List of article IDs to mark as unread
            
        Returns:
            Edit response
        """
        if not self.edit_token:
            await self.get_token()
        
        data = {
            "T": self.edit_token,
            "a": "user/-/state/com.google/kept-unread",
            "r": "user/-/state/com.google/read",
        }
        
        # Add item IDs
        for item_id in item_ids:
            data[f"i"] = item_id
        
        response = await self._request("POST", "reader/api/0/edit-tag", data=data)
        return EditResponse(status=response.text.strip())
    
    async def star_article(self, item_ids: List[str]) -> EditResponse:
        """Star articles.
        
        Args:
            item_ids: List of article IDs to star
            
        Returns:
            Edit response
        """
        if not self.edit_token:
            await self.get_token()
        
        data = {
            "T": self.edit_token,
            "a": "user/-/state/com.google/starred",
        }
        
        # Add item IDs
        for item_id in item_ids:
            data[f"i"] = item_id
        
        response = await self._request("POST", "reader/api/0/edit-tag", data=data)
        return EditResponse(status=response.text.strip())
    
    async def unstar_article(self, item_ids: List[str]) -> EditResponse:
        """Unstar articles.
        
        Args:
            item_ids: List of article IDs to unstar
            
        Returns:
            Edit response
        """
        if not self.edit_token:
            await self.get_token()
        
        data = {
            "T": self.edit_token,
            "r": "user/-/state/com.google/starred",
        }
        
        # Add item IDs
        for item_id in item_ids:
            data[f"i"] = item_id
        
        response = await self._request("POST", "reader/api/0/edit-tag", data=data)
        return EditResponse(status=response.text.strip())
    
    async def add_label(self, item_ids: List[str], label: str) -> EditResponse:
        """Add label to articles.
        
        Args:
            item_ids: List of article IDs
            label: Label name (without user/-/label/ prefix)
            
        Returns:
            Edit response
        """
        if not self.edit_token:
            await self.get_token()
        
        data = {
            "T": self.edit_token,
            "a": f"user/-/label/{label}",
        }
        
        # Add item IDs
        for item_id in item_ids:
            data[f"i"] = item_id
        
        response = await self._request("POST", "reader/api/0/edit-tag", data=data)
        return EditResponse(status=response.text.strip())
    
    async def subscribe(self, feed_url: str, title: Optional[str] = None, folder: Optional[str] = None) -> EditResponse:
        """Subscribe to a new feed.
        
        Args:
            feed_url: URL of the feed
            title: Optional custom title
            folder: Optional folder name
            
        Returns:
            Edit response
        """
        if not self.edit_token:
            await self.get_token()
        
        data = {
            "T": self.edit_token,
            "ac": "subscribe",
            "s": f"feed/{feed_url}",
        }
        
        if title:
            data["t"] = title
        if folder:
            data["a"] = f"user/-/label/{folder}"
        
        response = await self._request("POST", "reader/api/0/subscription/edit", data=data)
        return EditResponse(status=response.text.strip())
    
    async def unsubscribe(self, feed_url: str) -> EditResponse:
        """Unsubscribe from a feed.
        
        Args:
            feed_url: URL of the feed
            
        Returns:
            Edit response
        """
        if not self.edit_token:
            await self.get_token()
        
        data = {
            "T": self.edit_token,
            "ac": "unsubscribe",
            "s": f"feed/{feed_url}",
        }
        
        response = await self._request("POST", "reader/api/0/subscription/edit", data=data)
        return EditResponse(status=response.text.strip())