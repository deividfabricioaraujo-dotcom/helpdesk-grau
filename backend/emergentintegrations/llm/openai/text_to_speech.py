import os
from typing import Dict, Literal, Optional
from litellm import speech
import base64


class OpenAITextToSpeech:
    """
    Text-to-Speech integration using OpenAI's TTS models via LiteLLM.
    Supports both direct OpenAI API keys and Emergent LLM key through proxy.
    """

    # Supported models
    MODELS = ["tts-1", "tts-1-hd"]

    # Supported voices (9 voices for tts-1 and tts-1-hd)
    # Note: 'ballad' and 'verse' are only available with gpt-4o-mini-tts
    VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]

    # Supported formats (6 formats available)
    FORMATS = ["mp3", "opus", "aac", "flac", "wav", "pcm"]

    def __init__(self, api_key: str, custom_headers: Dict[str, str] = None):
        """
        Initialize the TTS client.

        Args:
            api_key: OpenAI API key or Emergent LLM key (starts with 'sk-emergent-')
            custom_headers: Custom headers to include in requests
        """
        self.api_key = api_key
        proxy_url = os.getenv("INTEGRATION_PROXY_URL", "https://integrations.emergentagent.com")
        self.emergent_proxy_url = proxy_url + "/llm"
        self.custom_headers = custom_headers or {}

        app_url = os.getenv('APP_URL')
        if app_url:
            self.custom_headers['X-App-ID'] = app_url

    def _is_emergent_key(self, api_key: str) -> bool:
        """Check if the API key is an Emergent LLM key."""
        return api_key.startswith("sk-emergent-")

    async def generate_speech(
        self,
        text: str,
        model: str = "tts-1",
        voice: Literal["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"] = "alloy",
        speed: float = 1.0,
        response_format: str = "mp3"
    ) -> bytes:
        """
        Generate speech audio from text using OpenAI's TTS models.

        Args:
            text: The text to convert to speech (max 4096 characters)
            model: The TTS model to use ('tts-1' or 'tts-1-hd')
            voice: The voice to use (alloy, ash, coral, echo, fable, nova, onyx, sage, shimmer)
            speed: Speed of the generated audio (0.25 to 4.0)
            response_format: Audio format (mp3, opus, aac, flac, wav, pcm)

        Returns:
            bytes: Generated audio data as bytes

        Raises:
            ValueError: If validation fails
            Exception: If speech generation fails
        """
        try:
            # Validate inputs
            if not text or len(text.strip()) == 0:
                raise ValueError("Text cannot be empty")

            if len(text) > 4096:
                raise ValueError("Text must be 4096 characters or less")

            if model not in self.MODELS:
                raise ValueError(f"Invalid model: {model}. Must be one of {self.MODELS}")

            if voice not in self.VOICES:
                raise ValueError(f"Invalid voice: {voice}. Must be one of {self.VOICES}")

            if speed < 0.25 or speed > 4.0:
                raise ValueError("Speed must be between 0.25 and 4.0")

            if response_format not in self.FORMATS:
                raise ValueError(f"Invalid format: {response_format}. Must be one of {self.FORMATS}")

            # Prepare parameters for litellm.speech()
            params = {
                "model": f"openai/{model}",
                "input": text,
                "voice": voice,
                "api_key": self.api_key,
            }

            # Add optional parameters
            if speed != 1.0:
                params["speed"] = speed

            if response_format != "mp3":
                params["response_format"] = response_format

            # If using Emergent key, configure proxy
            if self._is_emergent_key(self.api_key):
                params["api_base"] = self.emergent_proxy_url
                params["custom_llm_provider"] = "openai"

                # Add custom headers when using Emergent proxy
                if self.custom_headers:
                    params["extra_headers"] = self.custom_headers

            # Generate speech using litellm
            response = speech(**params)

            # The response is a HttpxBinaryResponseContent object
            # Read the content as bytes
            if hasattr(response, 'content'):
                return response.content
            elif hasattr(response, 'read'):
                return response.read()
            else:
                # Fallback: try to get bytes directly
                return bytes(response)

        except ValueError as ve:
            raise ValueError(f"Validation error: {str(ve)}")
        except Exception as e:
            raise Exception(f"Failed to generate speech: {str(e)}")

    async def generate_speech_base64(
        self,
        text: str,
        model: str = "tts-1",
        voice: Literal["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"] = "alloy",
        speed: float = 1.0,
        response_format: str = "mp3"
    ) -> str:
        """
        Generate speech and return as base64 encoded string.
        Useful for embedding audio in JSON responses.

        Args:
            text: The text to convert to speech
            model: The TTS model to use ('tts-1' or 'tts-1-hd')
            voice: The voice to use (9 voices supported)
            speed: Speed of the generated audio
            response_format: Audio format

        Returns:
            str: Base64 encoded audio data
        """
        audio_bytes = await self.generate_speech(
            text=text,
            model=model,
            voice=voice,
            speed=speed,
            response_format=response_format
        )
        return base64.b64encode(audio_bytes).decode('utf-8')
