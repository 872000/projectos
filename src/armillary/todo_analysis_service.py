"""ProjectOS: TODO / FIXME / test-health analysis.

Scans a project tree for task markers and test layout without
executing anything. Used by revival planning and potential scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

TASK_MARKERS = ("TODO", "FIXME", "HACK", "XXX", "BUG")
TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec"}
TEST_FILE_HINTS = ("test_", "_test.", ".test.", ".spec.")

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
             ".tox", "dist", "build", ".next", "target"}


@dataclass
class TodoItem:
    file: str
    line: int
    marker: str
    text: str


@dataclass
class TodoAnalysis:
    project_name: str
    todos: list[TodoItem] = field(default_factory=list)
    test_files: int = 0
    source_files: int = 0
    has_ci: bool = False

    @property
    def todo_count(self) -> int:
        return len(self.todos)

    @property
    def test_ratio(self) -> float:
        total = self.test_files + self.source_files
        return (self.test_files / total) if total else 0.0

    def to_markdown(self) -> str:
        lines = [
            f"# TODO / Test analysis: {self.project_name}",
            "",
            f"- Open task markers: **{self.todo_count}**",
            f"- Test files: **{self.test_files}**, source files: **{self.source_files}**",
            f"- Test ratio: **{self.test_ratio:.0%}**",
            f"- CI configured: **{'yes' if self.has_ci else 'no'}**",
            "",
        ]
        if self.todos:
            lines.append("## Open items (first 20)")
            for t in self.todos[:20]:
                lines.append(f"- `{t.file}:{t.line}` **{t.marker}** — {t.text}")
            if len(self.todos) > 20:
                lines.append(f"_…and {len(self.todos) - 20} more_")
        return "\n".join(lines)


def _is_test_path(path: Path) -> bool:
    parts = set(path.parts)
    if parts & TEST_DIR_NAMES:
        return True
    name = path.name.lower()
    return any(h in name for h in TEST_FILE_HINTS)


def analyze(root: Path, project_name: str = "") -> TodoAnalysis:
    """Walk *root* collecting TODO markers and test/source counts."""
    analysis = TodoAnalysis(project_name=project_name or root.name)
    if not root.is_dir():
        return analysis

    for dirpath, dirnames, filenames in _walk(root):
        for fn in filenames:
            fp = dirpath / fn
            if _is_test_path(fp):
                analysis.test_files += 1
            elif fp.suffix in {".py", ".js", ".ts", ".tsx", ".jsx",
                               ".go", ".rs", ".java", ".rb", ".swift"}:
                analysis.source_files += 1
            if fp.suffix not in {".py", ".js", ".ts", ".tsx", ".jsx", ".go",
                                 ".rs", ".java", ".rb", ".md", ".swift"}:
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                upper = line.upper()
                for marker in TASK_MARKERS:
                    if marker in upper:
                        stripped = line.strip()[:160]
                        analysis.todos.append(TodoItem(
                            file=str(fp.relative_to(root)), line=i,
                            marker=marker, text=stripped))
                        break
            if len(analysis.todos) > 500:
                break

    ci_paths = [root / ".github" / "workflows",
                root / ".gitlab-ci.yml", root / "tox.ini"]
    analysis.has_ci = any(p.exists() for p in ci_paths)
    return analysis


def _walk(root: Path):
    for dirpath, dirnames, filenames in _walk_inner(root):
        yield dirpath, dirnames, filenames


def _walk_inner(root: Path):
    import os
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        yield Path(dirpath), dirnames, filenames
