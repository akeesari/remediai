"""Unit tests for the .NET / Python stack frame parser."""

from __future__ import annotations

from packages.agent_runtime.root_cause.stack_parser import StackFrame, parse_stack_frames


class TestDotNetFrameParsing:
    def test_parses_frame_with_file_and_line(self) -> None:
        trace = "   at UserService.GetById(Int32 id) in C:\\src\\UserService.cs:line 42"
        frames = parse_stack_frames(trace)
        assert len(frames) == 1
        assert frames[0].method == "UserService.GetById(Int32 id)"
        assert frames[0].file_path == "C:\\src\\UserService.cs"
        assert frames[0].line_number == 42

    def test_parses_frame_without_file_path(self) -> None:
        trace = "   at OrderService.Process(Order order)"
        frames = parse_stack_frames(trace)
        assert len(frames) == 1
        assert frames[0].method == "OrderService.Process(Order order)"
        assert frames[0].file_path is None
        assert frames[0].line_number is None

    def test_user_code_flag_true_for_app_namespace(self) -> None:
        trace = "   at UserService.GetById(Int32 id)"
        frames = parse_stack_frames(trace)
        assert frames[0].is_user_code is True

    def test_filters_system_prefix_frames(self) -> None:
        trace = (
            "   at System.Linq.Enumerable.First(IEnumerable source)\n"
            "   at UserService.GetById(Int32 id)"
        )
        frames = parse_stack_frames(trace)
        assert len(frames) == 1
        assert frames[0].method == "UserService.GetById(Int32 id)"

    def test_filters_aspnetcore_prefix_frames(self) -> None:
        trace = (
            "   at Microsoft.AspNetCore.Mvc.Infrastructure.ActionMethodExecutor.Execute()\n"
            "   at OrderController.Create(CreateOrderRequest req)"
        )
        frames = parse_stack_frames(trace)
        assert len(frames) == 1
        assert frames[0].method == "OrderController.Create(CreateOrderRequest req)"

    def test_filters_efcore_prefix_frames(self) -> None:
        trace = (
            "   at Microsoft.EntityFrameworkCore.DbContext.SaveChanges()\n"
            "   at InventoryService.Save(Item item)"
        )
        frames = parse_stack_frames(trace)
        assert len(frames) == 1
        assert "InventoryService" in frames[0].method

    def test_falls_back_to_all_frames_when_only_framework_frames(self) -> None:
        trace = (
            "   at System.Linq.Enumerable.First(IEnumerable source)\n"
            "   at Microsoft.AspNetCore.Mvc.Controller.Execute()"
        )
        frames = parse_stack_frames(trace)
        assert len(frames) == 2

    def test_limits_to_max_frames(self) -> None:
        lines = [f"   at UserService.Method{i}()" for i in range(10)]
        trace = "\n".join(lines)
        frames = parse_stack_frames(trace, max_frames=5)
        assert len(frames) == 5

    def test_returns_empty_list_for_empty_string(self) -> None:
        assert parse_stack_frames("") == []

    def test_malformed_lines_are_skipped(self) -> None:
        trace = "not a stack frame\n   at UserService.GetById(Int32 id)"
        frames = parse_stack_frames(trace)
        assert len(frames) == 1

    def test_result_contains_stack_frame_instances(self) -> None:
        trace = "   at UserService.GetById(Int32 id)"
        frames = parse_stack_frames(trace)
        assert isinstance(frames[0], StackFrame)


class TestPythonFrameParsing:
    def test_parses_python_frame(self) -> None:
        trace = '  File "src/service.py", line 42, in get_user'
        frames = parse_stack_frames(trace)
        assert len(frames) == 1
        assert frames[0].file_path == "src/service.py"
        assert frames[0].line_number == 42
        assert "get_user" in frames[0].method

    def test_python_frame_user_code_flag(self) -> None:
        trace = '  File "src/my_service.py", line 10, in process'
        frames = parse_stack_frames(trace)
        assert frames[0].is_user_code is True

    def test_mixed_dotnet_and_python_lines(self) -> None:
        trace = '   at UserService.GetById(Int32 id)\n  File "src/helper.py", line 5, in helper_fn'
        frames = parse_stack_frames(trace)
        assert len(frames) == 2
