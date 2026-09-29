from pathlib import Path
from shutil import copy2, copytree

from playwright.async_api import BrowserContext, Playwright


def content_script_ready_delay_ms() -> int:
    """Allow the injected script to register its Alt+D handler after navigation."""
    return 1_500


def traffic_result_timeout_ms() -> int:
    """Bound each domain query so a batch can continue after a missing result."""
    return 15_000


def chromium_arguments(extension_directory: Path) -> list[str]:
    """Return the only extension-related Chromium flags used by this project."""
    return [
        f"--disable-extensions-except={extension_directory}",
        f"--load-extension={extension_directory}",
    ]


async def launch_isolated_context(
    playwright: Playwright,
    executable_path: Path,
    profile_directory: Path,
    extension_directory: Path,
) -> BrowserContext:
    """Launch a visible, persistent context separate from the user's profile."""
    if not executable_path.is_file():
        raise FileNotFoundError(f"browser executable not found: {executable_path}")
    profile_directory.mkdir(parents=True, exist_ok=True)
    return await playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_directory),
        executable_path=str(executable_path),
        headless=False,
        args=chromium_arguments(extension_directory),
    )


def prepare_chrome_extension_profile(
    source_user_data: Path,
    target_user_data: Path,
    extension_id: str,
) -> Path:
    """Copy only Chrome metadata and storage needed by one installed extension."""
    source_profile = source_user_data / "Default"
    target_profile = target_user_data / "Default"
    target_profile.mkdir(parents=True, exist_ok=True)

    for relative in (Path("Local State"), Path("Default/Preferences"), Path("Default/Secure Preferences")):
        source = source_user_data / relative
        if not source.is_file():
            raise FileNotFoundError(f"Chrome profile file not found: {source}")
        destination = target_user_data / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, destination)

    for storage in ("Extensions", "Local Extension Settings", "Sync Extension Settings"):
        source = source_profile / storage / extension_id
        if not source.is_dir():
            raise FileNotFoundError(f"Chrome extension data not found: {source}")
        copytree(source, target_profile / storage / extension_id, dirs_exist_ok=True)

    return target_user_data


async def launch_chrome_installed_extension_context(
    playwright: Playwright,
    executable_path: Path,
    profile_directory: Path,
) -> BrowserContext:
    """Launch Chrome with extensions registered in an isolated profile copy."""
    if not executable_path.is_file():
        raise FileNotFoundError(f"browser executable not found: {executable_path}")
    return await playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_directory),
        executable_path=str(executable_path),
        headless=False,
        args=["--profile-directory=Default"],
        ignore_default_args=["--disable-extensions"],
    )
