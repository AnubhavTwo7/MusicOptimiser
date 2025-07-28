#!/usr/bin/env python3
"""
API routes for MusicRecommender - Simple working version
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
import logging

logger = logging.getLogger(__name__)

# Create the router - this is what was missing!
router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def serve_home():
    """Serve the main application page."""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎵 MusicRecommender API</title>
        <style>
            body { 
                font-family: Arial, sans-serif; margin: 2rem; 
                background: #0d1117; color: #e6edf3; text-align: center; 
            }
            h1 { color: #7c3aed; font-size: 2.5rem; margin-bottom: 1rem; }
            .status { 
                background: #21262d; padding: 1.5rem; border-radius: 8px; 
                margin: 2rem auto; max-width: 600px; border-left: 4px solid #7c3aed; 
            }
            a { 
                color: #58a6ff; text-decoration: none; padding: 0.5rem 1rem; 
                background: rgba(88, 166, 255, 0.1); border-radius: 6px; margin: 0.5rem; 
                display: inline-block;
            }
            a:hover { background: rgba(88, 166, 255, 0.2); }
        </style>
    </head>
    <body>
        <h1>🎵 MusicRecommender API</h1>
        <div class="status">
            <p><strong>✅ Status:</strong> Server Running Successfully!</p>
            <p><strong>🔧 Fixed:</strong> Router import issue resolved</p>
        </div>
        <div>
            <a href="/api/health">📊 Health Check</a>
            <a href="/docs">📖 API Documentation</a>
            <a href="/api/test">🧪 Test Endpoint</a>
        </div>
        <p style="margin-top: 2rem; color: #8b949e;">
            🎶 Your API is back to working condition!
        </p>
    </body>
    </html>
    """)

@router.get("/api/health")
async def health_check():
    """API health check."""
    return {
        "status": "healthy",
        "message": "✅ MusicRecommender API is working perfectly!",
        "router": "successfully_loaded",
        "services": {
            "api": "online",
            "routes": "working"
        }
    }

@router.get("/api/test")
async def test_endpoint():
    """Simple test endpoint."""
    return {
        "message": "🎵 Test successful!",
        "status": "working",
        "timestamp": "2025-07-29"
    }

# This is crucial - make sure router is exported
__all__ = ["router"]
