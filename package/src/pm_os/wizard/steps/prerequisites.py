"""
Prerequisites Step

Check system requirements before installation.
"""

import shutil
import subprocess
import sys
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from pm_os.wizard.orchestrator import WizardOrchestrator


def check_python_version() -> Tuple[bool, str]:
    """Check Python version is 3.10+."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor} (need 3.10+)"


def check_pip() -> Tuple[bool, str]:
    """Check pip is available."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # Extract version from output like "pip 24.0 from ..."
            version = result.stdout.split()[1] if result.stdout else "available"
            return True, f"pip {version}"
        return False, "pip not found"
    except Exception as e:
        return False, f"pip check failed: {e}"


def check_claude_code() -> Tuple[bool, str]:
    """Check Claude Code CLI is installed."""
    if shutil.which("claude"):
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip() if result.stdout else "available"
                return True, version
        except Exception:
            pass
        return True, "installed"
    return False, "not found (install from claude.ai/code)"


def check_aws_cli() -> Tuple[bool, str]:
    """Check AWS CLI is installed (optional for Bedrock)."""
    if shutil.which("aws"):
        try:
            result = subprocess.run(
                ["aws", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Output like "aws-cli/2.15.0 Python/3.11.6 ..."
                version = result.stdout.split()[0] if result.stdout else "available"
                return True, version
        except Exception:
            pass
        return True, "installed"
    return False, "not found (optional, needed for Bedrock)"


def check_bedrock_access() -> Tuple[bool, str]:
    """Check AWS Bedrock model access (optional)."""
    if not shutil.which("aws"):
        return False, "AWS CLI not installed"

    try:
        result = subprocess.run(
            ["aws", "bedrock", "list-foundation-models", "--max-results", "1"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return True, "access confirmed"
        if "UnauthorizedException" in result.stderr or "AccessDeniedException" in result.stderr:
            return False, "no access (check IAM permissions)"
        return False, "check failed"
    except subprocess.TimeoutExpired:
        return False, "timeout (check AWS credentials)"
    except Exception as e:
        return False, f"check failed: {e}"


def check_git() -> Tuple[bool, str]:
    """Check git is installed."""
    if shutil.which("git"):
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip().replace("git version ", "")
                return True, f"git {version}"
        except Exception:
            pass
        return True, "installed"
    return False, "not found"


def prerequisites_step(wizard: "WizardOrchestrator") -> bool:
    """Check system prerequisites.

    Returns:
        True to continue, False to abort
    """
    wizard.console.print("[bold]Checking system requirements...[/bold]")
    wizard.console.print()

    # Required checks
    required_checks: List[Tuple[str, callable, bool]] = [
        ("Python 3.10+", check_python_version, True),
        ("pip", check_pip, True),
        ("Git", check_git, True),
    ]

    # Optional checks
    optional_checks: List[Tuple[str, callable, bool]] = [
        ("Claude Code CLI", check_claude_code, False),
        ("AWS CLI", check_aws_cli, False),
        ("Bedrock Access", check_bedrock_access, False),
    ]

    all_passed = True
    results = []

    # Run required checks
    for name, check_func, required in required_checks:
        passed, message = check_func()
        results.append((name, passed, message))
        if required and not passed:
            all_passed = False

    # Run optional checks
    for name, check_func, _ in optional_checks:
        passed, message = check_func()
        results.append((name, passed, message))
        # Optional checks don't block installation

    # Display results
    wizard.ui.show_checklist(results)
    wizard.console.print()

    if not all_passed:
        wizard.ui.print_error("Some required prerequisites are missing.")
        wizard.console.print()
        wizard.console.print("[yellow]Please install the missing requirements and try again.[/yellow]")
        return False

    # Store results for later reference
    wizard.set_data("prerequisites", {
        name: {"passed": passed, "message": message}
        for name, passed, message in results
    })

    wizard.ui.print_success("All required prerequisites met!")
    wizard.console.print()

    return True
