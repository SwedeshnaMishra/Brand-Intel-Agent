import sys
from datetime import datetime

def log(step: str, message: str, ok: bool = True) -> None:
    """Prints a single timestamped progress line, e.g.
    [14:31:20] url_extractor -> 5 amazon product URLs found
    """
    ts = datetime.now().strftime("%H:%M:%S")
    marker = "" if ok else "  [WARN]"
    print(f" [{ts}] {step} -> {message}{marker}", flush=True, file=sys.stdout)


def banner(brand: str) -> None:
    line = "=" * 70
    print(line)
    print(f" LEAD GEN AGENT | Brand: {brand}")
    print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(line)


def footer(brand: str, success: bool) -> None:
    line = "=" * 70
    status = "DONE" if success else "COMPLETED WITH ERRORS"
    print(f" {'✅' if success else '⚠️'} {status}: {brand}")
    print(line)