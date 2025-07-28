from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, List, Optional

Base = declarative_base()

class Song(Base):
    __tablename__ = "songs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # External IDs
    spotify_id = Column(String, unique=True, index=True, nullable=True)
    lastfm_id = Column(String, unique=True, nullable=True)
    musicbrainz_id = Column(String, unique=True, nullable=True)
    
    # Basic metadata
    title = Column(String, index=True, nullable=False)
    artist = Column(String, index=True, nullable=False)
    album = Column(String, index=True)
    album_artist = Column(String)
    track_number = Column(Integer)
    disc_number = Column(Integer, default=1)
    
    # Duration and technical info
    duration_ms = Column(Integer)
    file_format = Column(String)  # mp3, flac, etc.
    bitrate = Column(Integer)
    sample_rate = Column(Integer)
    
    # Popularity and metadata
    popularity = Column(Integer, default=0)  # 0-100 popularity score
    explicit = Column(Boolean, default=False)
    preview_url = Column(String)
    external_urls = Column(JSON)  # URLs to external services
    
    # Release information
    release_date = Column(DateTime)
    release_date_precision = Column(String)  # year, month, day
    label = Column(String)
    copyright_text = Column(Text)
    
    # Audio features (from Spotify API)
    acousticness = Column(Float)      # 0.0 to 1.0
    danceability = Column(Float)      # 0.0 to 1.0
    energy = Column(Float)            # 0.0 to 1.0
    instrumentalness = Column(Float)  # 0.0 to 1.0
    liveness = Column(Float)          # 0.0 to 1.0
    loudness = Column(Float)          # -60 to 0 dB
    speechiness = Column(Float)       # 0.0 to 1.0
    tempo = Column(Float)             # BPM
    valence = Column(Float)           # 0.0 to 1.0 (musical positivity)
    
    # Musical analysis
    key = Column(Integer)             # 0-11 (C, C#, D, etc.)
    mode = Column(Integer)            # 0 (minor) or 1 (major)
    time_signature = Column(Integer)  # 3, 4, 5, 6, 7
    
    # Genres and tags
    genres = Column(JSON)             # List of genre strings
    tags = Column(JSON)               # User-generated or computed tags
    mood_tags = Column(JSON)          # Mood classifications
    
    # Lyrics and content analysis
    has_lyrics = Column(Boolean, default=False)
    language = Column(String)         # ISO language code
    lyric_themes = Column(JSON)       # NLP-extracted themes
    lyric_sentiment = Column(Float)   # -1 to 1 sentiment score
    lyric_complexity = Column(Float)  # Readability/complexity score
    
    # Computed features for ML
    content_vector = Column(JSON)     # Content-based embedding vector
    acoustic_vector = Column(JSON)    # Audio feature vector (normalized)
    
    # Aggregated user data
    play_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    skip_count = Column(Integer, default=0)
    save_count = Column(Integer, default=0)
    avg_user_rating = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_played = Column(DateTime)
    
    def __repr__(self):
        return f"<Song(id={self.id}, title='{self.title}', artist='{self.artist}')>"
    
    def to_dict(self) -> Dict:
        """Convert song to dictionary representation."""
        return {
            "id": self.id,
            "spotify_id": self.spotify_id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration_ms": self.duration_ms,
            "popularity": self.popularity,
            "explicit": self.explicit,
            "preview_url": self.preview_url,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "genres": self.genres,
            "audio_features": {
                "acousticness": self.acousticness,
                "danceability": self.danceability,
                "energy": self.energy,
                "instrumentalness": self.instrumentalness,
                "liveness": self.liveness,
                "loudness": self.loudness,
                "speechiness": self.speechiness,
                "tempo": self.tempo,
                "valence": self.valence,
                "key": self.key,
                "mode": self.mode,
                "time_signature": self.time_signature
            },
            "play_count": self.play_count,
            "like_count": self.like_count,
            "avg_user_rating": self.avg_user_rating,
            "mood_tags": self.mood_tags,
            "lyric_themes": self.lyric_themes
        }
    
    def get_audio_features_vector(self) -> List[float]:
        """Get normalized audio features as a vector."""
        features = [
            self.acousticness or 0.0,
            self.danceability or 0.0,
            self.energy or 0.0,
            self.instrumentalness or 0.0,
            self.liveness or 0.0,
            (self.loudness + 60) / 60 if self.loudness else 0.0,  # Normalize loudness
            self.speechiness or 0.0,
            (self.tempo / 200) if self.tempo else 0.0,  # Normalize tempo
            self.valence or 0.0
        ]
        return features
    
    def calculate_similarity_score(self, other_song: 'Song') -> float:
        """Calculate similarity score with another song."""
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        
        self_features = np.array(self.get_audio_features_vector()).reshape(1, -1)
        other_features = np.array(other_song.get_audio_features_vector()).reshape(1, -1)
        
        similarity = cosine_similarity(self_features, other_features)[0][0]
        return float(similarity)

class Artist(Base):
    __tablename__ = "artists"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # External IDs
    spotify_id = Column(String, unique=True, index=True, nullable=True)
    lastfm_id = Column(String, unique=True, nullable=True)
    musicbrainz_id = Column(String, unique=True, nullable=True)
    
    # Basic info
    name = Column(String, index=True, nullable=False)
    popularity = Column(Integer, default=0)
    follower_count = Column(Integer, default=0)
    
    # Profile
    image_url = Column(String)
    biography = Column(Text)
    country = Column(String)
    formed_year = Column(Integer)
    
    # Classification
    genres = Column(JSON)
    tags = Column(JSON)
    similar_artists = Column(JSON)  # List of similar artist IDs
    
    # Computed features
    artist_vector = Column(JSON)  # Artist embedding vector
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Artist(id={self.id}, name='{self.name}')>"

class Album(Base):
    __tablename__ = "albums"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # External IDs
    spotify_id = Column(String, unique=True, index=True, nullable=True)
    lastfm_id = Column(String, unique=True, nullable=True)
    musicbrainz_id = Column(String, unique=True, nullable=True)
    
    # Basic info
    name = Column(String, index=True, nullable=False)
    artist = Column(String, index=True, nullable=False)
    album_type = Column(String)  # album, single, compilation
    total_tracks = Column(Integer)
    
    # Release info
    release_date = Column(DateTime)
    release_date_precision = Column(String)
    label = Column(String)
    copyright_text = Column(Text)
    
    # Metadata
    genres = Column(JSON)
    popularity = Column(Integer, default=0)
    image_url = Column(String)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Album(id={self.id}, name='{self.name}', artist='{self.artist}')>"
