#!/usr/bin/env python3
"""
批量为历史推文生成标签

使用方法:
    python tools/batch_generate_tags.py                    # 为所有未标记的推文生成标签
    python tools/batch_generate_tags.py --limit 100        # 只处理前100条
    python tools/batch_generate_tags.py --force            # 重新生成所有推文的标签
    python tools/batch_generate_tags.py --use-claude       # 使用Claude API（需要API密钥）
"""

import sys
import os
import sqlite3
import argparse
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.tag_generator import TagGenerator


def batch_generate_tags(limit=None, force=False, use_claude=False, api_key=None):
    """
    批量生成标签

    Args:
        limit: 处理数量限制
        force: 是否强制重新生成
        use_claude: 是否使用Claude API
        api_key: Claude API密钥
    """

    generator = TagGenerator()
    conn = sqlite3.connect('twitter_saver.db')
    cursor = conn.cursor()

    # 查询需要处理的推文
    if force:
        # 强制模式：处理所有已完成的推文
        query = '''
            SELECT id, tweet_text, author_username
            FROM tasks
            WHERE status = 'completed' AND tweet_text IS NOT NULL
            ORDER BY processed_at DESC
        '''
    else:
        # 正常模式：只处理未打标签的推文
        query = '''
            SELECT t.id, t.tweet_text, t.author_username
            FROM tasks t
            LEFT JOIN tweet_tags tt ON t.id = tt.task_id
            WHERE t.status = 'completed'
            AND t.tweet_text IS NOT NULL
            AND tt.id IS NULL
            ORDER BY t.processed_at DESC
        '''

    if limit:
        query += f' LIMIT {limit}'

    tasks = cursor.execute(query).fetchall()
    conn.close()

    total_count = len(tasks)
    print(f"\n找到 {total_count} 条待处理推文")
    print(f"生成方法: {'Claude API' if use_claude else '规则引擎'}")
    print("=" * 80)

    if total_count == 0:
        print("没有需要处理的推文")
        return

    # 开始处理
    success_count = 0
    skip_count = 0
    error_count = 0

    for idx, (task_id, tweet_text, author_username) in enumerate(tasks, 1):
        try:
            print(f"\n[{idx}/{total_count}] 处理任务 #{task_id}")
            print(f"  内容预览: {tweet_text[:60]}...")

            # 生成标签
            if use_claude and api_key:
                tags = generator.generate_tags_claude_api(tweet_text, api_key)
            else:
                tags = generator.generate_tags_rule_based(tweet_text, author_username)

            if not tags:
                print(f"  ⚠ 未匹配到标签")
                skip_count += 1
                continue

            # 如果强制模式，先清除旧标签
            if force:
                conn = sqlite3.connect('twitter_saver.db')
                cursor = conn.cursor()
                cursor.execute('DELETE FROM tweet_tags WHERE task_id = ?', (task_id,))
                conn.commit()
                conn.close()

            # 应用标签
            method = 'claude_api' if (use_claude and api_key) else 'rule_based'
            generator.apply_tags_to_tweet(task_id, tags, method)

            # 显示生成的标签
            tag_names = [f"{name}({conf:.2f})" for name, conf in tags]
            print(f"  ✓ 生成标签: {', '.join(tag_names)}")

            success_count += 1

        except Exception as e:
            print(f"  ✗ 错误: {e}")
            error_count += 1
            continue

    # 统计结果
    print("\n" + "=" * 80)
    print("批量生成完成！")
    print(f"  成功: {success_count}")
    print(f"  跳过: {skip_count}")
    print(f"  失败: {error_count}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="批量为历史推文生成标签",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 为所有未标记的推文生成标签（规则引擎）
    python tools/batch_generate_tags.py

    # 只处理前50条
    python tools/batch_generate_tags.py --limit 50

    # 重新生成所有推文的标签
    python tools/batch_generate_tags.py --force

    # 使用Claude API生成（需要API密钥）
    python tools/batch_generate_tags.py --use-claude --api-key sk-xxx
        """
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='处理数量限制'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重新生成所有推文的标签'
    )

    parser.add_argument(
        '--use-claude',
        action='store_true',
        help='使用Claude API生成标签（更准确但需要API密钥）'
    )

    parser.add_argument(
        '--api-key',
        help='Claude API密钥（使用--use-claude时需要）'
    )

    args = parser.parse_args()

    # 检查API密钥
    if args.use_claude and not args.api_key:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print("错误: 使用Claude API需要提供API密钥")
            print("  方式1: --api-key sk-xxx")
            print("  方式2: 设置环境变量 ANTHROPIC_API_KEY")
            sys.exit(1)
        args.api_key = api_key

    # 确认操作
    if args.force:
        response = input("\n⚠️  强制模式将重新生成所有推文的标签，确定继续？(yes/no): ")
        if response.lower() != 'yes':
            print("已取消")
            return

    # 执行批量生成
    batch_generate_tags(
        limit=args.limit,
        force=args.force,
        use_claude=args.use_claude,
        api_key=args.api_key
    )


if __name__ == '__main__':
    main()
