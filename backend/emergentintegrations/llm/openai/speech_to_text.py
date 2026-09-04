import os
from typing import Dict, Optional
from pathlib import Path
from litellm import atranscription


class OpenAISpeechToText:
    """
    Speech-to-Text integration using OpenAI's transcription models via LiteLLM.
    Supports both direct OpenAI API keys and Emergent LLM key through proxy.
    """

    # Supported models
    MODELS = ["whisper-1"]

    # Supported response formats
    RESPONSE_FORMATS = {
        "whisper-1": ["json", "text", "srt", "verbose_json", "vtt"]
    }

    # Supported file formats
    FILE_FORMATS = ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]

    # Maximum file size in bytes (25 MB)
    MAX_FILE_SIZE = 25 * 1024 * 1024

    def __init__(self, api_key: str, custom_headers: Dict[str, str] = None):
        """
        Initialize the STT client.

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

    def _validate_audio_file(self, file) -> None:
        """
        Validate audio file format and size.

        Args:
            file: Audio file object or path

        Raises:
            ValueError: If file validation fails
        """
        # Check if file is a path string
        if isinstance(file, (str, Path)):
            file_path = Path(file)

            # Check if file exists
            if not file_path.exists():
                raise ValueError(f"File not found: {file}")

            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.MAX_FILE_SIZE:
                raise ValueError(
                    f"File size ({file_size} bytes) exceeds maximum allowed size "
                    f"({self.MAX_FILE_SIZE} bytes / 25 MB)"
                )

            # Check file format
            file_extension = file_path.suffix.lstrip('.').lower()
            if file_extension not in self.FILE_FORMATS:
                raise ValueError(
                    f"Unsupported file format: {file_extension}. "
                    f"Supported formats: {', '.join(self.FILE_FORMATS)}"
                )
        # If file is a file object, check if it has a name attribute
        elif hasattr(file, 'name'):
            # Check file size if possible
            if hasattr(file, 'seek') and hasattr(file, 'tell'):
                current_pos = file.tell()
                file.seek(0, 2)  # Seek to end
                file_size = file.tell()
                file.seek(current_pos)  # Reset to original position
                
                if file_size > self.MAX_FILE_SIZE:
                    raise ValueError(
                        f"File size ({file_size} bytes) exceeds maximum allowed size "
                        f"({self.MAX_FILE_SIZE} bytes / 25 MB)"
                    )
            
            # Check file format
            file_extension = Path(file.name).suffix.lstrip('.').lower()
            if file_extension and file_extension not in self.FILE_FORMATS:
                raise ValueError(
                    f"Unsupported file format: {file_extension}. "
                    f"Supported formats: {', '.join(self.FILE_FORMATS)}"
                )

    async def transcribe(
        self,
        file,
        model: str = "whisper-1",
        response_format: str = "json",
        prompt: Optional[str] = None,
        language: Optional[str] = None,
        temperature: Optional[float] = None,
        timestamp_granularities: Optional[list] = None
    ):
        """
        Transcribe audio into the language of the input audio.

        Args:
            file: Audio file object or path (mp3, mp4, mpeg, mpga, m4a, wav, webm)
            model: Model to use ('whisper-1')
            response_format: Format of transcript output
            prompt: Optional text to guide the model's style
            language: Language of the input audio (ISO-639-1 format)
            temperature: Sampling temperature between 0 and 1
            timestamp_granularities: Timestamp granularities (only for whisper-1 with verbose_json)

        Returns:
            Transcription response object

        Raises:
            ValueError: If validation fails
            Exception: If transcription fails
        """
        try:
            # Validate file
            self._validate_audio_file(file)

            # Validate model
            if model not in self.MODELS:
                raise ValueError(f"Invalid model: {model}. Must be one of {self.MODELS}")

            # Validate response format for the model
            if response_format not in self.RESPONSE_FORMATS.get(model, []):
                raise ValueError(
                    f"Invalid response_format '{response_format}' for model '{model}'. "
                    f"Supported formats: {self.RESPONSE_FORMATS[model]}"
                )

            # Validate timestamp_granularities
            if timestamp_granularities and response_format != "verbose_json":
                raise ValueError("timestamp_granularities requires response_format='verbose_json'")

            # Prepare parameters for litellm.transcription()
            params = {
                "model": f"openai/{model}",
                "file": file,
                "api_key": self.api_key,
                "response_format": response_format,
            }

            # Add optional parameters
            if prompt:
                params["prompt"] = prompt

            if language:
                params["language"] = language

            if temperature is not None:
                if temperature < 0 or temperature > 1:
                    raise ValueError("Temperature must be between 0 and 1")
                params["temperature"] = temperature

            if timestamp_granularities:
                params["timestamp_granularities"] = timestamp_granularities

            # If using Emergent key, configure proxy
            if self._is_emergent_key(self.api_key):
                params["api_base"] = self.emergent_proxy_url
                params["custom_llm_provider"] = "openai"

                # Add custom headers when using Emergent proxy
                if self.custom_headers:
                    params["extra_headers"] = self.custom_headers

            # Transcribe using litellm
            response = await atranscription(**params)

            return response

        except ValueError as ve:
            raise ValueError(f"Validation error: {str(ve)}")
        except Exception as e:
            raise Exception(f"Failed to transcribe audio: {str(e)}")
