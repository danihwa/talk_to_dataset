import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.agent import run_question


def load_secrets() -> None:
    """Load environment variables from ~/secrets/.env or local .env fallback."""
    secrets = Path.home() / "secrets" / ".env"
    if secrets.exists():
        load_dotenv(secrets)
    else:
        load_dotenv()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    load_secrets()
    if len(sys.argv) < 2:
        print('Usage: python -m src.cli "your question"', file=sys.stderr)
        sys.exit(2)
    question = " ".join(sys.argv[1:])
    answer = asyncio.run(run_question(question))
    print(answer)


if __name__ == "__main__":
    main()
