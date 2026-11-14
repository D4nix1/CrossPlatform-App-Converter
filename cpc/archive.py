from __future__ import annotations

import os
import zipfile
from pathlib import Path

from cpc.models import PackageAnalysis

MAX_ENTRIES = 100_000
MAX_MANIFEST_BYTES = 16 * 1024 * 1024


def detect_package_kind(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    if path.suffix.lower() not in {".apk", ".ipa"}:
        raise ValueError("Formato não reconhecido: selecione um arquivo .apk ou .ipa.")
    if not zipfile.is_zipfile(path):
        raise ValueError("O arquivo não é um pacote ZIP/APK/IPA válido.")
    with zipfile.ZipFile(path) as archive:
        names = [item.filename for item in archive.infolist()[:MAX_ENTRIES]]
    has_android_manifest = "AndroidManifest.xml" in names
    has_ipa_payload = any(name.startswith("Payload/") and name.endswith(".app/Info.plist") for name in names)
    suffix_kind = path.suffix.lower()[1:]
    if has_android_manifest and has_ipa_payload:
        raise ValueError("O arquivo contém marcadores conflitantes de APK e IPA.")
    if has_android_manifest:
        return "apk"
    if has_ipa_payload:
        return "ipa"
    raise ValueError(f"O ZIP não contém a estrutura esperada para um {suffix_kind.upper()}.")


def collect_archive_inventory(analysis: PackageAnalysis, archive: zipfile.ZipFile) -> list[str]:
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES:
        analysis.warnings.append(f"Inventário limitado aos primeiros {MAX_ENTRIES:,} itens do ZIP.")
        infos = infos[:MAX_ENTRIES]
    analysis.file_count = len(infos)
    analysis.total_uncompressed_size = sum(max(0, item.file_size) for item in infos)
    files: list[str] = []
    types: dict[str, int] = {}
    for item in infos:
        name = item.filename
        if item.is_dir():
            continue
        files.append(name)
        ext = Path(name).suffix.lower() or "(sem extensão)"
        types[ext] = types.get(ext, 0) + 1
    analysis.file_types = dict(sorted(types.items()))
    return files


def read_member_limited(archive: zipfile.ZipFile, name: str, limit: int = MAX_MANIFEST_BYTES) -> bytes:
    info = archive.getinfo(name)
    if info.file_size > limit:
        raise ValueError(f"O item {name} excede o limite de leitura de {limit // (1024 * 1024)} MB.")
    with archive.open(info) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"O item {name} excede o limite de leitura seguro.")
    return data


def create_analysis(kind: str, path: Path) -> PackageAnalysis:
    return PackageAnalysis(
        kind=kind,
        path=os.fspath(path.resolve()),
        file_name=path.name,
        file_size=path.stat().st_size,
    )
