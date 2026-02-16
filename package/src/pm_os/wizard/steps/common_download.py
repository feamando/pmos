"""
Common Download Step

Download the common/ directory from GitHub during wizard setup.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pm_os.wizard.orchestrator import WizardOrchestrator


def common_download_step(wizard: "WizardOrchestrator") -> bool:
    """Download common/ from GitHub.

    Returns:
        True to continue, False to abort
    """
    from pm_os.downloader import CommonDownloader, DownloadError

    # Current layout: install_path contains brain/, personal/, etc.
    # common/ is placed alongside them in the same directory.
    # (Loop 4 will restructure to install_path/user/ + install_path/common/)
    root_dir = wizard.install_path
    user_dir = wizard.install_path
    common_dir = root_dir / "common"

    # Check if common/ already exists (e.g., from git clone)
    if common_dir.exists() and (common_dir / "tools").exists():
        wizard.ui.print_success(f"common/ already exists at {common_dir}")
        downloader = CommonDownloader(verbose=False)
        valid, missing = downloader.verify_download(common_dir)
        if valid:
            wizard.ui.print_success("Verified: tools, commands, scripts all present")
            wizard.set_data("common_dir", str(common_dir))
            wizard.set_data("root_dir", str(root_dir))
            return True
        else:
            wizard.ui.print_warning(f"common/ exists but missing: {', '.join(missing)}")
            if not wizard.quick_mode:
                if not wizard.ui.prompt_confirm("Re-download common/?", default=True):
                    wizard.set_data("common_dir", str(common_dir))
                    wizard.set_data("root_dir", str(root_dir))
                    return True

    # Check for manual common path
    manual_path = wizard.get_data("common_path")
    if manual_path:
        manual_common = Path(manual_path)
        if manual_common.exists() and (manual_common / "tools").exists():
            wizard.ui.print_success(f"Using provided common/ at {manual_common}")
            wizard.set_data("common_dir", str(manual_common))
            wizard.set_data("root_dir", str(manual_common.parent))
            return True

    # Download common/
    wizard.console.print("[bold]Downloading PM-OS tools and commands...[/bold]")
    wizard.console.print("[dim]This downloads ~84 slash commands, Python tools, and frameworks.[/dim]")
    wizard.console.print()

    # Determine version
    try:
        from importlib.metadata import version as pkg_version
        pip_version = pkg_version("pm-os")
    except Exception:
        pip_version = None

    version = pip_version or "latest"
    wizard.console.print(f"[dim]Version: {version}[/dim]")

    # Create root directory
    root_dir.mkdir(parents=True, exist_ok=True)

    downloader = CommonDownloader(version=version, verbose=not wizard.quick_mode)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            wizard.console.print(f"[dim]Downloading from GitHub...[/dim]")
            success = downloader.download(root_dir)

            if success:
                # Verify
                valid, missing = downloader.verify_download(common_dir)
                if valid:
                    wizard.ui.print_success("Download complete and verified!")

                    # Create markers and pin version
                    downloader.create_markers(root_dir, user_dir, common_dir)
                    downloader.pin_version(root_dir)

                    wizard.set_data("common_dir", str(common_dir))
                    wizard.set_data("root_dir", str(root_dir))

                    # Show what was downloaded
                    wizard.console.print()
                    _show_download_summary(wizard, common_dir)

                    return True
                else:
                    wizard.ui.print_warning(f"Download incomplete. Missing: {', '.join(missing)}")

        except DownloadError as e:
            wizard.ui.print_warning(f"Download failed: {e}")

        # Retry logic
        if attempt < max_retries - 1:
            if wizard.quick_mode:
                wizard.console.print(f"[dim]Retrying... ({attempt + 2}/{max_retries})[/dim]")
            else:
                if not wizard.ui.prompt_confirm("Retry download?", default=True):
                    break

    # All retries failed
    wizard.console.print()
    wizard.ui.print_error("Could not download common/ directory.")
    wizard.console.print()
    wizard.console.print("[yellow]Alternative setup methods:[/yellow]")
    wizard.console.print("  1. Clone manually:")
    wizard.console.print(f"     git clone https://github.com/feamando/pmos.git {common_dir}")
    wizard.console.print("  2. Provide existing path:")
    wizard.console.print("     pm-os init --common-path /path/to/common")
    wizard.console.print()

    if not wizard.quick_mode:
        manual = wizard.ui.prompt_text(
            "Enter path to existing common/ (or press Enter to abort)",
            default="",
        )
        if manual and Path(manual).exists():
            wizard.set_data("common_dir", manual)
            wizard.set_data("root_dir", str(Path(manual).parent))
            return True

    # In quick mode, continue without common/ (some features will be limited)
    if wizard.quick_mode:
        wizard.ui.print_warning("Continuing without common/ — some features will be limited.")
        wizard.ui.print_info("Run 'pm-os update' later to download tools.")
        return True

    return False


def _show_download_summary(wizard: "WizardOrchestrator", common_dir: Path):
    """Show summary of downloaded content."""
    # Count commands
    commands_dir = common_dir / ".claude" / "commands"
    command_count = len(list(commands_dir.glob("*.md"))) if commands_dir.exists() else 0

    # Count tools
    tools_dir = common_dir / "tools"
    tool_count = 0
    if tools_dir.exists():
        for item in tools_dir.iterdir():
            if item.is_dir() and not item.name.startswith((".", "__")):
                tool_count += 1

    wizard.ui.show_summary_table("Downloaded Content", {
        "Location": str(common_dir),
        "Slash Commands": str(command_count),
        "Tool Packages": str(tool_count),
        "AGENT.md": "Yes" if (common_dir / "AGENT.md").exists() else "No",
        "Boot Script": "Yes" if (common_dir / "scripts" / "boot.sh").exists() else "No",
    })
