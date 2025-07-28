from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Float, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, List, Optional

Base = declarative_base()

class Playlist(Base):
    __tablename__ = "playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Basic info
    name = Column(String, index=True, nullable=False)
    description = Column(Text)
    is_public = Column(Boolean, default=True)
    is_collaborative = Column(Boolean, default=False)
    
    # External IDs
    spotify_id = Column(String, unique=True, nullable=True)
    external_url = Column(String)
    
    # Generation parameters
    generation_type = Column(String)  # manual, ai_generated, hybrid
    source_playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=True)  # If based on another playlist
    
    # Target characteristics for AI generation
    target_mood = Column(String)  # energetic, chill, melancholic, happy, focus, etc.
    target_energy_range = Column(JSON)  # [min, max] energy values
    target_valence_range = Column(JSON)  # [min, max] valence values
    target_tempo_range = Column(JSON)  # [min, max] BPM
    target_duration_ms = Column(Integer)  # Desired total duration
    
    # Genre and style preferences
    genre_mix = Column(JSON)  # {"rock": 0.4, "pop": 0.3, "jazz": 0.3}
    artist_diversity = Column(Float, default=0.5)  # How much artist diversity to include
    decade_mix = Column(JSON)  # {"2010s": 0.5, "2000s": 0.3, "1990s": 0.2}
    
    # Optimization constraints
    flow_pattern = Column(String, default="smooth")  # smooth, increasing, decreasing, wave
    max_repeating_artists = Column(Integer, default=2)  # Max songs from same artist
    include_explicit = Column(Boolean, default=True)
    language_preference = Column(JSON)  # List of preferred languages
    
    # Quality metrics (computed after generation)
    diversity_score = Column(Float)  # How diverse the playlist is
    flow_score = Column(Float)  # How well songs transition
    freshness_score = Column(Float)  # How many new discoveries
    coherence_score = Column(Float)  # How well playlist matches target
    user_satisfaction_score = Column(Float)  # Based on user feedback
    
    # Usage statistics
    play_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    total_listening_time_ms = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_played = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="playlists")
    songs = relationship("PlaylistSong", back_populates="playlist", cascade="all, delete-orphan", order_by="PlaylistSong.position")
    source_playlist = relationship("Playlist", remote_side=[id])
    
    def __repr__(self):
        return f"<Playlist(id={self.id}, name='{self.name}', user_id={self.user_id})>"
    
    def to_dict(self) -> Dict:
        """Convert playlist to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_public": self.is_public,
            "is_collaborative": self.is_collaborative,
            "spotify_id": self.spotify_id,
            "generation_type": self.generation_type,
            "target_mood": self.target_mood,
            "target_energy_range": self.target_energy_range,
            "target_duration_ms": self.target_duration_ms,
            "genre_mix": self.genre_mix,
            "flow_pattern": self.flow_pattern,
            "diversity_score": self.diversity_score,
            "flow_score": self.flow_score,
            "freshness_score": self.freshness_score,
            "coherence_score": self.coherence_score,
            "play_count": self.play_count,
            "like_count": self.like_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "song_count": len(self.songs) if self.songs else 0
        }
    
    def get_total_duration_ms(self) -> int:
        """Calculate total duration of playlist."""
        if not self.songs:
            return 0
        return sum(song.song.duration_ms or 0 for song in self.songs)
    
    def get_genre_distribution(self) -> Dict[str, float]:
        """Calculate actual genre distribution in playlist."""
        if not self.songs:
            return {}
        
        genre_counts = {}
        total_songs = len(self.songs)
        
        for playlist_song in self.songs:
            song_genres = playlist_song.song.genres or []
            for genre in song_genres:
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
        
        return {genre: count / total_songs for genre, count in genre_counts.items()}

class PlaylistSong(Base):
    __tablename__ = "playlist_songs"
    
    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=False)
    
    # Position and metadata
    position = Column(Integer, nullable=False)  # Order in playlist (0-indexed)
    added_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Who added this song
    
    # Generation context
    reason_added = Column(String)  # recommendation_engine, user_manual, similar_to_liked, etc.
    confidence_score = Column(Float)  # How confident the algorithm was about this choice
    
    # Transition analysis
    transition_score_from_previous = Column(Float)  # How well it transitions from previous song
    transition_score_to_next = Column(Float)  # How well it transitions to next song
    
    # User feedback on this specific song in playlist
    user_rating = Column(Float)  # User's rating of this song in this playlist context
    was_skipped = Column(Boolean, default=False)
    skip_percentage = Column(Float)  # At what percentage of the song user skipped
    
    # Timestamps
    added_at = Column(DateTime, default=func.now())
    last_played = Column(DateTime)
    
    # Relationships
    playlist = relationship("Playlist", back_populates="songs")
    song = relationship("Song")
    added_by = relationship("User")
    
    def __repr__(self):
        return f"<PlaylistSong(playlist_id={self.playlist_id}, song_id={self.song_id}, position={self.position})>"
    
    def to_dict(self) -> Dict:
        """Convert playlist song to dictionary representation."""
        return {
            "id": self.id,
            "position": self.position,
            "song": self.song.to_dict() if self.song else None,
            "reason_added": self.reason_added,
            "confidence_score": self.confidence_score,
            "transition_score_from_previous": self.transition_score_from_previous,
            "user_rating": self.user_rating,
            "was_skipped": self.was_skipped,
            "added_at": self.added_at.isoformat() if self.added_at else None
        }

class PlaylistTemplate(Base):
    """Pre-defined playlist templates for quick generation."""
    __tablename__ = "playlist_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Template info
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String)  # workout, study, party, chill, etc.
    icon = Column(String)  # Icon identifier
    
    # Template parameters
    target_mood = Column(String)
    target_energy_range = Column(JSON)
    target_valence_range = Column(JSON)
    target_tempo_range = Column(JSON)
    recommended_duration_ms = Column(Integer)
    
    # Default constraints
    genre_mix = Column(JSON)
    flow_pattern = Column(String, default="smooth")
    artist_diversity = Column(Float, default=0.7)
    include_explicit = Column(Boolean, default=True)
    
    # Usage stats
    usage_count = Column(Integer, default=0)
    avg_user_rating = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<PlaylistTemplate(id={self.id}, name='{self.name}', category='{self.category}')>"
    
    def to_dict(self) -> Dict:
        """Convert template to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "icon": self.icon,
            "target_mood": self.target_mood,
            "target_energy_range": self.target_energy_range,
            "recommended_duration_ms": self.recommended_duration_ms,
            "genre_mix": self.genre_mix,
            "flow_pattern": self.flow_pattern,
            "usage_count": self.usage_count,
            "avg_user_rating": self.avg_user_rating
        }
