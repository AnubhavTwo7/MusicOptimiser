from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from ...core.database import get_db
from ...models.playlist import Playlist, PlaylistSong
from ...models.user import User
from ...services.recommendation_engine import RecommendationEngine, RecommendationRequest
from ...services.playlist_optimizer import PlaylistOptimizer, OptimizationConstraints
from ...utils.validators import validate_playlist_request

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for request/response
from pydantic import BaseModel

class PlaylistCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    target_mood: Optional[str] = None
    target_energy_range: Optional[List[float]] = None
    target_duration_ms: Optional[int] = None
    genre_mix: Optional[dict] = None
    flow_pattern: str = "smooth"
    is_public: bool = True

class PlaylistResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    song_count: int
    total_duration_ms: int
    diversity_score: Optional[float]
    flow_score: Optional[float]
    created_at: datetime
    
    class Config:
        from_attributes = True

class SongInPlaylist(BaseModel):
    position: int
    song_id: int
    title: str
    artist: str
    duration_ms: Optional[int]
    reason_added: Optional[str]

@router.post("/generate", response_model=PlaylistResponse)
async def generate_playlist(
    request: PlaylistCreateRequest,
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate an AI-optimized playlist."""
    
    try:
        # Validate user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Validate request
        validation_result = validate_playlist_request(request.dict())
        if not validation_result['valid']:
            raise HTTPException(status_code=400, detail=validation_result['errors'])
        
        # Initialize services
        recommendation_engine = RecommendationEngine(db)
        playlist_optimizer = PlaylistOptimizer()
        
        # Create recommendation request
        rec_request = RecommendationRequest(
            user_id=user_id,
            target_mood=request.target_mood,
            target_genres=list(request.genre_mix.keys()) if request.genre_mix else None,
            num_recommendations=100  # Get more candidates for optimization
        )
        
        # Get recommendations
        candidate_songs = await recommendation_engine.get_recommendations(rec_request)
        
        if not candidate_songs:
            raise HTTPException(status_code=404, detail="No suitable songs found")
        
        # Set up optimization constraints
        constraints = OptimizationConstraints(
            max_length=50,
            target_duration_ms=request.target_duration_ms,
            energy_flow=request.flow_pattern,
            genre_distribution=request.genre_mix
        )
        
        # Optimize playlist
        song_objects = [rec['song'] for rec in candidate_songs]
        optimized_songs = playlist_optimizer.optimize_playlist(song_objects, constraints)
        
        # Create playlist in database
        playlist = Playlist(
            user_id=user_id,
            name=request.name,
            description=request.description,
            generation_type="ai_generated",
            target_mood=request.target_mood,
            target_energy_range=request.target_energy_range,
            target_duration_ms=request.target_duration_ms,
            genre_mix=request.genre_mix,
            flow_pattern=request.flow_pattern,
            is_public=request.is_public
        )
        
        db.add(playlist)
        db.flush()  # Get playlist ID
        
        # Add songs to playlist
        for position, song in enumerate(optimized_songs):
            playlist_song = PlaylistSong(
                playlist_id=playlist.id,
                song_id=song.id,
                position=position,
                reason_added="ai_optimization",
                confidence_score=0.8  # Default confidence
            )
            db.add(playlist_song)
        
        # Calculate quality scores in background
        background_tasks.add_task(calculate_playlist_scores, playlist.id)
        
        db.commit()
        
        # Prepare response
        total_duration = sum(song.duration_ms or 0 for song in optimized_songs)
        
        return PlaylistResponse(
            id=playlist.id,
            name=playlist.name,
            description=playlist.description,
            song_count=len(optimized_songs),
            total_duration_ms=total_duration,
            diversity_score=None,  # Will be calculated in background
            flow_score=None,       # Will be calculated in background
            created_at=playlist.created_at
        )
        
    except Exception as e:
        logger.error(f"Error generating playlist: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Get playlist details."""
    
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    return PlaylistResponse(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        song_count=len(playlist.songs),
        total_duration_ms=playlist.get_total_duration_ms(),
        diversity_score=playlist.diversity_score,
        flow_score=playlist.flow_score,
        created_at=playlist.created_at
    )

@router.get("/{playlist_id}/songs", response_model=List[SongInPlaylist])
async def get_playlist_songs(playlist_id: int, db: Session = Depends(get_db)):
    """Get songs in a playlist."""
    
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    songs = []
    for playlist_song in playlist.songs:
        songs.append(SongInPlaylist(
            position=playlist_song.position,
            song_id=playlist_song.song.id,
            title=playlist_song.song.title,
            artist=playlist_song.song.artist,
            duration_ms=playlist_song.song.duration_ms,
            reason_added=playlist_song.reason_added
        ))
    
    return songs

@router.delete("/{playlist_id}")
async def delete_playlist(playlist_id: int, user_id: int, db: Session = Depends(get_db)):
    """Delete a playlist."""
    
    playlist = db.query(Playlist).filter(
        Playlist.id == playlist_id,
        Playlist.user_id == user_id
    ).first()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    db.delete(playlist)
    db.commit()
    
    return {"message": "Playlist deleted successfully"}

@router.post("/{playlist_id}/optimize")
async def optimize_existing_playlist(
    playlist_id: int,
    constraints: dict,
    db: Session = Depends(get_db)
):
    """Re-optimize an existing playlist."""
    
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    try:
        # Get current songs
        current_songs = [ps.song for ps in playlist.songs]
        
        # Set up optimization constraints
        opt_constraints = OptimizationConstraints(
            max_length=constraints.get('max_length', 50),
            target_duration_ms=constraints.get('target_duration_ms'),
            energy_flow=constraints.get('flow_pattern', 'smooth'),
            diversity_weight=constraints.get('diversity_weight', 0.3)
        )
        
        # Optimize
        playlist_optimizer = PlaylistOptimizer()
        optimized_songs = playlist_optimizer.optimize_playlist(current_songs, opt_constraints)
        
        # Update playlist order
        for playlist_song in playlist.songs:
            db.delete(playlist_song)
        
        for position, song in enumerate(optimized_songs):
            new_playlist_song = PlaylistSong(
                playlist_id=playlist.id,
                song_id=song.id,
                position=position,
                reason_added="reoptimization"
            )
            db.add(new_playlist_song)
        
        db.commit()
        
        return {"message": "Playlist optimized successfully", "new_song_count": len(optimized_songs)}
        
    except Exception as e:
        logger.error(f"Error optimizing playlist: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Optimization failed")

async def calculate_playlist_scores(playlist_id: int):
    """Background task to calculate playlist quality scores."""
    
    from ...core.database import get_db_context
    
    try:
        with get_db_context() as db:
            playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return
            
            playlist_optimizer = PlaylistOptimizer()
            songs = [ps.song for ps in playlist.songs]
            
            if songs:
                # Calculate scores
                diversity_score = playlist_optimizer._calculate_diversity_score(songs)
                flow_score = playlist_optimizer._calculate_flow_score(songs, playlist.flow_pattern or "smooth")
                freshness_score = playlist_optimizer._calculate_freshness_score(songs)
                
                # Update playlist
                playlist.diversity_score = diversity_score
                playlist.flow_score = flow_score
                playlist.freshness_score = freshness_score
                
                db.commit()
                
    except Exception as e:
        logger.error(f"Error calculating playlist scores: {str(e)}")
