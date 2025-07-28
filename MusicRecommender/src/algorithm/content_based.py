import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from typing import Dict, List, Optional, Tuple
import logging

from ..core.database import get_db_context
from ..models.song import Song
from ..models.user import User, ListeningHistory

logger = logging.getLogger(__name__)

class ContentBasedRecommender:
    def __init__(self):
        self.audio_scaler = StandardScaler()
        self.genre_vectorizer = TfidfVectorizer(max_features=100)
        self.song_features_matrix = None
        self.song_to_idx = {}
        self.idx_to_song = {}
        self.feature_weights = {
            'audio_features': 0.4,
            'genres': 0.3,
            'popularity': 0.1,
            'tempo_energy': 0.2
        }
    
    def build_content_matrix(self) -> np.ndarray:
        """Build content-based feature matrix for all songs."""
        logger.info("Building content-based feature matrix")
        
        with get_db_context() as db:
            songs = db.query(Song).filter(
                Song.acousticness.isnot(None),
                Song.danceability.isnot(None),
                Song.energy.isnot(None)
            ).all()
            
            if not songs:
                logger.warning("No songs with audio features found")
                return np.array([])
            
            # Create mappings
            self.song_to_idx = {song.id: idx for idx, song in enumerate(songs)}
            self.idx_to_song = {idx: song.id for song_id, idx in self.song_to_idx.items()}
            
            # Extract features
            audio_features = []
            genre_texts = []
            popularity_scores = []
            tempo_energy_features = []
            
            for song in songs:
                # Audio features
                audio_feat = [
                    song.acousticness or 0.0,
                    song.danceability or 0.0,
                    song.energy or 0.0,
                    song.instrumentalness or 0.0,
                    song.liveness or 0.0,
                    (song.loudness + 60) / 60 if song.loudness else 0.0,  # Normalize loudness
                    song.speechiness or 0.0,
                    song.valence or 0.0
                ]
                audio_features.append(audio_feat)
                
                # Genre text
                genres = song.genres or []
                genre_text = ' '.join(genres) if genres else ''
                genre_texts.append(genre_text)
                
                # Popularity (normalized)
                popularity = (song.popularity or 0) / 100.0
                popularity_scores.append(popularity)
                
                # Tempo-energy combination
                tempo_norm = (song.tempo / 200.0) if song.tempo else 0.5
                energy = song.energy or 0.5
                tempo_energy = [tempo_norm, energy, tempo_norm * energy]
                tempo_energy_features.append(tempo_energy)
            
            # Scale audio features
            audio_features = np.array(audio_features)
            audio_features_scaled = self.audio_scaler.fit_transform(audio_features)
            
            # Vectorize genres
            if any(genre_texts):
                genre_features = self.genre_vectorizer.fit_transform(genre_texts).toarray()
            else:
                genre_features = np.zeros((len(songs), 1))
            
            # Normalize other features
            popularity_features = np.array(popularity_scores).reshape(-1, 1)
            tempo_energy_features = np.array(tempo_energy_features)
            
            # Combine all features with weights
            combined_features = np.hstack([
                audio_features_scaled * self.feature_weights['audio_features'],
                genre_features * self.feature_weights['genres'],
                popularity_features * self.feature_weights['popularity'],
                tempo_energy_features * self.feature_weights['tempo_energy']
            ])
            
            self.song_features_matrix = combined_features
            logger.info(f"Built content matrix: {self.song_features_matrix.shape}")
            
            return self.song_features_matrix
    
    def compute_song_similarity(self, song1_id: int, song2_id: int) -> float:
        """Compute similarity between two songs."""
        if (song1_id not in self.song_to_idx or 
            song2_id not in self.song_to_idx or 
            self.song_features_matrix is None):
            return 0.0
        
        idx1 = self.song_to_idx[song1_id]
        idx2 = self.song_to_idx[song2_id]
        
        features1 = self.song_features_matrix[idx1].reshape(1, -1)
        features2 = self.song_features_matrix[idx2].reshape(1, -1)
        
        similarity = cosine_similarity(features1, features2)[0][0]
        return float(similarity)
    
    async def recommend_by_audio_features(self, target_features: Dict, 
                                        num_recommendations: int = 50) -> List[Dict]:
        """Recommend songs based on target audio features."""
        if self.song_features_matrix is None:
            self.build_content_matrix()
        
        if self.song_features_matrix.size == 0:
            return []
        
        # Build target feature vector
        target_audio = [
            target_features.get('acousticness', 0.5),
            target_features.get('danceability', 0.5),
            target_features.get('energy', 0.5),
            target_features.get('instrumentalness', 0.5),
            target_features.get('liveness', 0.5),
            target_features.get('loudness', 0.5),
            target_features.get('speechiness', 0.5),
            target_features.get('valence', 0.5)
        ]
        
        # Scale target audio features
        target_audio_scaled = self.audio_scaler.transform([target_audio])[0]
        
        # For simplicity, use audio features only for targeting
        audio_feature_size = len(target_audio_scaled)
        target_vector = np.zeros(self.song_features_matrix.shape[1])
        target_vector[:audio_feature_size] = target_audio_scaled * self.feature_weights['audio_features']
        
        # Compute similarities
        similarities = cosine_similarity([target_vector], self.song_features_matrix)[0]
        
        # Get top recommendations
        top_indices = np.argsort(similarities)[::-1][:num_recommendations]
        
        recommendations = []
        with get_db_context() as db:
            for idx in top_indices:
                song_id = self.idx_to_song[idx]
                song = db.query(Song).filter(Song.id == song_id).first()
                
                if song and similarities[idx] > 0:
                    recommendations.append({
                        'song': song,
                        'score': float(similarities[idx]),
                        'algorithm': 'content_based_audio',
                        'reason': 'Matches your audio preferences'
                    })
        
        return recommendations
    
    async def recommend_similar_to_song(self, song_id: int, 
                                      num_recommendations: int = 20) -> List[Dict]:
        """Recommend songs similar to a given song."""
        if song_id not in self.song_to_idx or self.song_features_matrix is None:
            return []
        
        song_idx = self.song_to_idx[song_id]
        song_features = self.song_features_matrix[song_idx].reshape(1, -1)
        
        # Compute similarities with all other songs
        similarities = cosine_similarity(song_features, self.song_features_matrix)[0]
        
        # Exclude the input song itself
        similarities[song_idx] = 0
        
        # Get top similar songs
        top_indices = np.argsort(similarities)[::-1][:num_recommendations]
        
        recommendations = []
        with get_db_context() as db:
            for idx in top_indices:
                similar_song_id = self.idx_to_song[idx]
                song = db.query(Song).filter(Song.id == similar_song_id).first()
                
                if song and similarities[idx] > 0:
                    recommendations.append({
                        'song': song,
                        'score': float(similarities[idx]),
                        'algorithm': 'content_based_similarity',
                        'reason': f'Similar to song you liked'
                    })
        
        return recommendations
    
    async def recommend_by_user_profile(self, user_id: int, 
                                      num_recommendations: int = 50) -> List[Dict]:
        """Recommend songs based on user's content profile."""
        with get_db_context() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return []
            
            # Get user's listening history to build profile
            recent_history = db.query(ListeningHistory).join(Song).filter(
                ListeningHistory.user_id == user_id,
                ListeningHistory.completion_percentage > 0.7,  # Songs user completed
                Song.acousticness.isnot(None)
            ).order_by(ListeningHistory.played_at.desc()).limit(100).all()
            
            if not recent_history:
                return []
            
            # Calculate average preferences
            audio_preferences = {
                'acousticness': np.mean([h.song.acousticness for h in recent_history if h.song.acousticness]),
                'danceability': np.mean([h.song.danceability for h in recent_history if h.song.danceability]),
                'energy': np.mean([h.song.energy for h in recent_history if h.song.energy]),
                'instrumentalness': np.mean([h.song.instrumentalness for h in recent_history if h.song.instrumentalness]),
                'liveness': np.mean([h.song.liveness for h in recent_history if h.song.liveness]),
                'speechiness': np.mean([h.song.speechiness for h in recent_history if h.song.speechiness]),
                'valence': np.mean([h.song.valence for h in recent_history if h.song.valence]),
                'loudness': np.mean([h.song.loudness for h in recent_history if h.song.loudness]),
            }
            
            # Get songs user has already heard
            user_songs = {h.song_id for h in recent_history}
            
            # Generate recommendations
            recommendations = await self.recommend_by_audio_features(audio_preferences, num_recommendations * 2)
            
            # Filter out songs user has already heard
            filtered_recommendations = [
                rec for rec in recommendations 
                if rec['song'].id not in user_songs
            ][:num_recommendations]
            
            return filtered_recommendations
    
    def get_song_content_vector(self, song_id: int) -> Optional[np.ndarray]:
        """Get content vector for a specific song."""
        if song_id not in self.song_to_idx or self.song_features_matrix is None:
            return None
        
        song_idx = self.song_to_idx[song_id]
        return self.song_features_matrix[song_idx]
    
    async def recommend_by_genres(self, target_genres: List[str], 
                                num_recommendations: int = 50) -> List[Dict]:
        """Recommend songs based on target genres."""
        with get_db_context() as db:
            # Find songs with matching genres
            songs_with_genres = db.query(Song).filter(
                Song.genres.isnot(None)
            ).all()
            
            genre_matches = []
            for song in songs_with_genres:
                song_genres = song.genres or []
                
                # Calculate genre overlap
                overlap = len(set(target_genres) & set(song_genres))
                if overlap > 0:
                    genre_score = overlap / len(target_genres)
                    genre_matches.append((song, genre_score))
            
            # Sort by genre match score
            genre_matches.sort(key=lambda x: x[1], reverse=True)
            
            # Format recommendations
            recommendations = []
            for song, score in genre_matches[:num_recommendations]:
                recommendations.append({
                    'song': song,
                    'score': float(score),
                    'algorithm': 'content_based_genre',
                    'reason': f'Matches genres: {", ".join(set(target_genres) & set(song.genres))}'
                })
            
            return recommendations
    
    async def recommend_by_mood(self, target_mood: str, 
                              num_recommendations: int = 50) -> List[Dict]:
        """Recommend songs based on mood."""
        # Define mood to audio feature mappings
        mood_profiles = {
            'happy': {'valence': 0.8, 'energy': 0.7, 'danceability': 0.7},
            'sad': {'valence': 0.2, 'energy': 0.3, 'acousticness': 0.7},
            'energetic': {'energy': 0.9, 'danceability': 0.8, 'tempo': 140},
            'chill': {'energy': 0.3, 'valence': 0.6, 'acousticness': 0.6},
            'focus': {'instrumentalness': 0.8, 'energy': 0.4, 'speechiness': 0.1},
            'party': {'danceability': 0.9, 'energy': 0.8, 'valence': 0.7},
            'romantic': {'valence': 0.6, 'acousticness': 0.5, 'energy': 0.4}
        }
        
        if target_mood not in mood_profiles:
            return []
        
        target_features = mood_profiles[target_mood]
        recommendations = await self.recommend_by_audio_features(target_features, num_recommendations)
        
        # Update reasoning
        for rec in recommendations:
            rec['reason'] = f'Matches {target_mood} mood'
            rec['algorithm'] = 'content_based_mood'
        
        return recommendations
