"""
Emotion detection service using singleton pattern
Enterprise-grade with comprehensive logging
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EmotionService:
    """
    Singleton service for emotion analysis from text
    Uses keyword-based sentiment analysis
    """
    _instance: Optional['EmotionService'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmotionService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.emotion_keywords = {
                'happy': ['happy', 'great', 'excellent', 'wonderful', 'amazing', 'joy', 'delighted', 'pleased', 'smile', 'laugh', 'cheerful'],
                'sad': ['sad', 'sorry', 'unfortunate', 'disappointed', 'regret', 'unhappy', 'depressed', 'down'],
                'excited': ['excited', 'thrilled', 'awesome', 'fantastic', 'incredible', 'wow', 'amazing'],
                'calm': ['calm', 'peaceful', 'relaxed', 'serene', 'tranquil', 'quiet'],
                'concerned': ['concern', 'worry', 'anxious', 'troubled', 'problem', 'issue'],
                'friendly': ['hello', 'hi', 'help', 'assist', 'welcome', 'glad', 'pleasure', 'namaste']
            }
            self.default_emotion = 'friendly'
            self._initialized = True
            
            logger.info(
                "EmotionService initialized - emotions: %d, default: %s",
                len(self.emotion_keywords),
                self.default_emotion
            )
    
    def analyze_emotion(self, text: str) -> Dict[str, Any]:
        """
        Analyze emotion from text using keyword matching
        
        Args:
            text: Text to analyze for emotion
            
        Returns:
            Dictionary with 'emotion' (str) and 'intensity' (float 0-1)
        """
        if not text or not text.strip():
            logger.debug("Empty text for emotion analysis, using default")
            return {
                'emotion': self.default_emotion,
                'intensity': 0.5
            }
        
        text_lower = text.lower()
        text_length = len(text)
        emotion_scores = {}
        
        logger.debug("Analyzing emotion for text: %d chars, preview: '%s'", text_length, text[:50])
        
        # Score each emotion based on keyword matches
        for emotion, keywords in self.emotion_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                emotion_scores[emotion] = score
        
        # Determine dominant emotion
        if emotion_scores:
            dominant_emotion = max(emotion_scores, key=emotion_scores.get)
            max_score = emotion_scores[dominant_emotion]
            intensity = min(max_score / 3.0, 1.0)  # Normalize to 0-1 range
            
            logger.debug(
                "Emotion detected - emotion: %s, intensity: %.2f, scores: %s",
                dominant_emotion,
                intensity,
                emotion_scores
            )
        else:
            dominant_emotion = self.default_emotion
            intensity = 0.5
            
            logger.debug(
                "No emotion keywords found, using default - emotion: %s, intensity: %.2f",
                dominant_emotion,
                intensity
            )
        
        result = {
            'emotion': dominant_emotion,
            'intensity': intensity
        }
        
        logger.info(
            "Emotion analysis complete - text: %d chars, emotion: %s (%.2f)",
            text_length,
            dominant_emotion,
            intensity
        )
        
        return result
    
    @classmethod
    def get_instance(cls) -> 'EmotionService':
        """Get singleton instance"""
        return cls()
