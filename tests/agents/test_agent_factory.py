from src.agents.factory import GraphFactory


class TestParseToolReferences:
    def test_parse_valid_references(self):
        tool_refs = [
            "impl:file_system:read_file",
            "mcp:server:tool1",
            "internal:todo:write_todos",
        ]

        impl, mcp, internal = GraphFactory._parse_tool_references(tool_refs)

        assert impl == ["file_system:read_file"]
        assert mcp == ["server:tool1"]
        assert internal == ["todo:write_todos"]

    def test_parse_none_returns_none(self):
        impl, mcp, internal = GraphFactory._parse_tool_references(None)

        assert impl is None
        assert mcp is None
        assert internal is None

    def test_parse_empty_list_returns_none(self):
        impl, mcp, internal = GraphFactory._parse_tool_references([])

        assert impl is None
        assert mcp is None
        assert internal is None

    def test_parse_only_impl_tools(self):
        tool_refs = ["impl:file_system:read_file", "impl:web:fetch_url"]

        impl, mcp, internal = GraphFactory._parse_tool_references(tool_refs)

        assert impl == ["file_system:read_file", "web:fetch_url"]
        assert mcp is None
        assert internal is None

    def test_parse_invalid_format_skipped(self):
        tool_refs = [
            "impl:file_system:read_file",
            "invalid_format",
            "mcp:server:tool1",
        ]

        impl, mcp, internal = GraphFactory._parse_tool_references(tool_refs)

        assert impl == ["file_system:read_file"]
        assert mcp == ["server:tool1"]
        assert internal is None

    def test_parse_unknown_tool_type_skipped(self):
        tool_refs = [
            "impl:file_system:read_file",
            "unknown:module:tool",
            "mcp:server:tool1",
        ]

        impl, mcp, internal = GraphFactory._parse_tool_references(tool_refs)

        assert impl == ["file_system:read_file"]
        assert mcp == ["server:tool1"]
        assert internal is None

    def test_parse_wildcard_patterns(self):
        tool_refs = [
            "impl:*:*",
            "mcp:server:*",
            "internal:todo:write_*",
        ]

        impl, mcp, internal = GraphFactory._parse_tool_references(tool_refs)

        assert impl == ["*:*"]
        assert mcp == ["server:*"]
        assert internal == ["todo:write_*"]


class TestFilterTools:
    def test_filter_by_exact_patterns(self, create_mock_tool):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")
        mock_tool3 = create_mock_tool("tool3")

        all_tools = [mock_tool1, mock_tool2, mock_tool3]
        tool_dict = GraphFactory._build_tool_dict(all_tools)
        module_map = {"tool1": "module1", "tool2": "module2", "tool3": "module3"}
        patterns = ["module1:tool1", "module3:tool3"]

        result = GraphFactory._filter_tools(tool_dict, patterns, module_map)

        assert len(result) == 2
        assert {t.name for t in result} == {"tool1", "tool3"}

    def test_filter_none_patterns_returns_empty(self, create_mock_tool):
        mock_tool = create_mock_tool("tool1")
        all_tools = [mock_tool]
        tool_dict = GraphFactory._build_tool_dict(all_tools)
        module_map = {"tool1": "module1"}

        result = GraphFactory._filter_tools(tool_dict, None, module_map)

        assert result == []

    def test_filter_empty_patterns_returns_empty(self, create_mock_tool):
        mock_tool = create_mock_tool("tool1")
        all_tools = [mock_tool]
        tool_dict = GraphFactory._build_tool_dict(all_tools)
        module_map = {"tool1": "module1"}

        result = GraphFactory._filter_tools(tool_dict, [], module_map)

        assert result == []

    def test_filter_no_matches(self, create_mock_tool):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        all_tools = [mock_tool1, mock_tool2]
        tool_dict = GraphFactory._build_tool_dict(all_tools)
        module_map = {"tool1": "module1", "tool2": "module2"}
        patterns = ["module3:tool3", "module4:tool4"]

        result = GraphFactory._filter_tools(tool_dict, patterns, module_map)

        assert result == []

    def test_filter_wildcard_all(self, create_mock_tool):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        all_tools = [mock_tool1, mock_tool2]
        tool_dict = GraphFactory._build_tool_dict(all_tools)
        module_map = {"tool1": "module1", "tool2": "module2"}
        patterns = ["*:*"]

        result = GraphFactory._filter_tools(tool_dict, patterns, module_map)

        assert len(result) == 2

    def test_filter_wildcard_module(self, create_mock_tool):
        mock_tool1 = create_mock_tool("read_file")
        mock_tool2 = create_mock_tool("write_file")
        mock_tool3 = create_mock_tool("fetch_url")

        all_tools = [mock_tool1, mock_tool2, mock_tool3]
        tool_dict = GraphFactory._build_tool_dict(all_tools)
        module_map = {
            "read_file": "file_system",
            "write_file": "file_system",
            "fetch_url": "web",
        }
        patterns = ["file_system:*"]

        result = GraphFactory._filter_tools(tool_dict, patterns, module_map)

        assert len(result) == 2
        assert {t.name for t in result} == {"read_file", "write_file"}

    def test_filter_wildcard_tool_name(self, create_mock_tool):
        mock_tool1 = create_mock_tool("read_file")
        mock_tool2 = create_mock_tool("read_dir")
        mock_tool3 = create_mock_tool("write_file")

        all_tools = [mock_tool1, mock_tool2, mock_tool3]
        tool_dict = GraphFactory._build_tool_dict(all_tools)
        module_map = {
            "read_file": "file_system",
            "read_dir": "file_system",
            "write_file": "file_system",
        }
        patterns = ["file_system:read_*"]

        result = GraphFactory._filter_tools(tool_dict, patterns, module_map)

        assert len(result) == 2
        assert {t.name for t in result} == {"read_file", "read_dir"}
