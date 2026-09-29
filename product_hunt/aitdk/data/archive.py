from pathlib import Path
from zipfile import ZipFile


class ArchiveError(ValueError):
    """The supplied extension archive is not safe or loadable."""


def unpack_extension_archive(archive: Path, destination: Path) -> Path:
    """Unpack the archive's single extension root into ``destination``."""
    with ZipFile(archive) as bundle:
        manifests = [name for name in bundle.namelist() if name.endswith("/manifest.json")]
        if len(manifests) != 1:
            raise ArchiveError("archive must contain exactly one manifest.json")

        root = manifests[0].removesuffix("manifest.json")
        destination.mkdir(parents=True, exist_ok=True)
        for member in bundle.infolist():
            if not member.filename.startswith(root) or member.is_dir():
                continue
            relative = Path(member.filename.removeprefix(root))
            if relative.is_absolute() or ".." in relative.parts:
                raise ArchiveError("archive contains an unsafe path")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(member))

    if not (destination / "manifest.json").is_file():
        raise ArchiveError("manifest.json was not unpacked")
    return destination
