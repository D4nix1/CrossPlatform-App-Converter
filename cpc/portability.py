from __future__ import annotations

import json
import hashlib
import re
import shutil
import struct
import zipfile
from pathlib import PurePosixPath
from pathlib import Path

from cpc.models import PackageAnalysis

TARGET_API_HINTS = {
    "camera": {
        "android": "AndroidX CameraX (CameraProvider/UseCase)",
        "ios": "AVFoundation (AVCaptureSession)",
    },
    "location": {
        "android": "Location Services / Fused Location Provider",
        "ios": "Core Location (CLLocationManager)",
    },
    "notifications": {
        "android": "Android notification APIs; select a push provider if required",
        "ios": "UserNotifications and APNs; configure push entitlements if required",
    },
    "bluetooth": {
        "android": "BluetoothAdapter / Bluetooth LE APIs",
        "ios": "Core Bluetooth (CBCentralManager/CBPeripheral)",
    },
    "contacts": {
        "android": "Contacts Provider / ContactsContract",
        "ios": "Contacts framework (CNContactStore)",
    },
    "health": {
        "android": "Health Connect (availability and permissions must be reviewed)",
        "ios": "HealthKit (capability, entitlement, and review required)",
    },
    "payments": {
        "android": "Google Play Billing or the applicable payment API",
        "ios": "StoreKit or the applicable payment API",
    },
    "biometrics": {
        "android": "BiometricPrompt",
        "ios": "LocalAuthentication (LAContext)",
    },
    "background": {
        "android": "WorkManager or a foreground service, based on user-visible work",
        "ios": "BackgroundTasks; execution is system-scheduled and limited",
    },
}


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", ".", value).strip(".").lower()
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "app." + cleaned
    parts = [part if part and part[0].isalpha() else "p" + part for part in cleaned.split(".")]
    return ".".join(parts)[:80]


