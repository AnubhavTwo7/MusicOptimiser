import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from typing import Dict, List, Optional, Tuple
import logging
import asyncio
from datetime import datetime, timedelta
import time

from ..core.config import config
from ..core.cache import cache_manager
from ..models.song import Song
from ..models.user import User

logger = logging.getLogger(__name__)

class SpotifyService:
    def __init__(self):
        self.client_credentials_manager = SpotifyClientCredentials(
            client_id=config.spotify.client_id,
            client_secret=config.spotify.client_secret
        )
        self.sp = spotipy.Spotify(client_credentials_manager=self.client_credentials_manager)
        self.rate_limit_delay = 0.1  # 100ms between requests to avoid rate limiting
        
    def get_user_auth_url(self, redirect_uri: str, scopes: List[str]) -> str:
        """Get Spotify authorization URL for user authentication."""
        auth_manager = SpotifyOAuth(
            client_id=config.spotify.client_id,
            client_secret=config.spotify.client_secret,
            redirect_uri=redirect_uri,
            scope=" ".join(scopes)
        )
        return auth_manager.get_authorize_url()
    
    async def get_user_token(self, authorization_code: str, redirect_uri: str) -> Dict:
        """Exchange authorization code for access token."""
        auth_manager = SpotifyOAuth(
            client_id=config.spotify.client_id,
            client_secret=config.spotify.client_secret,
            redirect_uri=redirect_uri
        )
        
        try:
            token_info = auth_manager.get_access_token(authorization_code)
            return token_info
        except Exception as e:
            logger.error(f"Error getting Spotify user token: {str(e)}")
            raise
    
    async def get_user_profile(self, access_token: str) -> Dict:
        """Get user's Spotify profile information."""
        cache_key = f"spotify_profile:{access_token[:10]}"
        cached_profile = await cache_manager.get(cache_key)
        
        if cached_profile:
            return cached_profile
        
        try:
            sp_user = spotipy.Spotify(auth=access_token)
            profile = sp_user.current_user()
            
            # Cache for 1 hour
            await cache_manager.set(cache_key, profile, ttl=3600)
            return profile
            
        except Exception as e:
            logger.error(f"Error fetching Spotify user profile: {str(e)}")
            raise
    
    async def get_user_top_tracks(self, access_token: str, limit: int = 50, 
                                 time_range: str = "medium_term") -> List[Dict]:
        """Get user's top tracks from Spotify."""
        cache_key = f"spotify_top_tracks:{access_token[:10]}:{time_range}:{limit}"
        cached_tracks = await cache_manager.get(cache_key)
        
        if cached_tracks:
            return cached_tracks
        
        try:
            sp_user = spotipy.Spotify(auth=access_token)
            results = sp_user.current_user_top_tracks(
                limit=limit, 
                offset=0, 
                time_range=time_range
            )
            
            tracks = results['items']
            
            # Cache for 6 hours
            await cache_manager.set(cache_key, tracks, ttl=21600)
            return tracks
            
        except Exception as e:
            logger.error(f"Error fetching user's top tracks: {str(e)}")
            return []
    
    async def get_user_top_artists(self, access_token: str, limit: int = 50,
                                  time_range: str = "medium_term") -> List[Dict]:
        """Get user's top artists from Spotify."""
        cache_key = f"spotify_top_artists:{access_token[:10]}:{time_range}:{limit}"
        cached_artists = await cache_manager.get(cache_key)
        
        if cached_artists:
            return cached_artists
        
        try:
            sp_user = spotipy.Spotify(auth=access_token)
            results = sp_user.current_user_top_artists(
                limit=limit,
                offset=0,
                time_range=time_range
            )
            
            artists = results['items']
            
            # Cache for 6 hours
            await cache_manager.set(cache_key, artists, ttl=21600)
            return artists
            
        except Exception as e:
            logger.error(f"Error fetching user's top artists: {str(e)}")
            return []
    
    async def get_recently_played(self, access_token: str, limit: int = 50) -> List[Dict]:
        """Get user's recently played tracks."""
        try:
            sp_user = spotipy.Spotify(auth=access_token)
            results = sp_user.current_user_recently_played(limit=limit)
            return results['items']
            
        except Exception as e:
            logger.error(f"Error fetching recently played tracks: {str(e)}")
            return []
    
    async def search_tracks(self, query: str, limit: int = 20) -> List[Dict]:
        """Search for tracks on Spotify."""
        cache_key = f"spotify_search:{hash(query)}:{limit}"
        cached_results = await cache_manager.get(cache_key)
        
        if cached_results:
            return cached_results
        
        try:
            await asyncio.sleep(self.rate_limit_delay)
            results = self.sp.search(q=query, type='track', limit=limit)
            tracks = results['tracks']['items']
            
            # Cache for 1 hour
            await cache_manager.set(cache_key, tracks, ttl=3600)
            return tracks
            
        except Exception as e:
            logger.error(f"Error searching tracks: {str(e)}")
            return []
    
    async def get_track_details(self, track_id: str) -> Optional[Dict]:
        """Get detailed information about a specific track."""
        cache_key = f"spotify_track:{track_id}"
        cached_track = await cache_manager.get(cache_key)
        
        if cached_track:
            return cached_track
        
        try:
            await asyncio.sleep(self.rate_limit_delay)
            track = self.sp.track(track_id)
            
            # Cache for 24 hours
            await cache_manager.set(cache_key, track, ttl=86400)
            return track
            
        except Exception as e:
            logger.error(f"Error fetching track details for {track_id}: {str(e)}")
            return None
    
    async def get_audio_features(self, track_ids: List[str]) -> List[Dict]:
        """Get audio features for multiple tracks."""
        if not track_ids:
            return []
        
        # Check cache first
        cached_features = {}
        uncached_ids = []
        
        for track_id in track_ids:
            cache_key = f"spotify_audio_features:{track_id}"
            cached_feature = await cache_manager.get(cache_key)
            if cached_feature:
                cached_features[track_id] = cached_feature
            else:
                uncached_ids.append(track_id)
        
        # Fetch uncached features
        all_features = []
        if uncached_ids:
            try:
                # Process in batches of 100 (Spotify API limit)
                for i in range(0, len(uncached_ids), 100):
                    batch = uncached_ids[i:i+100]
                    await asyncio.sleep(self.rate_limit_delay)
                    
                    features = self.sp.audio_features(batch)
                    if features:
                        # Cache individual features
                        for feature in features:
                            if feature:  # Some tracks might not have audio features
                                cache_key = f"spotify_audio_features:{feature['id']}"
                                await cache_manager.set(cache_key, feature, ttl=86400)
                        
                        all_features.extend(features)
                        
            except Exception as e:
                logger.error(f"Error fetching audio features: {str(e)}")
        
        # Combine cached and newly fetched features
        result = []
        for track_id in track_ids:
            if track_id in cached_features:
                result.append(cached_features[track_id])
            else:
                # Find in newly fetched features
                found_feature = next((f for f in all_features if f and f['id'] == track_id), None)
                result.append(found_feature)
        
        return result
    
    async def get_recommendations(self, seed_tracks: List[str] = None,
                                seed_artists: List[str] = None,
                                seed_genres: List[str] = None,
                                target_features: Dict = None,
                                limit: int = 20) -> List[Dict]:
        """Get track recommendations from Spotify."""
        
        # Build recommendation parameters
        params = {'limit': limit}
        
        if seed_tracks:
            params['seed_tracks'] = seed_tracks[:5]  # Spotify limit
        if seed_artists:
            params['seed_artists'] = seed_artists[:5]  # Spotify limit
        if seed_genres:
            params['seed_genres'] = seed_genres[:5]  # Spotify limit
        
        # Add target audio features
        if target_features:
            for feature, value in target_features.items():
                if feature in ['acousticness', 'danceability', 'energy', 'instrumentalness', 
                              'liveness', 'speechiness', 'valence']:
                    params[f'target_{feature}'] = value
                elif feature == 'tempo':
                    params['target_tempo'] = value
                elif feature == 'popularity':
                    params['target_popularity'] = value
        
        # Create cache key
        cache_key = f"spotify_recommendations:{hash(str(sorted(params.items())))}"
        cached_recs = await cache_manager.get(cache_key)
        
        if cached_recs:
            return cached_recs
        
        try:
            await asyncio.sleep(self.rate_limit_delay)
            results = self.sp.recommendations(**params)
            tracks = results['tracks']
            
            # Cache for 30 minutes
            await cache_manager.set(cache_key, tracks, ttl=1800)
            return tracks
            
        except Exception as e:
            logger.error(f"Error getting Spotify recommendations: {str(e)}")
            return []
    
    async def get_artist_top_tracks(self, artist_id: str, country: str = 'US') -> List[Dict]:
        """Get artist's top tracks."""
        cache_key = f"spotify_artist_top:{artist_id}:{country}"
        cached_tracks = await cache_manager.get(cache_key)
        
        if cached_tracks:
            return cached_tracks
        
        try:
            await asyncio.sleep(self.rate_limit_delay)
            results = self.sp.artist_top_tracks(artist_id, country=country)
            tracks = results['tracks']
            
            # Cache for 12 hours
            await cache_manager.set(cache_key, tracks, ttl=43200)
            return tracks
            
        except Exception as e:
            logger.error(f"Error fetching artist top tracks: {str(e)}")
            return []
    
    async def get_related_artists(self, artist_id: str) -> List[Dict]:
        """Get artists related to the given artist."""
        cache_key = f"spotify_related_artists:{artist_id}"
        cached_artists = await cache_manager.get(cache_key)
        
        if cached_artists:
            return cached_artists
        
        try:
            await asyncio.sleep(self.rate_limit_delay)
            results = self.sp.artist_related_artists(artist_id)
            artists = results['artists']
            
            # Cache for 24 hours
            await cache_manager.set(cache_key, artists, ttl=86400)
            return artists
            
        except Exception as e:
            logger.error(f"Error fetching related artists: {str(e)}")
            return []
    
    def parse_spotify_track(self, spotify_track: Dict) -> Dict:
        """Parse Spotify track data into our format."""
        try:
            return {
                'spotify_id': spotify_track['id'],
                'title': spotify_track['name'],
                'artist': ', '.join([artist['name'] for artist in spotify_track['artists']]),
                'album': spotify_track['album']['name'],
                'duration_ms': spotify_track['duration_ms'],
                'popularity': spotify_track['popularity'],
                'explicit': spotify_track['explicit'],
                'preview_url': spotify_track.get('preview_url'),
                'external_urls': spotify_track.get('external_urls', {}),
                'release_date': spotify_track['album'].get('release_date'),
                'genres': spotify_track['album'].get('genres', [])
            }
        except KeyError as e:
            logger.error(f"Error parsing Spotify track data: missing key {e}")
            return {}
    
    def parse_audio_features(self, audio_features: Dict) -> Dict:
        """Parse Spotify audio features into our format."""
        if not audio_features:
            return {}
        
        try:
            return {
                'acousticness': audio_features.get('acousticness'),
                'danceability': audio_features.get('danceability'),
                'energy': audio_features.get('energy'),
                'instrumentalness': audio_features.get('instrumentalness'),
                'liveness': audio_features.get('liveness'),
                'loudness': audio_features.get('loudness'),
                'speechiness': audio_features.get('speechiness'),
                'tempo': audio_features.get('tempo'),
                'valence': audio_features.get('valence'),
                'key': audio_features.get('key'),
                'mode': audio_features.get('mode'),
                'time_signature': audio_features.get('time_signature')
            }
        except Exception as e:
            logger.error(f"Error parsing audio features: {str(e)}")
            return {}
    
    async def batch_import_tracks(self, track_ids: List[str]) -> List[Dict]:
        """Import multiple tracks with their audio features."""
        tracks_data = []
        
        # Get track details
        track_details = []
        for i in range(0, len(track_ids), 50):  # Process in batches
            batch = track_ids[i:i+50]
            try:
                await asyncio.sleep(self.rate_limit_delay)
                tracks = self.sp.tracks(batch)
                track_details.extend(tracks['tracks'])
            except Exception as e:
                logger.error(f"Error fetching track batch: {str(e)}")
        
        # Get audio features
        audio_features = await self.get_audio_features(track_ids)
        
        # Combine track details with audio features
        for track, features in zip(track_details, audio_features):
            if track and features:
                track_data = self.parse_spotify_track(track)
                track_data.update(self.parse_audio_features(features))
                tracks_data.append(track_data)
        
        return tracks_data
