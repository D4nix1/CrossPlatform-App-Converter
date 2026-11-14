from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from cpc.archive import MAX_ENTRIES
from cpc.models import PackageAnalysis
from cpc.portability import (
    _new_directory,
    _safe_id,
    _unsafe_member_path,
    create_scaffold,
    import_recovered_android_images_to_ios,
)

JADX_VERSION = "1.5.6"
JADX_JAR = f"jadx-gui-{JADX_VERSION}-all.jar"
RECOVERY_TIMEOUT_SECONDS = 30 * 60
MAX_DECOMPILER_INPUT_BYTES = 1024 * 1024 * 1024
STATUS_LABELS = {
    "partial_timeout": "parcial (tempo limite)",
    "partial_failure": "falhou parcialmente",
    "partial_with_decompilation_errors": "parcial, com erros de decompilação",
    "partial_with_entries_omitted": "parcial, com entradas do APK omitidas",
    "resources_only": "somente recursos",
    "completed_with_heuristic_source": "concluído com código aproximado",
}


@dataclass
class RecoveryResult:
    output_dir: Path
    source_dir: Path
    report_path: Path
    log_path: Path
    java_files: int
    xml_files: int
    image_files: int
    decompilation_errors: int
    return_code: int | None
    status: str
    unsafe_entries_omitted: int
    inventory_path: Path
    layout_count: int
    string_count: int
    omitted_entry_names: list[str]


