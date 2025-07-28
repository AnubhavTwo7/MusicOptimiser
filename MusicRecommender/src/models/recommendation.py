from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, List, Optional

Base = declarative_base()

class RecommendationSession(Base):
    """Tracks recommendation sessions for analytics and improvement."""
    __tablename__ = "recommendation_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Session parameters
    session_type = Column(String)  # playlist_generation, daily_discover, similar_songs
    request_parameters = Column(JSON)  # Original request parameters
    
    # Algorithm details
    algorithms_used = Column(JSON)  # List of algorithms and their weights
    model_versions = Column(JSON)  # Version info for reproducibility
    
    # Results
    total_candidates = Column(Integer)  # Total songs considered
    total_recommendations = Column(Integer)  # Final recommendations returned
    processing_time_ms = Column(Integer)  # Time taken to generate
    
    # Quality metrics
    diversity_score = Column(Float)
    novelty_score = Column(Float)
    coverage_score = Column(Float)  # How well it covers user's taste
    
    # User feedback
    user_satisfaction = Column(Float)  # 1-5 rating if provided
    feedback_notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)
    
    # Relationships
    user = relationship("User")
    recommendations = relationship("Recommendation", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<RecommendationSession(id={self.id}, user_id={self.user_id}, type='{self.session_type}')>"

class Recommendation(Base):
    """Individual song recommendations within a session."""
    __tablename__ = "recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("recommendation_sessions.id"), nullable=False)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=False)
    
    # Recommendation details
    rank = Column(Integer)  # Position in recommendation list
    score = Column(Float)  # Overall recommendation score
    confidence = Column(Float)  # Confidence in this recommendation
    
    # Algorithm breakdown
    collaborative_score = Column(Float)
    content_score = Column(Float)
    popularity_score = Column(Float)
    freshness_score = Column(Float)
    context_score = Column(Float)  # How well it fits the context
    
    # Reasoning
    primary_reason = Column(String)  # Main reason for recommendation
    secondary_reasons = Column(JSON)  # Additional reasons
    similar_users = Column(JSON)  # IDs of users with similar taste who liked this
    similar_songs = Column(JSON)  # IDs of similar songs user has liked
    
    # User interaction
    was_accepted = Column(Boolean)  # Did user add to playlist/like
    was_rejected = Column(Boolean)  # Did user explicitly reject
    was_played = Column(Boolean)  # Did user play the song
    play_duration_ms = Column(Integer)  # How long user listened
    user_rating = Column(Float)  # Explicit rating if provided
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    interacted_at = Column(DateTime)
    
    # Relationships
    session = relationship("RecommendationSession", back_populates="recommendations")
    song = relationship("Song")
    
    def __repr__(self):
        return f"<Recommendation(id={self.id}, song_id={self.song_id}, score={self.score})>"
    
    def to_dict(self) -> Dict:
        """Convert recommendation to dictionary representation."""
        return {
            "id": self.id,
            "song": self.song.to_dict() if self.song else None,
            "rank": self.rank,
            "score": self.score,
            "confidence": self.confidence,
            "scores": {
                "collaborative": self.collaborative_score,
                "content": self.content_score,
                "popularity": self.popularity_score,
                "freshness": self.freshness_score,
                "context": self.context_score
            },
            "reasoning": {
                "primary_reason": self.primary_reason,
                "secondary_reasons": self.secondary_reasons,
                "similar_users": self.similar_users,
                "similar_songs": self.similar_songs
            },
            "user_interaction": {
                "was_accepted": self.was_accepted,
                "was_rejected": self.was_rejected,
                "was_played": self.was_played,
                "user_rating": self.user_rating
            }
        }

class UserSimilarity(Base):
    """Precomputed user similarity scores for collaborative filtering."""
    __tablename__ = "user_similarities"
    
    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Similarity scores
    overall_similarity = Column(Float)  # Overall similarity score
    taste_similarity = Column(Float)  # Based on liked songs
    audio_feature_similarity = Column(Float)  # Based on audio preferences
    genre_similarity = Column(Float)  # Based on genre preferences
    
    # Supporting data
    common_songs = Column(Integer)  # Number of songs both users liked
    common_artists = Column(Integer)  # Number of common artists
    common_genres = Column(Integer)  # Number of common genres
    
    # Computation details
    algorithm_used = Column(String)  # cosine, pearson, jaccard, etc.
    computed_at = Column(DateTime, default=func.now())
    
    # Relationships
    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    
    def __repr__(self):
        return f"<UserSimilarity(user1_id={self.user1_id}, user2_id={self.user2_id}, similarity={self.overall_similarity})>"

class SongSimilarity(Base):
    """Precomputed song similarity scores for content-based filtering."""
    __tablename__ = "song_similarities"
    
    id = Column(Integer, primary_key=True, index=True)
    song1_id = Column(Integer, ForeignKey("songs.id"), nullable=False)
    song2_id = Column(Integer, ForeignKey("songs.id"), nullable=False)
    
    # Similarity scores
    overall_similarity = Column(Float)  # Overall similarity score
    audio_similarity = Column(Float)  # Based on audio features
    genre_similarity = Column(Float)  # Based on genres
    lyric_similarity = Column(Float)  # Based on lyrical content
    
    # Feature similarities
    tempo_similarity = Column(Float)
    energy_similarity = Column(Float)
    valence_similarity = Column(Float)
    key_similarity = Column(Float)
    
    # Computation details
    algorithm_used = Column(String)
    computed_at = Column(DateTime, default=func.now())
    
    # Relationships
    song1 = relationship("Song", foreign_keys=[song1_id])
    song2 = relationship("Song", foreign_keys=[song2_id])
    
    def __repr__(self):
        return f"<SongSimilarity(song1_id={self.song1_id}, song2_id={self.song2_id}, similarity={self.overall_similarity})>"

class ModelPerformance(Base):
    """Track model performance metrics over time."""
    __tablename__ = "model_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Model info
    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    algorithm_type = Column(String)  # collaborative, content, hybrid, etc.
    
    # Performance metrics
    precision_at_5 = Column(Float)
    precision_at_10 = Column(Float)
    recall_at_5 = Column(Float)
    recall_at_10 = Column(Float)
    ndcg_at_5 = Column(Float)
    ndcg_at_10 = Column(Float)
    
    # User engagement metrics
    click_through_rate = Column(Float)
    conversion_rate = Column(Float)  # Songs added to playlists
    avg_listening_time = Column(Float)
    user_satisfaction = Column(Float)
    
    # Data info
    training_samples = Column(Integer)
    test_samples = Column(Integer)
    evaluation_period_start = Column(DateTime)
    evaluation_period_end = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<ModelPerformance(model='{self.model_name}', version='{self.model_version}', precision@10={self.precision_at_10})>"
