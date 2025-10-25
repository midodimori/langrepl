from src.tools.factory import ToolFactory


class TestToolFactory:
    def test_initialization(self):
        factory = ToolFactory()
        assert factory.impl_tools is not None
        assert factory.internal_tools is not None
        assert len(factory.impl_tools) > 0
        assert len(factory.internal_tools) > 0

    def test_get_impl_tools(self):
        factory = ToolFactory()
        impl_tools = factory.get_impl_tools()
        assert isinstance(impl_tools, list)
        assert len(impl_tools) > 0

    def test_get_internal_tools(self):
        factory = ToolFactory()
        internal_tools = factory.get_internal_tools()
        assert isinstance(internal_tools, list)
        assert len(internal_tools) > 0

    def test_impl_and_internal_are_different(self):
        factory = ToolFactory()
        impl_tools = factory.get_impl_tools()
        internal_tools = factory.get_internal_tools()

        impl_names = {tool.name for tool in impl_tools}
        internal_names = {tool.name for tool in internal_tools}

        assert impl_names != internal_names
