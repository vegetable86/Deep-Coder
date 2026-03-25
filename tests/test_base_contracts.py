from deep_coder.models.base import ModelBase
from deep_coder.tools.base import ToolBase


def test_tool_and_model_base_classes_define_required_methods():
    assert hasattr(ToolBase, "schema")
    assert hasattr(ToolBase, "exec")
    assert hasattr(ModelBase, "complete")
    assert hasattr(ModelBase, "manifest")
