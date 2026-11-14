from __future__ import annotations

import re
import struct
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from cpc.archive import collect_archive_inventory, create_analysis, read_member_limited
from cpc.models import Component, Dependency, FeatureEvidence, PackageAnalysis

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ANDROID_NS_BRACE = "{" + ANDROID_NS + "}"


def _local_name(name: str) -> str:
    if "}" in name:
        return name.rsplit("}", 1)[1]
    if ":" in name:
        return name.rsplit(":", 1)[1]
    return name


def _length8(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    if first & 0x80:
        return ((first & 0x7F) << 8) | data[offset + 1], offset + 2
    return first, offset + 1


def _length16(data: bytes, offset: int) -> tuple[int, int]:
    first = struct.unpack_from("<H", data, offset)[0]
    if first & 0x8000:
        second = struct.unpack_from("<H", data, offset + 2)[0]
        return ((first & 0x7FFF) << 16) | second, offset + 4
    return first, offset + 2


def _parse_string_pool(data: bytes, offset: int, size: int) -> list[str]:
    if size < 28 or offset + size > len(data):
        raise ValueError("String pool Android XML inválido.")
    _, header_size, chunk_size = struct.unpack_from("<HHI", data, offset)
    if chunk_size > size or header_size < 28:
        raise ValueError("Cabeçalho do string pool inválido.")
    string_count, _style_count, flags, strings_start, _styles_start = struct.unpack_from("<IIIII", data, offset + 8)
    if string_count > 1_000_000 or header_size + string_count * 4 > chunk_size:
        raise ValueError("Contagem de strings inválida no Android XML.")
    utf8 = bool(flags & 0x100)
    strings: list[str] = []
    for index in range(string_count):
        relative = struct.unpack_from("<I", data, offset + header_size + index * 4)[0]
        pos = offset + strings_start + relative
        if pos >= offset + chunk_size:
            raise ValueError("Offset fora do string pool Android XML.")
        if utf8:
            _utf16_len, pos = _length8(data, pos)
            byte_len, pos = _length8(data, pos)
            raw = data[pos:pos + byte_len]
            strings.append(raw.decode("utf-8", errors="replace"))
        else:
            char_len, pos = _length16(data, pos)
            raw = data[pos:pos + char_len * 2]
            strings.append(raw.decode("utf-16le", errors="replace"))
    return strings


def parse_binary_android_xml(data: bytes) -> list[tuple[str, dict[str, Any]]]:
    """Read tag names and attributes from Android's compiled XML (AXML) format."""
    if len(data) < 8:
        raise ValueError("Manifesto Android binário truncado.")
    root_type, root_header, root_size = struct.unpack_from("<HHI", data, 0)
    if root_type != 0x0003 or root_header < 8 or root_size > len(data):
        raise ValueError("Cabeçalho Android AXML inválido.")
    strings: list[str] = []
    events: list[tuple[str, dict[str, Any]]] = []
    cursor = root_header
    while cursor + 8 <= min(root_size, len(data)):
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, cursor)
        if chunk_size < 8 or cursor + chunk_size > root_size:
            raise ValueError("Chunk Android AXML inválido.")
        if chunk_type == 0x0001:
            strings = _parse_string_pool(data, cursor, chunk_size)
        elif chunk_type == 0x0102:
            if not strings or header_size < 16 or chunk_size < 36:
                raise ValueError("Elemento Android AXML sem string pool ou truncado.")
            _line, _comment, _ns, name_index, attr_start, attr_size, attr_count = struct.unpack_from(
                "<IIIIHHH", data, cursor + 8
            )
            if attr_size < 20 or attr_count > 16_384:
                raise ValueError("Atributos Android AXML inválidos.")
            name = strings[name_index] if name_index < len(strings) else "?"
            attrs: dict[str, Any] = {}
            first_attr = cursor + 16 + attr_start
            for i in range(attr_count):
                pos = first_attr + i * attr_size
                if pos + 20 > cursor + chunk_size:
                    raise ValueError("Atributo Android AXML truncado.")
                _ns_idx, attr_name, raw_idx = struct.unpack_from("<III", data, pos)
                _value_size, _res0, value_type = struct.unpack_from("<HBB", data, pos + 12)
                value_data = struct.unpack_from("<I", data, pos + 16)[0]
                attr_key = strings[attr_name] if attr_name < len(strings) else f"attribute_{i}"
                if raw_idx != 0xFFFFFFFF and raw_idx < len(strings):
                    value: Any = strings[raw_idx]
                elif value_type == 0x03 and value_data < len(strings):
                    value = strings[value_data]
                elif value_type == 0x12:
                    value = bool(value_data)
                elif value_type == 0x10:
                    value = value_data
                elif value_type == 0x11:
                    value = hex(value_data)
                else:
                    value = value_data
                attrs[attr_key] = value
            events.append((name, attrs))
        cursor += chunk_size
    return events


def _parse_manifest(data: bytes) -> list[tuple[str, dict[str, Any]]]:
    if data.lstrip().startswith(b"<"):
        if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", data, flags=re.IGNORECASE):
            raise ValueError("DTD e entidades não são aceitos no manifesto por segurança.")
        root = ET.fromstring(data)
        result: list[tuple[str, dict[str, Any]]] = []
        for element in root.iter():
            attrs = {_local_name(key): value for key, value in element.attrib.items()}
            result.append((_local_name(element.tag), attrs))
        return result
    try:
        return parse_binary_android_xml(data)
    except (IndexError, struct.error) as exc:
        raise ValueError("Android AXML truncado ou malformado.") from exc


