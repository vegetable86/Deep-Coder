from deep_coder.models.deepseek.model import DeepSeekModel


def test_deepseek_manifest_identifies_provider():
    manifest = DeepSeekModel.manifest()

    assert manifest["provider"] == "deepseek"
    assert manifest["transport"] == "openai-compatible-sdk"
