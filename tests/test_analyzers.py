from __future__ import annotations

import base64
import os
import plistlib
import json
import shutil
import subprocess
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from cpc.analyze import analyze_file, build_report
from cpc.compatibility import compare_packages
from cpc.portability import (
    _integrate_native_images,
    create_conversion_attempt,
    create_scaffold,
    import_recovered_android_images_to_ios,
)
from cpc.recovery import _android_layout_source_map, _android_ui_inventory, _swiftui_layout_preview, recover_apk
from cpc.reports import _unique_path, summarize, write_html_report, write_json_report

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


def _utf8_string(value: str) -> bytes:
    data = value.encode("utf-8")
    return bytes((len(value), len(data))) + data + b"\0"


def _binary_manifest() -> bytes:
    strings = ["manifest", "package", "com.example.demo", "versionName", "1.2.3", "uses-sdk", "minSdkVersion", "23", "targetSdkVersion", "35", "uses-permission", "name", "android.permission.CAMERA", "application", "activity", "exported", "MainActivity"]
    data = b"".join(_utf8_string(value) for value in strings)
    string_start = 28 + len(strings) * 4
    offsets: list[int] = []
    offset = 0
    for value in strings:
        offsets.append(offset)
        offset += len(_utf8_string(value))
    pool_size = string_start + len(data)
    pool = struct.pack("<HHI", 0x0001, 28, pool_size)
    pool += struct.pack("<IIIII", len(strings), 0, 0x100, string_start, 0)
    pool += struct.pack("<" + "I" * len(offsets), *offsets) + data

    def attr(name_index: int, raw_index: int, value_type: int = 0x03, value_data: int | None = None) -> bytes:
        data_index = raw_index if value_data is None else value_data
        return struct.pack("<IIIHBBI", 0xFFFFFFFF, name_index, raw_index, 8, 0, value_type, data_index)

    def start_tag(name_index: int, attrs: list[bytes]) -> bytes:
        ext = struct.pack("<IIHHHHHH", 0xFFFFFFFF, name_index, 20, 20, len(attrs), 0, 0, 0)
        payload = struct.pack("<II", 1, 0xFFFFFFFF) + ext + b"".join(attrs)
        return struct.pack("<HHI", 0x0102, 16, 8 + len(payload)) + payload

    tags = [
        start_tag(0, [attr(1, 2), attr(3, 4)]),
        start_tag(5, [attr(6, 7), attr(8, 9)]),
        start_tag(10, [attr(11, 12)]),
        start_tag(13, []),
        start_tag(14, [attr(11, 16), attr(15, 0xFFFFFFFF, 0x12, 1)]),
    ]
    body = pool + b"".join(tags)
    return struct.pack("<HHI", 0x0003, 8, 8 + len(body)) + body


class AnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_apk(self, path: Path, manifest: bytes) -> Path:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("AndroidManifest.xml", manifest)
            archive.writestr("lib/arm64-v8a/libsample.so", b"so")
            archive.writestr("res/drawable/logo.png", _PNG_1X1)
            archive.writestr("assets/flutter_assets/AssetManifest.json", b"{}")
        return path

    def make_ipa(self, path: Path) -> Path:
        info = {
            "CFBundleIdentifier": "com.example.demo",
            "CFBundleExecutable": "Demo",
            "CFBundleDisplayName": "Demo App",
            "CFBundleShortVersionString": "1.2.3",
            "CFBundleVersion": "7",
            "MinimumOSVersion": "16.0",
            "UIDeviceFamily": [1, 2],
            "NSCameraUsageDescription": "Camera required for test",
            "UIBackgroundModes": ["remote-notification"],
        }
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("Payload/Demo.app/Info.plist", plistlib.dumps(info))
            archive.writestr("Payload/Demo.app/Demo", b"synthetic Mach-O executable")
            archive.writestr("Payload/Demo.app/Frameworks/Flutter.framework/Flutter", b"macho")
            archive.writestr("Payload/Demo.app/Assets.car", b"compiled asset catalog")
            archive.writestr("Payload/Demo.app/Assets.xcassets/logo.png", _PNG_1X1)
            archive.writestr("Payload/Demo.app/Watch/Watch App.app/Info.plist", plistlib.dumps({"CFBundleIdentifier": "com.example.watch", "CFBundleExecutable": "Watch App", "MinimumOSVersion": "10.0"}))
            archive.writestr("Payload/Demo.app/Watch/Watch App.app/Watch App", b"watch executable")
        return path

    def test_analyzes_text_android_manifest(self) -> None:
        apk = self.make_apk(self.root / "demo.apk", b'''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.demo" android:versionName="1.2.3" android:versionCode="7"><uses-sdk android:minSdkVersion="23" android:targetSdkVersion="35"/><uses-permission android:name="android.permission.CAMERA"/><application android:label="Demo"><activity android:name=".MainActivity" android:exported="true"/></application></manifest>''')
        result = analyze_file(apk)
        self.assertEqual(result.package_id, "com.example.demo")
        self.assertEqual(result.version, "1.2.3")
        self.assertEqual(result.minimum_os, "23")
        self.assertIn("android.permission.CAMERA", result.permissions)
        self.assertEqual(result.components[0].name, ".MainActivity")
        self.assertTrue(result.native_binaries)
        self.assertEqual(result.dependencies[0].name, "Flutter")

    def test_analyzes_compiled_android_axml(self) -> None:
        apk = self.make_apk(self.root / "binary.apk", _binary_manifest())
        result = analyze_file(apk)
        self.assertEqual(result.package_id, "com.example.demo")
        self.assertEqual(result.version, "1.2.3")
        self.assertEqual(result.minimum_os, "23")
        self.assertEqual(result.target_os, "35")
        self.assertIn("android.permission.CAMERA", result.permissions)
        self.assertEqual(result.components[0].name, "MainActivity")
        self.assertTrue(result.components[0].exported)

    def test_analyzes_ipa_metadata_and_frameworks(self) -> None:
        ipa = self.make_ipa(self.root / "demo.ipa")
        result = analyze_file(ipa)
        self.assertEqual(result.package_id, "com.example.demo")
        self.assertEqual(result.app_name, "Demo App")
        self.assertIn("NSCameraUsageDescription", result.permissions)
        self.assertIn("Flutter.framework", [item.name for item in result.dependencies])
        self.assertIn("camera", [item.feature_id for item in result.features])
        self.assertIn("Payload/Demo.app/Demo", result.native_binaries)
        self.assertEqual(result.minimum_os, "16.0")
        self.assertIn("app diretamente em Payload", result.warnings[0])
        self.assertTrue(any(".car" in warning for warning in result.warnings))

    def test_compares_android_and_ios_evidence(self) -> None:
        apk = self.make_apk(self.root / "demo.apk", b'''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.demo"><uses-permission android:name="android.permission.CAMERA"/></manifest>''')
        ipa = self.make_ipa(self.root / "demo.ipa")
        report = build_report([apk, ipa])
        self.assertIsNotNone(report.compatibility)
        self.assertIn("camera", [row.feature_id for row in report.compatibility.feature_comparisons])
        self.assertIn("heurística", report.compatibility.caveats[0])
        self.assertIn("não é conversão", summarize(report).lower())

    def test_same_flutter_runtime_is_not_counted_as_two_frameworks(self) -> None:
        apk = analyze_file(self.make_apk(self.root / "flutter.apk", b'<manifest package="com.example.demo"/>'))
        ipa = analyze_file(self.make_ipa(self.root / "flutter.ipa"))
        report = compare_packages(apk, ipa)
        framework_note = next(note for note in report.portability_notes if note.startswith("Frameworks identificados:"))
        self.assertEqual(framework_note.casefold().count("flutter"), 1)
        self.assertEqual([item.name for item in ipa.dependencies if item.name.casefold() == "flutter"], [])

    def test_unknown_and_invalid_files_fail_cleanly(self) -> None:
        file = self.root / "broken.apk"
        file.write_bytes(b"not a zip")
        with self.assertRaises(ValueError):
            analyze_file(file)

    def test_android_manifest_rejects_dtd_and_entities(self) -> None:
        apk = self.make_apk(
            self.root / "entity.apk",
            b'<!DOCTYPE manifest [<!ENTITY x "expanded">]><manifest package="com.example.demo"><application android:label="&x;"/></manifest>',
        )
        with self.assertRaisesRegex(ValueError, "DTD e entidades"):
            analyze_file(apk)

    def test_ipa_rejects_non_dictionary_plist_and_warns_on_bad_device_family(self) -> None:
        malformed = self.root / "malformed-plist.ipa"
        with zipfile.ZipFile(malformed, "w") as archive:
            archive.writestr("Payload/Demo.app/Info.plist", b'<?xml version="1.0"?><plist><dict>broken')
        with self.assertRaisesRegex(ValueError, "Não foi possível analisar o IPA"):
            analyze_file(malformed)

        bad_root = self.root / "bad-root.ipa"
        with zipfile.ZipFile(bad_root, "w") as archive:
            archive.writestr("Payload/Demo.app/Info.plist", plistlib.dumps(["not a dictionary"]))
        with self.assertRaisesRegex(ValueError, "raiz do Info.plist"):
            analyze_file(bad_root)

        odd_family = self.root / "odd-family.ipa"
        with zipfile.ZipFile(odd_family, "w") as archive:
            archive.writestr("Payload/Demo.app/Info.plist", plistlib.dumps({"CFBundleIdentifier": "com.example.demo", "UIDeviceFamily": 1}))
        result = analyze_file(odd_family)
        self.assertIsNone(result.target_os)
        self.assertTrue(any("UIDeviceFamily" in warning for warning in result.warnings))

        odd_value = self.root / "odd-value.ipa"
        with zipfile.ZipFile(odd_value, "w") as archive:
            archive.writestr("Payload/Demo.app/Info.plist", plistlib.dumps({"CFBundleIdentifier": "com.example.demo", "UIDeviceFamily": ["²"]}))
        result = analyze_file(odd_value)
        self.assertIsNone(result.target_os)
        self.assertTrue(any("valores de UIDeviceFamily" in warning for warning in result.warnings))

    def test_reports_and_scaffolds_do_not_overwrite(self) -> None:
        apk = self.make_apk(self.root / "demo.apk", b'''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.demo"><application/></manifest>''')
        source = analyze_file(apk)
        report = build_report([apk])
        out = self.root / "reports"
        first = write_json_report(report, out, "same")
        html_path = write_html_report(report, out, "same")
        second = _unique_path(first)
        self.assertNotEqual(first, second)
        self.assertIn("Metadados extraídos", html_path.read_text(encoding="utf-8"))
        first.write_text("preserve", encoding="utf-8")
        scaffold1 = create_scaffold(source, "ios", self.root)
        scaffold2 = create_scaffold(source, "ios", self.root)
        android_scaffold = create_scaffold(analyze_file(self.make_ipa(self.root / "demo.ipa")), "android", self.root)
        self.assertNotEqual(scaffold1, scaffold2)
        self.assertTrue((scaffold1 / "PortabilityStarter.xcodeproj" / "project.pbxproj").is_file())
        self.assertTrue((scaffold1 / "Assets.xcassets" / "Contents.json").is_file())
        self.assertIn("folder.assetcatalog", (scaffold1 / "PortabilityStarter.xcodeproj" / "project.pbxproj").read_text(encoding="utf-8"))
        self.assertTrue((scaffold1 / "MIGRATION-PLAN.md").is_file())
        self.assertTrue((scaffold1 / "migration-plan.json").is_file())
        scaffold_plan = json.loads((scaffold1 / "migration-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(scaffold_plan["source"]["package_id"], "com.example.demo")
        self.assertEqual(scaffold_plan["target_platform"], "ios")
        self.assertTrue(scaffold_plan["reconstruction_checklist"])
        self.assertTrue((android_scaffold / "app" / "src" / "main" / "AndroidManifest.xml").is_file())
        android_manifest = (android_scaffold / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertNotIn("package=", android_manifest)
        self.assertIn('namespace = "com.example.demo"', (android_scaffold / "app" / "build.gradle.kts").read_text(encoding="utf-8"))
        self.assertEqual(first.read_text(encoding="utf-8"), "preserve")

    def test_rejects_same_platform_scaffold(self) -> None:
        apk = self.make_apk(self.root / "demo.apk", b'<manifest package="demo"/>')
        with self.assertRaises(ValueError):
            create_scaffold(analyze_file(apk), "android", self.root)

    def test_conversion_attempt_makes_honest_bundle_and_copies_candidate_resource(self) -> None:
        apk = self.make_apk(self.root / "demo.apk", b'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.demo"><uses-permission android:name="android.permission.CAMERA"/></manifest>')
        bundle, copied, skipped = create_conversion_attempt(analyze_file(apk), self.root / "attempts")
        self.assertTrue(bundle.is_file())
        self.assertEqual(bundle.suffix, ".zip")
        self.assertEqual(copied, 2)
        self.assertEqual(skipped, [])
        with zipfile.ZipFile(bundle) as archive:
            notice = archive.read("CONVERSION-ATTEMPT.txt").decode("utf-8")
            self.assertIn("NÃO É UM APP INSTALÁVEL", notice)
            self.assertIn("O conversor não é milagroso", notice)
            self.assertEqual(archive.read("imported_resources/res/drawable/logo.png"), _PNG_1X1)
            self.assertIn("App.swift", archive.namelist())
            self.assertIn("Assets.xcassets/logo.imageset/logo.png", archive.namelist())
            image_contents = json.loads(archive.read("Assets.xcassets/logo.imageset/Contents.json"))
            self.assertEqual(image_contents["images"][0]["filename"], "logo.png")
            xcode_project = archive.read("PortabilityStarter.xcodeproj/project.pbxproj").decode("utf-8")
            self.assertIn("folder.assetcatalog", xcode_project)
            self.assertIn("A10000000000000000000018 = {isa = PBXBuildFile", xcode_project)
            native_map = json.loads(archive.read("native-resource-map.json"))
            self.assertEqual(native_map["integrated_image_count"], 1)
            self.assertEqual(native_map["assets"][0]["target_usage_hint"], 'Image("logo")')
            self.assertIn("migration-plan.json", archive.namelist())
            plan = json.loads(archive.read("migration-plan.json"))
            self.assertIn("Reconstruir cada tela", " ".join(item["task"] for item in plan["reconstruction_checklist"]))
            camera = next(item for item in plan["extracted_evidence"]["features_to_verify"] if item["id"] == "camera")
            self.assertEqual(camera["target_api_hint"], "AVFoundation (AVCaptureSession)")
        self.assertTrue(apk.is_file())
        bundle2, _, _ = create_conversion_attempt(analyze_file(apk), self.root / "attempts")
        self.assertNotEqual(bundle, bundle2)
        self.assertTrue(bundle.is_file())

    def test_ipa_image_is_added_to_android_drawable_and_named_resource_map(self) -> None:
        ipa = self.make_ipa(self.root / "demo.ipa")
        bundle, copied, skipped = create_conversion_attempt(analyze_file(ipa), self.root / "attempts")
        self.assertGreaterEqual(copied, 1)
        self.assertEqual(skipped, [])
        with zipfile.ZipFile(bundle) as archive:
            target = "app/src/main/res/drawable-nodpi/logo.png"
            self.assertEqual(archive.read(target), _PNG_1X1)
            resource_map = json.loads(archive.read("native-resource-map.json"))
            self.assertEqual(resource_map["integrated_image_count"], 1)
            self.assertEqual(resource_map["assets"][0]["target_usage_hint"], "R.drawable.logo")

    def test_native_image_names_get_unique_safe_android_resource_ids(self) -> None:
        apk = self.make_apk(self.root / "duplicate-image.apk", b'<manifest package="com.example.demo"/>')
        with zipfile.ZipFile(apk, "a") as archive:
            archive.writestr("assets/logo.png", _PNG_1X1)
            archive.writestr("assets/Logo!.png", _PNG_1X1)
        bundle, _, _ = create_conversion_attempt(analyze_file(apk), self.root / "attempts")
        with zipfile.ZipFile(bundle) as archive:
            resource_map = json.loads(archive.read("native-resource-map.json"))
            names = [Path(item["target"]).stem for item in resource_map["assets"]]
            self.assertEqual(len(names), 3)
            self.assertEqual(len(set(names)), len(names))
            self.assertTrue(all(name[0].isalpha() and name.islower() for name in names))

    def test_apk_recovery_records_partial_decompile_and_preserves_original(self) -> None:
        apk = self.make_apk(self.root / "recover.apk", b'<manifest package="com.example.recover"/>')
        source = analyze_file(apk)
        tool = self.root / "jadx-tool"
        java = tool / "jre" / "bin" / "java.exe"
        jar = tool / "lib" / "jadx-gui-1.5.6-all.jar"
        java.parent.mkdir(parents=True)
        jar.parent.mkdir(parents=True)
        java.write_bytes(b"portable java stub")
        jar.write_bytes(b"portable JADX stub")

        def fake_jadx(command, **kwargs):
            output = Path(command[command.index("--output-dir") + 1])
            (output / "sources").mkdir(parents=True)
            (output / "resources").mkdir()
            (output / "sources" / "Main.java").write_text("class Main {}", encoding="utf-8")
            (output / "resources" / "AndroidManifest.xml").write_text("<manifest/>", encoding="utf-8")
            (output / "resources" / "res" / "layout").mkdir(parents=True)
            (output / "resources" / "res" / "values").mkdir(parents=True)
            (output / "resources" / "res" / "layout" / "home.xml").write_text(
                '<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"><TextView android:text="Hello"/></LinearLayout>', encoding="utf-8"
            )
            (output / "resources" / "res" / "drawable").mkdir()
            (output / "resources" / "res" / "drawable" / "logo.png").write_bytes(_PNG_1X1)
            (output / "resources" / "res" / "values" / "strings.xml").write_text(
                '<resources><string name="app_name">Test</string></resources>', encoding="utf-8"
            )
            kwargs["stdout"].write("ERROR - finished with errors, count: 3\n")
            self.assertFalse(kwargs["shell"])
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual(Path(command[0]), java)
            self.assertTrue(Path(command[command.index("--output-dir") + 1]).is_absolute())
            return subprocess.CompletedProcess(command, 0)

        with patch("cpc.recovery.subprocess.run", side_effect=fake_jadx) as runner:
            relative_output = Path(os.path.relpath(self.root / "recovered", Path.cwd()))
            result = recover_apk(source, relative_output, tool_root=tool)
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(result.status, "partial_with_decompilation_errors")
        self.assertEqual(result.java_files, 1)
        self.assertEqual(result.xml_files, 3)
        self.assertEqual(result.image_files, 1)
        self.assertEqual(result.decompilation_errors, 3)
        self.assertEqual(result.layout_count, 1)
        self.assertEqual(result.string_count, 1)
        self.assertTrue(result.report_path.is_file())
        self.assertTrue(result.inventory_path.is_file())
        preview = result.output_dir / "swiftui-layout-preview.swift"
        preview_report = json.loads((result.output_dir / "swiftui-preview-report.json").read_text(encoding="utf-8"))
        layout_map = json.loads((result.output_dir / "android-layout-source-map.json").read_text(encoding="utf-8"))
        self.assertTrue(preview.is_file())
        self.assertEqual(preview_report["layout_count"], 1)
        self.assertIn("AndroidLayout_layout_home", preview.read_text(encoding="utf-8"))
        report_data = json.loads(result.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report_data["swiftui_visual_reference"], "swiftui-layout-preview.swift")
        self.assertEqual(report_data["android_layout_source_map"], "android-layout-source-map.json")
        self.assertEqual(layout_map["limits"]["java_files_examined"], 1)
        ios_starter = result.output_dir / report_data["ios_starter_project"]
        self.assertTrue((ios_starter / "PortabilityStarter.xcodeproj" / "project.pbxproj").is_file())
        app_source = (ios_starter / "App.swift").read_text(encoding="utf-8")
        self.assertIn("WindowGroup { ReconstructedPreview() }", app_source)
        self.assertIn('Text("Hello")', app_source)
        self.assertEqual(app_source.count("import SwiftUI"), 1)
        native_map = json.loads((ios_starter / "native-resource-map.json").read_text(encoding="utf-8"))
        self.assertEqual(native_map["integrated_into_xcode_asset_catalog"], 1)
        asset = ios_starter / native_map["native_assets"][0]["target"]
        self.assertEqual(asset.read_bytes(), _PNG_1X1)
        self.assertEqual(report_data["input_sha256"], report_data["input_sha256_after"])
        self.assertIn("não recupera o projeto-fonte original", (result.output_dir / "README.md").read_text(encoding="utf-8"))

    def test_apk_recovery_refuses_ipa_and_missing_tool_without_overwriting(self) -> None:
        ipa = self.make_ipa(self.root / "demo.ipa")
        with self.assertRaisesRegex(ValueError, "somente para APKs"):
            recover_apk(analyze_file(ipa), self.root / "recovered", tool_root=self.root / "missing")
        apk = self.make_apk(self.root / "recover.apk", b'<manifest package="com.example.recover"/>')
        with self.assertRaises(FileNotFoundError):
            recover_apk(analyze_file(apk), self.root / "recovered", tool_root=self.root / "missing")

    def test_apk_recovery_keeps_partial_output_on_timeout(self) -> None:
        apk = self.make_apk(self.root / "timeout.apk", b'<manifest package="com.example.timeout"/>')
        source = analyze_file(apk)
        tool = self.root / "jadx-tool"
        (tool / "jre" / "bin").mkdir(parents=True)
        (tool / "lib").mkdir()
        (tool / "jre" / "bin" / "java.exe").write_bytes(b"java")
        (tool / "lib" / "jadx-gui-1.5.6-all.jar").write_bytes(b"jar")

        def timeout(command, **kwargs):
            output = Path(command[command.index("--output-dir") + 1])
            (output / "sources").mkdir(parents=True)
            (output / "sources" / "Partial.java").write_text("class Partial {}", encoding="utf-8")
            raise subprocess.TimeoutExpired(command, 1)

        with patch("cpc.recovery.subprocess.run", side_effect=timeout):
            result = recover_apk(source, self.root / "timeout-out", tool_root=tool, timeout_seconds=1)
        self.assertEqual(result.status, "partial_timeout")
        self.assertEqual(result.java_files, 1)
        self.assertIn("Tempo limite", result.log_path.read_text(encoding="utf-8"))

    def test_apk_recovery_filters_zip_traversal_before_calling_jadx(self) -> None:
        apk = self.make_apk(self.root / "unsafe-recovery.apk", b'<manifest package="com.example.safe"/>')
        with zipfile.ZipFile(apk, "a") as archive:
            archive.writestr("assets/../outside.txt", b"unsafe")
        source = analyze_file(apk)
        tool = self.root / "jadx-tool"
        (tool / "jre" / "bin").mkdir(parents=True)
        (tool / "lib").mkdir()
        (tool / "jre" / "bin" / "java.exe").write_bytes(b"java")
        (tool / "lib" / "jadx-gui-1.5.6-all.jar").write_bytes(b"jar")

        def fake_jadx(command, **kwargs):
            safe_copy = Path(command[-1])
            self.assertNotEqual(safe_copy, apk.resolve())
            with zipfile.ZipFile(safe_copy) as sanitized:
                self.assertNotIn("assets/../outside.txt", sanitized.namelist())
                self.assertIn("AndroidManifest.xml", sanitized.namelist())
            output = Path(command[command.index("--output-dir") + 1])
            (output / "sources").mkdir(parents=True)
            kwargs["stdout"].write("INFO - finished\n")
            return subprocess.CompletedProcess(command, 0)

        with patch("cpc.recovery.subprocess.run", side_effect=fake_jadx):
            result = recover_apk(source, self.root / "safe-out", tool_root=tool)
        self.assertEqual(result.unsafe_entries_omitted, 1)
        self.assertEqual(result.omitted_entry_names, ["assets/../outside.txt"])
        self.assertEqual(result.status, "partial_with_entries_omitted")
        report = json.loads(result.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["unsafe_archive_entry_names"], ["assets/../outside.txt"])
        self.assertFalse((result.output_dir / "jadx-input-sanitized.apk").exists())
        self.assertTrue(apk.is_file())

    def test_swiftui_preview_maps_basic_android_views_and_marks_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "decompiled" / "resources" / "res"
            (root / "layout").mkdir(parents=True)
            (root / "values").mkdir()
            (root / "values" / "strings.xml").write_text(
                '<resources><string name="hello">Hello &amp; welcome</string></resources>', encoding="utf-8"
            )
            (root / "layout" / "main.xml").write_text(
                '<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:orientation="vertical">'
                '<TextView android:text="@string/hello"/><Button android:text="Go"/>'
                '<com.example.SpecialView/></LinearLayout>', encoding="utf-8"
            )
            (root / "layout-land").mkdir()
            (root / "layout-land" / "main.xml").write_text(
                '<FrameLayout><TextView android:text="Landscape" xmlns:android="http://schemas.android.com/apk/res/android"/></FrameLayout>',
                encoding="utf-8",
            )
            output = Path(temporary) / "preview.swift"
            report = _swiftui_layout_preview(root.parent.parent, output)
            swift = output.read_text(encoding="utf-8")
            self.assertEqual(report["layout_count"], 2)
            self.assertEqual(report["layouts_in_catalog"], 2)
            self.assertEqual(len(set(report["generated_view_names"])), 2)
            self.assertEqual(swift.count("NavigationLink {"), 2)
            self.assertIn('Text("layout-land/main.xml")', swift)
            self.assertIn('Text("Hello & welcome")', swift)
            self.assertIn("TODO: reimplementar ação Android", swift)
            self.assertIn("SpecialView", swift)
            self.assertIn("does not port android logic", " ".join(report["limitations"]).lower())

    def test_android_layout_source_map_records_only_static_java_references(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            decompiled = Path(temporary) / "decompiled"
            source = decompiled / "sources" / "com" / "example" / "HomeActivity.java"
            source.parent.mkdir(parents=True)
            source.write_text(
                "package com.example; class HomeActivity { int layout = R.layout.home; }",
                encoding="utf-8",
            )
            output = Path(temporary) / "layout-map.json"
            preview = {"layouts_generated": ["layout/home.xml", "layout/item_row.xml"]}
            result = _android_layout_source_map(decompiled, preview, output)
            home = next(item for item in result["layouts"] if item["resource_file"] == "layout/home.xml")
            row = next(item for item in result["layouts"] if item["resource_file"] == "layout/item_row.xml")
            self.assertEqual(home["referenced_by"][0]["class_name"], "HomeActivity")
            self.assertEqual(row["referenced_by"], [])
            self.assertIn("does not prove", home["interpretation"])
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)

    def test_recovered_android_images_reach_ios_assets_from_deep_project_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / ("p" * 110)
            project = base / "ios-starter"
            (project / "Assets.xcassets").mkdir(parents=True)
            resources = Path(temporary) / "decoded" / "res" / "drawable-hdpi"
            resources.mkdir(parents=True)
            original_image = resources / "logo.png"
            original_image.write_bytes(_PNG_1X1)
            result = import_recovered_android_images_to_ios(project, resources.parent)
            self.assertEqual(result["copied_to_review_folder"], 1)
            self.assertEqual(result["integrated_into_xcode_asset_catalog"], 1)
            self.assertEqual(result["native_assets"][0]["source"], "drawable-hdpi/logo.png")
            asset = project / result["native_assets"][0]["target"]
            self.assertEqual(asset.read_bytes(), _PNG_1X1)
            self.assertLessEqual(len(str(asset.resolve())), 250)
            self.assertEqual(original_image.read_bytes(), _PNG_1X1)

    def test_native_image_write_error_is_isolated_and_partial_file_removed(self) -> None:
        original_copyfileobj = shutil.copyfileobj
        for target_platform in ("ios", "android"):
            with self.subTest(target=target_platform), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                project = root / "starter"
                project.mkdir()
                resources = root / "resources"
                resources.mkdir()
                (resources / "a.png").write_bytes(_PNG_1X1)
                (resources / "b.png").write_bytes(_PNG_1X1)
                calls = 0

                def copy_with_first_failure(source, destination, length=0):
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        destination.write(source.read(8))
                        raise OSError("simulated disk write failure")
                    original_copyfileobj(source, destination, length=length)

                with patch("cpc.portability.shutil.copyfileobj", side_effect=copy_with_first_failure):
                    result = _integrate_native_images(
                        project, target_platform, [resources / "a.png", resources / "b.png"], resource_root=resources
                    )
                self.assertEqual(result["integrated_image_count"], 1)
                self.assertEqual(len(result["not_integrated"]), 1)
                self.assertIn("simulated disk write failure", result["not_integrated"][0]["reason"])
                if target_platform == "ios":
                    imagesets = list((project / "Assets.xcassets").glob("*.imageset"))
                    self.assertEqual(len(imagesets), 1)
                    self.assertEqual([path.name for path in imagesets[0].iterdir()], ["b.png", "Contents.json"])
                else:
                    drawables = list((project / "app" / "src" / "main" / "res" / "drawable-nodpi").glob("*.png"))
                    self.assertEqual(len(drawables), 1)
                    self.assertEqual(drawables[0].read_bytes(), _PNG_1X1)

    def test_android_ui_inventory_summarizes_layout_menu_navigation_and_localized_strings(self) -> None:
        decompiled = self.root / "decompiled"
        resources = decompiled / "resources" / "res"
        (resources / "layout").mkdir(parents=True)
        (resources / "menu").mkdir()
        (resources / "navigation").mkdir()
        (resources / "values").mkdir()
        (resources / "values-fr").mkdir()
        (resources / "layout" / "main.xml").write_text(
            '<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"><TextView android:id="@+id/title" android:text="@string/app_name"/><Button android:text="Go"/></LinearLayout>',
            encoding="utf-8",
        )
        (resources / "menu" / "main.xml").write_text(
            '<menu xmlns:android="http://schemas.android.com/apk/res/android"><item android:id="@+id/settings" android:title="@string/settings"/></menu>',
            encoding="utf-8",
        )
        (resources / "navigation" / "main.xml").write_text(
            '<navigation xmlns:android="http://schemas.android.com/apk/res/android"><fragment android:id="@+id/home" android:name="com.example.Home" android:label="Home"/></navigation>',
            encoding="utf-8",
        )
        (resources / "values" / "strings.xml").write_text(
            '<resources><string name="app_name">Demo</string><string name="settings">Settings</string></resources>',
            encoding="utf-8",
        )
        (resources / "values-fr" / "strings.xml").write_text(
            '<resources><string name="app_name">Démo</string></resources>', encoding="utf-8"
        )
        (resources / "values" / "unsafe.xml").write_text(
            '<!DOCTYPE resources [<!ENTITY x "expanded">]><resources><string name="unsafe">&x;</string></resources>',
            encoding="utf-8",
        )

        output = self.root / "android-ui-inventory.json"
        inventory = _android_ui_inventory(decompiled, output)
        self.assertEqual(inventory["counts"]["layouts"], 1)
        self.assertEqual(inventory["counts"]["menus"], 1)
        self.assertEqual(inventory["counts"]["navigation_graphs"], 1)
        self.assertEqual(inventory["counts"]["string_resources"], 3)
        self.assertEqual(inventory["counts"]["ignored_or_invalid_xml"], 1)
        self.assertIn("@+id/title", json.dumps(inventory["layouts"]))
        self.assertIn("@string/settings", json.dumps(inventory["menus"]))
        self.assertTrue(output.is_file())

    def test_conversion_attempt_continues_after_normalized_resource_collision(self) -> None:
        apk = self.make_apk(self.root / "collision.apk", b'<manifest package="com.example.demo"/>')
        with zipfile.ZipFile(apk, "a") as archive:
            archive.writestr("assets/./flutter_assets/AssetManifest.json", b"duplicate path")
            archive.writestr("assets/z-last.json", b"{}")
        bundle, copied, skipped = create_conversion_attempt(analyze_file(apk), self.root / "attempts")
        self.assertEqual(copied, 3)
        self.assertEqual(len(skipped), 1)
        self.assertIn("colisão de caminho", skipped[0])
        with zipfile.ZipFile(bundle) as archive:
            self.assertIn("imported_resources/assets/z-last.json", archive.namelist())

    def test_conversion_attempt_rejects_traversal_and_windows_device_paths(self) -> None:
        apk = self.make_apk(self.root / "unsafe.apk", b'<manifest package="com.example.demo"/>')
        with zipfile.ZipFile(apk, "a") as archive:
            archive.writestr("assets/../outside.png", b"outside")
            archive.writestr("assets/NUL.png", b"device")
            archive.writestr("assets/ok.png", b"safe")
            symlink = zipfile.ZipInfo("assets/link.png")
            symlink.create_system = 3
            symlink.external_attr = 0o120777 << 16
            archive.writestr(symlink, "target.png")
        bundle, copied, skipped = create_conversion_attempt(analyze_file(apk), self.root / "attempts")
        self.assertEqual(copied, 3)  # two original assets plus the safe added asset
        self.assertEqual(len(skipped), 3)
        self.assertFalse((self.root / "outside.png").exists())
        with zipfile.ZipFile(bundle) as archive:
            self.assertNotIn("imported_resources/outside.png", archive.namelist())
            self.assertIn("imported_resources/assets/ok.png", archive.namelist())

    def test_conversion_attempt_skips_corrupt_resource_and_continues(self) -> None:
        apk = self.make_apk(self.root / "corrupt-resource.apk", b'<manifest package="com.example.demo"/>')
        with zipfile.ZipFile(apk, "a", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("assets/broken.png", b"broken")
            archive.writestr("assets/good.png", b"good")
        with zipfile.ZipFile(apk) as archive:
            info = archive.getinfo("assets/broken.png")
        with apk.open("r+b") as raw:
            raw.seek(info.header_offset)
            header = raw.read(30)
            fields = struct.unpack("<IHHHHHIIIHH", header)
            data_offset = info.header_offset + 30 + fields[-2] + fields[-1]
            raw.seek(data_offset)
            first = raw.read(1)
            raw.seek(data_offset)
            raw.write(bytes((first[0] ^ 0xFF,)))
        bundle, copied, skipped = create_conversion_attempt(analyze_file(apk), self.root / "attempts")
        self.assertEqual(copied, 3)
        self.assertEqual(len(skipped), 1)
        with zipfile.ZipFile(bundle) as archive:
            names = archive.namelist()
            self.assertNotIn("imported_resources/assets/broken.png", names)
            self.assertIn("imported_resources/assets/good.png", names)


if __name__ == "__main__":
    unittest.main()
