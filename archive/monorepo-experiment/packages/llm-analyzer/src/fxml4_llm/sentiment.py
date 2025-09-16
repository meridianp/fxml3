"""
Sentiment analysis using LLM.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import re
import asyncio

from fxml4_core.logging import get_logger
from fxml4_llm.client import LLMClient

logger = get_logger(__name__)


class SentimentAnalyzer:
    """Analyze sentiment from text using LLM."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.sentiment_cache = {}
    
    async def analyze_text(
        self,
        text: str,
        context: Optional[str] = None,
        asset: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze sentiment of given text."""
        # Check cache
        cache_key = hash(text[:100])  # Use first 100 chars for cache key
        if cache_key in self.sentiment_cache:
            return self.sentiment_cache[cache_key]
        
        prompt = self._build_sentiment_prompt(text, context, asset)
        
        response = await self.llm.complete(
            prompt,
            system="You are a financial sentiment analyst. Analyze text for market sentiment "
                   "and provide structured output with scores."
        )
        
        # Parse response
        result = self._parse_sentiment_response(response, text)
        
        # Cache result
        self.sentiment_cache[cache_key] = result
        
        return result
    
    async def analyze_news_batch(
        self,
        news_items: List[Dict[str, Any]],
        asset: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze sentiment for multiple news items."""
        if not news_items:
            return {
                "overall_sentiment": 0,
                "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0},
                "high_impact_items": [],
                "summary": "No news items to analyze"
            }
        
        # Analyze each item
        tasks = []
        for item in news_items:
            task = self.analyze_text(
                text=f"{item.get('title', '')} {item.get('content', '')}",
                context="financial_news",
                asset=asset
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # Aggregate results
        return self._aggregate_sentiment_results(results, news_items)
    
    async def analyze_market_mood(
        self,
        social_data: List[Dict[str, Any]],
        news_data: List[Dict[str, Any]],
        asset: str
    ) -> Dict[str, Any]:
        """Analyze overall market mood from multiple sources."""
        # Prepare combined text
        combined_text = self._prepare_market_mood_text(social_data, news_data)
        
        prompt = f"""Analyze the overall market mood for {asset} based on the following data:

{combined_text}

Provide:
1. Overall market sentiment score (-1 to 1)
2. Key themes and concerns
3. Sentiment trend (improving/deteriorating/stable)
4. Risk factors identified
5. Contrarian indicators if any
"""
        
        response = await self.llm.complete(prompt)
        
        return {
            "asset": asset,
            "timestamp": datetime.now(),
            "mood_analysis": response,
            "data_sources": {
                "social_posts": len(social_data),
                "news_items": len(news_data)
            }
        }
    
    async def analyze_event_impact(
        self,
        event: Dict[str, Any],
        historical_context: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Analyze potential market impact of an event."""
        prompt = f"""Analyze the potential market impact of the following event:

Event: {event.get('title', 'Unknown')}
Type: {event.get('type', 'Unknown')}
Time: {event.get('time', 'Unknown')}
Description: {event.get('description', 'No description')}

"""
        
        if historical_context:
            prompt += "Historical Context:\n"
            for ctx in historical_context[:3]:
                prompt += f"- {ctx.get('event')}: {ctx.get('impact')}\n"
        
        prompt += """
Assess:
1. Expected market impact (High/Medium/Low)
2. Affected currency pairs
3. Direction of impact (Bullish/Bearish/Neutral)
4. Duration of impact (Short-term/Medium-term/Long-term)
5. Key levels to watch
"""
        
        response = await self.llm.complete(prompt)
        
        return {
            "event": event.get('title'),
            "timestamp": datetime.now(),
            "impact_analysis": response
        }
    
    def _build_sentiment_prompt(
        self,
        text: str,
        context: Optional[str],
        asset: Optional[str]
    ) -> str:
        """Build sentiment analysis prompt."""
        prompt = "Analyze the sentiment of the following text"
        
        if context:
            prompt += f" in the context of {context}"
        
        if asset:
            prompt += f" regarding {asset}"
        
        prompt += f":\n\n{text}\n\n"
        
        prompt += """Provide:
1. Sentiment score (-1 to 1, where -1 is very negative, 0 is neutral, 1 is very positive)
2. Confidence level (0-1)
3. Key phrases that influenced the sentiment
4. Market impact assessment (High/Medium/Low/None)
5. Brief explanation

Format as:
SENTIMENT_SCORE: [score]
CONFIDENCE: [confidence]
KEY_PHRASES: [phrase1], [phrase2], ...
IMPACT: [impact level]
EXPLANATION: [explanation]
"""
        
        return prompt
    
    def _parse_sentiment_response(self, response: str, original_text: str) -> Dict[str, Any]:
        """Parse sentiment analysis response."""
        result = {
            "text": original_text[:200] + "..." if len(original_text) > 200 else original_text,
            "timestamp": datetime.now(),
            "sentiment_score": 0,
            "confidence": 0,
            "key_phrases": [],
            "impact": "None",
            "explanation": ""
        }
        
        # Parse structured response
        lines = response.strip().split('\n')
        for line in lines:
            if line.startswith("SENTIMENT_SCORE:"):
                try:
                    result["sentiment_score"] = float(line.split(":", 1)[1].strip())
                except:
                    pass
            
            elif line.startswith("CONFIDENCE:"):
                try:
                    result["confidence"] = float(line.split(":", 1)[1].strip())
                except:
                    pass
            
            elif line.startswith("KEY_PHRASES:"):
                phrases = line.split(":", 1)[1].strip()
                result["key_phrases"] = [p.strip() for p in phrases.split(",")]
            
            elif line.startswith("IMPACT:"):
                result["impact"] = line.split(":", 1)[1].strip()
            
            elif line.startswith("EXPLANATION:"):
                result["explanation"] = line.split(":", 1)[1].strip()
        
        # Determine sentiment category
        score = result["sentiment_score"]
        if score > 0.3:
            result["sentiment"] = "positive"
        elif score < -0.3:
            result["sentiment"] = "negative"
        else:
            result["sentiment"] = "neutral"
        
        return result
    
    def _aggregate_sentiment_results(
        self,
        results: List[Dict[str, Any]],
        news_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate sentiment results from multiple items."""
        if not results:
            return {
                "overall_sentiment": 0,
                "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0},
                "high_impact_items": []
            }
        
        # Calculate weighted average sentiment
        total_weight = 0
        weighted_sentiment = 0
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        high_impact_items = []
        
        for i, result in enumerate(results):
            weight = result.get("confidence", 0.5)
            sentiment_score = result.get("sentiment_score", 0)
            
            weighted_sentiment += sentiment_score * weight
            total_weight += weight
            
            # Count sentiment distribution
            sentiment_counts[result.get("sentiment", "neutral")] += 1
            
            # Identify high impact items
            if result.get("impact") in ["High", "Medium"]:
                high_impact_items.append({
                    "title": news_items[i].get("title", "Unknown"),
                    "sentiment": result.get("sentiment"),
                    "impact": result.get("impact"),
                    "score": sentiment_score
                })
        
        overall_sentiment = weighted_sentiment / total_weight if total_weight > 0 else 0
        
        # Convert counts to percentages
        total_items = len(results)
        sentiment_distribution = {
            k: (v / total_items * 100) for k, v in sentiment_counts.items()
        }
        
        return {
            "overall_sentiment": overall_sentiment,
            "sentiment_distribution": sentiment_distribution,
            "high_impact_items": high_impact_items,
            "total_items_analyzed": total_items,
            "timestamp": datetime.now()
        }
    
    def _prepare_market_mood_text(
        self,
        social_data: List[Dict[str, Any]],
        news_data: List[Dict[str, Any]]
    ) -> str:
        """Prepare text for market mood analysis."""
        text = "SOCIAL MEDIA SENTIMENT:\n"
        
        # Add top social posts
        for post in social_data[:10]:
            text += f"- {post.get('content', '')} (engagement: {post.get('engagement', 0)})\n"
        
        text += "\nNEWS HEADLINES:\n"
        
        # Add news headlines
        for news in news_data[:10]:
            text += f"- {news.get('title', '')} ({news.get('source', 'Unknown')})\n"
        
        return text