"""
Azure Speech Services TTS Integration (REST API)
===============================================

This module provides Azure Speech Services integration using the REST API for high-quality, 
low-latency text-to-speech synthesis. This approach is more reliable in container environments
than the Azure Speech SDK.

Key Features:
- Azure Speech Services REST API integration
- Neural voice synthesis with SSML support
- In-memory audio caching for performance
- Graceful fallback to Twilio TTS
- Comprehensive logging and error handling
- Async/await support for non-blocking operations

Performance Benefits:
- ~100-200ms latency vs 500-800ms for Twilio Polly
- More natural-sounding voices
- Better pronunciation of names and technical terms
- SSML support for pacing and emphasis
- Container-compatible REST API approach
"""

import asyncio
import base64
import logging
import time
from typing import Optional, Dict
import aiohttp
from config import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, TTS_VOICE, USE_AZURE_TTS

# Simple in-memory cache for common responses
# In production, consider using Redis for distributed caching
_audio_cache: Dict[str, str] = {}

class AzureTTSService:
    """
    Azure Speech Services TTS service using REST API for high-quality voice synthesis
    """
    
    def __init__(self):
        self.session = None
        self.base_url = None
        self.headers = None
        try:
            if not USE_AZURE_TTS or not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
                logging.warning("[TTS] Azure TTS disabled or missing config. Will fallback to Twilio TTS.")
                return
            logging.info(f"[TTS] Initializing Azure TTS REST API with region={AZURE_SPEECH_REGION}, voice={TTS_VOICE}")
            self.base_url = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
            self.headers = {
                "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
                "User-Agent": "AI-Voice-Concierge/1.0"
            }
            logging.info(f"[TTS] Azure TTS REST API Service initialized with voice: {TTS_VOICE}")
        except Exception as e:
            logging.error(f"[TTS] Exception initializing Azure TTS REST API: {e}")
            self.base_url = None

    async def _get_session(self) -> Optional[aiohttp.ClientSession]:
        """Get or create aiohttp session for making requests."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def generate_audio(self, text: str, use_cache: bool = True) -> Optional[str]:
        """
        Generate audio using Azure Speech Services REST API
        
        Args:
            text: Text to synthesize
            use_cache: Whether to use audio caching
            
        Returns:
            Base64 encoded audio data or None if synthesis fails
        """
        if not text or not text.strip():
            logging.warning("[TTS] Empty text provided to TTS service")
            return None
        if not self.base_url:
            logging.info("[TTS] Azure TTS not available, will fallback to Twilio TTS")
            return None
        if use_cache and text in _audio_cache:
            logging.info(f"[TTS] Using cached audio for text: {text[:50]}...")
            # Temporarily disable caching to test new audio serving approach
            # return _audio_cache[text]
            logging.info(f"[TTS] Cache disabled - generating fresh audio for testing")
        
        try:
            logging.info(f"[TTS] Generating Azure TTS audio for: {text[:50]}... (region={AZURE_SPEECH_REGION}, voice={TTS_VOICE})")
            start = time.time()
            
            ssml = self.create_ssml(text)
            
            session = await self._get_session()
            async with session.post(
                self.base_url,
                headers=self.headers,
                data=ssml.encode('utf-8')
            ) as response:
                elapsed = time.time() - start
                logging.info(f"[TTS] Azure TTS REST API request took {elapsed:.2f}s")
                
                if response.status == 200:
                    audio_data = await response.read()
                    
                    # Validate audio data
                    if len(audio_data) == 0:
                        logging.error("[TTS] Azure TTS returned empty audio data")
                        return None
                    
                    # Check if it's valid WAV data (should start with "RIFF")
                    if len(audio_data) >= 4 and audio_data[:4] != b'RIFF':
                        logging.error(f"[TTS] Invalid audio format - expected WAV (RIFF header), got: {audio_data[:10]}")
                        return None
                    
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    
                    # Validate base64 encoding
                    if len(audio_base64) == 0:
                        logging.error("[TTS] Failed to encode audio data to base64")
                        return None
                    
                    if use_cache and len(text) < 200:
                        _audio_cache[text] = audio_base64
                        logging.info(f"[TTS] Cached audio for text: {text[:50]}...")
                    
                    logging.info(f"[TTS] Successfully generated Azure TTS audio ({len(audio_base64)} chars, {len(audio_data)} bytes)")
                    return audio_base64
                else:
                    error_text = await response.text()
                    logging.error(f"[TTS] Azure TTS REST API failed with status {response.status}: {error_text}")
                    return None
                    
        except Exception as e:
            logging.error(f"[TTS] Azure TTS REST API error: {str(e)}")
            return None

    async def generate_ssml_audio(self, ssml: str, use_cache: bool = True) -> Optional[str]:
        if not ssml or not ssml.strip():
            logging.warning("[TTS] Empty SSML provided to TTS service")
            return None
        if not self.base_url:
            logging.info("[TTS] Azure TTS not available, will fallback to Twilio TTS")
            return None
        if use_cache and ssml in _audio_cache:
            logging.info(f"[TTS] Using cached audio for SSML: {ssml[:50]}...")
            return _audio_cache[ssml]
        
        try:
            logging.info(f"[TTS] Generating Azure TTS audio from SSML: {ssml[:50]}... (region={AZURE_SPEECH_REGION}, voice={TTS_VOICE})")
            start = time.time()
            
            session = await self._get_session()
            async with session.post(
                self.base_url,
                headers=self.headers,
                data=ssml.encode('utf-8')
            ) as response:
                elapsed = time.time() - start
                logging.info(f"[TTS] Azure TTS REST API SSML request took {elapsed:.2f}s")
                
                if response.status == 200:
                    audio_data = await response.read()
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    
                    if use_cache and len(ssml) < 200:
                        _audio_cache[ssml] = audio_base64
                        logging.info(f"[TTS] Cached audio for SSML: {ssml[:50]}...")
                    
                    logging.info(f"[TTS] Successfully generated Azure TTS SSML audio ({len(audio_base64)} chars)")
                    return audio_base64
                else:
                    error_text = await response.text()
                    logging.error(f"[TTS] Azure TTS REST API SSML failed with status {response.status}: {error_text}")
                    return None
                    
        except Exception as e:
            logging.error(f"[TTS] Azure TTS REST API SSML error: {str(e)}")
            return None

    def create_ssml(self, text: str, voice: str = None, rate: str = "medium", pitch: str = "medium") -> str:
        """
        Create SSML markup for enhanced speech synthesis.
        
        Args:
            text: The text to synthesize
            voice: Voice name (defaults to TTS_VOICE from config)
            rate: Speaking rate (slow, medium, fast)
            pitch: Pitch level (low, medium, high)
            
        Returns:
            SSML string for Azure Speech Services REST API
        """
        voice_name = voice or TTS_VOICE
        rate_map = {"slow": "slow", "medium": "medium", "fast": "fast"}
        pitch_map = {"low": "low", "medium": "medium", "high": "high"}
        
        rate_value = rate_map.get(rate, "medium")
        pitch_value = pitch_map.get(pitch, "medium")
        
        # Clean text for SSML (escape special characters)
        clean_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
            <voice name="{voice_name}">
                <prosody rate="{rate_value}" pitch="{pitch_value}">
                    {clean_text}
                </prosody>
            </voice>
        </speak>"""
        
        return ssml.strip()

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    def clear_cache(self):
        """Clear the audio cache"""
        global _audio_cache
        _audio_cache.clear()
        logging.info("TTS audio cache cleared")

# Global TTS service instance
_tts_service: Optional[AzureTTSService] = None

def get_tts_service() -> AzureTTSService:
    """Get or create the global TTS service instance"""
    global _tts_service
    if _tts_service is None:
        _tts_service = AzureTTSService()
    return _tts_service

async def generate_tts_audio(text: str, use_ssml: bool = False, **kwargs) -> Optional[str]:
    """
    Convenience function to generate TTS audio using Azure Speech Services REST API
    
    Args:
        text: Text to synthesize
        use_ssml: Whether to use SSML for better control
        **kwargs: Additional arguments for SSML creation
        
    Returns:
        Base64 encoded audio data or None if synthesis fails
    """
    service = get_tts_service()
    
    if use_ssml:
        ssml = service.create_ssml(text, **kwargs)
        return await service.generate_ssml_audio(ssml)
    else:
        return await service.generate_audio(text) 