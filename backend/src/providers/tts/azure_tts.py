"""Azure Text-to-Speech provider."""

from __future__ import annotations

from typing import Any

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.tts.base import BaseTTSProvider, SpeechResult, VoiceInfo


@ProviderRegistry.register
class AzureTTSProvider(BaseTTSProvider):
    """Azure Cognitive Services Text-to-Speech provider."""

    provider_name = "azure_tts"
    display_name = "Azure Speech"
    description = "Microsoft Azure Neural TTS with SSML support"
    requires_api_key = True

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.region = config.settings.get("region", "eastus")

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "neural",
                "name": "Neural",
                "description": "High-quality neural voices",
            },
        ]

    @classmethod
    def get_available_voices(cls) -> list[VoiceInfo]:
        return [
            VoiceInfo(id="en-US-JennyNeural", name="Jenny", language="en-US", gender="female"),
            VoiceInfo(id="en-US-GuyNeural", name="Guy", language="en-US", gender="male"),
            VoiceInfo(id="en-US-AriaNeural", name="Aria", language="en-US", gender="female"),
            VoiceInfo(id="en-US-DavisNeural", name="Davis", language="en-US", gender="male"),
            VoiceInfo(id="en-US-AmberNeural", name="Amber", language="en-US", gender="female"),
            VoiceInfo(id="en-US-AnaNeural", name="Ana", language="en-US", gender="female"),
            VoiceInfo(id="en-US-AshleyNeural", name="Ashley", language="en-US", gender="female"),
            VoiceInfo(id="en-US-BrandonNeural", name="Brandon", language="en-US", gender="male"),
            VoiceInfo(id="en-US-ChristopherNeural", name="Christopher", language="en-US", gender="male"),
            VoiceInfo(id="en-US-CoraNeural", name="Cora", language="en-US", gender="female"),
            VoiceInfo(id="en-US-ElizabethNeural", name="Elizabeth", language="en-US", gender="female"),
            VoiceInfo(id="en-US-EricNeural", name="Eric", language="en-US", gender="male"),
            VoiceInfo(id="en-US-JacobNeural", name="Jacob", language="en-US", gender="male"),
            VoiceInfo(id="en-US-JaneNeural", name="Jane", language="en-US", gender="female"),
            VoiceInfo(id="en-US-JasonNeural", name="Jason", language="en-US", gender="male"),
            VoiceInfo(id="en-US-MichelleNeural", name="Michelle", language="en-US", gender="female"),
            VoiceInfo(id="en-US-MonicaNeural", name="Monica", language="en-US", gender="female"),
            VoiceInfo(id="en-US-NancyNeural", name="Nancy", language="en-US", gender="female"),
            VoiceInfo(id="en-US-RogerNeural", name="Roger", language="en-US", gender="male"),
            VoiceInfo(id="en-US-SaraNeural", name="Sara", language="en-US", gender="female"),
            VoiceInfo(id="en-US-SteffanNeural", name="Steffan", language="en-US", gender="male"),
            VoiceInfo(id="en-US-TonyNeural", name="Tony", language="en-US", gender="male"),
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "default": "eastus",
                    "description": "Azure region",
                },
                "style": {
                    "type": "string",
                    "enum": [
                        "default", "cheerful", "sad", "angry", "fearful",
                        "disgruntled", "serious", "affectionate", "gentle",
                        "depressed", "calm", "embarrassed", "lyrical",
                    ],
                    "default": "default",
                    "description": "Speaking style",
                },
                "style_degree": {
                    "type": "number",
                    "minimum": 0.01,
                    "maximum": 2,
                    "default": 1.0,
                    "description": "Style intensity",
                },
                "rate": {
                    "type": "string",
                    "enum": ["x-slow", "slow", "medium", "fast", "x-fast"],
                    "default": "medium",
                    "description": "Speaking rate",
                },
                "pitch": {
                    "type": "string",
                    "enum": ["x-low", "low", "medium", "high", "x-high"],
                    "default": "medium",
                    "description": "Voice pitch",
                },
            },
            "required": ["region"],
        }

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        **kwargs,
    ) -> SpeechResult:
        """Synthesize speech using Azure TTS."""
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            raise ImportError(
                "azure-cognitiveservices-speech is required for Azure TTS. "
                "Install with: pip install azure-cognitiveservices-speech"
            )

        voice = voice or "en-US-JennyNeural"

        # Configure speech
        speech_config = speechsdk.SpeechConfig(
            subscription=self.config.api_key,
            region=self.region,
        )

        # Set output format
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )

        # Build SSML with style support
        style = kwargs.get("style", "default")
        style_degree = kwargs.get("style_degree", 1.0)
        rate = kwargs.get("rate", "medium")
        pitch = kwargs.get("pitch", "medium")

        if style != "default":
            ssml = f"""
            <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
                   xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">
                <voice name="{voice}">
                    <mstts:express-as style="{style}" styledegree="{style_degree}">
                        <prosody rate="{rate}" pitch="{pitch}">
                            {text}
                        </prosody>
                    </mstts:express-as>
                </voice>
            </speak>
            """
        else:
            ssml = f"""
            <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
                <voice name="{voice}">
                    <prosody rate="{rate}" pitch="{pitch}">
                        {text}
                    </prosody>
                </voice>
            </speak>
            """

        # Create synthesizer
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=None,  # Output to memory
        )

        # Perform synthesis
        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return SpeechResult(
                audio=result.audio_data,
                format="mp3",
            )
        else:
            raise Exception(f"Speech synthesis failed: {result.reason}")
