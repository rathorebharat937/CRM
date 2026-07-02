"""Enable and seed all Level 5 platform modules (one command)."""

from __future__ import annotations

import argparse
import sys

from seed_enable_level5 import enable_level5_modules


def seed_demo_level5(reset: bool = False) -> None:
    print("=== Enabling Level 5 modules ===")
    enable_level5_modules()

    steps = [
        ("website", "seed_demo_website", "seed_demo_website"),
        ("ecommerce", "seed_demo_ecommerce", "seed_demo_ecommerce"),
        ("pos", "seed_demo_pos", "seed_demo_pos"),
        ("manufacturing", "seed_demo_manufacturing", "seed_demo_manufacturing"),
        ("quality", "seed_demo_quality", "seed_demo_quality"),
        ("maintenance", "seed_demo_maintenance", "seed_demo_maintenance"),
        ("field_service", "seed_demo_field_service", "seed_demo_field_service"),
        ("subscriptions", "seed_demo_subscriptions", "seed_demo_subscriptions"),
        ("rental", "seed_demo_rental", "seed_demo_rental"),
        ("ai_reports", "seed_demo_ai_reports", "seed_demo_ai_reports"),
        ("workflows", "seed_demo_workflows", "seed_demo_workflows"),
        ("marketing", "seed_demo_marketing", "seed_demo_marketing"),
        ("ai_assistant", "seed_demo_ai_assistant", "seed_demo_ai_assistant"),
        ("marketplace", "seed_demo_marketplace", "seed_demo_marketplace"),
    ]

    for label, module_name, func_name in steps:
        print(f"\n=== {label} ===")
        mod = __import__(module_name)
        fn = getattr(mod, func_name)
        try:
            if reset and "reset" in fn.__code__.co_varnames:
                fn(reset=True)
            elif func_name == "seed_demo_workflows":
                fn(activate=True)
            elif func_name == "seed_demo_marketing":
                fn(activate=True)
            else:
                fn()
        except Exception as exc:
            print(f"ERROR ({label}): {exc}", file=sys.stderr)

    print("\n=== Level 5 demo seed complete ===")
    print("Log out and log back in, then open /subscriptions, /pos, /manufacturing, etc.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enable + seed all Level 5 modules")
    parser.add_argument("--reset", action="store_true", help="Pass reset=True to seeds that support it")
    args = parser.parse_args()
    seed_demo_level5(reset=args.reset)
