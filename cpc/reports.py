from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from cpc.models import FullReport


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10_000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Não foi possível escolher um nome livre para {path}.")


def write_json_report(report: FullReport, folder: str | Path, basename: str = "analysis") -> Path:
    folder_path = Path(folder).expanduser()
    folder_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = _unique_path(folder_path / f"{basename}-{timestamp}.json")
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(report.to_dict(), stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return destination


def write_html_report(report: FullReport, folder: str | Path, basename: str = "analysis") -> Path:
    folder_path = Path(folder).expanduser()
    folder_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = _unique_path(folder_path / f"{basename}-{timestamp}.html")
    body = [
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>CrossPlatform App Converter — relatório</title>",
        "<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#18212b}h1,h2{color:#155eef}table{border-collapse:collapse;width:100%;margin:1rem 0}td,th{border:1px solid #ccd3dd;padding:.55rem;text-align:left;vertical-align:top}th{background:#eef3ff}.warning{background:#fff7e6;padding:.8rem;border-left:4px solid #d88b00}code{overflow-wrap:anywhere}</style>",
        "<h1>CrossPlatform App Converter</h1><p>Análise estática. Nenhum pacote foi extraído ou alterado.</p>",
    ]
    for analysis in report.analyses:
        esc = lambda value: html.escape(str(value if value is not None else "—"))
        body.extend([
            f"<h2>{esc(analysis.kind.upper())}: {esc(analysis.app_name or analysis.file_name)}</h2>",
            "<table><tbody>",
        ])
        for label, value in [("Arquivo", analysis.file_name), ("ID", analysis.package_id), ("Versão", analysis.version), ("Build", analysis.build_version), ("SO mínimo", analysis.minimum_os), ("Alvo", analysis.target_os), ("Entradas no pacote", analysis.file_count), ("Tamanho descompactado declarado", analysis.total_uncompressed_size)]:
            body.append(f"<tr><th>{esc(label)}</th><td>{esc(value)}</td></tr>")
        body.append("</tbody></table>")
        body.append("<h3>Dependências / frameworks</h3><ul>" + "".join(f"<li>{esc(dep.name)} — {esc(dep.category)} ({esc(dep.evidence)})</li>" for dep in analysis.dependencies) + "</ul>")
        body.append("<h3>Componentes</h3><ul>" + "".join(f"<li>{esc(comp.kind)}: {esc(comp.name)}</li>" for comp in analysis.components) + "</ul>")
        body.append("<h3>Permissões / usage descriptions</h3><ul>" + "".join(f"<li>{esc(value)}</li>" for value in analysis.permissions) + "</ul>")
        body.append("<h3>Indícios de funcionalidades</h3><ul>" + "".join(f"<li>{esc(item.label)}: {esc(', '.join(item.evidence))}</li>" for item in analysis.features) + "</ul>")
        body.append("<h3>Bibliotecas nativas</h3><ul>" + "".join(f"<li><code>{esc(value)}</code></li>" for value in analysis.native_binaries[:200]) + "</ul>")
        body.append("<h3>Candidatos a recursos (inventário por nome)</h3><ul>" + "".join(f"<li><code>{esc(value)}</code></li>" for value in analysis.resource_candidates[:200]) + "</ul>")
        body.append("<h3>Metadados extraídos</h3><pre>" + esc(json.dumps(analysis.metadata, ensure_ascii=False, indent=2)) + "</pre>")
        if analysis.warnings:
            body.append("<div class='warning'><strong>Observações</strong><ul>" + "".join(f"<li>{esc(value)}</li>" for value in analysis.warnings) + "</ul></div>")
    if report.compatibility:
        comp = report.compatibility
        body.append(f"<h2>Compatibilidade: {html.escape(comp.difficulty)} ({comp.score}/100)</h2><p>{html.escape(comp.summary)}</p>")
        body.append("<table><thead><tr><th>Função</th><th>APK</th><th>IPA</th><th>Leitura</th></tr></thead><tbody>")
        for item in comp.feature_comparisons:
            body.append(f"<tr><td>{html.escape(item.label)}</td><td>{html.escape(', '.join(item.android_evidence) or 'Sem indício encontrado')}</td><td>{html.escape(', '.join(item.ios_evidence) or 'Sem indício encontrado')}</td><td>{html.escape(item.note)}</td></tr>")
        body.append("</tbody></table><h3>Pistas de portabilidade</h3><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in comp.portability_notes) + "</ul>")
        body.append("<h3>Limitações</h3><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in comp.caveats) + "</ul>")
    body.append("<footer><p>Versão 0.1.0 · CrossPlatform App Converter</p></footer></html>")
    with destination.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(body))
    return destination


def summarize(report: FullReport, language: str = "pt") -> str:
    if language == "en":
        return _summarize_english(report)
    lines = ["CROSSPLATFORM APP CONVERTER — ANÁLISE ESTÁTICA", "=" * 52]
    for item in report.analyses:
        lines.extend([
            f"\n{item.kind.upper()} · {item.app_name or item.file_name}",
            f"ID: {item.package_id or 'não encontrado'}    Versão: {item.version or 'não encontrada'}    Build: {item.build_version or 'não encontrado'}",
            f"SO mínimo: {item.minimum_os or 'não encontrado'}    Alvo: {item.target_os or 'não encontrado'}",
            f"Arquivos: {item.file_count:,}    Tamanho descompactado declarado: {item.total_uncompressed_size:,} bytes",
            f"Componentes: {len(item.components)}    Permissões/uso: {len(item.permissions)}    Dependências: {len(item.dependencies)}",
        ])
        if item.dependencies:
            lines.append("Dependências: " + ", ".join(dep.name for dep in item.dependencies[:40]))
        if item.features:
            lines.append("Indícios: " + ", ".join(feature.label for feature in item.features))
        if item.warnings:
            lines.extend("Observação: " + warning for warning in item.warnings)
    if report.compatibility:
        comp = report.compatibility
        lines.extend([f"\nCOMPARAÇÃO DE COMPATIBILIDADE · DIFICULDADE ESTIMADA: {comp.difficulty} ({comp.score}/100)", comp.summary])
        for feature in comp.feature_comparisons:
            lines.append(f"• {feature.label}: {feature.note}")
        lines.extend("Portabilidade: " + note for note in comp.portability_notes)
        lines.extend("Limite: " + note for note in comp.caveats)
    else:
        lines.append("\nPara avaliar compatibilidade, analise um APK e um IPA na mesma execução.")
    lines.extend(["", "Este resultado é uma estimativa estrutural. Não é conversão nem execução do aplicativo."])
    return "\n".join(lines)


def _summarize_english(report: FullReport) -> str:
    lines = ["CROSSPLATFORM APP CONVERTER — STATIC ANALYSIS", "=" * 52]
    for item in report.analyses:
        lines.extend([
            f"\n{item.kind.upper()} · {item.app_name or item.file_name}",
            f"ID: {item.package_id or 'not found'}    Version: {item.version or 'not found'}    Build: {item.build_version or 'not found'}",
            f"Minimum OS: {item.minimum_os or 'not found'}    Target: {item.target_os or 'not found'}",
            f"Files: {item.file_count:,}    Declared uncompressed size: {item.total_uncompressed_size:,} bytes",
            f"Components: {len(item.components)}    Permissions/usage: {len(item.permissions)}    Dependencies: {len(item.dependencies)}",
        ])
        if item.dependencies:
            lines.append("Dependencies: " + ", ".join(dep.name for dep in item.dependencies[:40]))
        if item.features:
            lines.append("Evidence: " + ", ".join(feature.label for feature in item.features))
        if item.warnings:
            lines.extend("Note: " + warning for warning in item.warnings)
    if report.compatibility:
        comp = report.compatibility
        lines.extend([f"\nCOMPATIBILITY COMPARISON · ESTIMATED DIFFICULTY: {comp.difficulty} ({comp.score}/100)", comp.summary])
        for feature in comp.feature_comparisons:
            lines.append(f"• {feature.label}: {feature.note}")
        lines.extend("Portability: " + note for note in comp.portability_notes)
        lines.extend("Limitation: " + note for note in comp.caveats)
    else:
        lines.append("\nTo compare compatibility, analyze an APK and an IPA in the same run.")
    lines.extend(["", "This result is a structural estimate. It is not an app conversion or execution."])
    return "\n".join(lines)
