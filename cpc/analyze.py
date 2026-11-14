from __future__ import annotations

from pathlib import Path

from cpc.analyzers.android import analyze_apk
from cpc.analyzers.ios import analyze_ipa
from cpc.archive import detect_package_kind
from cpc.compatibility import compare_packages
from cpc.models import FullReport, PackageAnalysis


def analyze_file(path: str | Path) -> PackageAnalysis:
    source = Path(path).expanduser()
    kind = detect_package_kind(source)
    return analyze_apk(source) if kind == "apk" else analyze_ipa(source)


def build_report(paths: list[str | Path]) -> FullReport:
    if not paths:
        raise ValueError("Selecione ao menos um arquivo APK ou IPA.")
    analyses = [analyze_file(path) for path in paths]
    android = next((item for item in analyses if item.kind == "apk"), None)
    ios = next((item for item in analyses if item.kind == "ipa"), None)
    compatibility = compare_packages(android, ios) if android and ios else None
    return FullReport(analyses=analyses, compatibility=compatibility)
