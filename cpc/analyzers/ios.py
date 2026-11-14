from __future__ import annotations

import plistlib
import zipfile
from pathlib import Path
from typing import Any
from xml.parsers.expat import ExpatError

from cpc.archive import MAX_MANIFEST_BYTES, collect_archive_inventory, create_analysis, read_member_limited
from cpc.models import Component, Dependency, FeatureEvidence, PackageAnalysis


def _normalize_plist(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _normalize_plist(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_plist(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _feature_evidence(metadata: dict[str, Any], files: list[str], permissions: list[str]) -> list[FeatureEvidence]:
    all_text = "\n".join([*files, *permissions, *metadata.keys(), repr(metadata)]).lower()
    checks = [
        ("camera", "Câmera", ("nscamerausagedescription", "avfoundation.framework", "camera")),
        ("location", "Localização", ("nslocation", "corelocation.framework", "location")),
        ("notifications", "Notificações push", ("remote-notification", "usernotifications.framework", "push")),
        ("bluetooth", "Bluetooth", ("nsbluetooth", "corebluetooth.framework")),
        ("contacts", "Contatos", ("nscontacts", "contacts.framework")),
        ("health", "Saúde", ("healthkit.framework", "healthkit", "nshealth")),
        ("payments", "Pagamentos / compras no app", ("storekit.framework", "storekit", "in-app purchase")),
        ("biometrics", "Biometria", ("localauthentication.framework", "faceid", "touchid")),
        ("background", "Execução em segundo plano", ("uibackgroundmodes", "background fetch", "processing")),
    ]
    features: list[FeatureEvidence] = []
    for feature_id, label, needles in checks:
        found = [needle for needle in needles if needle in all_text]
        if found:
            features.append(FeatureEvidence(feature_id, label, found))
    return features


def analyze_ipa(path: Path) -> PackageAnalysis:
    analysis = create_analysis("ipa", path)
    try:
        with zipfile.ZipFile(path) as archive:
            files = collect_archive_inventory(analysis, archive)
            all_app_plists = [name for name in files if name.startswith("Payload/") and name.endswith(".app/Info.plist")]
            # The primary iOS app is directly under Payload; nested watch apps have their own Info.plist.
            plist_paths = [name for name in all_app_plists if name.count("/") == 2]
            if not plist_paths:
                plist_paths = all_app_plists
            if not plist_paths:
                raise ValueError("Não foi encontrado Payload/*.app/Info.plist no IPA.")
            if len(plist_paths) > 1:
                analysis.warnings.append("O IPA contém mais de um app diretamente em Payload; metadados do primeiro foram escolhidos.")
            elif len(all_app_plists) > 1:
                analysis.warnings.append("O IPA inclui apps aninhados (por exemplo, watchOS); os metadados principais foram lidos do app diretamente em Payload.")
            plist_path = sorted(plist_paths, key=lambda name: (".appex/" in name, name))[0]
            plist_bytes = read_member_limited(archive, plist_path, MAX_MANIFEST_BYTES)
            metadata = _normalize_plist(plistlib.loads(plist_bytes))
    except (zipfile.BadZipFile, KeyError, OSError, ValueError, OverflowError, TypeError, RecursionError, ExpatError, plistlib.InvalidFileException) as exc:
        raise ValueError(f"Não foi possível analisar o IPA: {exc}") from exc

    if not isinstance(metadata, dict):
        raise ValueError("A raiz do Info.plist deve ser um dicionário.")
    analysis.metadata = metadata
    analysis.package_id = str(metadata.get("CFBundleIdentifier", "")) or None
    analysis.app_name = str(metadata.get("CFBundleDisplayName") or metadata.get("CFBundleName") or "") or None
    analysis.version = str(metadata.get("CFBundleShortVersionString", "")) or None
    analysis.build_version = str(metadata.get("CFBundleVersion", "")) or None
    analysis.minimum_os = str(metadata.get("MinimumOSVersion", "")) or None
    device_family = metadata.get("UIDeviceFamily", [])
    if isinstance(device_family, (list, tuple)):
        labels: list[str] = []
        invalid_family_value = False
        for item in device_family:
            if isinstance(item, bool):
                invalid_family_value = True
                continue
            if isinstance(item, int):
                family_id = item
            elif isinstance(item, str) and item.isdecimal():
                family_id = int(item)
            else:
                invalid_family_value = True
                continue
            labels.append({1: "iPhone", 2: "iPad"}.get(family_id, str(item)))
        analysis.target_os = ", ".join(dict.fromkeys(labels)) or None
        if invalid_family_value:
            analysis.warnings.append("Alguns valores de UIDeviceFamily têm formato inesperado e foram ignorados.")
    elif device_family:
        analysis.warnings.append("UIDeviceFamily tem formato inesperado no Info.plist e foi ignorado.")

    usage_keys = sorted(key for key in metadata if key.startswith("NS") and key.endswith("UsageDescription"))
    analysis.permissions = usage_keys
    for ext in sorted({name.rsplit("/", 1)[-1].split(".", 1)[0] for name in files if ".appex/" in name}):
        analysis.components.append(Component("app extension", ext))

    framework_paths = [name for name in files if "/Frameworks/" in name and (".framework/" in name or name.endswith(".dylib"))]
    native_paths = {name for name in files if name.endswith(".dylib") or ".framework/" in name and name.count("/") < 5}
    executable = metadata.get("CFBundleExecutable")
    if isinstance(executable, str) and executable:
        executable_path = f"{plist_path.rsplit('/Info.plist', 1)[0]}/{executable}"
        if executable_path in files:
            native_paths.add(executable_path)
        else:
            analysis.warnings.append(f"Executável declarado no Info.plist não encontrado no pacote: {executable}.")
    analysis.native_binaries = sorted(native_paths)[:500]
    for framework in sorted({name.split("/Frameworks/", 1)[1].split("/", 1)[0] for name in framework_paths}):
        analysis.dependencies.append(Dependency(framework, "framework", "Frameworks/" + framework))

    framework_hints = [
        ("Flutter", ("flutter.framework", "app.framework", "flutter_assets/")),
        ("React Native", ("react.framework", "hermes.framework", "main.jsbundle")),
        ("Unity", ("unityframework.framework", "data/raw/")),
        ("Kotlin Multiplatform", ("kotlinmultiplatform", "kotlinx.coroutines")),
    ]
    file_text = "\n".join(files).lower()
    known_frameworks = {item.name.casefold().removesuffix(".framework") for item in analysis.dependencies if item.category == "framework"}
    for name, needles in framework_hints:
        evidence = next((item for item in needles if item in file_text), None)
        if evidence and name.casefold().removesuffix(".framework") not in known_frameworks:
            analysis.dependencies.append(Dependency(name, "framework", evidence))
            known_frameworks.add(name.casefold().removesuffix(".framework"))
    if any(name.endswith("embedded.mobileprovision") for name in files):
        analysis.warnings.append("O perfil de provisionamento foi inventariado, mas sua assinatura CMS e os entitlements não foram decodificados nesta versão.")
    if any(Path(name).name.casefold().endswith(".car") for name in files):
        analysis.warnings.append("Catálogos de recursos compilados (.car) foram inventariados, mas não foram extraídos nem decodificados nesta versão.")
    if analysis.native_binaries:
        analysis.warnings.append("Executáveis Mach-O e frameworks Apple não podem ser reutilizados diretamente em Android.")
    if not analysis.package_id:
        analysis.warnings.append("CFBundleIdentifier não foi encontrado no Info.plist.")
    analysis.resource_candidates = [name for name in files if Path(name).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".ttf", ".otf", ".mp3", ".ogg", ".wav", ".json", ".strings", ".plist"}][:500]
    analysis.features = _feature_evidence(metadata, files, analysis.permissions)
    return analysis
