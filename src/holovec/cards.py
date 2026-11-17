"""Dataset card formatting."""


import yaml


def card_metadata(root):
    path = root / "catalog/dataset.yaml"
    if path.is_file():
        return yaml.safe_load(path.read_text())
    parts = (root / "README.md").read_text().split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError("Dataset metadata is missing")
    return yaml.safe_load(parts[1])


def render_card(root):
    metadata = yaml.safe_dump(card_metadata(root), sort_keys=False, allow_unicode=True)
    body = (root / "README.md").read_text()
    if body.startswith("---\n"):
        body = body.split("---", 2)[2].lstrip()
    return "---\n" + metadata + "---\n\n" + body
