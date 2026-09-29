from pathlib import Path
from zipfile import ZipFile

import pytest

from product_hunt.aitdk.data.archive import ArchiveError, unpack_extension_archive


def test_unpack_extension_archive_returns_manifest_directory(tmp_path: Path) -> None:
    archive = tmp_path / "extension.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("2.7.0_0/manifest.json", '{"manifest_version": 3}')
    destination = tmp_path / "runtime" / "extension"
    assert unpack_extension_archive(archive, destination) == destination
    assert (destination / "manifest.json").is_file()


def test_unpack_extension_archive_rejects_missing_manifest(tmp_path: Path) -> None:
    archive = tmp_path / "invalid.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("extension/readme.txt", "missing manifest")
    with pytest.raises(ArchiveError, match="manifest.json"):
        unpack_extension_archive(archive, tmp_path / "runtime" / "extension")
