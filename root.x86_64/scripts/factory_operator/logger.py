import datetime
import re
from pathlib import Path
from typing import Dict, Any

_RECENTLY_CHANGED_HEADER = "## Recently Changed"
_MAX_RECENT_ENTRIES = 10

class ReceiptLogger:
    def __init__(self, state_file: str | Path):
        self.state_file = Path(state_file)

    def _ensure_file(self) -> None:
        if not self.state_file.exists():
            self.state_file.write_text(
                "# Pleiades Team State\n\n"
                "## Recently Changed\n\n"
                "## Agent Communication Log\n"
                "| Date | Agent | Summary |\n"
                "|---|---|---|\n"
            )

    def log_receipt(self, task: Dict[str, Any], result: Dict[str, Any]) -> None:
        self._ensure_file()
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        summary = f"{task.get('title')} - {result.get('status')}: {result.get('summary')}"
        entry = f"| {date_str} | Factory Operator | {summary} |\n"
        with open(self.state_file, "a") as f:
            f.write(entry)

    def log_recently_changed(self, date: str, summary: str, details: list[str]) -> None:
        """Update the ## Recently Changed section, keeping the last _MAX_RECENT_ENTRIES items."""
        self._ensure_file()
        content = self.state_file.read_text()

        detail_lines = "".join(f"  - {d}\n" for d in details)
        new_entry = f"- **{date}** — {summary}\n{detail_lines}"

        if _RECENTLY_CHANGED_HEADER in content:
            # Find the section and extract existing entries
            pattern = re.compile(
                rf"({re.escape(_RECENTLY_CHANGED_HEADER)}\n)(.*?)(\n##|\Z)",
                re.DOTALL,
            )
            match = pattern.search(content)
            if match:
                existing_body = match.group(2).strip()
                entries = [e for e in re.split(r"\n(?=- \*\*)", existing_body) if e.strip()]
                entries.insert(0, new_entry.strip())
                entries = entries[:_MAX_RECENT_ENTRIES]
                updated_body = "\n".join(entries) + "\n\n"
                content = content[: match.start(2)] + updated_body + content[match.end(2):]
            else:
                content = re.sub(
                    re.escape(_RECENTLY_CHANGED_HEADER) + r"\n?",
                    _RECENTLY_CHANGED_HEADER + "\n\n" + new_entry,
                    content,
                    count=1,
                )
        else:
            content += f"\n{_RECENTLY_CHANGED_HEADER}\n\n{new_entry}"

        self.state_file.write_text(content)
