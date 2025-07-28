from fastapi import FastAPI, HTTPException, Query, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, DateTime, Boolean, Float, JSON
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import uvicorn
import os
from dotenv import load_dotenv
import random
from datetime import datetime
from typing import List, Optional
import hashlib

load_dotenv()

app = FastAPI(title="Music Playlist Optimizer - Full Stack")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = "postgresql://postgres:password123@localhost:5432/music_playlist"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Spotify setup
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

client_credentials_manager = SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
)
spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    """Serve the main web interface."""
    return FileResponse('static/index.html')

# ============== API ENDPOINTS ==============

@app.get("/api/health")
async def health_check():
    """API health check."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        spotify.search("test", limit=1, type='track')
        
        return {
            "status": "healthy",
            "database": "connected",
            "spotify": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# ============== USER MANAGEMENT ==============

@app.post("/api/users/register")
async def register_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Register a new user."""
    try:
        # Hash password (simple hash for demo - use proper hashing in production)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        with engine.connect() as conn:
            # Check if user exists
            result = conn.execute(text(
                "SELECT id FROM users WHERE username = :username OR email = :email"
            ), {"username": username, "email": email})
            
            if result.fetchone():
                raise HTTPException(status_code=400, detail="User already exists")
            
            # Create user
            result = conn.execute(text("""
                INSERT INTO users (username, email, password_hash, created_at, is_active)
                VALUES (:username, :email, :password_hash, CURRENT_TIMESTAMP, true)
                RETURNING id
            """), {"username": username, "email": email, "password_hash": password_hash})
            
            user_id = result.fetchone()[0]
            conn.commit()
            
            return {
                "message": "User registered successfully",
                "user_id": user_id,
                "username": username
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/login")
async def login_user(
    username: str = Form(...),
    password: str = Form(...)
):
    """User login."""
    try:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, username, email FROM users 
                WHERE username = :username AND password_hash = :password_hash AND is_active = true
            """), {"username": username, "password_hash": password_hash})
            
            user = result.fetchone()
            if not user:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            return {
                "message": "Login successful",
                "user": {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2]
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{user_id}")
async def get_user_profile(user_id: int):
    """Get user profile."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT u.id, u.username, u.email, u.created_at,
                       COUNT(DISTINCT p.id) as playlist_count,
                       COUNT(DISTINCT lh.id) as total_listens
                FROM users u
                LEFT JOIN playlists p ON u.id = p.user_id
                LEFT JOIN listening_history lh ON u.id = lh.user_id
                WHERE u.id = :user_id AND u.is_active = true
                GROUP BY u.id, u.username, u.email, u.created_at
            """), {"user_id": user_id})
            
            user = result.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {
                "user": {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "created_at": user[3].isoformat() if user[3] else None,
                    "playlist_count": user[4] or 0,
                    "total_listens": user[5] or 0
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============== RECOMMENDATIONS ==============

@app.get("/api/recommendations/search")
async def search_recommendations(
    genre: str = Query("pop"),
    limit: int = Query(20, ge=1, le=50),
    min_popularity: int = Query(0, ge=0, le=100)
):
    """Get recommendations using search method."""
    try:
        search_queries = [
            f"genre:{genre}",
            f"genre:{genre} year:2020-2024",
            f"{genre} popular",
            f"{genre} top hits"
        ]
        
        all_tracks = []
        
        for query in search_queries:
            try:
                results = spotify.search(q=query, type='track', limit=limit//4, market='US')
                for track in results['tracks']['items']:
                    if track['popularity'] >= min_popularity:
                        all_tracks.append({
                            "id": track['id'],
                            "name": track['name'],
                            "artist": ', '.join([artist['name'] for artist in track['artists']]),
                            "album": track['album']['name'],
                            "popularity": track['popularity'],
                            "preview_url": track['preview_url'],
                            "external_url": track['external_urls']['spotify'],
                            "image_url": track['album']['images'][0]['url'] if track['album']['images'] else None,
                            "duration_ms": track['duration_ms']
                        })
            except Exception:
                continue
        
        # Remove duplicates and sort by popularity
        unique_tracks = {}
        for track in all_tracks:
            if track['id'] not in unique_tracks:
                unique_tracks[track['id']] = track
        
        final_tracks = list(unique_tracks.values())
        final_tracks.sort(key=lambda x: x['popularity'], reverse=True)
        
        return {
            "recommendations": final_tracks[:limit],
            "total": len(final_tracks),
            "method": "search_based",
            "genre": genre
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recommendations/artist")
async def artist_recommendations(
    artist_name: str = Query(...),
    limit: int = Query(10, ge=1, le=50)
):
    """Get recommendations based on artist."""
    try:
        # Search for the artist
        artist_results = spotify.search(q=artist_name, type='artist', limit=1)
        
        if not artist_results['artists']['items']:
            raise HTTPException(status_code=404, detail="Artist not found")
        
        artist = artist_results['artists']['items'][0]
        artist_id = artist['id']
        
        # Get artist's top tracks
        top_tracks = spotify.artist_top_tracks(artist_id, country='US')
        
        recommendations = []
        for track in top_tracks['tracks']:
            recommendations.append({
                "id": track['id'],
                "name": track['name'],
                "artist": ', '.join([artist['name'] for artist in track['artists']]),
                "album": track['album']['name'],
                "popularity": track['popularity'],
                "preview_url": track['preview_url'],
                "external_url": track['external_urls']['spotify'],
                "image_url": track['album']['images'][0]['url'] if track['album']['images'] else None,
                "duration_ms": track['duration_ms']
            })
        
        return {
            "recommendations": recommendations[:limit],
            "total": len(recommendations),
            "method": "artist_based",
            "seed_artist": artist_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recommendations/mood")
async def mood_recommendations(
    mood: str = Query(...),
    limit: int = Query(20, ge=1, le=50)
):
    """Get recommendations based on mood."""
    mood_queries = {
        "happy": ["happy music", "upbeat songs", "feel good hits", "positive vibes"],
        "sad": ["sad songs", "melancholy music", "emotional ballads", "heartbreak songs"],
        "energetic": ["workout music", "high energy", "pump up songs", "dance hits"],
        "chill": ["chill music", "relaxing songs", "ambient music", "lo-fi beats"],
        "romantic": ["love songs", "romantic music", "date night playlist", "intimate songs"],
        "focus": ["study music", "concentration", "instrumental focus", "productivity music"]
    }
    
    if mood not in mood_queries:
        raise HTTPException(status_code=400, detail="Invalid mood")
    
    try:
        all_tracks = []
        
        for query in mood_queries[mood]:
            try:
                results = spotify.search(q=query, type='track', limit=10, market='US')
                for track in results['tracks']['items']:
                    all_tracks.append({
                        "id": track['id'],
                        "name": track['name'],
                        "artist": ', '.join([artist['name'] for artist in track['artists']]),
                        "album": track['album']['name'],
                        "popularity": track['popularity'],
                        "preview_url": track['preview_url'],
                        "external_url": track['external_urls']['spotify'],
                        "image_url": track['album']['images'][0]['url'] if track['album']['images'] else None,
                        "duration_ms": track['duration_ms']
                    })
            except Exception:
                continue
        
        # Remove duplicates and shuffle
        unique_tracks = {}
        for track in all_tracks:
            if track['id'] not in unique_tracks:
                unique_tracks[track['id']] = track
        
        final_tracks = list(unique_tracks.values())
        random.shuffle(final_tracks)
        
        return {
            "recommendations": final_tracks[:limit],
            "total": len(final_tracks),
            "method": "mood_based",
            "mood": mood
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============== PLAYLIST MANAGEMENT ==============

@app.get("/api/playlists")
async def get_playlists(user_id: Optional[int] = Query(None)):
    """Get playlists (all public or user's playlists)."""
    try:
        with engine.connect() as conn:
            if user_id:
                # Get user's playlists
                result = conn.execute(text("""
                    SELECT p.id, p.name, p.description, p.created_at, p.is_public,
                           u.username, COUNT(ps.song_id) as song_count
                    FROM playlists p
                    LEFT JOIN users u ON p.user_id = u.id
                    LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
                    WHERE p.user_id = :user_id
                    GROUP BY p.id, p.name, p.description, p.created_at, p.is_public, u.username
                    ORDER BY p.created_at DESC
                """), {"user_id": user_id})
            else:
                # Get public playlists
                result = conn.execute(text("""
                    SELECT p.id, p.name, p.description, p.created_at, p.is_public,
                           u.username, COUNT(ps.song_id) as song_count
                    FROM playlists p
                    LEFT JOIN users u ON p.user_id = u.id
                    LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
                    WHERE p.is_public = true
                    GROUP BY p.id, p.name, p.description, p.created_at, p.is_public, u.username
                    ORDER BY p.created_at DESC
                """))
            
            playlists = []
            for row in result:
                playlists.append({
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "is_public": row[4],
                    "creator": row[5],
                    "song_count": row[6] or 0
                })
            
            return {"playlists": playlists}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/playlists/create")
async def create_playlist(
    user_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    is_public: bool = Form(True),
    song_ids: str = Form("")  # Comma-separated song IDs
):
    """Create a new playlist."""
    try:
        with engine.connect() as conn:
            # Create playlist
            result = conn.execute(text("""
                INSERT INTO playlists (user_id, name, description, is_public, created_at)
                VALUES (:user_id, :name, :description, :is_public, CURRENT_TIMESTAMP)
                RETURNING id
            """), {
                "user_id": user_id,
                "name": name,
                "description": description,
                "is_public": is_public
            })
            
            playlist_id = result.fetchone()[0]
            
            # Add songs if provided
            if song_ids.strip():
                song_id_list = [sid.strip() for sid in song_ids.split(',') if sid.strip()]
                
                for position, song_id in enumerate(song_id_list):
                    conn.execute(text("""
                        INSERT INTO playlist_songs (playlist_id, song_id, position, added_at)
                        VALUES (:playlist_id, :song_id, :position, CURRENT_TIMESTAMP)
                    """), {
                        "playlist_id": playlist_id,
                        "song_id": song_id,
                        "position": position
                    })
            
            conn.commit()
            
            return {
                "message": "Playlist created successfully",
                "playlist_id": playlist_id,
                "name": name,
                "song_count": len(song_id_list) if song_ids.strip() else 0
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/playlists/{playlist_id}")
async def get_playlist_details(playlist_id: int):
    """Get detailed playlist information."""
    try:
        with engine.connect() as conn:
            # Get playlist info
            playlist_result = conn.execute(text("""
                SELECT p.id, p.name, p.description, p.created_at, p.is_public,
                       u.username
                FROM playlists p
                LEFT JOIN users u ON p.user_id = u.id
                WHERE p.id = :playlist_id
            """), {"playlist_id": playlist_id})
            
            playlist = playlist_result.fetchone()
            if not playlist:
                raise HTTPException(status_code=404, detail="Playlist not found")
            
            # Get songs in playlist
            songs_result = conn.execute(text("""
                SELECT ps.song_id, ps.position, ps.added_at
                FROM playlist_songs ps
                WHERE ps.playlist_id = :playlist_id
                ORDER BY ps.position
            """), {"playlist_id": playlist_id})
            
            song_ids = [row[0] for row in songs_result]
            
            # Get song details from Spotify
            songs = []
            if song_ids:
                try:
                    # Spotify API allows max 50 tracks per request
                    for i in range(0, len(song_ids), 50):
                        batch = song_ids[i:i+50]
                        spotify_tracks = spotify.tracks(batch)
                        
                        for track in spotify_tracks['tracks']:
                            if track:  # Check if track exists
                                songs.append({
                                    "id": track['id'],
                                    "name": track['name'],
                                    "artist": ', '.join([artist['name'] for artist in track['artists']]),
                                    "album": track['album']['name'],
                                    "popularity": track['popularity'],
                                    "preview_url": track['preview_url'],
                                    "external_url": track['external_urls']['spotify'],
                                    "image_url": track['album']['images'][0]['url'] if track['album']['images'] else None,
                                    "duration_ms": track['duration_ms']
                                })
                except Exception as e:
                    print(f"Error fetching Spotify tracks: {e}")
            
            return {
                "playlist": {
                    "id": playlist[0],
                    "name": playlist[1],
                    "description": playlist[2],
                    "created_at": playlist[3].isoformat() if playlist[3] else None,
                    "is_public": playlist[4],
                    "creator": playlist[5],
                    "song_count": len(songs),
                    "total_duration_ms": sum(song.get('duration_ms', 0) for song in songs)
                },
                "songs": songs
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/playlists/{playlist_id}/songs")
async def add_song_to_playlist(
    playlist_id: int,
    song_id: str = Form(...),
    position: Optional[int] = Form(None)
):
    """Add a song to playlist."""
    try:
        with engine.connect() as conn:
            # Get current max position
            if position is None:
                result = conn.execute(text("""
                    SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_songs 
                    WHERE playlist_id = :playlist_id
                """), {"playlist_id": playlist_id})
                position = result.fetchone()[0]
            
            # Add song
            conn.execute(text("""
                INSERT INTO playlist_songs (playlist_id, song_id, position, added_at)
                VALUES (:playlist_id, :song_id, :position, CURRENT_TIMESTAMP)
            """), {
                "playlist_id": playlist_id,
                "song_id": song_id,
                "position": position
            })
            conn.commit()
            
            return {"message": "Song added to playlist", "position": position}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/playlists/{playlist_id}/songs/{song_id}")
async def remove_song_from_playlist(playlist_id: int, song_id: str):
    """Remove a song from playlist."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM playlist_songs 
                WHERE playlist_id = :playlist_id AND song_id = :song_id
            """), {"playlist_id": playlist_id, "song_id": song_id})
            conn.commit()
            
            return {"message": "Song removed from playlist"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============== SEARCH ==============

@app.get("/api/search")
async def search_music(
    query: str = Query(...),
    type: str = Query("track", regex="^(track|artist|album)$"),
    limit: int = Query(20, ge=1, le=50)
):
    """Search for music."""
    try:
        results = spotify.search(q=query, type=type, limit=limit, market='US')
        
        if type == "track":
            items = []
            for track in results['tracks']['items']:
                items.append({
                    "id": track['id'],
                    "name": track['name'],
                    "artist": ', '.join([artist['name'] for artist in track['artists']]),
                    "album": track['album']['name'],
                    "popularity": track['popularity'],
                    "preview_url": track['preview_url'],
                    "external_url": track['external_urls']['spotify'],
                    "image_url": track['album']['images'][0]['url'] if track['album']['images'] else None,
                    "duration_ms": track['duration_ms']
                })
        elif type == "artist":
            items = []
            for artist in results['artists']['items']:
                items.append({
                    "id": artist['id'],
                    "name": artist['name'],
                    "popularity": artist['popularity'],
                    "genres": artist['genres'],
                    "external_url": artist['external_urls']['spotify'],
                    "image_url": artist['images'][0]['url'] if artist['images'] else None,
                    "followers": artist['followers']['total']
                })
        
        return {
            "results": items,
            "total": len(items),
            "query": query,
            "type": type
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
