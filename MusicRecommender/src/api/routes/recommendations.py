from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from ...core.database import get_db
from ...models.user import User
from ...services.recommendation_engine import RecommendationEngine, RecommendationRequest
from ...services.hybrid_recommender import HybridRecommender

logger = logging.getLogger(__name__)

router = APIRouter()

from pydantic import BaseModel

class RecommendationResponse(BaseModel):
    song_id: int
    title: str
    artist: str
    album: Optional[str]
    score: float
    confidence: Optional[float]
    algorithm: str
    reason: str
    audio_features: Optional[dict]

class RecommendationRequest(BaseModel):
    target_mood: Optional[str] = None
    target_energy: Optional[float] = None
    target_genres: Optional[List[str]] = None
    num_recommendations: int = 20
    exclude_recent: bool = True
    context: Optional[dict] = None

@router.post("/", response_model=List[RecommendationResponse])
async def get_recommendations(
    request: RecommendationRequest,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get personalized recommendations for a user."""
    
    try:
        # Validate user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Use hybrid recommender for best results
        hybrid_recommender = HybridRecommender()
        
        recommendations = await hybrid_recommender.recommend_hybrid(
            user_id=user_id,
            num_recommendations=request.num_recommendations,
            context=request.context
        )
        
        # Format response
        response = []
        for rec in recommendations:
            song = rec['song']
            response.append(RecommendationResponse(
                song_id=song.id,
                title=song.title,
                artist=song.artist,
                album=song.album,
                score=rec['score'],
                confidence=rec.get('confidence'),
                algorithm=rec['algorithm'],
                reason=rec['reason'],
                audio_features={
                    'energy': song.energy,
                    'valence': song.valence,
                    'danceability': song.danceability,
                    'tempo': song.tempo
                } if song.energy is not None else None
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get recommendations")

@router.get("/similar/{song_id}", response_model=List[RecommendationResponse])
async def get_similar_songs(
    song_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get songs similar to a specific song."""
    
    try:
        from ...services.content_based import ContentBasedRecommender
        
        content_recommender = ContentBasedRecommender()
        recommendations = await content_recommender.recommend_similar_to_song(song_id, limit)
        
        response = []
        for rec in recommendations:
            song = rec['song']
            response.append(RecommendationResponse(
                song_id=song.id,
                title=song.title,
                artist=song.artist,
                album=song.album,
                score=rec['score'],
                algorithm=rec['algorithm'],
                reason=rec['reason'],
                audio_features={
                    'energy': song.energy,
                    'valence': song.valence,
                    'danceability': song.danceability,
                    'tempo': song.tempo
                } if song.energy is not None else None
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting similar songs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get similar songs")
