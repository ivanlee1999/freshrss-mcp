"""Data models for FreshRSS MCP server."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Category(BaseModel):
    """Represents a category/label/tag in FreshRSS."""
    
    id: str
    label: str
    type: str = Field(default="category")  # category, tag, or state
    
    @property
    def is_state(self) -> bool:
        """Check if this is a state category (read, starred, etc.)."""
        return self.id.startswith("user/-/state/com.google/")
    
    @property
    def is_label(self) -> bool:
        """Check if this is a user label/folder."""
        return self.id.startswith("user/-/label/")


class UnreadCount(BaseModel):
    """Represents unread count for a feed or category."""
    
    id: str
    count: int
    newestItemTimestampUsec: Optional[str] = None


class Subscription(BaseModel):
    """Represents a feed subscription."""
    
    id: str
    title: str
    categories: List[Category] = Field(default_factory=list)
    url: Optional[str] = None
    htmlUrl: Optional[str] = None
    iconUrl: Optional[str] = None
    
    @property
    def feed_id(self) -> str:
        """Extract the feed URL from the subscription ID."""
        if self.id.startswith("feed/"):
            return self.id[5:]
        return self.id


class Article(BaseModel):
    """Represents an RSS article/entry."""
    
    id: str
    title: str
    published: datetime
    updated: Optional[datetime] = None
    author: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    origin: Optional[dict] = None
    alternate: Optional[List[dict]] = None
    
    # Computed properties
    crawlTimeMsec: Optional[str] = None
    timestampUsec: Optional[str] = None
    
    @property
    def is_read(self) -> bool:
        """Check if article is marked as read."""
        return "user/-/state/com.google/read" in self.categories
    
    @property
    def is_starred(self) -> bool:
        """Check if article is starred."""
        return "user/-/state/com.google/starred" in self.categories
    
    @property
    def is_kept_unread(self) -> bool:
        """Check if article is kept unread."""
        return "user/-/state/com.google/kept-unread" in self.categories
    
    @property
    def url(self) -> Optional[str]:
        """Get the article URL from alternate links."""
        if self.alternate:
            for link in self.alternate:
                if link.get("type") == "text/html":
                    return link.get("href")
        return None
    
    @property
    def feed_title(self) -> Optional[str]:
        """Get the feed title from origin."""
        if self.origin:
            return self.origin.get("title")
        return None
    
    @property
    def feed_url(self) -> Optional[str]:
        """Get the feed URL from origin."""
        if self.origin:
            stream_id = self.origin.get("streamId", "")
            if stream_id.startswith("feed/"):
                return stream_id[5:]
        return None


class StreamContents(BaseModel):
    """Represents a stream of articles."""
    
    id: str
    title: Optional[str] = None
    items: List[Article] = Field(default_factory=list)
    continuation: Optional[str] = None
    updated: Optional[int] = None
    
    @property
    def has_more(self) -> bool:
        """Check if there are more items to fetch."""
        return self.continuation is not None


class TagList(BaseModel):
    """Represents a list of tags/labels."""
    
    tags: List[Category] = Field(default_factory=list)
    
    @property
    def folders(self) -> List[Category]:
        """Get only folder/label categories."""
        return [tag for tag in self.tags if tag.is_label]
    
    @property
    def states(self) -> List[Category]:
        """Get only state categories."""
        return [tag for tag in self.tags if tag.is_state]


class SubscriptionList(BaseModel):
    """Represents a list of subscriptions."""
    
    subscriptions: List[Subscription] = Field(default_factory=list)


class AuthResponse(BaseModel):
    """Represents authentication response."""
    
    SID: str
    Auth: str
    
    @property
    def token(self) -> str:
        """Get the auth token for API requests."""
        return self.Auth


class EditResponse(BaseModel):
    """Represents response from edit operations."""
    
    status: str = "OK"