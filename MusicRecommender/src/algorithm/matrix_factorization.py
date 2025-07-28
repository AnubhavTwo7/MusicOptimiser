import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD, NMF
from sklearn.metrics import mean_squared_error
import logging
from typing import Dict, List, Optional, Tuple
import pickle
import os

from ..core.database import get_db_context
from ..models.user import User, ListeningHistory
from ..models.song import Song

logger = logging.getLogger(__name__)

class MatrixFactorization:
    def __init__(self, embedding_dim: int = 128, algorithm: str = 'svd'):
        self.embedding_dim = embedding_dim
        self.algorithm = algorithm  # 'svd', 'nmf'
        self.model = None
        self.user_embeddings = None
        self.item_embeddings = None
        self.user_to_idx = {}
        self.idx_to_user = {}
        self.song_to_idx = {}
        self.idx_to_song = {}
        self.user_item_matrix = None
        self.mean_rating = 0.0
        
    def prepare_data(self, min_interactions: int = 5) -> csr_matrix:
        """Prepare user-item matrix for matrix factorization."""
        logger.info("Preparing data for matrix factorization")
        
        with get_db_context() as db:
            # Get interaction data with implicit feedback
            query = """
            SELECT 
                lh.user_id,
                lh.song_id,
                COUNT(*) as play_count,
                AVG(lh.completion_percentage) as avg_completion,
                AVG(CASE WHEN lh.was_skipped THEN 0 ELSE 1 END) as completion_rate
            FROM listening_history lh
            JOIN users u ON lh.user_id = u.id
            WHERE u.is_active = TRUE
            GROUP BY lh.user_id, lh.song_id
            HAVING COUNT(*) >= %s
            """
            
            result = db.execute(query, (min_interactions,)).fetchall()
            
            if not result:
                logger.warning("No sufficient interaction data found")
                return csr_matrix((0, 0))
            
            # Convert to DataFrame
            df = pd.DataFrame(result, columns=['user_id', 'song_id', 'play_count', 'avg_completion', 'completion_rate'])
            
            # Calculate implicit rating (0-5 scale)
            df['rating'] = (
                0.4 * np.log1p(df['play_count']) +
                0.35 * df['avg_completion'] +
                0.25 * df['completion_rate']
            )
            
            # Normalize to 0-5 scale
            min_rating, max_rating = df['rating'].min(), df['rating'].max()
            df['rating'] = 5 * (df['rating'] - min_rating) / (max_rating - min_rating)
            
            self.mean_rating = df['rating'].mean()
            
            # Create mappings
            unique_users = df['user_id'].unique()
            unique_songs = df['song_id'].unique()
            
            self.user_to_idx = {user_id: idx for idx, user_id in enumerate(unique_users)}
            self.idx_to_user = {idx: user_id for user_id, idx in self.user_to_idx.items()}
            self.song_to_idx = {song_id: idx for idx, song_id in enumerate(unique_songs)}
            self.idx_to_song = {idx: song_id for song_id, idx in self.song_to_idx.items()}
            
            # Create sparse matrix
            row_indices = [self.user_to_idx[user_id] for user_id in df['user_id']]
            col_indices = [self.song_to_idx[song_id] for song_id in df['song_id']]
            ratings = df['rating'].values
            
            self.user_item_matrix = csr_matrix(
                (ratings, (row_indices, col_indices)),
                shape=(len(unique_users), len(unique_songs))
            )
            
            logger.info(f"Prepared matrix: {self.user_item_matrix.shape}, density: {self.user_item_matrix.nnz / (self.user_item_matrix.shape[0] * self.user_item_matrix.shape[1]):.4f}")
            
            return self.user_item_matrix
    
    def train(self, user_item_matrix: Optional[csr_matrix] = None):
        """Train the matrix factorization model."""
        if user_item_matrix is None:
            user_item_matrix = self.prepare_data()
        
        if user_item_matrix.size == 0:
            logger.error("No data available for training")
            return
        
        logger.info(f"Training {self.algorithm} model with embedding dimension {self.embedding_dim}")
        
        try:
            if self.algorithm == 'svd':
                self.model = TruncatedSVD(
                    n_components=self.embedding_dim,
                    random_state=42,
                    n_iter=10
                )
                
                # Fit model
                user_embeddings = self.model.fit_transform(user_item_matrix)
                item_embeddings = self.model.components_.T
                
                self.user_embeddings = user_embeddings
                self.item_embeddings = item_embeddings
                
            elif self.algorithm == 'nmf':
                self.model = NMF(
                    n_components=self.embedding_dim,
                    init='random',
                    random_state=42,
                    max_iter=200
                )
                
                # NMF requires non-negative values
                user_item_dense = user_item_matrix.toarray()
                user_item_dense = np.maximum(user_item_dense, 0)
                
                user_embeddings = self.model.fit_transform(user_item_dense)
                item_embeddings = self.model.components_.T
                
                self.user_embeddings = user_embeddings
                self.item_embeddings = item_embeddings
            
            else:
                raise ValueError(f"Unsupported algorithm: {self.algorithm}")
            
            # Calculate explained variance
            explained_variance_ratio = getattr(self.model, 'explained_variance_ratio_', None)
            if explained_variance_ratio is not None:
                total_variance = np.sum(explained_variance_ratio)
                logger.info(f"Model trained. Explained variance: {total_variance:.4f}")
            else:
                logger.info("Model trained successfully")
                
        except Exception as e:
            logger.error(f"Error training matrix factorization model: {str(e)}")
            raise
    
    def predict_rating(self, user_id: int, song_id: int) -> float:
        """Predict rating for a user-song pair."""
        if (user_id not in self.user_to_idx or 
            song_id not in self.song_to_idx or 
            self.user_embeddings is None or 
            self.item_embeddings is None):
            return self.mean_rating
        
        user_idx = self.user_to_idx[user_id]
        song_idx = self.song_to_idx[song_id]
        
        # Compute dot product of user and item embeddings
        predicted_rating = np.dot(self.user_embeddings[user_idx], self.item_embeddings[song_idx])
        
        # Add global mean for better predictions
        predicted_rating += self.mean_rating
        
        # Clip to valid rating range
        return np.clip(predicted_rating, 0, 5)
    
    async def recommend(self, user_embedding: np.ndarray, 
                       num_recommendations: int = 50) -> List[Dict]:
        """Generate recommendations using user embedding."""
        if self.item_embeddings is None:
            return []
        
        # Compute scores for all items
        scores = np.dot(user_embedding, self.item_embeddings.T)
        
        # Get top recommendations
        top_song_indices = np.argsort(scores)[::-1][:num_recommendations]
        
        recommendations = []
        with get_db_context() as db:
            for song_idx in top_song_indices:
                song_id = self.idx_to_song[song_idx]
                song = db.query(Song).filter(Song.id == song_id).first()
                
                if song:
                    recommendations.append({
                        'song': song,
                        'score': float(scores[song_idx]),
                        'algorithm': f'matrix_factorization_{self.algorithm}',
                        'reason': 'Based on latent factors from your listening patterns'
                    })
        
        return recommendations
    
    async def recommend_for_user(self, user_id: int, 
                               num_recommendations: int = 50,
                               exclude_seen: bool = True) -> List[Dict]:
        """Generate recommendations for a specific user."""
        if user_id not in self.user_to_idx or self.user_embeddings is None:
            return []
        
        user_idx = self.user_to_idx[user_id]
        user_embedding = self.user_embeddings[user_idx]
        
        # Get all song scores
        scores = np.dot(user_embedding, self.item_embeddings.T)
        
        # Exclude songs user has already interacted with
        if exclude_seen:
            user_songs = set()
            with get_db_context() as db:
                history = db.query(ListeningHistory.song_id).filter(
                    ListeningHistory.user_id == user_id
                ).all()
                user_songs = {song_id for (song_id,) in history}
            
            # Set scores to -inf for seen songs
            for song_id in user_songs:
                if song_id in self.song_to_idx:
                    song_idx = self.song_to_idx[song_id]
                    scores[song_idx] = -np.inf
        
        # Get top recommendations
        top_song_indices = np.argsort(scores)[::-1][:num_recommendations]
        
        recommendations = []
        with get_db_context() as db:
            for song_idx in top_song_indices:
                if scores[song_idx] == -np.inf:
                    continue
                    
                song_id = self.idx_to_song[song_idx]
                song = db.query(Song).filter(Song.id == song_id).first()
                
                if song:
                    recommendations.append({
                        'song': song,
                        'score': float(scores[song_idx]),
                        'algorithm': f'matrix_factorization_{self.algorithm}',
                        'predicted_rating': self.predict_rating(user_id, song_id),
                        'reason': 'Discovered through latent preference patterns'
                    })
        
        return recommendations
    
    def get_user_embedding(self, user_id: int) -> Optional[np.ndarray]:
        """Get embedding vector for a user."""
        if user_id not in self.user_to_idx or self.user_embeddings is None:
            return None
        
        user_idx = self.user_to_idx[user_id]
        return self.user_embeddings[user_idx]
    
    def get_song_embedding(self, song_id: int) -> Optional[np.ndarray]:
        """Get embedding vector for a song."""
        if song_id not in self.song_to_idx or self.item_embeddings is None:
            return None
        
        song_idx = self.song_to_idx[song_id]
        return self.item_embeddings[song_idx]
    
    def find_similar_users(self, user_id: int, top_k: int = 20) -> List[Tuple[int, float]]:
        """Find users with similar embeddings."""
        user_embedding = self.get_user_embedding(user_id)
        if user_embedding is None:
            return []
        
        # Compute cosine similarity with all users
        similarities = np.dot(self.user_embeddings, user_embedding) / (
            np.linalg.norm(self.user_embeddings, axis=1) * np.linalg.norm(user_embedding)
        )
        
        # Get top similar users (excluding self)
        user_idx = self.user_to_idx[user_id]
        similarities[user_idx] = -1  # Exclude self
        
        top_user_indices = np.argsort(similarities)[::-1][:top_k]
        
        similar_users = [
            (self.idx_to_user[idx], similarities[idx])
            for idx in top_user_indices
            if similarities[idx] > 0
        ]
        
        return similar_users
    
    def find_similar_songs(self, song_id: int, top_k: int = 20) -> List[Tuple[int, float]]:
        """Find songs with similar embeddings."""
        song_embedding = self.get_song_embedding(song_id)
        if song_embedding is None:
            return []
        
        # Compute cosine similarity with all songs
        similarities = np.dot(self.item_embeddings, song_embedding) / (
            np.linalg.norm(self.item_embeddings, axis=1) * np.linalg.norm(song_embedding)
        )
        
        # Get top similar songs (excluding self)
        song_idx = self.song_to_idx[song_id]
        similarities[song_idx] = -1  # Exclude self
        
        top_song_indices = np.argsort(similarities)[::-1][:top_k]
        
        similar_songs = [
            (self.idx_to_song[idx], similarities[idx])
            for idx in top_song_indices
            if similarities[idx] > 0
        ]
        
        return similar_songs
    
    def save_model(self, filepath: str):
        """Save the trained model to disk."""
        model_data = {
            'algorithm': self.algorithm,
            'embedding_dim': self.embedding_dim,
            'model': self.model,
            'user_embeddings': self.user_embeddings,
            'item_embeddings': self.item_embeddings,
            'user_to_idx': self.user_to_idx,
            'idx_to_user': self.idx_to_user,
            'song_to_idx': self.song_to_idx,
            'idx_to_song': self.idx_to_song,
            'mean_rating': self.mean_rating
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load a trained model from disk."""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.algorithm = model_data['algorithm']
            self.embedding_dim = model_data['embedding_dim']
            self.model = model_data['model']
            self.user_embeddings = model_data['user_embeddings']
            self.item_embeddings = model_data['item_embeddings']
            self.user_to_idx = model_data['user_to_idx']
            self.idx_to_user = model_data['idx_to_user']
            self.song_to_idx = model_data['song_to_idx']
            self.idx_to_song = model_data['idx_to_song']
            self.mean_rating = model_data['mean_rating']
            
            logger.info(f"Model loaded from {filepath}")
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise
    
    def evaluate(self, test_data: List[Tuple[int, int, float]]) -> Dict[str, float]:
        """Evaluate model performance on test data."""
        if self.user_embeddings is None or self.item_embeddings is None:
            return {}
        
        predictions = []
        actuals = []
        
        for user_id, song_id, actual_rating in test_data:
            predicted_rating = self.predict_rating(user_id, song_id)
            predictions.append(predicted_rating)
            actuals.append(actual_rating)
        
        mse = mean_squared_error(actuals, predictions)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(np.array(predictions) - np.array(actuals)))
        
        return {
            'mse': mse,
            'rmse': rmse,
            'mae': mae,
            'num_predictions': len(predictions)
        }
