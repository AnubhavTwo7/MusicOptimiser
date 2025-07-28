import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.spatial.distance import cosine
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
from typing import Dict, List, Tuple, Optional
import logging
from collections import defaultdict

from ..core.database import get_db_context
from ..models.user import User, ListeningHistory
from ..models.song import Song

logger = logging.getLogger(__name__)

class CollaborativeFiltering:
    def __init__(self, min_interactions: int = 5, max_users: int = 10000):
        self.min_interactions = min_interactions
        self.max_users = max_users
        self.user_item_matrix = None
        self.user_similarity_matrix = None
        self.item_similarity_matrix = None
        self.user_to_idx = {}
        self.idx_to_user = {}
        self.song_to_idx = {}
        self.idx_to_song = {}
        
    def build_user_item_matrix(self) -> csr_matrix:
        """Build user-item interaction matrix from listening history."""
        logger.info("Building user-item matrix for collaborative filtering")
        
        with get_db_context() as db:
            # Get listening history with implicit ratings
            query = """
            SELECT 
                lh.user_id,
                lh.song_id,
                COUNT(*) as play_count,
                AVG(lh.completion_percentage) as avg_completion,
                AVG(CASE WHEN lh.was_skipped THEN 0 ELSE 1 END) as completion_rate
            FROM listening_history lh
            JOIN users u ON lh.user_id = u.id
            JOIN songs s ON lh.song_id = s.id
            WHERE u.is_active = TRUE
            GROUP BY lh.user_id, lh.song_id
            HAVING COUNT(*) >= %s
            """
            
            result = db.execute(query, (self.min_interactions,)).fetchall()
            
            if not result:
                logger.warning("No interaction data found for collaborative filtering")
                return csr_matrix((0, 0))
            
            # Convert to DataFrame
            df = pd.DataFrame(result, columns=['user_id', 'song_id', 'play_count', 'avg_completion', 'completion_rate'])
            
            # Calculate implicit rating
            df['rating'] = (
                0.4 * np.log1p(df['play_count']) +  # Play count component
                0.3 * df['avg_completion'] +         # Completion component
                0.3 * df['completion_rate']          # Skip rate component
            )
            
            # Normalize ratings to 0-5 scale
            df['rating'] = 5 * (df['rating'] - df['rating'].min()) / (df['rating'].max() - df['rating'].min())
            
            # Create user and item mappings
            unique_users = df['user_id'].unique()[:self.max_users]
            unique_songs = df['song_id'].unique()
            
            self.user_to_idx = {user_id: idx for idx, user_id in enumerate(unique_users)}
            self.idx_to_user = {idx: user_id for user_id, idx in self.user_to_idx.items()}
            self.song_to_idx = {song_id: idx for idx, song_id in enumerate(unique_songs)}
            self.idx_to_song = {idx: song_id for song_id, idx in self.song_to_idx.items()}
            
            # Filter DataFrame to include only mapped users and songs
            df = df[df['user_id'].isin(unique_users) & df['song_id'].isin(unique_songs)]
            
            # Create sparse matrix
            row_indices = [self.user_to_idx[user_id] for user_id in df['user_id']]
            col_indices = [self.song_to_idx[song_id] for song_id in df['song_id']]
            ratings = df['rating'].values
            
            self.user_item_matrix = csr_matrix(
                (ratings, (row_indices, col_indices)),
                shape=(len(unique_users), len(unique_songs))
            )
            
            logger.info(f"Built user-item matrix: {self.user_item_matrix.shape}")
            return self.user_item_matrix
    
    def compute_user_similarity(self, metric: str = 'cosine') -> np.ndarray:
        """Compute user-user similarity matrix."""
        if self.user_item_matrix is None:
            self.build_user_item_matrix()
        
        logger.info("Computing user similarity matrix")
        
        if metric == 'cosine':
            # Compute cosine similarity
            self.user_similarity_matrix = cosine_similarity(self.user_item_matrix)
        elif metric == 'pearson':
            # Convert to DataFrame for easier correlation calculation
            df = pd.DataFrame(self.user_item_matrix.toarray())
            self.user_similarity_matrix = df.T.corr().fillna(0).values
        else:
            raise ValueError(f"Unsupported similarity metric: {metric}")
        
        # Set diagonal to 0 (user shouldn't be similar to themselves)
        np.fill_diagonal(self.user_similarity_matrix, 0)
        
        logger.info(f"Computed user similarity matrix: {self.user_similarity_matrix.shape}")
        return self.user_similarity_matrix
    
    def compute_item_similarity(self, metric: str = 'cosine') -> np.ndarray:
        """Compute item-item similarity matrix."""
        if self.user_item_matrix is None:
            self.build_user_item_matrix()
        
        logger.info("Computing item similarity matrix")
        
        if metric == 'cosine':
            # Transpose matrix for item-item similarity
            item_matrix = self.user_item_matrix.T
            self.item_similarity_matrix = cosine_similarity(item_matrix)
        elif metric == 'pearson':
            # Convert to DataFrame
            df = pd.DataFrame(self.user_item_matrix.T.toarray())
            self.item_similarity_matrix = df.T.corr().fillna(0).values
        else:
            raise ValueError(f"Unsupported similarity metric: {metric}")
        
        np.fill_diagonal(self.item_similarity_matrix, 0)
        
        logger.info(f"Computed item similarity matrix: {self.item_similarity_matrix.shape}")
        return self.item_similarity_matrix
    
    async def find_similar_users(self, user_id: int, user_history: List[Dict], 
                               top_k: int = 50) -> List[Tuple[int, float]]:
        """Find users similar to the given user."""
        if user_id not in self.user_to_idx:
            logger.warning(f"User {user_id} not found in collaborative filtering data")
            return []
        
        if self.user_similarity_matrix is None:
            self.compute_user_similarity()
        
        user_idx = self.user_to_idx[user_id]
        similarities = self.user_similarity_matrix[user_idx]
        
        # Get top-k similar users
        similar_user_indices = np.argsort(similarities)[::-1][:top_k]
        similar_users = [
            (self.idx_to_user[idx], similarities[idx])
            for idx in similar_user_indices
            if similarities[idx] > 0
        ]
        
        return similar_users
    
    async def recommend_from_similar_users(self, user_id: int, similar_users: List[Tuple[int, float]],
                                         exclude_history: bool = True, top_k: int = 50) -> List[Dict]:
        """Generate recommendations based on similar users' preferences."""
        if not similar_users:
            return []
        
        # Get user's listening history to exclude
        user_songs = set()
        if exclude_history:
            with get_db_context() as db:
                history = db.query(ListeningHistory.song_id).filter(
                    ListeningHistory.user_id == user_id
                ).all()
                user_songs = {song_id for (song_id,) in history}
        
        # Aggregate recommendations from similar users
        song_scores = defaultdict(float)
        song_recommenders = defaultdict(list)
        
        for similar_user_id, similarity_score in similar_users:
            if similar_user_id not in self.user_to_idx:
                continue
            
            similar_user_idx = self.user_to_idx[similar_user_id]
            user_ratings = self.user_item_matrix[similar_user_idx]
            
            # Get songs this similar user liked
            liked_song_indices = user_ratings.nonzero()[1]
            liked_ratings = user_ratings.data
            
            for song_idx, rating in zip(liked_song_indices, liked_ratings):
                song_id = self.idx_to_song[song_idx]
                
                # Skip if user already heard this song
                if exclude_history and song_id in user_songs:
                    continue
                
                # Weight the rating by user similarity
                weighted_score = rating * similarity_score
                song_scores[song_id] += weighted_score
                song_recommenders[song_id].append((similar_user_id, similarity_score))
        
        # Sort recommendations by score
        sorted_recommendations = sorted(song_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        # Format recommendations
        recommendations = []
        with get_db_context() as db:
            for song_id, score in sorted_recommendations:
                song = db.query(Song).filter(Song.id == song_id).first()
                if song:
                    recommendations.append({
                        'song': song,
                        'score': float(score),
                        'algorithm': 'collaborative_filtering',
                        'similar_users': song_recommenders[song_id][:5],  # Top 5 similar users
                        'reason': f'Liked by {len(song_recommenders[song_id])} similar users'
                    })
        
        return recommendations
    
    async def recommend_user_based(self, user_id: int, top_k: int = 50) -> List[Dict]:
        """User-based collaborative filtering recommendations."""
        # Get user's listening history
        user_history = []
        with get_db_context() as db:
            history = db.query(ListeningHistory).filter(
                ListeningHistory.user_id == user_id
            ).all()
            user_history = [{'song_id': h.song_id, 'rating': h.rating or 3.0} for h in history]
        
        # Find similar users
        similar_users = await self.find_similar_users(user_id, user_history)
        
        # Generate recommendations
        return await self.recommend_from_similar_users(user_id, similar_users, top_k=top_k)
    
    async def recommend_item_based(self, user_id: int, top_k: int = 50) -> List[Dict]:
        """Item-based collaborative filtering recommendations."""
        if self.item_similarity_matrix is None:
            self.compute_item_similarity()
        
        # Get user's listening history
        user_songs = []
        with get_db_context() as db:
            history = db.query(ListeningHistory).filter(
                ListeningHistory.user_id == user_id
            ).order_by(ListeningHistory.played_at.desc()).limit(100).all()
            
            user_songs = [(h.song_id, h.rating or 3.0) for h in history]
        
        if not user_songs:
            return []
        
        # Calculate scores for all songs based on similarity to user's songs
        song_scores = defaultdict(float)
        user_song_set = {song_id for song_id, _ in user_songs}
        
        for user_song_id, user_rating in user_songs:
            if user_song_id not in self.song_to_idx:
                continue
            
            song_idx = self.song_to_idx[user_song_id]
            similarities = self.item_similarity_matrix[song_idx]
            
            # Find similar songs
            for other_song_idx, similarity in enumerate(similarities):
                if similarity > 0:
                    other_song_id = self.idx_to_song[other_song_idx]
                    
                    # Skip if user already heard this song
                    if other_song_id in user_song_set:
                        continue
                    
                    # Weight similarity by user's rating of the original song
                    weighted_score = similarity * user_rating
                    song_scores[other_song_id] += weighted_score
        
        # Sort recommendations by score
        sorted_recommendations = sorted(song_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        # Format recommendations
        recommendations = []
        with get_db_context() as db:
            for song_id, score in sorted_recommendations:
                song = db.query(Song).filter(Song.id == song_id).first()
                if song:
                    recommendations.append({
                        'song': song,
                        'score': float(score),
                        'algorithm': 'item_based_collaborative',
                        'reason': 'Similar to songs you\'ve enjoyed'
                    })
        
        return recommendations
    
    def get_user_profile_vector(self, user_id: int) -> Optional[np.ndarray]:
        """Get user's preference vector from the user-item matrix."""
        if user_id not in self.user_to_idx:
            return None
        
        user_idx = self.user_to_idx[user_id]
        return self.user_item_matrix[user_idx].toarray().flatten()
    
    def predict_rating(self, user_id: int, song_id: int) -> float:
        """Predict rating for a user-song pair."""
        if user_id not in self.user_to_idx or song_id not in self.song_to_idx:
            return 0.0
        
        if self.user_similarity_matrix is None:
            self.compute_user_similarity()
        
        user_idx = self.user_to_idx[user_id]
        song_idx = self.song_to_idx[song_id]
        
        # Find users who have rated this song
        song_raters = self.user_item_matrix[:, song_idx].nonzero()[0]
        
        if len(song_raters) == 0:
            return 0.0
        
        # Calculate weighted average rating
        numerator = 0.0
        denominator = 0.0
        
        for rater_idx in song_raters:
            if rater_idx == user_idx:
                continue
            
            similarity = self.user_similarity_matrix[user_idx, rater_idx]
            rating = self.user_item_matrix[rater_idx, song_idx]
            
            numerator += similarity * rating
            denominator += abs(similarity)
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
