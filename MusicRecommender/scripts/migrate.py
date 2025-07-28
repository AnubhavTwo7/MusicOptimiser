#!/usr/bin/env python3
"""Database migration script."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import logging

from src.core.config import config
from src.core.database import Base, engine
from src.models import user, song, playlist, recommendation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database_if_not_exists():
    """Create database if it doesn't exist."""
    
    # Create engine without database name to connect to PostgreSQL server
    server_url = f"postgresql://{config.database.user}:{config.database.password}@{config.database.host}:{config.database.port}/postgres"
    server_engine = create_engine(server_url)
    
    try:
        with server_engine.connect() as conn:
            conn.execute(text("COMMIT"))  # End any existing transaction
            
            # Check if database exists
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{config.database.name}'"))
            
            if not result.fetchone():
                logger.info(f"Creating database '{config.database.name}'...")
                conn.execute(text(f"CREATE DATABASE {config.database.name}"))
                logger.info("Database created successfully")
            else:
                logger.info(f"Database '{config.database.name}' already exists")
                
    except SQLAlchemyError as e:
        logger.error(f"Error creating database: {str(e)}")
        raise
    finally:
        server_engine.dispose()

def run_migrations():
    """Run database migrations."""
    
    try:
        # Create database if needed
        create_database_if_not_exists()
        
        # Create all tables
        logger.info("Creating tables...")
        Base.metadata.create_all(bind=engine)
        
        # Create indexes for better performance
        with engine.connect() as conn:
            
            # User indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_spotify_id ON users(spotify_id);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
            """))
            
            # Song indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_songs_spotify_id ON songs(spotify_id);
                CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title);
                CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist);
                CREATE INDEX IF NOT EXISTS idx_songs_genres ON songs USING GIN(genres);
                CREATE INDEX IF NOT EXISTS idx_songs_energy ON songs(energy);
                CREATE INDEX IF NOT EXISTS idx_songs_valence ON songs(valence);
                CREATE INDEX IF NOT EXISTS idx_songs_popularity ON songs(popularity);
            """))
            
            # Listening history indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_listening_history_user_id ON listening_history(user_id);
                CREATE INDEX IF NOT EXISTS idx_listening_history_song_id ON listening_history(song_id);
                CREATE INDEX IF NOT EXISTS idx_listening_history_played_at ON listening_history(played_at);
                CREATE INDEX IF NOT EXISTS idx_listening_history_user_song ON listening_history(user_id, song_id);
            """))
            
            # Playlist indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_playlists_user_id ON playlists(user_id);
                CREATE INDEX IF NOT EXISTS idx_playlists_created_at ON playlists(created_at);
                CREATE INDEX IF NOT EXISTS idx_playlists_is_public ON playlists(is_public);
            """))
            
            # Playlist songs indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_playlist_songs_playlist_id ON playlist_songs(playlist_id);
                CREATE INDEX IF NOT EXISTS idx_playlist_songs_song_id ON playlist_songs(song_id);
                CREATE INDEX IF NOT EXISTS idx_playlist_songs_position ON playlist_songs(playlist_id, position);
            """))
            
            # Recommendation indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_recommendations_session_id ON recommendations(session_id);
                CREATE INDEX IF NOT EXISTS idx_recommendations_song_id ON recommendations(song_id);
                CREATE INDEX IF NOT EXISTS idx_recommendations_score ON recommendations(score);
            """))
            
            conn.commit()
            
        logger.info("All tables and indexes created successfully")
        
    except SQLAlchemyError as e:
        logger.error(f"Migration failed: {str(e)}")
        raise

def create_triggers():
    """Create database triggers for automatic updates."""
    
    try:
        with engine.connect() as conn:
            
            # Trigger to update user's updated_at timestamp
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """))
            
            conn.execute(text("""
                CREATE TRIGGER update_users_updated_at
                    BEFORE UPDATE ON users
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
            """))
            
            conn.execute(text("""
                CREATE TRIGGER update_songs_updated_at
                    BEFORE UPDATE ON songs
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
            """))
            
            conn.execute(text("""
                CREATE TRIGGER update_playlists_updated_at
                    BEFORE UPDATE ON playlists
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
            """))
            
            conn.commit()
            
        logger.info("Database triggers created successfully")
        
    except SQLAlchemyError as e:
        logger.error(f"Error creating triggers: {str(e)}")
        # Don't raise here as triggers are optional

if __name__ == "__main__":
    logger.info("Starting database migration...")
    
    try:
        run_migrations()
        create_triggers()
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        sys.exit(1)
