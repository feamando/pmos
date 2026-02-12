import json
import sys


def search_tree():
    try:
        with open(".gemini/tmp/shared_mobile_tree.json", "r", encoding="utf-16") as f:
            data = json.load(f)

        tree = data.get("tree", [])
        keywords = ["factor", "rte", "vms"]

        matches = []
        for item in tree:
            path = item.get("path", "")
            # Focus on code directories
            if path.startswith("src/modules") or path.startswith("src/features"):
                if any(k in path.lower() for k in keywords):
                    # Store only the module/feature root to avoid noise
                    # e.g. src/modules/factor-onboarding/index.ts -> src/modules/factor-onboarding
                    parts = path.split("/")
                    if len(parts) >= 3:
                        root = "/".join(parts[:3])
                        if root not in matches:
                            matches.append(root)

        # Deduplicate
        matches = sorted(list(set(matches)))

        for m in matches:
            print(m)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    search_tree()