def _xml_str(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return str(value) if value is not None else ""


def _add_android_features(analysis: PackageAnalysis, files: list[str]) -> None:
    text = "\n".join([*analysis.permissions, *files, *analysis.metadata.keys()]).lower()
    checks = [
        ("camera", "Câmera", ("android.permission.camera", "camerax", "camera2")),
        ("location", "Localização", ("android.permission.access_fine_location", "android.permission.access_coarse_location", "location")),
        ("notifications", "Notificações push", ("android.permission.post_notifications", "firebase-messaging", "firebase/messaging")),
        ("bluetooth", "Bluetooth", ("android.permission.bluetooth", "bluetooth_le", "bluetoothadapter")),
        ("contacts", "Contatos", ("android.permission.read_contacts", "android.permission.write_contacts")),
        ("health", "Saúde", ("healthconnect", "android.permission.health", "healthconnectclient")),
        ("payments", "Pagamentos / compras no app", ("com.android.vending.billing", "billingclient", "googlepay")),
        ("biometrics", "Biometria", ("use_biometric", "use_fingerprint", "biometricprompt")),
        ("background", "Execução em segundo plano", ("foreground_service", "android.permission.boot_completed", "workmanager")),
    ]
    for feature_id, label, needles in checks:
        evidence = [item for item in [*analysis.permissions, *files] if any(needle in item.lower() for needle in needles)]
        if evidence:
            analysis.features.append(FeatureEvidence(feature_id, label, sorted(set(evidence))[:8]))


def analyze_apk(path: Path) -> PackageAnalysis:
    analysis = create_analysis("apk", path)
    try:
        with zipfile.ZipFile(path) as archive:
            files = collect_archive_inventory(analysis, archive)
            manifest_bytes = read_member_limited(archive, "AndroidManifest.xml")
            events = _parse_manifest(manifest_bytes)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError, ET.ParseError) as exc:
        raise ValueError(f"Não foi possível analisar o APK: {exc}") from exc

    for tag, attrs in events:
        if tag == "manifest":
            analysis.package_id = _xml_str(attrs.get("package")) or None
            analysis.version = _xml_str(attrs.get("versionName")) or None
            analysis.build_version = _xml_str(attrs.get("versionCode")) or None
        elif tag == "uses-sdk":
            analysis.minimum_os = _xml_str(attrs.get("minSdkVersion")) or None
            analysis.target_os = _xml_str(attrs.get("targetSdkVersion")) or None
        elif tag.startswith("uses-permission"):
            permission = _xml_str(attrs.get("name"))
            if permission:
                analysis.permissions.append(permission)
        elif tag in {"activity", "activity-alias", "service", "receiver", "provider"}:
            name = _xml_str(attrs.get("name"))
            if name:
                analysis.components.append(Component(
                    kind=tag,
                    name=name,
                    exported=attrs.get("exported") if isinstance(attrs.get("exported"), bool) else None,
                    permission=_xml_str(attrs.get("permission")) or None,
                ))
        elif tag == "application":
            analysis.app_name = _xml_str(attrs.get("label")) or None

    analysis.permissions = sorted(set(analysis.permissions))
    analysis.native_binaries = [name for name in files if name.startswith("lib/") and name.lower().endswith(".so")]
    analysis.resource_candidates = [name for name in files if name.startswith(("assets/", "res/")) and Path(name).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".ttf", ".otf", ".mp3", ".ogg", ".wav", ".json", ".xml"}][:500]
    framework_markers = [
        ("Flutter", "framework", ("flutter_assets/", "libflutter.so", "libapp.so")),
        ("React Native", "framework", ("libreactnativejni.so", "index.android.bundle")),
        ("Unity", "framework", ("libunity.so", "assets/bin/data/")),
        ("Capacitor", "framework", ("assets/capacitor.config", "com.getcapacitor")),
    ]
    for name, category, needles in framework_markers:
        evidence = next((item for item in files if any(needle in item.lower() for needle in needles)), None)
        if evidence:
            analysis.dependencies.append(Dependency(name, category, evidence))
    if analysis.native_binaries:
        native_by_name: dict[str, list[str]] = {}
        for path in analysis.native_binaries:
            native_by_name.setdefault(Path(path).name, []).append(path)
        analysis.dependencies.extend(
            Dependency(name, "native library", paths[0] if len(paths) == 1 else f"{len(paths)} variantes ABI: " + ", ".join(paths[:8]))
            for name, paths in sorted(native_by_name.items())
        )
    if not analysis.package_id:
        analysis.warnings.append("O identificador do pacote não foi encontrado no manifesto.")
    if analysis.native_binaries:
        analysis.warnings.append("Bibliotecas .so são específicas de ABI Android e não são reutilizáveis diretamente no iOS.")
    if not analysis.components:
        analysis.warnings.append("Nenhum componente Android foi extraído do manifesto.")
    _add_android_features(analysis, files)
    return analysis
