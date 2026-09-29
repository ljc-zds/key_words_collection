from pathlib import Path

from product_hunt.aitdk.cdp.browser import (
    content_script_ready_delay_ms,
    chromium_arguments,
    prepare_chrome_extension_profile,
    traffic_result_timeout_ms,
)


def test_chromium_arguments_load_only_the_supplied_extension(tmp_path: Path) -> None:
    extension = tmp_path / "extension"
    extension.mkdir()
    arguments = chromium_arguments(extension)
    assert f"--disable-extensions-except={extension}" in arguments
    assert f"--load-extension={extension}" in arguments


def test_content_script_ready_delay_allows_hotkey_registration() -> None:
    assert content_script_ready_delay_ms() == 1_500


def test_traffic_result_timeout_is_short_enough_for_batch_collection() -> None:
    assert traffic_result_timeout_ms() == 15_000


def test_prepare_chrome_profile_copies_only_extension_state(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    extension_id = "test-extension"
    for relative in ("Local State", "Default/Preferences", "Default/Secure Preferences"):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    for storage in ("Extensions", "Local Extension Settings", "Sync Extension Settings"):
        path = source / "Default" / storage / extension_id / "state"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(storage)
    (source / "Default/History").write_text("private browsing data")

    prepare_chrome_extension_profile(source, target, extension_id)

    assert (target / "Default/Extensions" / extension_id / "state").is_file()
    assert (target / "Default/Local Extension Settings" / extension_id / "state").is_file()
    assert not (target / "Default/History").exists()
