#!/usr/bin/env python3
"""
创建标签系统数据库架构
"""

import sqlite3
import sys

def create_tags_schema(db_path='twitter_saver.db'):
    """创建标签相关的数据库表"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("创建标签系统数据库表...")

    # 1. 标签表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,              -- 标签名称，如 "技术"
            emoji TEXT,                              -- 可选表情符号，如 "💻"
            color TEXT DEFAULT '#6c757d',            -- 标签颜色（用于UI显示）
            description TEXT,                        -- 标签描述
            is_auto_generated BOOLEAN DEFAULT FALSE, -- 是否自动生成
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usage_count INTEGER DEFAULT 0            -- 使用次数（冗余字段，便于排序）
        )
    ''')

    # 2. 推文-标签关联表（多对多）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tweet_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,                -- 关联到 tasks 表
            tag_id INTEGER NOT NULL,                 -- 关联到 tags 表
            confidence REAL DEFAULT 1.0,             -- AI生成的置信度（0.0-1.0）
            is_manual BOOLEAN DEFAULT FALSE,         -- 是否手动添加
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
            UNIQUE(task_id, tag_id)                  -- 防止重复关联
        )
    ''')

    # 3. AI标签生成记录表（可选，用于审计）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tag_generation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            method TEXT,                             -- 生成方法: 'rule_based', 'claude_api', 'manual'
            generated_tags TEXT,                     -- JSON格式的生成结果
            confidence_scores TEXT,                  -- JSON格式的置信度
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    ''')

    # 创建索引以提高查询性能
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_tags_task ON tweet_tags(task_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_tags_tag ON tweet_tags(tag_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_usage ON tags(usage_count DESC)')

    # 插入一些预定义的常用标签
    default_tags = [
        ('技术', '💻', '#007bff', '技术相关内容'),
        ('设计', '🎨', '#6f42c1', '设计、UI/UX相关'),
        ('AI', '🤖', '#fd7e14', '人工智能、机器学习'),
        ('编程', '⌨️', '#28a745', '编程、代码相关'),
        ('产品', '📦', '#17a2b8', '产品设计、产品管理'),
        ('创业', '🚀', '#dc3545', '创业、商业'),
        ('教程', '📚', '#ffc107', '教程、学习资源'),
        ('新闻', '📰', '#6c757d', '新闻、资讯'),
        ('灵感', '💡', '#e83e8c', '灵感、创意'),
        ('工具', '🔧', '#20c997', '工具、资源推荐'),
        ('观点', '💭', '#6610f2', '观点、评论'),
        ('数据', '📊', '#fd7e14', '数据、统计'),
        ('营销', '📢', '#dc3545', '营销、推广'),
        ('生活', '🌟', '#ffc107', '生活、日常'),
        ('幽默', '😄', '#28a745', '幽默、搞笑'),
    ]

    for tag_name, emoji, color, description in default_tags:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO tags (name, emoji, color, description, is_auto_generated)
                VALUES (?, ?, ?, ?, FALSE)
            ''', (tag_name, emoji, color, description))
        except sqlite3.IntegrityError:
            pass  # 标签已存在

    conn.commit()

    print("✓ 标签表创建完成")
    print("✓ 推文-标签关联表创建完成")
    print("✓ 标签生成日志表创建完成")
    print(f"✓ 预定义标签插入完成 ({len(default_tags)}个)")

    # 统计信息
    tag_count = cursor.execute('SELECT COUNT(*) FROM tags').fetchone()[0]
    print(f"\n当前标签总数: {tag_count}")

    conn.close()
    print("\n数据库架构创建完成！")

if __name__ == '__main__':
    create_tags_schema()
