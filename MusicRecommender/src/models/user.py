from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, List, Optional

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    spotify_id = Column(String, unique=True, index=True, nullable=True)
    lastfm_username = Column(String, unique=True, nullable=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    
    # Authentication
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_login = Column(DateTime)
    
    # Profile information
    profile_image_url = Column(String)
    country = Column(String)
    date_of_birth = Column(DateTime)
    
    # Musical preferences (computed from listening history)
    taste_vector = Column(JSON)  # User's musical taste embedding vector
    preferred_genres = Column(JSON)  # List of preferred genres with weights
    top_artists = Column(JSON)  # Top artists with play counts
    
    # Audio feature preferences (0-1 scale)
    avg_energy = Column(Float, default=0.5)
    avg_valence = Column(Float, default=0.5)  # Positivity
    avg_danceability = Column(Float, default=0.5)
    avg_acousticness = Column(Float, default=0.5)
    avg_instrumentalness = Column(Float, default=0.5)
    avg_tempo = Column(Float, default=120.0)
    
    # Listening behavior patterns
    total_listening_time_ms = Column(Integer, default=0)
    total_tracks_played = Column(Integer, default=0)
    skip_rate = Column(Float, default=0.0)  # Percentage of skipped tracks
    
    # Playlist preferences
    preferred_playlist_length = Column(Integer, default=25)
    diversity_preference = Column(Float, default=0.5)  # How much variety user likes
    discovery_preference = Column(Float, default=0.5)  # How much new music user likes
    
    # Privacy settings
    public_playlists = Column(Boolean, default=True)
    share_listening_data = Column(Boolean, default=True)
    
    # Relationships
    playlists = relationship("Playlist", back_populates="user", cascade="all, delete-orphan")
    listening_history = relationship("ListeningHistory", back_populates="user", cascade="all, delete-orphan")
    user_songs = relationship("UserSong", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
    
    def to_dict(self) -> Dict:
        """Convert user to dictionary representation."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "spotify_id": self.spotify_id,
            "lastfm_username": self.lastfm_username,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "profile_image_url": self.profile_image_url,
            "country": self.country,
            "preferred_genres": self.preferred_genres,
            "avg_energy": self.avg_energy,
            "avg_valence": self.avg_valence,
            "avg_danceability": self.avg_danceability,
            "total_tracks_played": self.total_tracks_played,
            "preferred_playlist_length": self.preferred_playlist_length,
            "diversity_preference": self.diversity_preference,
            "discovery_preference": self.discovery_preference
        }

class ListeningHistory(Base):
    __tablename__ = "listening_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, Column("users.id"))
    song_id = Column(Integer, Column("songs.id"))
    
    # Listening details
    played_at = Column(DateTime, default=func.now())
    duration_played_ms = Column(Integer)  # How long the user listened
    was_skipped = Column(Boolean, default=False)
    completion_percentage = Column(Float)  # Percentage of song completed
    
    # Context
    device_type = Column(String)  # mobile, desktop, speaker, etc.
    playlist_context = Column(String)  # playlist name if played from playlist
    listening_context = Column(String)  # workout, commute, focus, etc.
    
    # Implicit feedback
    rating = Column(Float)  # Implicit rating based on listening behavior
    
    # Relationships
    user = relationship("User", back_populates="listening_history")
    song = relationship("Song")
    
    def __repr__(self):
        return f"<ListeningHistory(user_id={self.user_id}, song_id={self.song_id}, played_at={self.played_at})>"

class UserSong(Base):
    """User-song interactions and preferences."""
    __tablename__ = "user_songs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, Column("users.id"))
    song_id = Column(Integer, Column("songs.id"))
    
    # Explicit ratings and interactions
    explicit_rating = Column(Float)  # 1-5 stars if user explicitly rated
    is_liked = Column(Boolean)  # Heart/like status
    is_disliked = Column(Boolean)
    is_saved = Column(Boolean)  # Saved to library
    
    # Computed scores
    implicit_score = Column(Float)  # Computed from listening behavior
    play_count = Column(Integer, default=0)
    skip_count = Column(Integer, default=0)
    
    # Timestamps
    first_played = Column(DateTime)
    last_played = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="user_songs")
    song = relationship("Song")
    
    def __repr__(self):
        return f"<UserSong(user_id={self.user_id}, song_id={self.song_id}, implicit_score={self.implicit_score})>"