def _resolve_jadx_root(tool_root: str | Path | None = None) -> Path:
    if tool_root is not None:
        candidates = [Path(tool_root).resolve()]
    else:
        candidates = [
            Path(sys.executable).resolve().parent / "tools" / f"jadx-{JADX_VERSION}",
            Path(__file__).resolve().parents[1] / "work" / "tools" / f"jadx-{JADX_VERSION}",
        ]
    for candidate in candidates:
        jar = candidate / "lib" / JADX_JAR
        java = candidate / "jre" / "bin" / "java.exe"
        if jar.is_file() and java.is_file():
            return candidate
    raise FileNotFoundError(
        f"JADX {JADX_VERSION} portátil não foi encontrado. Reinstale a distribuição completa ou gere-a com conexão à internet."
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_jadx_input(apk: Path, result_dir: Path) -> tuple[Path, list[str]]:
    """Filter unsafe/noncanonical ZIP member names before passing an APK to a decompiler."""
    with zipfile.ZipFile(apk) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ValueError(f"O APK ultrapassa o limite de {MAX_ENTRIES:,} entradas para recuperação.")
        total_size = sum(max(0, info.file_size) for info in infos)
        if total_size > MAX_DECOMPILER_INPUT_BYTES:
            raise ValueError("O tamanho descompactado declarado do APK ultrapassa 1 GiB para recuperação.")

        safe_infos = []
        skipped = []
        seen: set[tuple[str, ...]] = set()
        for info in infos:
            posix_member = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            is_symlink = (mode & 0o170000) == 0o120000
            normalized = tuple(part.casefold() for part in posix_member.parts)
            if (
                info.is_dir()
                or is_symlink
                or _unsafe_member_path(posix_member, info.filename)
                or posix_member.as_posix() != info.filename
                or normalized in seen
            ):
                if not info.is_dir():
                    skipped.append(info.filename)
                continue
            seen.add(normalized)
            safe_infos.append(info)

        if not skipped:
            return apk, []
        if not safe_infos:
            raise ValueError("O APK não contém arquivos com caminhos seguros para recuperação.")

        sanitized = result_dir / "jadx-input-sanitized.apk"
        with zipfile.ZipFile(sanitized, "x", compression=zipfile.ZIP_DEFLATED) as output:
            for info in safe_infos:
                with archive.open(info) as source_stream, output.open(info, "w") as target_stream:
                    shutil.copyfileobj(source_stream, target_stream, length=1024 * 1024)
        return sanitized, skipped


def _local_xml_name(name: str) -> str:
    if "}" in name:
        return name.rsplit("}", 1)[1]
    if ":" in name:
        return name.rsplit(":", 1)[1]
    return name


def _android_ui_inventory(decompiled: Path, output: Path) -> dict:
    """Summarize decoded Android layouts, menus, navigation XML and user-facing strings."""
    resource_root = decompiled / "resources" / "res"
    max_xml_files = 20_000
    max_total_xml_bytes = 128 * 1024 * 1024
    if resource_root.is_dir():
        def resource_order(path: Path) -> tuple[int, str]:
            directory = path.parent.name
            if directory.startswith("layout"):
                priority = 0
            elif directory.startswith("menu"):
                priority = 1
            elif directory.startswith("navigation"):
                priority = 2
            elif directory == "values":
                priority = 3
            elif directory.startswith("values-"):
                priority = 4
            else:
                priority = 5
            return priority, path.relative_to(resource_root).as_posix().casefold()

        xml_paths = sorted(resource_root.rglob("*.xml"), key=resource_order)
    else:
        xml_paths = []
    if len(xml_paths) > max_xml_files:
        xml_paths = xml_paths[:max_xml_files]

    layouts = []
    menus = []
    navigation = []
    strings = []
    ignored = []
    total_bytes = 0
    for path in xml_paths:
        if path.is_symlink() or not path.is_file():
            ignored.append(f"{path.name}: arquivo não regular")
            continue
        try:
            size = path.stat().st_size
            if size > 4 * 1024 * 1024 or total_bytes + size > max_total_xml_bytes:
                ignored.append(f"{path.name}: limite de tamanho XML atingido")
                continue
            data = path.read_bytes()
            total_bytes += len(data)
            if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", data, flags=re.IGNORECASE):
                ignored.append(f"{path.name}: DTD/ENTITY recusado")
                continue
            root = ET.fromstring(data)
        except (OSError, ET.ParseError, ValueError, RecursionError) as exc:
            ignored.append(f"{path.name}: XML inválido ({exc})")
            continue

        directory = path.parent.name
        relative = path.relative_to(resource_root).as_posix()
        if directory.startswith("layout"):
            counts: Counter[str] = Counter()
            views = []
            for element in root.iter():
                tag = _local_xml_name(element.tag)
                counts[tag] += 1
                if len(views) >= 200:
                    continue
                attrs = {_local_xml_name(key): value for key, value in element.attrib.items()}
                view = {"type": tag}
                if attrs.get("id"):
                    view["id"] = attrs["id"]
                for attr in ("text", "hint", "contentDescription"):
                    if attrs.get(attr):
                        view[attr] = attrs[attr][:500]
                views.append(view)
            layouts.append({
                "resource_file": relative,
                "root_view": _local_xml_name(root.tag),
                "element_count": sum(counts.values()),
                "element_types": dict(sorted(counts.items())),
                "views_preview": views,
                "views_truncated": sum(counts.values()) > len(views),
            })
        elif directory.startswith("menu"):
            items = []
            for element in root.iter():
                if _local_xml_name(element.tag) != "item":
                    continue
                attrs = {_local_xml_name(key): value for key, value in element.attrib.items()}
                items.append({key: attrs[key][:500] for key in ("id", "title", "icon", "showAsAction") if key in attrs})
            menus.append({"resource_file": relative, "items": items[:500]})
        elif directory.startswith("navigation"):
            destinations = []
            for element in root.iter():
                tag = _local_xml_name(element.tag)
                attrs = {_local_xml_name(key): value for key, value in element.attrib.items()}
                if tag in {"navigation", "fragment", "activity", "dialog", "deepLink", "action"}:
                    destinations.append({
                        "type": tag,
                        **{key: attrs[key][:500] for key in ("id", "name", "label", "destination", "uri") if key in attrs},
                    })
            navigation.append({"resource_file": relative, "destinations": destinations[:500]})
        elif directory.startswith("values"):
            for element in root:
                tag = _local_xml_name(element.tag)
                if tag not in {"string", "plurals", "string-array", "item"}:
                    continue
                name = element.attrib.get("name")
                if not name:
                    continue
                text = " ".join("".join(element.itertext()).split())[:1000]
                strings.append({"resource_file": relative, "type": tag, "name": name[:300], "text": text})
                if len(strings) >= 5_000:
                    break
        if len(strings) >= 5_000:
            break

    inventory = {
        "schema_version": "1.0",
        "source": "JADX decoded Android resource XML; inferred structure, not a screen-flow reconstruction",
        "counts": {
            "decoded_xml_files_examined": len(xml_paths),
            "layouts": len(layouts),
            "menus": len(menus),
            "navigation_graphs": len(navigation),
            "string_resources": len(strings),
            "ignored_or_invalid_xml": len(ignored),
        },
        "layouts": layouts,
        "menus": menus,
        "navigation": navigation,
        "strings": strings,
        "ignored_or_invalid": ignored[:2000],
        "limitations": [
            "XML resource names and view attributes are extracted, but layout variations, runtime-created views, Compose UI, and actual navigation behavior may be absent.",
            "The preview limits each layout to 200 elements; all counted types remain in element_types.",
            "Strings are collected across configurations and locales; duplicates are retained with their resource paths.",
            "A separate SwiftUI visual reference may be generated, but it does not port behavior and is not an iOS project conversion.",
        ],
    }
    output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return inventory


def _swift_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def _swiftui_layout_preview(decompiled: Path, output: Path) -> dict:
    """Generate a deliberately incomplete SwiftUI visual reference from decoded XML layouts."""
    root = decompiled / "resources" / "res"
    layout_paths = sorted(
        (p for p in root.rglob("*.xml") if p.parent.name.startswith("layout") and p.is_file() and not p.is_symlink()),
        key=lambda p: p.relative_to(root).as_posix().casefold(),
    ) if root.is_dir() else []
    strings: dict[str, str] = {}
    value_paths = sorted((p for p in root.glob("values*/**/*.xml") if p.is_file()), key=lambda p: p.as_posix().casefold()) if root.is_dir() else []
    for path in value_paths[:5000]:
        try:
            data = path.read_bytes()
            if len(data) > 4 * 1024 * 1024 or re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.I):
                continue
            for item in ET.fromstring(data):
                name = item.attrib.get("name")
                if name and _local_xml_name(item.tag) == "string":
                    strings.setdefault(name, " ".join("".join(item.itertext()).split())[:300])
        except (OSError, ET.ParseError, ValueError, RecursionError):
            continue

    supported = {
        "LinearLayout": "container", "FrameLayout": "container", "RelativeLayout": "container",
        "ConstraintLayout": "container", "ScrollView": "container", "NestedScrollView": "container",
        "TextView": "text", "Button": "button", "ImageButton": "button", "EditText": "field",
        "ImageView": "image", "ProgressBar": "progress", "Switch": "toggle", "CheckBox": "toggle",
        "RadioButton": "toggle", "Space": "space", "View": "unknown",
    }
    aliases = {
        "AppCompatTextView": "text", "NewPipeTextView": "text", "DialogTitle": "text",
        "AppCompatButton": "button", "MaterialButton": "button", "AppCompatImageButton": "button",
        "NewPipeEditText": "field", "AppCompatEditText": "field", "PreferenceImageView": "image",
        "FitWindowsLinearLayout": "container", "FitWindowsFrameLayout": "container",
        "Toolbar": "container", "ActionBarOverlayLayout": "container", "ActionBarContextView": "container",
        "ButtonBarLayout": "container", "AlertDialogLayout": "container", "ConstraintLayout": "container",
        "CoordinatorLayout": "container", "AppBarLayout": "container", "CardView": "container",
        "FragmentContainerView": "container", "NavigationView": "container", "FocusAwareDrawerLayout": "container",
        "FocusAwareCoordinator": "container", "NestedScrollView": "container", "HorizontalScrollView": "container",
        "RecyclerView": "unknown", "NewPipeRecyclerView": "unknown", "WebView": "unknown",
        "Spinner": "unknown", "SeekBar": "unknown", "ViewStub": "unknown",
    }
    unknown: Counter[str] = Counter()
    generated: list[str] = []
    included: list[str] = []
    generated_names: list[str] = []
    used_names: set[str] = set()
    total_nodes = 0

    def swift_view(element: ET.Element, depth: int) -> str:
        nonlocal total_nodes
        total_nodes += 1
        tag = _local_xml_name(element.tag)
        simple_tag = tag.rsplit(".", 1)[-1]
        kind = aliases.get(simple_tag, supported.get(simple_tag, "unknown"))
        attrs = {_local_xml_name(k): v for k, v in element.attrib.items()}
        raw_text = attrs.get("text") or attrs.get("hint") or attrs.get("contentDescription") or ""
        ref = re.fullmatch(r"@string/([A-Za-z0-9_.]+)", raw_text)
        label = strings.get(ref.group(1), f"[{ref.group(1)}]") if ref else raw_text
        children = list(element)
        indent = "    " * depth
        if kind == "container":
            layout = "HStack" if attrs.get("orientation") == "horizontal" else "VStack"
            body = ",\n".join(swift_view(child, depth + 2) for child in children[:80])
            if len(children) > 80:
                body += (",\n" if body else "") + f'{"    " * (depth + 2)}Text("[filhos omitidos: limite experimental]")'
            return f"{indent}{layout}(alignment: .leading, spacing: 8) {{\n{body}\n{indent}}}.padding(8)"
        if kind == "text":
            return f'{indent}Text("{_swift_string(label or "[texto Android não resolvido]")}").fixedSize(horizontal: false, vertical: true)'
        if kind == "button":
            return f'{indent}Button("{_swift_string(label or "Ação sem rótulo")}") {{ /* TODO: reimplementar ação Android */ }}'
        if kind == "field":
            return f'{indent}TextField("{_swift_string(label or "Campo Android")}", text: .constant(""))'
        if kind == "image":
            name = attrs.get("src", "imagem Android")
            return f'{indent}Image(systemName: "photo").accessibilityLabel("{_swift_string(name)}")'
        if kind == "progress":
            return f'{indent}ProgressView()'
        if kind == "toggle":
            return f'{indent}Toggle("{_swift_string(label or tag)}", isOn: .constant(false))'
        if kind == "space":
            return f'{indent}Spacer(minLength: 8)'
        unknown[tag] += 1
        return f'{indent}Text("[{_swift_string(simple_tag)}: componente dinâmico, revisar manualmente]").foregroundStyle(.secondary)'

    for path in layout_paths[:100]:
        if total_nodes >= 5000:
            break
        try:
            data = path.read_bytes()
            if len(data) > 4 * 1024 * 1024 or re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.I):
                continue
            xml = ET.fromstring(data)
            view = swift_view(xml, 3)
        except (OSError, ET.ParseError, ValueError, RecursionError):
            continue
        relative_layout = path.relative_to(root).with_suffix("").as_posix()
        name = re.sub(r"[^A-Za-z0-9]", "_", relative_layout)
        if not name or name[0].isdigit():
            name = "Layout_" + name
        base_name = name
        suffix = 2
        while name in used_names:
            name = f"{base_name}_{suffix}"
            suffix += 1
        used_names.add(name)
        included.append(path.relative_to(root).as_posix())
        generated_names.append(name)
        generated.append(f"struct AndroidLayout_{name}: View {{\n    var body: some View {{\n{view}\n    }}\n}}")

    if generated_names:
        rows = []
        for resource_path, view_name in zip(included, generated_names):
            rows.append(
                "                    NavigationLink {\n"
                f"                        AndroidLayout_{view_name}()\n"
                "                    } label: {\n"
                f'                        Text("{_swift_string(resource_path)}")\n'
                "                    }"
            )
        catalog = (
            "        NavigationStack {\n"
            "            List {\n"
            '                Section("Layouts Android recuperados") {\n'
            + "\n".join(rows)
            + "\n                }\n            }\n"
            '            .navigationTitle("Prévia experimental")\n'
            "        }"
        )
    else:
        catalog = '        Text("Nenhum layout XML simples foi recuperado.")'
    source = (
        "import SwiftUI\n\n"
        "// REFERÊNCIA VISUAL EXPERIMENTAL. Não é conversão funcional.\n"
        "// A lista permite revisar cada layout XML gerado; navegação e ações do app não foram reconstruídas.\n"
        "struct ReconstructedPreview: View {\n"
        "    var body: some View {\n"
        + catalog
        + "\n    }\n}\n\n"
        + "\n\n".join(generated)
        + "\n"
    )
    output.write_text(source, encoding="utf-8")
    manifest = {
        "status": "experimental_visual_reference",
        "source": "decoded Android XML layouts",
        "swift_file": output.name,
        "layouts_generated": included,
        "generated_view_names": generated_names,
        "layout_count": len(included),
        "layouts_in_catalog": len(included),
        "total_nodes_processed": total_nodes,
        "unmapped_view_types": dict(sorted(unknown.items())),
        "limitations": [
            "This is a visual starting point only; it does not port Android logic, event handlers, navigation, lifecycle, permissions, networking, storage, or platform APIs.",
            "Android dimensions, styles, themes, constraints, layout variants, runtime-created views, custom drawing, and Compose screens are not faithfully translated.",
            "Buttons have empty actions, fields and toggles use constant placeholder state, and images are SF Symbol placeholders.",
            "Generated SwiftUI was not compiled: Xcode/iOS SDK require macOS and are not available in this Windows build environment.",
        ],
    }
    return manifest