def _new_directory(parent: Path, name: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    base = parent / name
    for index in range(1, 10_000):
        candidate = base if index == 1 else parent / f"{name}-{index}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise FileExistsError(f"Não foi possível criar diretório livre em {parent}.")


def _unsafe_member_path(member: PurePosixPath, original: str) -> bool:
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
    if member.is_absolute() or ".." in member.parts or "\\" in original or ":" in original or "\0" in original:
        return True
    for part in member.parts:
        stem = part.rstrip(" .").split(".", 1)[0].casefold()
        if part != part.rstrip(" .") or stem in reserved or len(part) > 150:
            return True
    return False


def create_scaffold(
    source: PackageAnalysis,
    target: str,
    output_parent: str | Path,
    *,
    swiftui_preview: str | Path | None = None,
) -> Path:
    """Create a clearly labelled starting project. Existing files are never replaced."""
    if target not in {"android", "ios"}:
        raise ValueError("O destino deve ser 'android' ou 'ios'.")
    if (source.kind == "apk" and target == "android") or (source.kind == "ipa" and target == "ios"):
        raise ValueError("Escolha a plataforma oposta à do pacote de origem.")
    source_stem = Path(source.file_name).stem
    destination = _new_directory(Path(output_parent).expanduser(), f"{_safe_id(source_stem)}-{target}-starter")
    package_id = _safe_id(source.package_id or source_stem or "portability.starter")
    inventory = _build_migration_plan(source, target)
    resource_inventory = {
        "source_file": source.file_name,
        "source_platform": source.kind,
        "target_platform": target,
        "resource_candidates_reviewed": source.resource_candidates,
        "warning": "Candidatos não foram copiados neste inventário; revise licença e conteúdo antes de reutilizar.",
    }
    (destination / "resource-inventory.json").write_text(
        json.dumps(resource_inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if target == "android":
        _write_android(destination, package_id)
    else:
        _write_ios(destination, package_id, swiftui_preview=swiftui_preview)
    _write_migration_plan(destination, inventory)
    return destination


def _build_migration_plan(source: PackageAnalysis, target: str) -> dict:
    """Preserve extracted evidence as an actionable, explicitly incomplete porting plan."""
    component_tasks = [
        {
            "kind": item.kind,
            "name": item.name,
            "exported": item.exported,
            "required_permission": item.permission,
            "status": "reconstruction_required",
        }
        for item in source.components
    ]
    feature_tasks = [
        {
            "id": item.feature_id,
            "name": item.label,
            "evidence": item.evidence,
            "target_api_hint": TARGET_API_HINTS.get(item.feature_id, {}).get(
                target, "Pesquisar e validar a API nativa equivalente para esta funcionalidade"
            ),
            "status": "verify_and_reimplement",
        }
        for item in source.features
    ]
    return {
        "schema_version": "1.0",
        "source": {
            "file": source.file_name,
            "platform": source.kind,
            "package_id": source.package_id,
            "app_name": source.app_name,
            "version": source.version,
            "build_version": source.build_version,
            "minimum_os": source.minimum_os,
            "target_os": source.target_os,
            "package_size_bytes": source.file_size,
        },
        "target_platform": target,
        "extracted_evidence": {
            "metadata": source.metadata,
            "components": component_tasks,
            "permissions_or_usage_descriptions": source.permissions,
            "features_to_verify": feature_tasks,
            "dependencies": [item.__dict__ for item in source.dependencies],
            "native_binaries_not_ported": source.native_binaries,
            "resource_candidates": source.resource_candidates,
            "archive_file_count": source.file_count,
            "analysis_warnings": source.warnings,
        },
        "reconstruction_checklist": [
            {"task": "Revisar as evidências extraídas e confirmar quais pertencem ao app principal", "status": "todo"},
            {"task": "Reconstruir cada tela, fluxo de navegação e interação", "status": "todo"},
            {"task": "Reimplementar o comportamento e os serviços nativos na plataforma de destino", "status": "todo"},
            {"task": "Selecionar dependências da plataforma de destino e substituir binários incompatíveis", "status": "todo"},
            {"task": "Revisar permissões, textos de privacidade, assinatura e requisitos da loja", "status": "todo"},
            {"task": "Compilar, instalar e testar em aparelhos e versões suportadas da plataforma de destino", "status": "todo"},
        ],
        "limitations": [
            "Este é um relatório de evidências e um projeto-base, não um tradutor automático de código.",
            "Em geral, pacotes APK/IPA não incluem o código-fonte editável original.",
            "Nomes, permissões, recursos e indícios de funcionalidades não comprovam o comportamento em execução.",
            "Lógica, telas, bibliotecas nativas, identidade de assinatura e configuração de loja não são portadas automaticamente.",
            "Verifique direitos autorais, licenças, privacidade e autorização antes de reutilizar conteúdo.",
        ],
    }


def _write_migration_plan(destination: Path, plan: dict) -> None:
    (destination / "migration-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    source = plan["source"]
    evidence = plan["extracted_evidence"]
    lines = [
        "# Plano de reconstrução (rascunho)",
        "",
        "> Este arquivo organiza evidências estáticas; não significa que o app foi convertido.",
        "",
        "## Pacote analisado",
        "",
        f"- Arquivo: `{source['file']}` ({source['platform'].upper()})",
        f"- App: {source['app_name'] or '(não identificado)'}",
        f"- Identificador: `{source['package_id'] or '(não identificado)'}`",
        f"- Versão: {source['version'] or '(não identificada)'}",
        f"- Plataforma de destino: {plan['target_platform']}",
        "",
        "## Evidências encontradas",
        "",
        f"- Componentes: {len(evidence['components'])}",
        f"- Indícios de funcionalidades para revisar: {len(evidence['features_to_verify'])}",
        f"- Permissões/descrições de uso: {len(evidence['permissions_or_usage_descriptions'])}",
        f"- Bibliotecas/dependências reconhecidas: {len(evidence['dependencies'])}",
        f"- Recursos candidatos: {len(evidence['resource_candidates'])}",
        f"- Binários nativos específicos da origem, sem portabilidade automática: {len(evidence['native_binaries_not_ported'])}",
        "",
        "Os detalhes completos e as evidências estão em `migration-plan.json`. As contagens são pistas de inventário, não equivalência funcional.",
        "Sugestões de API são referências para investigação e não geram implementação, permissões nem configuração de plataforma automaticamente.",
        "",
        "## Lista de reconstrução",
        "",
    ]
    lines.extend(f"- [ ] {task['task']}" for task in plan["reconstruction_checklist"])
    lines.extend(["", "## Limites", ""])
    lines.extend(f"- {item}" for item in plan["limitations"])
    (destination / "MIGRATION-PLAN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_conversion_attempt(source: PackageAnalysis, output_parent: str | Path) -> tuple[Path, int, list[str]]:
    """Create an editable porting draft with selected assets, never a pretend installable app."""
    target = "ios" if source.kind == "apk" else "android"
    destination = create_scaffold(source, target, output_parent)
    source_archive = Path(source.path)
    resource_root = destination / "imported_resources"
    copied = 0
    skipped: list[str] = []
    total_bytes = 0
    max_file_bytes = 20 * 1024 * 1024
    max_total_bytes = 200 * 1024 * 1024
    candidate_names = set(source.resource_candidates[:500])
    copied_paths: list[Path] = []

    try:
        with zipfile.ZipFile(source_archive) as archive:
            for name in sorted(candidate_names):
                member = PurePosixPath(name)
                info = archive.getinfo(name)
                mode = info.external_attr >> 16
                is_symlink = (mode & 0o170000) == 0o120000
                if _unsafe_member_path(member, name) or info.is_dir() or is_symlink:
                    skipped.append(f"{name}: caminho inseguro")
                    continue
                if info.file_size > max_file_bytes or total_bytes + info.file_size > max_total_bytes:
                    skipped.append(f"{name}: limite de tamanho atingido")
                    continue
                target_path = resource_root.joinpath(*member.parts)
                if len(str(target_path)) > 240:
                    skipped.append(f"{name}: caminho excede o limite seguro do Windows")
                    continue
                created_file = False
                try:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as src, target_path.open("xb") as dst:
                        created_file = True
                        shutil.copyfileobj(src, dst)
                except FileExistsError:
                    skipped.append(f"{name}: colisão de caminho após normalização")
                    continue
                except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    if created_file:
                        target_path.unlink(missing_ok=True)
                    skipped.append(f"{name}: falha ao copiar ({exc})")
                    continue
                copied += 1
                total_bytes += info.file_size
                copied_paths.append(target_path)
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError) as exc:
        skipped.append(f"Não foi possível copiar todos os recursos: {exc}")

    native_map = _integrate_native_images(destination, target, copied_paths)
    (destination / "native-resource-map.json").write_text(
        json.dumps(native_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (destination / "resource-inventory.json").write_text(
        json.dumps({
            "source_file": source.file_name,
            "source_platform": source.kind,
            "target_platform": target,
            "resource_candidates_reviewed": source.resource_candidates,
            "copied_to_imported_resources": [
                path.relative_to(resource_root).as_posix() for path in copied_paths
            ],
            "native_asset_count": len(native_map["assets"]),
            "warning": "Candidatos foram copiados por extensão/nome; revise visualmente, licença, resolução e uso antes de integrar à interface.",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    target_name = "IPA" if target == "ios" else "APK"
    notice = (
        "RASCUNHO EXPERIMENTAL — NÃO É UM APP INSTALÁVEL.\n"
        "O conversor não é milagroso: este conteúdo pode conter erros/bugs, estar incompleto e até resultar em um app que não funciona. Revise, compile e teste antes de publicar.\n"
        f"Origem: {source.file_name} ({source.kind.upper()})\nDestino pretendido: {target_name}\n"
        f"Recursos mantidos na pasta de revisão: {copied}.\n"
        f"Imagens adicionadas ao catálogo nativo do projeto-base: {len(native_map['assets'])}.\n"
        "O código original, telas, lógica, bibliotecas nativas e assinatura não foram convertidos.\n"
        "Use este projeto-base para reconstrução manual. Ele precisa ser implementado, compilado e testado "
        "com as ferramentas da plataforma de destino.\n"
    )
    if skipped:
        notice += "Itens ignorados:\n" + "\n".join(skipped) + "\n"
    (destination / "CONVERSION-ATTEMPT.txt").write_text(notice, encoding="utf-8")

    archive_base = Path(output_parent).expanduser()
    archive_base.mkdir(parents=True, exist_ok=True)
    output = archive_base / f"{destination.name}-attempt.zip"
    index = 2
    while output.exists():
        output = archive_base / f"{destination.name}-attempt-{index}.zip"
        index += 1
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for file_path in destination.rglob("*"):
            if file_path.is_file():
                bundle.write(file_path, file_path.relative_to(destination).as_posix())
    return output, copied, skipped


def _asset_stem(filename: str) -> str:
    stem = Path(filename).stem.lower()
    stem = re.sub(r"[^a-z0-9_]+", "_", stem).strip("_")
    if not stem or not stem[0].isalpha():
        stem = "asset_" + stem
    return stem[:70].rstrip("_") or "asset"


def _unique_asset_stem(filename: str, used: set[str], *, max_length: int = 70) -> str:
    stem = _asset_stem(filename)
    candidate = stem
    if len(candidate) > max_length:
        digest = hashlib.sha256(filename.encode("utf-8", errors="replace")).hexdigest()[:8]
        candidate = f"{stem[:max(0, max_length - 9)]}_{digest}"
    if candidate in used:
        digest = hashlib.sha256(filename.encode("utf-8", errors="replace")).hexdigest()[:8]
        candidate = f"{stem[:max(0, max_length - 9)]}_{digest}"
        index = 2
        while candidate in used:
            suffix = f"_{index}"
            candidate = f"{stem[:max(0, max_length - len(digest) - len(suffix) - 1)]}_{digest}{suffix}"
            index += 1
    used.add(candidate)
    return candidate


def _has_valid_raster_header(path: Path) -> bool:
    data = path.read_bytes()
    ext = path.suffix.lower()
    if ext == ".png":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            return False
        width, height = struct.unpack(">II", data[16:24])
        return 0 < width <= 32768 and 0 < height <= 32768 and width * height <= 100_000_000
    if ext in {".jpg", ".jpeg"}:
        return len(data) >= 4 and data.startswith(b"\xff\xd8") and b"\xff\xd9" in data[-4096:]
    if ext == ".webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def _copy_file_exclusive(source: Path, target: Path) -> None:
    """Copy a file without replacing an existing path; remove partial output on failure."""
    created_target = False
    try:
        with source.open("rb") as input_stream, target.open("xb") as output_stream:
            created_target = True
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
    except (OSError, shutil.Error, RuntimeError):
        if created_target:
            target.unlink(missing_ok=True)
        raise


def _integrate_native_images(
    destination: Path,
    target: str,
    copied_paths: list[Path],
    *,
    resource_root: Path | None = None,
) -> dict:
    """Place supported, already-copied raster assets in the target project's native bundle."""
    entries = []
    unsupported = []
    used: set[str] = set()
    resource_root = resource_root or destination / "imported_resources"
    android_root = destination / "app" / "src" / "main" / "res" / "drawable-nodpi"
    ios_root = destination / "Assets.xcassets"
    if target == "android":
        android_root.mkdir(parents=True, exist_ok=True)
        supported = {".png", ".jpg", ".jpeg", ".webp"}
    else:
        ios_root.mkdir(parents=True, exist_ok=True)
        (ios_root / "Contents.json").write_text(
            json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2) + "\n", encoding="utf-8"
        )
        supported = {".png", ".jpg", ".jpeg"}

    for path in copied_paths:
        relative = path.relative_to(resource_root).as_posix()
        ext = path.suffix.lower()
        if ext not in supported:
            if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}:
                unsupported.append({"source": relative, "reason": f"Formato {ext} não é integrado automaticamente no destino {target}."})
            continue
        try:
            if not _has_valid_raster_header(path):
                unsupported.append({"source": relative, "reason": "Cabeçalho de imagem inválido ou dimensões fora dos limites."})
                continue
        except OSError as exc:
            unsupported.append({"source": relative, "reason": f"Não foi possível validar a imagem: {exc}"})
            continue
        max_stem = 70
        if target == "ios":
            # Keep Xcode bundle paths portable even when the project lives in a deeply nested folder.
            max_stem = min(70, (250 - len(str(ios_root)) - 11 - len(ext)) // 2)
            if max_stem < 9:
                unsupported.append({"source": relative, "reason": "pasta base longa demais para criar um caminho Xcode portátil"})
                continue
        stem = _unique_asset_stem(relative, used, max_length=max_stem)
        created_target = False
        image_set: Path | None = None
        target_path: Path | None = None
        if target == "android":
            target_path = android_root / f"{stem}{ext}"
            try:
                _copy_file_exclusive(path, target_path)
                created_target = True
                target_relative = target_path.relative_to(destination).as_posix()
                usage = f"R.drawable.{stem}"
            except (OSError, shutil.Error, RuntimeError) as exc:
                if created_target:
                    target_path.unlink(missing_ok=True)
                unsupported.append({"source": relative, "reason": f"falha ao gravar recurso Android ({exc})"})
                continue
        else:
            image_set = ios_root / f"{stem}.imageset"
            filename = f"{stem}{ext}"
            target_path = image_set / filename
            try:
                image_set.mkdir()
                _copy_file_exclusive(path, target_path)
                created_target = True
                (image_set / "Contents.json").write_text(
                    json.dumps({
                        "images": [{"filename": filename, "idiom": "universal"}],
                        "info": {"author": "xcode", "version": 1},
                    }, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                target_relative = target_path.relative_to(destination).as_posix()
                usage = f'Image("{stem}")'
            except (OSError, shutil.Error, RuntimeError) as exc:
                if created_target:
                    target_path.unlink(missing_ok=True)
                if image_set.is_dir():
                    (image_set / "Contents.json").unlink(missing_ok=True)
                    try:
                        image_set.rmdir()
                    except OSError:
                        pass
                unsupported.append({"source": relative, "reason": f"falha ao gravar asset iOS ({exc})"})
                continue
        entries.append({"source": relative, "target": target_relative, "target_usage_hint": usage})

    return {
        "target_platform": target,
        "integrated_image_count": len(entries),
        "assets": entries,
        "not_integrated": unsupported,
        "limitations": [
            "Image headers are checked, but a full image decode/visual review is not performed; names and pixels are copied without resizing, color conversion, density variants, or semantic review.",
            "Native resource availability does not create or modify app screens or behavior.",
        ],
    }


def import_recovered_android_images_to_ios(destination: str | Path, recovered_resource_root: str | Path) -> dict:
    """Copy decoded Android drawable/mipmap images into an iOS starter for manual review."""
    project = Path(destination).resolve()
    resource_root = Path(recovered_resource_root).resolve()
    imported_root = project / "r"
    allowed_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
    image_paths = sorted(
        (
            path for path in resource_root.rglob("*")
            if path.is_file() and path.suffix.lower() in allowed_extensions
            and (path.parent.name.startswith("drawable") or path.parent.name.startswith("mipmap"))
        ) if resource_root.is_dir() else (),
        key=lambda path: path.relative_to(resource_root).as_posix().casefold(),
    )
    copied_paths: list[Path] = []
    stage_to_source: dict[str, str] = {}
    skipped: list[dict[str, str]] = []
    total_bytes = 0
    max_files = 500
    max_file_bytes = 20 * 1024 * 1024
    max_total_bytes = 200 * 1024 * 1024
    seen: set[str] = set()
    for source in image_paths:
        relative = source.relative_to(resource_root)
        relative_name = relative.as_posix()
        if source.is_symlink() or _unsafe_member_path(PurePosixPath(relative_name), relative_name):
            skipped.append({"source": relative_name, "reason": "caminho ou link inseguro"})
            continue
        normalized = relative_name.casefold()
        if normalized in seen:
            skipped.append({"source": relative_name, "reason": "colisão de caminho no Windows"})
            continue
        seen.add(normalized)
        target: Path | None = None
        created_target = False
        try:
            size = source.stat().st_size
            if len(copied_paths) >= max_files or size > max_file_bytes or total_bytes + size > max_total_bytes:
                skipped.append({"source": relative_name, "reason": "limite de quantidade/tamanho atingido"})
                continue
            source_stem = re.sub(r"[^a-z0-9_]+", "_", source.stem.casefold()).strip("_")[:20] or "image"
            safe_leaf = f"{hashlib.sha256(relative_name.casefold().encode('utf-8')).hexdigest()[:8]}_{source_stem}{source.suffix.lower()}"
            target = imported_root / safe_leaf
            if len(str(target)) > 250:
                skipped.append({"source": relative_name, "reason": "caminho base longo demais para copiar no Windows"})
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as input_stream, target.open("xb") as output_stream:
                created_target = True
                shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
            if target.stat().st_size != size:
                target.unlink(missing_ok=True)
                skipped.append({"source": relative_name, "reason": "cópia incompleta"})
                continue
            copied_paths.append(target)
            total_bytes += size
            stage_to_source[target.relative_to(project).as_posix()] = relative_name
        except (OSError, RuntimeError) as exc:
            if created_target and target is not None:
                target.unlink(missing_ok=True)
            skipped.append({"source": relative_name, "reason": f"falha ao copiar ({exc})"})

    native = _integrate_native_images(project, "ios", copied_paths, resource_root=project)
    result = {
        "source": "JADX decoded Android res/drawable* and res/mipmap* images",
        "target_platform": "ios",
        "copied_to_review_folder": len(copied_paths),
        "bytes_copied": total_bytes,
        "integrated_into_xcode_asset_catalog": native["integrated_image_count"],
        "copied_sources": [
            {"source": stage_to_source[path.relative_to(project).as_posix()], "review_copy": path.relative_to(project).as_posix()}
            for path in copied_paths
        ],
        "native_assets": native["assets"],
        "not_integrated": native["not_integrated"],
        "skipped": skipped,
        "limits": {"max_files": max_files, "max_file_bytes": max_file_bytes, "max_total_bytes": max_total_bytes},
        "limitations": [
            "Only selected decoded raster resources are copied; density/locale variants may duplicate or conflict semantically.",
            "Names and files are not matched to views or semantics, and images are not resized, recolored, or visually reviewed.",
            "Image availability does not recreate UI behavior; the originals inside the APK remain untouched.",
        ],
    }
    for asset in result["native_assets"]:
        asset["source"] = stage_to_source.get(asset["source"], asset["source"])
    (project / "native-resource-map.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _write_android(destination: Path, package_id: str) -> None:
    namespace_path = Path(*package_id.split("."))
    source_dir = destination / "app" / "src" / "main" / "java" / namespace_path
    source_dir.mkdir(parents=True)
    (destination / "settings.gradle.kts").write_text(
        'pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\n'
        'dependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories { google(); mavenCentral() } }\n'
        'rootProject.name = "PortabilityStarter"\ninclude(":app")\n', encoding="utf-8")
    (destination / "build.gradle.kts").write_text(
        'plugins { id("com.android.application") version "8.7.3" apply false }\n', encoding="utf-8")
    (destination / "app" / "build.gradle.kts").write_text(
        'plugins { id("com.android.application") }\n\n'
        f'android {{ namespace = "{package_id}"; compileSdk = 35\n'
        '    defaultConfig { applicationId = namespace; minSdk = 23; targetSdk = 35; versionCode = 1; versionName = "0.1.0" }\n'
        '    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }\n'
        '}\n', encoding="utf-8")
    (destination / "app" / "src" / "main" / "AndroidManifest.xml").write_text(
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <application android:label="Portability Starter" android:theme="@android:style/Theme.Material.Light.NoActionBar">\n'
        '        <activity android:name=".MainActivity" android:exported="true">\n'
        '            <intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter>\n'
        '        </activity>\n    </application>\n</manifest>\n', encoding="utf-8")
    (source_dir / "MainActivity.java").write_text(
        f'package {package_id};\n\n'
        'import android.app.Activity;\nimport android.os.Bundle;\nimport android.widget.TextView;\n\n'
        'public final class MainActivity extends Activity {\n'
        '    @Override protected void onCreate(Bundle state) {\n'
        '        super.onCreate(state);\n'
        '        TextView placeholder = new TextView(this);\n'
        '        placeholder.setText("Portability starter — app behavior has not been ported.");\n'
        '        setContentView(placeholder);\n'
        '    }\n}\n', encoding="utf-8")
    (destination / "README.md").write_text(
        "# Android portability starter\n\n"
        "Status: experimental scaffold; no source code or behavior has been ported.\n\n"
        "Open this folder in Android Studio with Android SDK 35 and JDK 17 installed. Gradle will download the Android Gradle Plugin when you build. In a conversion attempt, supported raster images are copied into drawable-nodpi; see native-resource-map.json for names and paths. They are not wired into the placeholder screen. Review package ID, SDK levels, permissions, dependencies, and license before use. The original package is not modified.\n", encoding="utf-8")


def _write_ios(destination: Path, package_id: str, *, swiftui_preview: str | Path | None = None) -> None:
    project = destination / "PortabilityStarter.xcodeproj"
    project.mkdir()
    asset_catalog = destination / "Assets.xcassets"
    asset_catalog.mkdir()
    (asset_catalog / "Contents.json").write_text(
        json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2) + "\n", encoding="utf-8"
    )
    preview_source = None
    if swiftui_preview is not None:
        preview_path = Path(swiftui_preview).resolve(strict=True)
        if not preview_path.is_file() or preview_path.suffix.lower() != ".swift":
            raise ValueError("A prévia SwiftUI deve ser um arquivo .swift regular.")
        preview_source = preview_path.read_text(encoding="utf-8")
        if "struct ReconstructedPreview: View" not in preview_source:
            raise ValueError("A prévia SwiftUI não contém a tela ReconstructedPreview esperada.")
        preview_source = re.sub(r"\Aimport SwiftUI\s*", "", preview_source, count=1)
    app_source = (
        'import SwiftUI\n\n'
        '@main\nstruct PortabilityStarterApp: App {\n'
        '    var body: some Scene {\n'
        f'        WindowGroup {{ {"ReconstructedPreview()" if preview_source else "ContentView()"} }}\n'
        '    }\n}\n\n'
        + (preview_source if preview_source else (
            'struct ContentView: View {\n'
            '    var body: some View {\n'
            '        Text("Portability starter — app behavior has not been ported.")\n'
            '            .padding()\n'
            '    }\n}\n'
        ))
    )
    (destination / "App.swift").write_text(app_source, encoding="utf-8")
    ids = {
        "project": "A10000000000000000000001", "mainGroup": "A10000000000000000000002",
        "products": "A10000000000000000000003", "appFile": "A10000000000000000000004",
        "productFile": "A10000000000000000000005", "buildFile": "A10000000000000000000006",
        "assetCatalogFile": "A10000000000000000000017", "assetCatalogBuildFile": "A10000000000000000000018",
        "sources": "A10000000000000000000007", "frameworks": "A10000000000000000000008",
        "resources": "A10000000000000000000009", "target": "A10000000000000000000010",
        "projectConfigs": "A10000000000000000000011", "projectDebug": "A10000000000000000000012",
        "projectRelease": "A10000000000000000000013", "targetConfigs": "A10000000000000000000014",
        "targetDebug": "A10000000000000000000015", "targetRelease": "A10000000000000000000016",
    }
    xcode = f'''// !$*UTF8*$!
{{
    archiveVersion = 1;
    classes = {{}};
    objectVersion = 56;
    objects = {{
        {ids['project']} = {{isa = PBXProject; attributes = {{BuildIndependentTargetsInParallel = 1; LastUpgradeCheck = 1600;}}; buildConfigurationList = {ids['projectConfigs']}; compatibilityVersion = "Xcode 14.0"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en, Base); mainGroup = {ids['mainGroup']}; productRefGroup = {ids['products']}; projectDirPath = ""; projectRoot = ""; targets = ({ids['target']},);}};
        {ids['mainGroup']} = {{isa = PBXGroup; children = ({ids['appFile']}, {ids['assetCatalogFile']}, {ids['products']},); sourceTree = "<group>";}};
        {ids['products']} = {{isa = PBXGroup; children = ({ids['productFile']},); name = Products; sourceTree = "<group>";}};
        {ids['appFile']} = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = App.swift; sourceTree = "<group>";}};
        {ids['assetCatalogFile']} = {{isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; path = Assets.xcassets; sourceTree = "<group>";}};
        {ids['productFile']} = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = PortabilityStarter.app; sourceTree = BUILT_PRODUCTS_DIR;}};
        {ids['buildFile']} = {{isa = PBXBuildFile; fileRef = {ids['appFile']};}};
        {ids['assetCatalogBuildFile']} = {{isa = PBXBuildFile; fileRef = {ids['assetCatalogFile']};}};
        {ids['sources']} = {{isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ({ids['buildFile']},); runOnlyForDeploymentPostprocessing = 0;}};
        {ids['frameworks']} = {{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;}};
        {ids['resources']} = {{isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = ({ids['assetCatalogBuildFile']},); runOnlyForDeploymentPostprocessing = 0;}};
        {ids['target']} = {{isa = PBXNativeTarget; buildConfigurationList = {ids['targetConfigs']}; buildPhases = ({ids['sources']}, {ids['frameworks']}, {ids['resources']},); buildRules = (); dependencies = (); name = PortabilityStarter; productName = PortabilityStarter; productReference = {ids['productFile']}; productType = "com.apple.product-type.application";}};
        {ids['projectConfigs']} = {{isa = XCConfigurationList; buildConfigurations = ({ids['projectDebug']}, {ids['projectRelease']},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;}};
        {ids['projectDebug']} = {{isa = XCBuildConfiguration; buildSettings = {{SDKROOT = iphoneos;}}; name = Debug;}};
        {ids['projectRelease']} = {{isa = XCBuildConfiguration; buildSettings = {{SDKROOT = iphoneos;}}; name = Release;}};
        {ids['targetConfigs']} = {{isa = XCConfigurationList; buildConfigurations = ({ids['targetDebug']}, {ids['targetRelease']},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;}};
        {ids['targetDebug']} = {{isa = XCBuildConfiguration; buildSettings = {{GENERATE_INFOPLIST_FILE = YES; INFOPLIST_KEY_UILaunchScreen_Generation = YES; IPHONEOS_DEPLOYMENT_TARGET = 16.0; PRODUCT_BUNDLE_IDENTIFIER = {package_id}; PRODUCT_NAME = "$(TARGET_NAME)"; SWIFT_VERSION = 5.0; TARGETED_DEVICE_FAMILY = "1,2";}}; name = Debug;}};
        {ids['targetRelease']} = {{isa = XCBuildConfiguration; buildSettings = {{GENERATE_INFOPLIST_FILE = YES; INFOPLIST_KEY_UILaunchScreen_Generation = YES; IPHONEOS_DEPLOYMENT_TARGET = 16.0; PRODUCT_BUNDLE_IDENTIFIER = {package_id}; PRODUCT_NAME = "$(TARGET_NAME)"; SWIFT_VERSION = 5.0; TARGETED_DEVICE_FAMILY = "1,2";}}; name = Release;}};
    }};
    rootObject = {ids['project']};
}}
'''
    (project / "project.pbxproj").write_text(xcode, encoding="utf-8")
    (destination / "README.md").write_text(
        "# iOS portability starter\n\n"
        "Status: experimental Xcode project scaffold; no app behavior has been ported.\n\n"
        "Open `PortabilityStarter.xcodeproj` in Xcode on macOS. The project targets iOS 16 and uses SwiftUI. In a conversion attempt, supported PNG/JPEG images are added to Assets.xcassets; see native-resource-map.json for names and paths. They are not wired into the screen. If App.swift contains a generated Android layout preview, that preview only approximates selected XML controls and includes placeholders; review it manually. Review the bundle identifier, deployment target, capabilities, permissions, assets, and licensing. This generator does not install Xcode, sign the app, or modify the original package.\n", encoding="utf-8")
