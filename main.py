#!/usr/bin/env python3
"""GitHub Trending Tool — 主入口"""

import argparse
import logging
import os
import sys
from datetime import datetime

import config
from src.scraper import GitHubTrendingScraper
from src.summarizer import create_summarizer


def run(dry_run: bool = False, no_export: bool = False, no_project_summary: bool = False) -> None:
    """执行完整流程：爬取 → 总结 → 项目概括 → 导出 → 发布"""
    date = datetime.now().strftime("%Y-%m-%d")

    # 1. 爬取
    print(f"🕷️  正在爬取 GitHub Trending ({date})...")
    scraper = GitHubTrendingScraper()
    repos = scraper.scrape()

    if not repos:
        print("⚠️  未爬取到任何仓库数据，退出。")
        sys.exit(1)

    print(f"✅ 爬取到 {len(repos)} 个仓库")

    # 2. 总结
    print("📝 正在生成总结...")
    summarizer = create_summarizer()
    summary = summarizer.summarize(repos, date)

    if dry_run:
        print("\n" + "=" * 50)
        print("🔍 DRY-RUN 模式 — 以下为生成的总结内容：")
        print("=" * 50)
        print(summary)
        print("=" * 50)

    # 3. 项目概括（Top 10）
    project_summaries = []
    if not no_project_summary:
        print("📖 正在生成 Top 10 项目概括...")
        try:
            from src.project_summarizer import ProjectSummarizer
            proj_summarizer = ProjectSummarizer(
                use_llm=config.LLM_ENABLED,
                llm_api_key=config.LLM_API_KEY if config.LLM_ENABLED else None,
            )
            project_summaries = proj_summarizer.summarize_top_repos(repos, top_n=10)
            print(f"✅ 生成了 {len(project_summaries)} 个项目概括")
            if dry_run:
                print("\n项目概括预览:")
                for i, ps in enumerate(project_summaries[:5], 1):
                    tags_str = ", ".join(ps.tags) if ps.tags else "无"
                    print(f"  {i}. {ps.repo_name} [{tags_str}]")
                    print(f"     {ps.summary[:100]}...")
        except Exception as e:
            print(f"⚠️  项目概括生成失败: {e}")
            project_summaries = []

    # 4. 导出文件（MD / HTML / PDF）
    pdf_path = ""
    if not no_export:
        print("📁 正在导出文件...")
        try:
            from src.exporter import export_all
            paths = export_all(repos, summary, date, project_summaries=project_summaries)
            print(f"✅ Markdown → {paths['md']}")
            print(f"✅ HTML     → {paths['html']}")
            print(f"✅ PDF      → {paths['pdf']}")
            pdf_path = paths['pdf']
        except Exception as e:
            print(f"️  文件导出失败: {e}")
            if dry_run:
                # dry-run 下导出失败不阻断流程
                pass
            else:
                raise

    if dry_run:
        print("\n🏁 Dry-run 结束，未实际发送消息。")
        return

    # 5. 发布到飞书（文本摘要 + PDF 文件）
    print("📤 正在发布到飞书...")
    try:
        from src.publisher.feishu import FeishuPublisher
        publisher = FeishuPublisher()
        publisher.publish(summary)
        # 发送 PDF 文件（失败不影响主流程）
        if pdf_path and os.path.exists(pdf_path):
            try:
                publisher.publish_pdf(pdf_path)
            except Exception as e:
                print(f"⚠️  PDF 文件发送失败: {e}")
                print("   请确保已将机器人添加到飞书群聊")
        print("✅ 发布成功！")
    except ValueError as e:
        print(f"❌ 发布失败：{e}")
        print("   请确保已配置 FEISHU_WEBHOOK_URL 环境变量。")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 发布失败：{e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="GitHub Trending 每日爬取 & 推送工具")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅生成总结并打印，不实际发送消息",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="跳过 MD/HTML/PDF 文件导出",
    )
    parser.add_argument(
        "--no-project-summary",
        action="store_true",
        help="跳过 Top 10 项目概括生成",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="开启详细日志",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run(dry_run=args.dry_run, no_export=args.no_export, no_project_summary=args.no_project_summary)


if __name__ == "__main__":
    main()
