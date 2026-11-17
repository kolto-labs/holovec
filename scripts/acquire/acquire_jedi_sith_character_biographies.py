"""Run a pinned biography extraction recipe."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from wiki_biographies import run_recipe

if __name__ == "__main__":
    run_recipe("acquire_jedi_sith_character_biographies")
