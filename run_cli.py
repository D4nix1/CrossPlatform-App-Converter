from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cpc.analyze import build_report
from cpc.portability import create_conversion_attempt, create_scaffold
from cpc.recovery import recover_apk, recovery_status_label
from cpc.reports import summarize, write_html_report, write_json_report


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Análise estrutural estática de pacotes APK e IPA.")
    parser.add_argument("packages", nargs="+", help="Um APK ou IPA; informe ambos para comparar.")
    parser.add_argument("--reports", type=Path, help="Pasta de destino dos relatórios JSON e HTML.")
    parser.add_argument("--scaffold", choices=("android", "ios"), help="Gera um esqueleto experimental para a plataforma indicada.")
    parser.add_argument("--scaffold-dir", type=Path, help="Pasta onde o esqueleto será criado (padrão: pasta atual).")
    parser.add_argument("--attempt-conversion", action="store_true", help="Cria um ZIP de portabilidade experimental; não é instalável.")
    parser.add_argument("--attempt-dir", type=Path, help="Pasta para o ZIP da tentativa (padrão: pasta atual).")
    parser.add_argument("--recover-apk", action="store_true", help="Tenta recuperar Java aproximado e recursos do primeiro APK usando JADX portátil.")
    parser.add_argument("--recover-dir", type=Path, help="Pasta onde a saída de recuperação será criada.")
    args = parser.parse_args()
    if len(args.packages) > 2:
        parser.error("Informe no máximo um APK e um IPA.")
    if args.recover_apk and len(args.packages) != 1:
        parser.error("--recover-apk requer exatamente um pacote, que precisa ser um APK.")
    try:
        report = build_report(args.packages)
        print(summarize(report))
        if args.reports:
            print("\nRelatório JSON:", write_json_report(report, args.reports))
            print("Relatório HTML:", write_html_report(report, args.reports))
        if args.scaffold:
            source = report.analyses[0]
            target = args.scaffold
            if (source.kind == "apk" and target == "ios") or (source.kind == "ipa" and target == "android"):
                print("\nEsqueleto experimental:", create_scaffold(source, target, args.scaffold_dir or Path.cwd()))
            else:
                parser.error("O destino do esqueleto deve ser a plataforma oposta à do primeiro pacote.")
        if args.attempt_conversion:
            bundle, copied, skipped = create_conversion_attempt(report.analyses[0], args.attempt_dir or Path.cwd())
            print(f"\nRascunho experimental ZIP: {bundle}")
            print(f"Recursos candidatos copiados: {copied}; ignorados: {len(skipped)}")
            print("Não é um APK/IPA instalável; consulte CONVERSION-ATTEMPT.txt dentro do ZIP.")
        if args.recover_apk:
            recovered = recover_apk(report.analyses[0], args.recover_dir or Path.cwd())
            print(f"\nRecuperação JADX ({recovery_status_label(recovered.status)}): {recovered.output_dir}")
            print(
                f"Java: {recovered.java_files}; XML: {recovered.xml_files}; imagens: {recovered.image_files}; "
                f"layouts: {recovered.layout_count}; strings: {recovered.string_count}; "
                f"erros de decompilação: {recovered.decompilation_errors}; entradas ZIP omitidas por segurança/caminho: {recovered.unsafe_entries_omitted}."
            )
            print("Resultado aproximado, não é código-fonte original nem conversão para iOS; consulte README.md, android-ui-inventory.json e jadx.log.")
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
