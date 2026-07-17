"""Second pass: remove leftover _get_company helpers and fix call sites."""

from __future__ import annotations

import re
from pathlib import Path

ROUTERS_DIR = Path(__file__).resolve().parent.parent / "routers"

_GET_COMPANY_FUNC = re.compile(
    r"def _get_company\(db: Session\) -> Company:\n(?:    .+\n)+?    return company\n",
    re.MULTILINE,
)


def _find_user_param(signature: str) -> str | None:
    for match in re.finditer(
        r"(\w+):\s*User\s*=\s*Depends\((?:require_permission|get_current_user|require_admin)",
        signature,
    ):
        return match.group(1)
    return None


def _split_router_functions(text: str) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    pattern = re.compile(r"^@router", re.MULTILINE)
    starts = [m.start() for m in pattern.finditer(text)]
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(text)
        blocks.append((start, end, text[start:end]))
    return blocks


def refactor_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    text = _GET_COMPANY_FUNC.sub("", original)

    if "from tenant_utils import get_current_company" not in text and (
        "_get_company(db)" in text or "def _get_company" in text
    ):
        if "from auth_utils import" in text:
            text = text.replace(
                "from auth_utils import",
                "from tenant_utils import get_current_company\nfrom auth_utils import",
                1,
            )

    blocks = _split_router_functions(text)
    pieces: list[str] = []
    cursor = 0
    changed = text != original

    for start, end, block in blocks:
        pieces.append(text[cursor:start])
        new_block = block

        if "_get_company(db)" in block:
            sig_match = re.search(
                r"(@router[^\n]*\n(?:@[^\n]*\n)*)def (\w+)\((.*?)\):",
                block,
                re.DOTALL,
            )
            if sig_match:
                signature = sig_match.group(3)
                user_param = _find_user_param(signature)
                if user_param:
                    if user_param == "_":
                        new_sig = signature.replace("_: User", "user: User", 1)
                        new_block = block.replace(signature, new_sig, 1)
                        user_param = "user"
                    new_block = new_block.replace(
                        "company = _get_company(db)",
                        f"company = get_current_company(db, {user_param})",
                    )
                    new_block = new_block.replace(
                        "_get_company(db)",
                        f"get_current_company(db, {user_param})",
                    )
                else:
                    print(f"WARN {path.name}: missing User Depends")

        if new_block != block:
            changed = True
        pieces.append(new_block)
        cursor = end

    pieces.append(text[cursor:])
    updated = "".join(pieces)

    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print(f"Fixed {path.name}")
        return True
    return changed


def main() -> None:
    count = 0
    for path in sorted(ROUTERS_DIR.glob("*.py")):
        if refactor_file(path):
            count += 1
    print(f"Fixed {count} files")


if __name__ == "__main__":
    main()