def _android_layout_source_map(decompiled: Path, preview: dict, output: Path) -> dict:
    """Index static R.layout references in recovered Java without asserting screen-flow semantics."""
    source_root = decompiled / "sources"
    layout_by_name: dict[str, list[str]] = {}
    for resource_file in preview.get("layouts_generated", []):
        layout_by_name.setdefault(Path(resource_file).stem, []).append(resource_file)

    references: dict[str, list[dict[str, str]]] = {name: [] for name in layout_by_name}
    java_files = sorted(source_root.rglob("*.java"), key=lambda p: p.as_posix().casefold()) if source_root.is_dir() else []
    examined = 0
    skipped = 0
    total_bytes = 0
    max_files = 20_000
    max_file_bytes = 4 * 1024 * 1024
    max_total_bytes = 128 * 1024 * 1024
    reference_pattern = re.compile(r"\b(?:[A-Za-z_$][\w$]*\.)?R\.layout\.([A-Za-z0-9_]+)\b")
    class_pattern = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)")
    for path in java_files[:max_files]:
        if path.is_symlink() or not path.is_file():
            skipped += 1
            continue
        try:
            size = path.stat().st_size
            if size > max_file_bytes or total_bytes + size > max_total_bytes:
                skipped += 1
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            skipped += 1
            continue
        total_bytes += size
        examined += 1
        class_names = class_pattern.findall(text)
        class_name = class_names[0] if class_names else "(classe não identificada)"
        relative = path.relative_to(source_root).as_posix()
        for match in reference_pattern.finditer(text):
            name = match.group(1)
            if name not in references:
                continue
            refs = references[name]
            entry = {"source_file": relative, "class_name": class_name}
            if entry not in refs and len(refs) < 100:
                refs.append(entry)

    layouts = []
    for name, resource_files in layout_by_name.items():
        for resource_file in resource_files:
            refs = references.get(name, [])
            layouts.append({
                "resource_file": resource_file,
                "static_reference_count_sampled": len(refs),
                "referenced_by": refs,
                "interpretation": "R.layout identifier occurrence in recovered Java; it does not prove a user-facing screen, navigation entry, or runtime use.",
            })
    result = {
        "schema_version": "1.0",
        "source": "JADX recovered Java source; regex index of static R.layout references",
        "limits": {
            "java_files_examined": examined,
            "java_files_skipped_or_over_limit": skipped + max(0, len(java_files) - max_files),
            "max_file_bytes": max_file_bytes,
            "max_total_bytes": max_total_bytes,
            "references_retained_per_layout_name": 100,
        },
        "layouts": layouts,
        "limitations": [
            "Recovered Java may be incomplete, decompiler-generated, or incorrect; references can occur in adapters, dialogs, tests, or dead code.",
            "The map does not identify the launcher screen, runtime navigation, layout variants selected at runtime, or whether a reference executes.",
            "Only the generated preview layouts are indexed; this preview currently has a 100-layout cap.",
        ],
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def recover_apk(
    source: PackageAnalysis,
    output_parent: str | Path,
    *,
    tool_root: str | Path | None = None,
    timeout_seconds: int = RECOVERY_TIMEOUT_SECONDS,
) -> RecoveryResult:
    """Recover approximate Java source and Android resources from an APK using bundled JADX.

    The APK is treated as data and is never installed or launched. Existing output folders
    are preserved by choosing a fresh destination for every attempt.
    """
    if source.kind != "apk":
        raise ValueError("A recuperação Java está disponível somente para APKs; não decompila IPAs.")
    apk = Path(source.path).resolve()
    if not apk.is_file():
        raise FileNotFoundError(f"APK não encontrado: {apk}")
    if timeout_seconds <= 0:
        raise ValueError("O limite de tempo deve ser maior que zero.")

    root = _resolve_jadx_root(tool_root)
    java = root / "jre" / "bin" / "java.exe"
    jar = root / "lib" / JADX_JAR
    label = _safe_id(source.package_id or Path(source.file_name).stem or "apk")
    output_root = Path(output_parent).expanduser().resolve()
    result_dir = _new_directory(output_root, f"{label}-recovered")
    source_dir = result_dir / "decompiled"
    log_path = result_dir / "jadx.log"
    report_path = result_dir / "decompilation-report.json"
    original_hash = _sha256(apk)
    jadx_input, omitted_entry_names = _prepare_jadx_input(apk, result_dir)

    command = [
        str(java), "--enable-native-access=ALL-UNNAMED", "-Xms256m", "-Xmx2g", "-cp", str(jar), "jadx.cli.JadxCLI",
        "--threads-count", "2", "--output-dir", str(source_dir), str(jadx_input.resolve()),
    ]
    return_code: int | None = None
    timed_out = False
    with log_path.open("w", encoding="utf-8", errors="replace", newline="\n") as log:
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
                check=False,
                shell=False,
            )
            return_code = completed.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            log.write(f"\nTempo limite excedido após {timeout_seconds} segundos; os arquivos parciais foram preservados.\n")
        finally:
            if jadx_input != apk:
                jadx_input.unlink(missing_ok=True)

    output_files = list(source_dir.rglob("*")) if source_dir.exists() else []
    java_count = sum(path.is_file() and path.suffix.lower() == ".java" for path in output_files)
    xml_count = sum(path.is_file() and path.suffix.lower() == ".xml" for path in output_files)
    image_count = sum(path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} for path in output_files)
    inventory_path = result_dir / "android-ui-inventory.json"
    ui_inventory = _android_ui_inventory(source_dir, inventory_path)
    swiftui_path = result_dir / "swiftui-layout-preview.swift"
    swiftui_preview = _swiftui_layout_preview(source_dir, swiftui_path)
    swiftui_report_path = result_dir / "swiftui-preview-report.json"
    swiftui_report_path.write_text(json.dumps(swiftui_preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    layout_source_map_path = result_dir / "android-layout-source-map.json"
    layout_source_map = _android_layout_source_map(source_dir, swiftui_preview, layout_source_map_path)
    ios_starter = create_scaffold(source, "ios", result_dir / "portability-starters", swiftui_preview=swiftui_path)
    ios_resource_map = import_recovered_android_images_to_ios(
        ios_starter, source_dir / "resources" / "res"
    )
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    summaries = re.findall(r"finished with errors,\s*count:\s*(\d+)", log_text, flags=re.IGNORECASE)
    error_count = int(summaries[-1]) if summaries else sum(
        1 for line in log_text.splitlines() if re.search(r"\bERROR\s+-", line, flags=re.IGNORECASE)
    )
    final_hash = _sha256(apk)
    if final_hash != original_hash:
        raise RuntimeError("O APK de origem mudou durante a leitura; a análise foi interrompida.")

    if timed_out:
        status = "partial_timeout"
    elif error_count:
        status = "partial_with_decompilation_errors"
    elif omitted_entry_names:
        status = "partial_with_entries_omitted"
    elif return_code != 0:
        status = "partial_failure"
    elif not java_count:
        status = "resources_only"
    else:
        status = "completed_with_heuristic_source"

    warnings = [
        "O resultado é código Java aproximado derivado de bytecode, não o código-fonte original.",
        "Nomes, comentários, estrutura Kotlin, configurações de build e partes do fluxo podem ter sido perdidos ou reconstruídos incorretamente.",
        "JADX não converte o resultado para Swift/iOS; use os arquivos somente como referência para a reimplementação.",
        "O resultado não foi compilado nem executado. Revise segurança, licença e comportamento antes de reutilizar qualquer conteúdo.",
    ]
    if omitted_entry_names:
        warnings.append(
            f"{len(omitted_entry_names)} entradas com caminhos inseguros, não canônicos ou colisões sem distinção entre maiúsculas/minúsculas foram omitidas da cópia enviada ao JADX; os nomes aparecem neste relatório."
        )
    report = {
        "schema_version": "1.0",
        "tool": "JADX",
        "tool_version": JADX_VERSION,
        "status": status,
        "input_file": source.file_name,
        "input_sha256": original_hash,
        "input_sha256_after": final_hash,
        "source_output": "decompiled/sources",
        "resource_output": "decompiled/resources",
        "android_ui_inventory": "android-ui-inventory.json",
        "swiftui_visual_reference": "swiftui-layout-preview.swift",
        "swiftui_preview_report": "swiftui-preview-report.json",
        "android_layout_source_map": "android-layout-source-map.json",
        "ios_starter_resource_map": (ios_starter.relative_to(result_dir) / "native-resource-map.json").as_posix(),
        "ios_starter_project": ios_starter.relative_to(result_dir).as_posix(),
        "log_file": "jadx.log",
        "process_return_code": return_code,
        "timed_out": timed_out,
        "unsafe_archive_entries_omitted": len(omitted_entry_names),
        "unsafe_archive_entry_names": omitted_entry_names[:2000],
        "decompilation_error_count_reported_by_tool": error_count,
        "recovered_file_counts": {"java": java_count, "xml": xml_count, "raster_images": image_count},
        "warnings": warnings,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (result_dir / "README.md").write_text(
        "# Recuperação estática de APK (experimental)\n\n"
        f"Estado: `{status}`.\n\n"
        "JADX tentou reconstruir Java aproximado a partir dos arquivos DEX e decodificar recursos Android. "
        f"Encontrou {java_count} arquivo(s) Java, {xml_count} XML e {image_count} imagem(ns); "
        f"o inventário identificou {ui_inventory['counts']['layouts']} layouts e {ui_inventory['counts']['string_resources']} strings; "
        f"o registro do decompilador informa {error_count} erro(s), e {len(omitted_entry_names)} entradas do ZIP foram omitidas. "
        "Consulte `android-ui-inventory.json`, `jadx.log` e `decompilation-report.json`.\n\n"
        f"A ferramenta também gerou uma referência SwiftUI visual experimental com {swiftui_preview['layout_count']} layout(s), em `swiftui-layout-preview.swift`. Ela não implementa ações ou lógica, não foi compilada e exige revisão manual; detalhes em `swiftui-preview-report.json`.\n\n"
        f"Um esqueleto Xcode foi criado em `{ios_starter.relative_to(result_dir).as_posix()}` e usa essa prévia como tela inicial; abra-o somente em um Mac com Xcode e trate a tela como referência visual incompleta.\n\n"
        f"`android-layout-source-map.json` relaciona layouts à ocorrência estática de `R.layout` no Java recuperado ({layout_source_map['limits']['java_files_examined']} arquivos Java examinados). Essas referências podem estar em adapters ou código sem uso em runtime; não determinam telas ou navegação.\n\n"
        f"O projeto Xcode recebeu {ios_resource_map['integrated_into_xcode_asset_catalog']} imagem(ns) compatíveis de drawable/mipmap no catálogo de assets. Veja `{(ios_starter.relative_to(result_dir) / 'native-resource-map.json').as_posix()}`; imagens não foram associadas a telas e as variantes podem duplicar conteúdo.\n\n"
        "Isto não recupera o projeto-fonte original nem converte para iOS. Código ofuscado, Kotlin, lógica, "
        "nomes, comentários e configurações podem estar ausentes ou incorretos. A saída não foi compilada nem executada. "
        "O APK original foi lido como dado e seu SHA-256 permaneceu igual. Revise licenças e autorização antes de reutilizar.\n",
        encoding="utf-8",
    )
    return RecoveryResult(
        output_dir=result_dir,
        source_dir=source_dir,
        report_path=report_path,
        log_path=log_path,
        java_files=int(java_count),
        xml_files=int(xml_count),
        image_files=int(image_count),
        decompilation_errors=error_count,
        return_code=return_code,
        status=status,
        unsafe_entries_omitted=len(omitted_entry_names),
        inventory_path=inventory_path,
        layout_count=ui_inventory["counts"]["layouts"],
        string_count=ui_inventory["counts"]["string_resources"],
        omitted_entry_names=omitted_entry_names,
    )


def recovery_status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)
