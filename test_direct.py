#!/usr/bin/env python3
"""Test FreshRSS client directly."""

import asyncio
import os
from dotenv import load_dotenv
from freshrss_mcp.client import FreshRSSClient

# Load environment variables
load_dotenv()

async def test_freshrss():
    """Test FreshRSS client functionality."""
    client = FreshRSSClient(
        base_url=os.getenv('FRESHRSS_URL'),
        email=os.getenv('FRESHRSS_EMAIL'), 
        api_password=os.getenv('FRESHRSS_API_PASSWORD')
    )
    
    try:
        print('🔐 Authenticating...')
        auth = await client.authenticate()
        print(f'✅ Authenticated successfully!')
        
        print('\n📁 Getting folders...')
        folders = await client.get_tag_list()
        print(f'✅ Found {len(folders.tags)} tags/folders')
        for folder in folders.folders[:5]:  # Show first 5
            print(f'   📂 {folder.label}')
        
        print('\n📰 Getting subscriptions...')
        subs = await client.get_subscription_list()
        print(f'✅ Found {len(subs.subscriptions)} subscriptions')
        for sub in subs.subscriptions[:5]:  # Show first 5
            print(f'   📡 {sub.title}')
        
        print('\n📊 Getting unread counts...')
        counts = await client.get_unread_counts()
        total_unread = next((c.count for c in counts if c.id == 'user/-/state/com.google/reading-list'), 0)
        print(f'✅ Total unread articles: {total_unread}')
        
        print('\n📄 Getting recent articles...')
        articles = await client.get_stream_contents(count=3)
        print(f'✅ Found {len(articles.items)} recent articles')
        for i, article in enumerate(articles.items, 1):
            print(f'   {i}. {article.title[:50]}...')
            print(f'      Read: {article.is_read}, Starred: {article.is_starred}')
            if article.feed_title:
                print(f'      From: {article.feed_title}')
        
        if total_unread > 0:
            print('\n📄 Getting unread articles...')
            unread_articles = await client.get_stream_contents(
                count=3,
                exclude_target="user/-/state/com.google/read"
            )
            print(f'✅ Found {len(unread_articles.items)} unread articles')
            for i, article in enumerate(unread_articles.items, 1):
                print(f'   {i}. {article.title[:50]}...')
                print(f'      From: {article.feed_title or "Unknown"}')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_freshrss())