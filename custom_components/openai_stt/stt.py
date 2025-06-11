from __future__ import annotations

from collections.abc import AsyncIterable
import io
import logging
import struct
import wave

import httpx
import voluptuous as vol

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    Provider,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client

_LOGGER = logging.getLogger(__name__)


CONF_API_URL = "api_url"

DEFAULT_API_URL = "http://sanjeev-debian-llm-vm:9000"

SUPPORTED_LANGUAGES = [
    "af",
    "ar",
    "hy",
    "az",
    "be",
    "bs",
    "bg",
    "ca",
    "zh",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "et",
    "fi",
    "fr",
    "gl",
    "de",
    "el",
    "he",
    "hi",
    "hu",
    "is",
    "id",
    "it",
    "ja",
    "kn",
    "kk",
    "ko",
    "lv",
    "lt",
    "mk",
    "ms",
    "mr",
    "mi",
    "ne",
    "no",
    "fa",
    "pl",
    "pt",
    "ro",
    "ru",
    "sr",
    "sk",
    "sl",
    "es",
    "sw",
    "sv",
    "tl",
    "ta",
    "th",
    "tr",
    "uk",
    "ur",
    "vi",
    "cy",
]

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_API_URL, default=DEFAULT_API_URL): cv.string,
    }
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up the Local Whisper STT component."""
    api_url = config.get(CONF_API_URL, DEFAULT_API_URL)
    return LocalWhisperSTTProvider(hass, api_url)


def convert_pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Convert raw PCM audio data to WAV format"""
    # WAV file header
    wav_buffer = io.BytesIO()
    
    # Calculate sizes
    data_size = len(pcm_data)
    file_size = 36 + data_size
    
    # Write WAV header
    wav_buffer.write(b'RIFF')  # ChunkID
    wav_buffer.write(struct.pack('<I', file_size))  # ChunkSize
    wav_buffer.write(b'WAVE')  # Format
    wav_buffer.write(b'fmt ')  # Subchunk1ID
    wav_buffer.write(struct.pack('<I', 16))  # Subchunk1Size (PCM = 16)
    wav_buffer.write(struct.pack('<H', 1))   # AudioFormat (PCM = 1)
    wav_buffer.write(struct.pack('<H', channels))  # NumChannels
    wav_buffer.write(struct.pack('<I', sample_rate))  # SampleRate
    wav_buffer.write(struct.pack('<I', sample_rate * channels * sample_width))  # ByteRate
    wav_buffer.write(struct.pack('<H', channels * sample_width))  # BlockAlign
    wav_buffer.write(struct.pack('<H', sample_width * 8))  # BitsPerSample
    wav_buffer.write(b'data')  # Subchunk2ID
    wav_buffer.write(struct.pack('<I', data_size))  # Subchunk2Size
    wav_buffer.write(pcm_data)  # Data
    
    return wav_buffer.getvalue()


class LocalWhisperSTTProvider(Provider):
    """The Local Whisper STT provider."""

    def __init__(self, hass, api_url) -> None:
        """Init Local Whisper STT service."""
        self.hass = hass
        self.name = "Local Whisper STT"

        self._api_url = api_url
        self._client = get_async_client(hass)

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        _LOGGER.debug(
            "Start processing audio stream for language: %s", metadata.language
        )

        # Collect data
        audio_data = b""
        async for chunk in stream:
            audio_data += chunk

        _LOGGER.debug("Audio data size: %d bytes", len(audio_data))

        try:
            # Convert PCM to WAV format
            wav_audio = convert_pcm_to_wav(
                audio_data, 
                sample_rate=metadata.sample_rate, 
                channels=metadata.channel, 
                sample_width=metadata.bit_rate // 8
            )

            # Prepare form data
            files = {
                'audio_file': ('recording.wav', wav_audio, 'audio/wav')
            }

            params = {
                'encode': 'true',
                'task': 'transcribe',
                'output': 'txt'
            }

            url = f"{self._api_url}/asr"
            headers = {'Accept': 'text/plain'}

            _LOGGER.debug("Sending request to API: %s", url)

            # Send the request to the API
            response = await self._client.post(
                url,
                params=params,
                files=files,
                headers=headers,
                timeout=httpx.Timeout(30.0),
            )
            response.raise_for_status()
            
            transcribed_text = response.text
            _LOGGER.debug("API response: %s", transcribed_text)
            
            if not transcribed_text or not transcribed_text.strip():
                _LOGGER.warning("Transcription returned empty text")
                return SpeechResult("", SpeechResultState.ERROR)
                
            return SpeechResult(transcribed_text.strip(), SpeechResultState.SUCCESS)

        except httpx.HTTPError as err:
            if hasattr(err, "response") and err.response:
                error_text = await err.response.atext()
                _LOGGER.error(
                    "HTTP error %s: %s",
                    err.response.status_code,
                    error_text,
                )
            else:
                _LOGGER.error("HTTP error: %s", err)
            return SpeechResult("", SpeechResultState.ERROR)
        except Exception as err:
            _LOGGER.error("Error during transcription: %s", err)
            return SpeechResult("", SpeechResultState.ERROR)
