from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Component:
    kind: str
    name: str
    exported: bool | None = None
    permission: str | None = None


@dataclass
class Dependency:
    name: str
    category: str
    evidence: str


@dataclass
class FeatureEvidence:
    feature_id: str
    label: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class PackageAnalysis:
    kind: str
    path: str
    file_name: str
    file_size: int
    package_id: str | None = None
    app_name: str | None = None
    version: str | None = None
    build_version: str | None = None
    minimum_os: str | None = None
    target_os: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    components: list[Component] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    features: list[FeatureEvidence] = field(default_factory=list)
    file_count: int = 0
    total_uncompressed_size: int = 0
    file_types: dict[str, int] = field(default_factory=dict)
    native_binaries: list[str] = field(default_factory=list)
    resource_candidates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FeatureComparison:
    feature_id: str
    label: str
    android_evidence: list[str]
    ios_evidence: list[str]
    note: str


@dataclass
class CompatibilityReport:
    android_package: str
    ios_package: str
    difficulty: str
    score: int
    summary: str
    feature_comparisons: list[FeatureComparison] = field(default_factory=list)
    portability_notes: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FullReport:
    analyses: list[PackageAnalysis]
    compatibility: CompatibilityReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "analyses": [item.to_dict() for item in self.analyses],
            "compatibility": self.compatibility.to_dict() if self.compatibility else None,
        }
