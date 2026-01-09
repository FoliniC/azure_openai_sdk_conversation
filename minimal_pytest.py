from custom_components.azure_openai_sdk_conversation.local_intent.text_normalizer import (
    TextNormalizer,
)


def test_minimal():
    normalizer = TextNormalizer()
    assert normalizer.normalize("test") == "test"
