# -*- coding: utf-8 -*-
"""
AegisOne Test-as-Code CLI Entry (harness_cli.py)
标准 Unix 风格命令行工具，支持 scaffold / scan / diff / run 四大子命令，
支持 --json 格式化输出，专为 DeepSeek Harness、本地终端及 CI/CD 打造。
"""
import argparse
import json
import sys
from runner.harness_engine import HarnessEngine


def main():
    shared_parser = argparse.ArgumentParser(add_help=False)
    shared_parser.add_argument("--json", action="store_true", help="以结构化 JSON 输出结果")

    parser = argparse.ArgumentParser(
        prog="aegis",
        description="AegisOne Test-as-Code Harness CLI for DeepSeek Agent & Developers",
        parents=[shared_parser],
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 1. scaffold
    scaffold_p = subparsers.add_parser("scaffold", parents=[shared_parser], help="生成标准化测试用例脚手架")
    scaffold_p.add_argument("--lang", required=True, choices=["python", "java", "go"], help="开发语言")
    scaffold_p.add_argument("--req", required=True, help="关联需求 ID (如 REQ-ORDER-001)")
    scaffold_p.add_argument("--risk", default="P1", choices=["P0", "P1", "P2", "P3"], help="风险等级")
    scaffold_p.add_argument("--title", default="验证核心业务逻辑断言", help="用例标题")
    scaffold_p.add_argument("--id", dest="case_id", help="指定用例 ID (可选)")
    scaffold_p.add_argument("--out", dest="out_path", help="输出文件路径 (可选)")

    # 2. scan
    scan_p = subparsers.add_parser("scan", parents=[shared_parser], help="毫秒级静态 AST 扫描全仓库用例与步骤资产")
    scan_p.add_argument("--dir", dest="target_dir", default=".", help="扫描目标目录 (默认当前目录)")

    # 3. diff
    diff_p = subparsers.add_parser("diff", parents=[shared_parser], help="比对 Git 变更与已有用例，分析未覆盖风险盲区")
    diff_p.add_argument("--base", default="HEAD~1", help="基准 Git commit/branch (默认 HEAD~1)")

    # 4. run
    run_p = subparsers.add_parser("run", parents=[shared_parser], help="本地极速运行测试并生成五问质量风控门禁答卷")
    run_p.add_argument("target", nargs="?", default=".", help="测试目标文件或目录")
    run_p.add_argument("--lang", choices=["python", "java", "go"], help="指定测试语言 (可选)")
    run_p.add_argument("--base", default="HEAD~1", help="基准 Git commit/branch 用于风控比对")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    engine = HarnessEngine()

    if args.command == "scaffold":
        res = engine.scaffold_case(
            lang=args.lang,
            req=args.req,
            risk=args.risk,
            title=args.title,
            case_id=args.case_id,
            out_path=args.out_path,
        )
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"✅ 成功生成 {args.lang.upper()} 测试脚手架: {res['caseId']}")
            if args.out_path:
                print(f"📁 已写入文件: {res['targetPath']}")
            else:
                print("📝 代码预览:\n" + res["codeContent"])

    elif args.command == "scan":
        res = engine.scan_cases(target_dir=args.target_dir)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"📦 全仓库用例资产盘点完成! 共发现 {res['totalCases']} 个测试用例")
            print(f"   - 风险分布: P0={res['riskDistribution']['P0']}, P1={res['riskDistribution']['P1']}, P2={res['riskDistribution']['P2']}")
            print(f"   - 覆盖需求数: {res['linkedRequirementsCount']}")
            for c in res["cases"][:10]:
                print(f"   • [{c.get('risk', 'P1')}] {c['id']} ({c.get('req', '')}) -> {c['filePath']}:{c['lineNo']} | Steps: {len(c.get('steps', []))}")
            if len(res["cases"]) > 10:
                print(f"   ... 还有 {len(res['cases']) - 10} 个用例，使用 --json 查看完整索引")

    elif args.command == "diff":
        res = engine.analyze_diff_gaps(base_ref=args.base)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"🔍 Git 变更与用例覆盖缺口分析 (Base: {res['baseRef']}):")
            print(f"   - 变更源码文件: {res['totalSourceFilesChanged']}")
            print(f"   - 已覆盖组件: {len(res['coveredComponents'])}")
            print(f"   - ⚠️ 未测代码盲区 (Gaps): {res['gapCount']}")
            print(f"   - 总体风险定级: {res['riskAssessment']}")
            for g in res["uncoveredGaps"]:
                print(f"     ❌ [{g['riskLevel']}] {g['sourceFile']} ({g['changedLinesCount']} 行变更未测) - {g['suggestedAction']}")

    elif args.command == "run":
        res = engine.run_tests_with_gate(
            target_path=args.target,
            lang=args.lang,
            base_ref=args.base,
        )
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            gate = res["releaseRiskGate"]
            verdict_icon = "✅" if gate["verdict"] == "APPROVED" else "🚫"
            print(f"{verdict_icon} 测试运行完成! 状态: {res['status']} (耗时: {res['durationMs']}ms)")
            print("\n📋 【发布前质量风控五问答卷】")
            print(f"  [Q1 核心风险]     : {gate['q1_core_risk']}")
            print(f"  [Q2 验证证据]     : {gate['q2_verification_evidence']}")
            print(f"  [Q3 未覆盖风险]   : {gate['q3_uncovered_risk']}")
            print(f"  [Q4 发布影响预判] : {gate['q4_release_impact']}")
            print(f"  [Q5 生产观测指标] : {gate['q5_post_release_observability']}")
            if res["status"] != "PASSED":
                print("\n❌ 错误详情:\n" + res.get("stdout", "") + res.get("stderr", ""))
                sys.exit(res["exitCode"] if res["exitCode"] != 0 else 1)


if __name__ == "__main__":
    main()
