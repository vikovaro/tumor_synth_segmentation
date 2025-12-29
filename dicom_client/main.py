import sys
from pathlib import Path

# Добавляем корневую директорию в путь Python
sys.path.insert(0, str(Path(__file__).parent))

from interfaces.cli import cli

if __name__ == '__main__':
    cli()