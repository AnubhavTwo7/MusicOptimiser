#!/usr/bin/env python3
"""Simplified database migration script."""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, DateTime, Boolean, Float, JSON
from sqlalchemy.exc import SQLAlchemyError
import logging

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "music_playlist")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password123")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
SERVER_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database_if_not_exists():
    """Create database if it doesn't exist."""
    try:
        # Connect to PostgreSQL server
        server_engine = create_engine(SERVER_URL)
        
        with server_engine.connect() as conn:
            conn.execute(text("COMMIT"))
            
            # Check if database exists
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'"))
            
            if not result.fetchone():
                logger.info(f"Creating database '{DB_NAME}'...")
                conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
                logger.info("Database created successfully")
            else:
                logger.info(f"Database '{DB_NAME}' already exists")
                
        server_engine.dispose()
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"Error creating database: {str(e)}")
        return False

def create_tables():
    """Create basic tables."""
    try:
        engine = create_engine(DATABASE_URL)
        metadata = MetaData()
        
        # Users table
        users_table = Table('users', metadata,
            Column('id', Integer, primary_key=True),
            Column('spotify_id', String, unique=True),
            Column('email', String, unique=True),
            Column('username', String, unique=True),
            Column('created_at', DateTime),
            Column('is_active', Boolean, default=True)
        )
        
        # Songs table
        songs_table = Table('songs', metadata,
            Column('id', Integer, primary_key=True),
            Column('spotify_id', String, unique=True),
            Column('title', String),
            Column('artist', String),
            Column('album', String),
            Column('duration_ms', Integer),
            Column('popularity', Integer),
            Column('energy', Float),
            Column('valence', Float),
            Column('danceability', Float),
            Column('created_at', DateTime)
        )
        
        # Playlists table
        playlists_table = Table('playlists', metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', Integer),
            Column('name', String),
            Column('description', String),
            Column('created_at', DateTime),
            Column('is_public', Boolean, default=True)
        )
        
        # Create all tables
        metadata.create_all(engine)
        logger.info("Tables created successfully")
        
        # Create indexes
        with engine.connect() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_spotify_id ON users(spotify_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_songs_spotify_id ON songs(spotify_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_playlists_user_id ON playlists(user_id)"))
            conn.commit()
            
        logger.info("Indexes created successfully")
        engine.dispose()
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"Error creating tables: {str(e)}")
        return False

def test_connection():
    """Test database connection."""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"Database connection successful! PostgreSQL version: {version}")
        engine.dispose()
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting database migration...")
    
    print("🔍 Checking database connection...")
    if not test_connection():
        if create_database_if_not_exists():
            logger.info("✅ Database created, testing connection again...")
            if not test_connection():
                print("❌ Migration failed - can't connect to database")
                print("Make sure PostgreSQL is running: docker compose up -d postgres")
                sys.exit(1)
        else:
            print("❌ Migration failed - can't create database")
            sys.exit(1)
    
    print("✅ Database connection successful!")
    
    print("🏗️  Creating tables...")
    if create_tables():
        print("✅ Tables created successfully!")
    else:
        print("❌ Failed to create tables")
        sys.exit(1)
    
    print("🎉 Database migration completed successfully!")
    print("You can now start your application!")
