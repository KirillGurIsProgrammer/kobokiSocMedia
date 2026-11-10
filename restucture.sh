
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
DJANGO_DIR="$ROOT/Koboki"

echo "=== Koboki structure migration ==="

# Проверяем расположение
if [[ ! -d "$DJANGO_DIR" ]]; then
    echo "ERROR: Directory Koboki/ not found."
    exit 1
fi

# Проверяем Git
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: Run this script from Git repository root."
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "ERROR: Working tree is not clean."
    echo "Commit or stash your changes before migration."
    exit 1
fi

# Проверяем конфликты перед перемещением
for item in apps config manage.py static templates requirements.txt; do
    if [[ -e "$ROOT/$item" ]]; then
        echo "ERROR: $item already exists in root."
        exit 1
    fi
done

echo "[1/5] Moving Django project..."

for item in apps config manage.py static templates requirements.txt; do
    if [[ -e "$DJANGO_DIR/$item" ]]; then
        mv "$DJANGO_DIR/$item" "$ROOT/$item"
    fi
done

echo "[2/5] Moving hidden configuration files..."

for item in .env.example .gitignore; do
    if [[ -e "$DJANGO_DIR/$item" ]]; then
        if [[ -e "$ROOT/$item" ]]; then
            echo "WARNING: $item already exists in root. Keeping both is impossible."
            exit 1
        fi
        mv "$DJANGO_DIR/$item" "$ROOT/$item"
    fi
done

echo "[3/5] Preserving inner README..."

mkdir -p "$ROOT/docs"

if [[ -f "$DJANGO_DIR/README.md" ]]; then
    mv "$DJANGO_DIR/README.md" "$ROOT/docs/django-setup.md"
fi

echo "[4/5] Updating Python imports..."

python - <<'PY'
from pathlib import Path

root = Path.cwd()

replacements = {
    "Koboki.apps.": "apps.",
    "Koboki.config.": "config.",
}

for path in root.rglob("*.py"):
    if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
        continue

    content = path.read_text(encoding="utf-8")
    updated = content

    for old, new in replacements.items():
        updated = updated.replace(old, new)

    if updated != content:
        path.write_text(updated, encoding="utf-8")
        print(f"Updated: {path.relative_to(root)}")
PY

echo "[5/5] Creating developer directories..."

mkdir -p scripts/autocommit
mkdir -p tests

touch scripts/__init__.py
touch scripts/autocommit/__init__.py
touch tests/__init__.py
touch apps/__init__.py

cat > scripts/README.md <<'EOF'
# Developer Scripts

Project automation and maintenance utilities.

## Available tools

- autocommit/ — automatic Git commit tooling.
EOF

# Удаляем старую пустую директорию
rmdir "$DJANGO_DIR" 2>/dev/null || {
    echo "WARNING: Koboki/ is not empty. Inspect remaining files manually."
}

# Удаляем старый пустой src
rmdir "$ROOT/src" 2>/dev/null || true

echo
echo "Migration completed!"
echo "Next: run Django checks and inspect imports."