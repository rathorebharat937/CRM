"""One-off refactor: replace _get_company(db) with tenant_company dependency."""

from __future__ import annotations

import re
from pathlib import Path

ROUTERS_DIR = Path(__file__).resolve().parent.parent / "routers"

_GET_COMPANY_RE = re.compile(
    r"\ndef _get_company\(db: Session\) -> Company:\n"
    r"    company = db\.query\(Company\)\.first\(\)\n"
    r"    if not company:\n"
    r"        raise HTTPException\(\n"
    r"            status_code=400,\n"
    r"            detail=[^\n]+\n"
    r"        \)\n"
    r"    return company\n",
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
    """Return (start, end, block) for each @router-decorated function."""
    blocks: list[tuple[int, int, str]] = []
    pattern = re.compile(r"^@router", re.MULTILINE)
    starts = [m.start() for m in pattern.finditer(text)]
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(text)
        blocks.append((start, end, text[start:end]))
    return blocks


def refactor_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    if "_get_company" not in original:
        return False

    text = _GET_COMPANY_RE.sub("", original, count=1)

    if "from tenant_utils import get_current_company" not in text:
        if "from auth_utils import" in text:
            text = text.replace(
                "from auth_utils import",
                "from tenant_utils import get_current_company\nfrom auth_utils import",
                1,
            )
        else:
            text = "from tenant_utils import get_current_company\n" + text

    blocks = _split_router_functions(text)
    if not blocks:
        return False

    pieces: list[str] = []
    cursor = 0
    changed = "_get_company" in original

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
                prefix, _func_name, signature = sig_match.groups()
                user_param = _find_user_param(signature)
                if user_param:
                    if user_param == "_":
                        new_sig = signature.replace("_: User", "user: User", 1)
                        new_block = block.replace(signature, new_sig, 1)
                        user_param = "user"
                    new_block = new_block.replace(
                        f"company = _get_company(db)",
                        f"company = get_current_company(db, {user_param})",
                    )
                    new_block = new_block.replace(
                        f"_get_company(db)",
                        f"get_current_company(db, {user_param})",
                    )
                else:
                    print(f"WARN {path.name}: no User Depends in function using _get_company")

        if new_block != block:
            changed = True
        pieces.append(new_block)
        cursor = end

    pieces.append(text[cursor:])
    updated = "".join(pieces)

    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print(f"Updated {path.name}")
        return True

    return changed


def main() -> None:
    count = 0
    for path in sorted(ROUTERS_DIR.glob("*.py")):
        if refactor_file(path):
            count += 1
    print(f"Refactored {count} router files")


if __name__ == "__main__":
    main()
