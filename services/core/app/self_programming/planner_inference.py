from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from app.domain.models import SelfProgrammingEdit

if TYPE_CHECKING:
    from app.self_programming.models import SelfProgrammingCandidate


class PlannerInferenceMixin:
    workspace_root: Path | None

    def _infer_python_constant_edit(
        self,
        candidate: "SelfProgrammingCandidate",
    ) -> list[SelfProgrammingEdit]:
        test_path = self._find_pytest_target(candidate.test_commands)
        if test_path is None or not test_path.exists():
            return []

        content = test_path.read_text(encoding="utf-8")
        import_match = re.search(
            r"from\s+([A-Za-z0-9_\.]+)\s+import\s+([A-Za-z0-9_]+)",
            content,
        )
        constant_assert_match = re.search(
            r"assert\s+([A-Za-z0-9_]+)\s*==\s*([^\n#]+)",
            content,
        )
        function_assert_match = re.search(
            r"assert\s+([A-Za-z0-9_]+)\(\)\s*==\s*([^\n#]+)",
            content,
        )
        if import_match is None or (
            constant_assert_match is None and function_assert_match is None
        ):
            return []

        module_name, imported_symbol = import_match.groups()
        if self.workspace_root is None:
            return []
        module_path = self.workspace_root / f"{module_name.replace('.', '/')}.py"
        if not module_path.exists():
            return []

        module_content = module_path.read_text(encoding="utf-8")
        if constant_assert_match is not None:
            asserted_symbol, expected_value = constant_assert_match.groups()
            if imported_symbol != asserted_symbol:
                return []

            assignment_match = re.search(
                rf"^(\s*{re.escape(imported_symbol)}\s*=\s*)([^\n#]+)$",
                module_content,
                flags=re.MULTILINE,
            )
            if assignment_match is None:
                return []

            current_value = assignment_match.group(2).strip()
            target_value = expected_value.strip()
            if current_value == target_value:
                return []

            relative_path = module_path.relative_to(self.workspace_root).as_posix()
            search_text = f"{imported_symbol} = {current_value}"
            replace_text = f"{imported_symbol} = {target_value}"
            if search_text not in module_content:
                return []

            return [
                SelfProgrammingEdit(
                    file_path=relative_path,
                    search_text=search_text,
                    replace_text=replace_text,
                )
            ]

        called_function, expected_value = function_assert_match.groups()
        if imported_symbol != called_function:
            return []

        return self._infer_zero_arg_function_edit(
            module_path=module_path,
            function_name=called_function,
            target_value=expected_value.strip(),
        )

    def _infer_zero_arg_function_edit(
        self,
        module_path: Path,
        function_name: str,
        target_value: str,
    ) -> list[SelfProgrammingEdit]:
        module_content = module_path.read_text(encoding="utf-8")
        function_body_match = re.search(
            rf"def\s+{re.escape(function_name)}\(\):\n((?:\s+.+\n?)*)",
            module_content,
        )
        if function_body_match is None:
            return []

        body = function_body_match.group(1)
        return_match = re.search(r"^\s+return\s+([^\n#]+)$", body, flags=re.MULTILINE)
        if return_match is None:
            return []

        current_value = return_match.group(1).strip()
        assignment_source = self._resolve_assigned_value(body, current_value)
        if assignment_source is not None:
            current_value = assignment_source
        if current_value == target_value:
            return []

        nested_call_match = re.fullmatch(r"([A-Za-z0-9_]+)\(\)", current_value)
        if nested_call_match is not None:
            nested_function = nested_call_match.group(1)
            local_definition = re.search(
                rf"def\s+{re.escape(nested_function)}\(\):",
                module_content,
            )
            if local_definition is not None:
                return self._infer_zero_arg_function_edit(
                    module_path=module_path,
                    function_name=nested_function,
                    target_value=target_value,
                )

            imported_module_path = self._find_imported_module_path(module_content, nested_function)
            if imported_module_path is not None:
                return self._infer_zero_arg_function_edit(
                    module_path=imported_module_path,
                    function_name=nested_function,
                    target_value=target_value,
                )
            return []

        if self.workspace_root is None:
            return []
        relative_path = module_path.relative_to(self.workspace_root).as_posix()
        search_text = f"return {current_value}"
        replace_text = f"return {target_value}"
        if search_text not in module_content:
            return []

        return [
            SelfProgrammingEdit(
                file_path=relative_path,
                search_text=search_text,
                replace_text=replace_text,
            )
        ]

    def _infer_class_method_return_edit(
        self,
        candidate: "SelfProgrammingCandidate",
    ) -> list[SelfProgrammingEdit]:
        test_path = self._find_pytest_target(candidate.test_commands)
        if test_path is None or not test_path.exists():
            return []

        content = test_path.read_text(encoding="utf-8")
        import_match = re.search(
            r"from\s+([A-Za-z0-9_\.]+)\s+import\s+([A-Za-z0-9_]+)",
            content,
        )
        method_assert_match = re.search(
            r'assert\s+([A-Za-z0-9_]+)\(\)\.([A-Za-z0-9_]+)\("([^"]+)"\)\s*==\s*([^\n#]+)',
            content,
        )
        if import_match is None or method_assert_match is None:
            return []

        module_name, imported_symbol = import_match.groups()
        class_name, method_name, method_arg, expected_value = method_assert_match.groups()
        if imported_symbol != class_name:
            return []

        if self.workspace_root is None:
            return []
        module_path = self.workspace_root / f"{module_name.replace('.', '/')}.py"
        if not module_path.exists():
            return []

        module_content = module_path.read_text(encoding="utf-8")
        class_match = re.search(
            rf"class\s+{re.escape(class_name)}[^\n]*:\n((?:    .+\n?)*)",
            module_content,
        )
        if class_match is None:
            return []

        class_body = class_match.group(1)
        method_match = re.search(
            rf"\s{{4}}def\s+{re.escape(method_name)}\([^\)]*\)(?:\s*->\s*[^\n:]+)?:\n((?:\s{{8}}.+\n?)*)",
            class_body,
        )
        if method_match is None:
            return []

        method_body = method_match.group(1)
        branch_return_match = re.search(
            rf'if\s+"([^"]+)"\s+in\s+[A-Za-z0-9_]+:\n\s+return\s+([^\n#]+)',
            method_body,
        )
        if branch_return_match is None:
            return []

        trigger_text, current_value = branch_return_match.groups()
        if trigger_text not in method_arg:
            return []

        target_value = expected_value.strip()
        current_value = current_value.strip()
        if current_value == target_value:
            return []

        search_text = f"return {current_value}"
        replace_text = f"return {target_value}"
        if search_text not in module_content:
            return []

        relative_path = module_path.relative_to(self.workspace_root).as_posix()
        return [
            SelfProgrammingEdit(
                file_path=relative_path,
                search_text=search_text,
                replace_text=replace_text,
            )
        ]

    def _resolve_assigned_value(self, body: str, returned_name: str) -> str | None:
        current_name = returned_name
        visited: set[str] = set()

        while re.fullmatch(r"[A-Za-z0-9_]+", current_name):
            if current_name in visited:
                return None
            visited.add(current_name)

            assignment_matches = re.findall(
                rf"^\s*{re.escape(current_name)}\s*=\s*([^\n#]+)$",
                body,
                flags=re.MULTILINE,
            )
            if not assignment_matches:
                return None if current_name == returned_name else current_name

            next_value = assignment_matches[-1].strip()
            if next_value == current_name:
                return current_name
            current_name = next_value

        return current_name if current_name != returned_name else None

    def _find_pytest_target(self, commands: list[str]) -> Path | None:
        if self.workspace_root is None:
            return None
        for command in commands:
            for token in command.split():
                if token.endswith(".py"):
                    return self.workspace_root / token
        return None

    def _find_imported_module_path(self, module_content: str, symbol: str) -> Path | None:
        if self.workspace_root is None:
            return None
        for line in module_content.splitlines():
            import_match = re.match(
                r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+(.+?)\s*$",
                line,
            )
            if import_match is None:
                continue

            imported_module, imported_names = import_match.groups()
            names = []
            for imported_name in imported_names.split(","):
                symbol_name = imported_name.strip().split(" as ", maxsplit=1)[0].strip()
                if symbol_name:
                    names.append(symbol_name)
            if symbol not in names:
                continue

            module_path = self.workspace_root / f"{imported_module.replace('.', '/')}.py"
            if module_path.exists():
                return module_path
        return None

