import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict

from .collaborative_filtering import CollaborativeFiltering
from .content_based import ContentBasedRecommender
from .matrix_factorization import MatrixFactorization

logger = logging.getLogger(__name__)

class HybridRecommender:
    def __init__(self):
        self.collaborative = CollaborativeFiltering()
        self.content_based = ContentBasedRecommender()
        self.matrix_factorization = MatrixFactorization()
        
        # Default weights for different algorithms
        self.default_weights = {
            'collaborative': 0.4,
            'content': 0.3,
            'matrix_factorization': 0.3
        }
        
    def combine_recommendations(self, 
                              collaborative_recs: List[Dict],
                              content_recs: List[Dict],
                              mf_recs: List[Dict],
                              weights: Optional[List[float]] = None) -> List[Dict]:
        """Combine recommendations from different algorithms using weighted scoring."""
        
        if weights is None:
            weights = [
                self.default_weights['collaborative'],
                self.default_weights['content'],
                self.default_weights['matrix_factorization']
            ]
        
        # Normalize weights
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        else:
            weights = [1/3, 1/3, 1/3]
        
        # Collect all unique songs and their scores
        song_scores = defaultdict(lambda: {'total_score': 0.0, 'count': 0, 'algorithms': [], 'song': None})
        
        # Process collaborative filtering recommendations
        for rec in collaborative_recs:
            song_id = rec['song'].id
            weighted_score = rec['score'] * weights[0]
            song_scores[song_id]['total_score'] += weighted_score
            song_scores[song_id]['count'] += 1
            song_scores[song_id]['algorithms'].append('collaborative')
            song_scores[song_id]['song'] = rec['song']
        
        # Process content-based recommendations
        for rec in content_recs:
            song_id = rec['song'].id
            weighted_score = rec['score'] * weights[1]
            song_scores[song_id]['total_score'] += weighted_score
            song_scores[song_id]['count'] += 1
            song_scores[song_id]['algorithms'].append('content')
            song_scores[song_id]['song'] = rec['song']
        
        # Process matrix factorization recommendations
        for rec in mf_recs:
            song_id = rec['song'].id
            weighted_score = rec['score'] * weights[2]
            song_scores[song_id]['total_score'] += weighted_score
            song_scores[song_id]['count'] += 1
            song_scores[song_id]['algorithms'].append('matrix_factorization')
            song_scores[song_id]['song'] = rec['song']
        
        # Create final recommendations
        hybrid_recommendations = []
        for song_id, data in song_scores.items():
            if data['song'] is not None:
                # Calculate confidence based on algorithm agreement
                confidence = data['count'] / 3.0  # Max 3 algorithms
                
                # Boost score for songs recommended by multiple algorithms
                consensus_boost = 1.0 + (data['count'] - 1) * 0.2
                final_score = data['total_score'] * consensus_boost
                
                hybrid_recommendations.append({
                    'song': data['song'],
                    'score': final_score,
                    'confidence': confidence,
                    'algorithm': 'hybrid',
                    'contributing_algorithms': data['algorithms'],
                    'reason': self._generate_hybrid_reason(data['algorithms'])
                })
        
        # Sort by score
        hybrid_recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        return hybrid_recommendations
    
    def _generate_hybrid_reason(self, algorithms: List[str]) -> str:
        """Generate explanation for why a song was recommended."""
        if len(algorithms) == 1:
            if 'collaborative' in algorithms:
                return "Recommended based on users with similar taste"
            elif 'content' in algorithms:
                return "Matches your musical preferences"
            elif 'matrix_factorization' in algorithms:
                return "Discovered through pattern analysis"
        else:
            return f"Recommended by {len(algorithms)} different methods for high confidence"
    
    def adaptive_weights(self, user_history_length: int, 
                        user_diversity_score: float,
                        cold_start: bool = False) -> Dict[str, float]:
        """Adapt algorithm weights based on user characteristics."""
        
        weights = self.default_weights.copy()
        
        # Cold start users: rely more on content-based
        if cold_start or user_history_length < 10:
            weights['collaborative'] = 0.2
            weights['content'] = 0.5
            weights['matrix_factorization'] = 0.3
        
        # Users with limited history: balance content and collaborative
        elif user_history_length < 50:
            weights['collaborative'] = 0.3
            weights['content'] = 0.4
            weights['matrix_factorization'] = 0.3
        
        # Users with rich history: rely more on collaborative and MF
        elif user_history_length >= 200:
            weights['collaborative'] = 0.45
            weights['content'] = 0.2
            weights['matrix_factorization'] = 0.35
        
        # Adjust based on user diversity
        if user_diversity_score > 0.7:  # Very diverse user
            weights['content'] += 0.1  # Boost content-based for exploration
            weights['collaborative'] -= 0.05
            weights['matrix_factorization'] -= 0.05
        elif user_diversity_score < 0.3:  # Focused user
            weights['collaborative'] += 0.1  # Boost collaborative for similar users
            weights['content'] -= 0.05
            weights['matrix_factorization'] -= 0.05
        
        # Normalize weights
        total = sum(weights.values())
        return {k: v/total for k, v in weights.items()}
    
    async def recommend_hybrid(self, user_id: int, 
                             num_recommendations: int = 50,
                             context: Optional[Dict] = None) -> List[Dict]:
        """Generate hybrid recommendations for a user."""
        
        # Get user characteristics for adaptive weighting
        from ..core.database import get_db_context
        from ..models.user import User, ListeningHistory
        
        with get_db_context() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return []
            
            # Get user history length
            history_count = db.query(ListeningHistory).filter(
                ListeningHistory.user_id == user_id
            ).count()
            
            # Calculate user diversity (placeholder - would need more sophisticated calculation)
            user_diversity = user.diversity_preference or 0.5
            
            # Determine if cold start
            cold_start = history_count < 5
        
        # Get adaptive weights
        weights = self.adaptive_weights(history_count, user_diversity, cold_start)
        weight_list = [weights['collaborative'], weights['content'], weights['matrix_factorization']]
        
        # Get recommendations from each algorithm
        try:
            collaborative_recs = await self.collaborative.recommend_user_based(user_id, num_recommendations)
        except Exception as e:
            logger.warning(f"Collaborative filtering failed: {str(e)}")
            collaborative_recs = []
        
        try:
            content_recs = await self.content_based.recommend_by_user_profile(user_id, num_recommendations)
        except Exception as e:
            logger.warning(f"Content-based filtering failed: {str(e)}")
            content_recs = []
        
        try:
            mf_recs = await self.matrix_factorization.recommend_for_user(user_id, num_recommendations)
        except Exception as e:
            logger.warning(f"Matrix factorization failed: {str(e)}")
            mf_recs = []
        
        # Combine recommendations
        hybrid_recs = self.combine_recommendations(
            collaborative_recs, content_recs, mf_recs, weight_list
        )
        
        # Apply context-based filtering if provided
        if context:
            hybrid_recs = self._apply_context_filter(hybrid_recs, context)
        
        return hybrid_recs[:num_recommendations]
    
    def _apply_context_filter(self, recommendations: List[Dict], 
                            context: Dict) -> List[Dict]:
        """Apply contextual filters to recommendations."""
        
        filtered_recs = []
        
        for rec in recommendations:
            song = rec['song']
            include_song = True
            
            # Time of day filter
            if 'time_of_day' in context:
                time_period = context['time_of_day']  # morning, afternoon, evening, night
                
                if time_period == 'morning' and song.energy < 0.3:
                    rec['score'] *= 0.7  # Reduce score for low-energy morning songs
                elif time_period == 'night' and song.energy > 0.8:
                    rec['score'] *= 0.7  # Reduce score for high-energy night songs
            
            # Activity filter
            if 'activity' in context:
                activity = context['activity']  # workout, study, party, relax
                
                if activity == 'workout':
                    if song.energy > 0.7 and song.tempo > 120:
                        rec['score'] *= 1.2  # Boost workout-appropriate songs
                    else:
                        rec['score'] *= 0.5
                
                elif activity == 'study':
                    if song.instrumentalness > 0.5 and song.speechiness < 0.1:
                        rec['score'] *= 1.3  # Boost instrumental songs
                    elif song.speechiness > 0.3:
                        rec['score'] *= 0.3  # Reduce vocal-heavy songs
                
                elif activity == 'party':
                    if song.danceability > 0.7 and song.valence > 0.6:
                        rec['score'] *= 1.4  # Boost party songs
                    else:
                        rec['score'] *= 0.6
            
            # Mood filter
            if 'mood' in context:
                mood = context['mood']
                
                if mood == 'happy' and song.valence > 0.6:
                    rec['score'] *= 1.2
                elif mood == 'sad' and song.valence < 0.4:
                    rec['score'] *= 1.2
                elif mood == 'energetic' and song.energy > 0.7:
                    rec['score'] *= 1.2
            
            # Explicit content filter
            if context.get('explicit_filter', True) and song.explicit:
                rec['score'] *= 0.5
            
            # Duration filter
            if 'max_duration_ms' in context:
                max_duration = context['max_duration_ms']
                if song.duration_ms and song.duration_ms > max_duration:
                    include_song = False
            
            if include_song and rec['score'] > 0:
                filtered_recs.append(rec)
        
        # Re-sort by adjusted scores
        filtered_recs.sort(key=lambda x: x['score'], reverse=True)
        
        return filtered_recs
    
    def explain_recommendation(self, recommendation: Dict) -> str:
        """Generate detailed explanation for a recommendation."""
        song = recommendation['song']
        algorithms = recommendation.get('contributing_algorithms', [])
        confidence = recommendation.get('confidence', 0.0)
        
        explanation = f"'{song.title}' by {song.artist} was recommended "
        
        if len(algorithms) > 1:
            explanation += f"by {len(algorithms)} different algorithms, "
            explanation += f"giving us {confidence:.1%} confidence. "
        
        if 'collaborative' in algorithms:
            explanation += "Users with similar taste to yours have enjoyed this song. "
        
        if 'content' in algorithms:
            explanation += "This song matches your musical preferences based on audio characteristics. "
        
        if 'matrix_factorization' in algorithms:
            explanation += "Our AI discovered this through patterns in listening behavior. "
        
        # Add song characteristics
        if song.genres:
            explanation += f"Genres: {', '.join(song.genres[:3])}. "
        
        if song.energy and song.valence:
            if song.energy > 0.7:
                explanation += "High energy. "
            elif song.energy < 0.3:
                explanation += "Low energy. "
            
            if song.valence > 0.7:
                explanation += "Positive mood. "
            elif song.valence < 0.3:
                explanation += "Melancholic mood. "
        
        return explanation.strip()
