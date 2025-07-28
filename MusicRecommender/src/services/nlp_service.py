import nltk
from textblob import TextBlob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import numpy as np
import re
from typing import Dict, List, Optional, Tuple
import logging

from ..core.cache import cache_manager

logger = logging.getLogger(__name__)

class NLPService:
    def __init__(self):
        # Download required NLTK data
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            nltk.download('vader_lexicon', quiet=True)
        except:
            pass
        
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.theme_clusters = None
        
    def extract_lyric_themes(self, lyrics: str) -> Dict:
        """Extract themes and topics from song lyrics."""
        if not lyrics:
            return {}
        
        try:
            # Clean lyrics
            cleaned_lyrics = self._clean_lyrics(lyrics)
            
            if not cleaned_lyrics:
                return {}
            
            # Extract themes using keyword analysis
            themes = self._extract_themes_keywords(cleaned_lyrics)
            
            # Sentiment analysis
            sentiment = self.analyze_sentiment(cleaned_lyrics)
            
            # Complexity analysis
            complexity = self._analyze_complexity(cleaned_lyrics)
            
            return {
                'themes': themes,
                'sentiment': sentiment,
                'complexity': complexity,
                'word_count': len(cleaned_lyrics.split()),
                'language': self._detect_language(lyrics)
            }
            
        except Exception as e:
            logger.error(f"Error extracting lyric themes: {str(e)}")
            return {}
    
    def _clean_lyrics(self, lyrics: str) -> str:
        """Clean and preprocess lyrics."""
        # Remove common song structure indicators
        structure_words = ['[verse]', '[chorus]', '[bridge]', '[outro]', '[intro]', 
                          '[pre-chorus]', '[hook]', '[refrain]']
        
        cleaned = lyrics.lower()
        for word in structure_words:
            cleaned = cleaned.replace(word, '')
        
        # Remove repeated whitespace and newlines
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = re.sub(r'\n+', '\n', cleaned)
        
        # Remove special characters but keep basic punctuation
        cleaned = re.sub(r'[^\w\s\.,!?]', '', cleaned)
        
        return cleaned.strip()
    
    def _extract_themes_keywords(self, lyrics: str) -> List[str]:
        """Extract themes using keyword analysis."""
        
        # Define theme keywords
        theme_keywords = {
            'love': ['love', 'heart', 'kiss', 'romance', 'together', 'forever', 'baby', 'darling'],
            'breakup': ['goodbye', 'leave', 'apart', 'break', 'over', 'done', 'end', 'miss'],
            'party': ['party', 'dance', 'night', 'club', 'drink', 'fun', 'celebration', 'weekend'],
            'sadness': ['sad', 'cry', 'tears', 'lonely', 'hurt', 'pain', 'broken', 'depression'],
            'happiness': ['happy', 'joy', 'smile', 'laugh', 'celebration', 'bright', 'sunshine'],
            'freedom': ['free', 'freedom', 'fly', 'escape', 'independence', 'liberation', 'break free'],
            'nature': ['sun', 'moon', 'stars', 'ocean', 'mountain', 'sky', 'earth', 'river'],
            'struggle': ['fight', 'battle', 'struggle', 'hard', 'difficult', 'challenge', 'overcome'],
            'nostalgia': ['remember', 'memories', 'past', 'yesterday', 'childhood', 'old days'],
            'spirituality': ['god', 'heaven', 'soul', 'spirit', 'faith', 'prayer', 'divine', 'blessed']
        }
        
        detected_themes = []
        lyrics_words = set(lyrics.lower().split())
        
        for theme, keywords in theme_keywords.items():
            matches = len(set(keywords) & lyrics_words)
            if matches >= 2:  # Require at least 2 keyword matches
                detected_themes.append(theme)
        
        return detected_themes
    
    def analyze_sentiment(self, text: str) -> Dict:
        """Analyze sentiment of text."""
        try:
            blob = TextBlob(text)
            
            # TextBlob sentiment
            polarity = blob.sentiment.polarity  # -1 to 1
            subjectivity = blob.sentiment.subjectivity  # 0 to 1
            
            # Convert to categorical
            if polarity > 0.1:
                sentiment_label = 'positive'
            elif polarity < -0.1:
                sentiment_label = 'negative'
            else:
                sentiment_label = 'neutral'
            
            return {
                'polarity': polarity,
                'subjectivity': subjectivity,
                'label': sentiment_label
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {str(e)}")
            return {'polarity': 0.0, 'subjectivity': 0.0, 'label': 'neutral'}
    
    def _analyze_complexity(self, text: str) -> Dict:
        """Analyze text complexity."""
        words = text.split()
        sentences = text.split('.')
        
        if not words:
            return {'score': 0.0, 'level': 'simple'}
        
        # Basic complexity metrics
        avg_word_length = np.mean([len(word) for word in words])
        avg_sentence_length = np.mean([len(sent.split()) for sent in sentences if sent.strip()])
        unique_words_ratio = len(set(words)) / len(words)
        
        # Calculate complexity score (0-1)
        complexity_score = (
            min(avg_word_length / 10, 1) * 0.3 +
            min(avg_sentence_length / 20, 1) * 0.4 +
            unique_words_ratio * 0.3
        )
        
        # Categorize complexity
        if complexity_score < 0.3:
            level = 'simple'
        elif complexity_score < 0.7:
            level = 'moderate'
        else:
            level = 'complex'
        
        return {
            'score': complexity_score,
            'level': level,
            'avg_word_length': avg_word_length,
            'avg_sentence_length': avg_sentence_length,
            'unique_words_ratio': unique_words_ratio
        }
    
    def _detect_language(self, text: str) -> str:
        """Detect language of text."""
        try:
            blob = TextBlob(text)
            return blob.detect_language()
        except:
            return 'unknown'
    
    def create_thematic_playlists(self, songs_with_lyrics: List[Dict]) -> Dict[str, List[int]]:
        """Group songs by themes for thematic playlists."""
        
        theme_groups = {}
        
        for song_data in songs_with_lyrics:
            song_id = song_data['song_id']
            themes = song_data.get('themes', [])
            
            for theme in themes:
                if theme not in theme_groups:
                    theme_groups[theme] = []
                theme_groups[theme].append(song_id)
        
        # Filter groups with sufficient songs
        filtered_groups = {
            theme: song_ids for theme, song_ids in theme_groups.items()
            if len(song_ids) >= 10  # Minimum songs for a thematic playlist
        }
        
        return filtered_groups
    
    async def analyze_song_lyrics(self, song_id: int, lyrics: str) -> Dict:
        """Analyze lyrics for a specific song."""
        cache_key = f"lyrics_analysis:{song_id}"
        
        # Check cache first
        cached_analysis = await cache_manager.get(cache_key)
        if cached_analysis:
            return cached_analysis
        
        # Perform analysis
        analysis = self.extract_lyric_themes(lyrics)
        
        # Cache result
        await cache_manager.set(cache_key, analysis, ttl=86400)  # Cache for 24 hours
        
        return analysis
    
    def suggest_playlist_names(self, dominant_themes: List[str], 
                             mood: Optional[str] = None) -> List[str]:
        """Suggest creative playlist names based on themes and mood."""
        
        name_templates = {
            'love': [
                "Love Songs Collection",
                "Romantic Vibes",
                "Heart & Soul",
                "Love Letters in Music"
            ],
            'party': [
                "Party Mix",
                "Dance Floor Hits",
                "Weekend Vibes",
                "Turn Up Time"
            ],
            'sadness': [
                "Melancholy Moments",
                "Rainy Day Blues",
                "Emotional Journey",
                "Healing Hearts"
            ],
            'happiness': [
                "Feel Good Hits",
                "Sunshine Playlist",
                "Happy Vibes Only",
                "Good Mood Music"
            ],
            'nostalgia': [
                "Memory Lane",
                "Throwback Thursday",
                "Nostalgic Journey",
                "Golden Memories"
            ]
        }
        
        suggested_names = []
        
        # Add theme-based names
        for theme in dominant_themes:
            if theme in name_templates:
                suggested_names.extend(name_templates[theme])
        
        # Add mood-based names if provided
        if mood and mood in name_templates:
            suggested_names.extend(name_templates[mood])
        
        # Add some generic creative names
        suggested_names.extend([
            "My Curated Mix",
            "Personal Soundtrack",
            "Musical Journey",
            "Vibe Check",
            "Sound Therapy"
        ])
        
        return list(set(suggested_names))  # Remove duplicates
