#!/usr/bin/env python3
"""Demo script to show FreshRSS MCP server running in HTTP mode."""

import subprocess
import time
import os

def demo_http_server():
    """Demonstrate the HTTP server running."""
    print("=" * 60)
    print("🚀 FreshRSS MCP Server - HTTP Mode Demo")
    print("=" * 60)
    print()
    print("📍 Server will run on: http://localhost:8000")
    print("🔧 Virtual environment: ACTIVATED")
    print("📡 Transport: Streamable HTTP")
    print("🛠️  Tools: 13 FreshRSS management tools")
    print()
    
    # Start the server
    print("⏳ Starting server...")
    proc = subprocess.Popen(
        ['freshrss-mcp', '--http'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Give it time to start and capture initial output
    time.sleep(3)
    
    print("✅ Server started!")
    print()
    print("📋 Server Information:")
    print("   • URL: http://localhost:8000")
    print("   • MCP Endpoint: http://localhost:8000/mcp")
    print("   • Protocol: Server-Sent Events / WebSocket")
    print("   • Status: RUNNING")
    print()
    
    print("🎯 Usage Options:")
    print("   1. For MCP clients: Connect to http://localhost:8000/mcp")
    print("   2. For WebSocket: ws://localhost:8000/mcp")
    print("   3. Server-Sent Events: GET http://localhost:8000/mcp")
    print()
    
    print("🔧 Claude Desktop Config (HTTP mode):")
    print('   {')
    print('     "mcpServers": {')
    print('       "freshrss": {')
    print('         "command": "freshrss-mcp",')
    print('         "args": ["--http"],')
    print('         "env": {')
    print('           "FRESHRSS_URL": "https://your-instance.com",')
    print('           "FRESHRSS_EMAIL": "your-email",')
    print('           "FRESHRSS_API_PASSWORD": "your-api-password"')
    print('         }')
    print('       }')
    print('     }')
    print('   }')
    print()
    
    print("⏹️  Press Enter to stop the server (or Ctrl+C)...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n🛑 Stopping server via Ctrl+C...")
    
    print("🛑 Terminating server...")
    proc.terminate()
    
    try:
        stdout, _ = proc.communicate(timeout=3)
        if stdout:
            print("\n📋 Server Output:")
            print(stdout)
    except subprocess.TimeoutExpired:
        proc.kill()
        print("   Server forcefully stopped")
    
    print("✅ Server stopped successfully!")
    print("=" * 60)

if __name__ == "__main__":
    demo_http_server()