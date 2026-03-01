#!/usr/bin/env python3
"""
AI标签生成器
支持多种方法生成推文标签
"""

import re
import json
from typing import List, Dict, Tuple
import sqlite3


class TagGenerator:
    """标签生成器"""

    def __init__(self, db_path='twitter_saver.db'):
        self.db_path = db_path

        # 预定义的关键词规则
        self.keyword_rules = {
            '技术': ['技术', 'tech', 'technology', '开发', 'development', '代码', 'code', 'github'],
            'AI': ['ai', 'gpt', 'llm', 'claude', '人工智能', 'machine learning', 'ml', '深度学习', 'deep learning', 'chatgpt', 'openai', 'anthropic'],
            '编程': ['编程', 'programming', 'python', 'javascript', 'java', 'rust', 'go', 'c++', 'react', 'vue', 'node'],
            '设计': ['设计', 'design', 'ui', 'ux', 'figma', 'sketch', '界面', 'interface'],
            '产品': ['产品', 'product', 'pm', 'prd', '需求', 'feature', '功能'],
            '创业': ['创业', 'startup', '融资', 'vc', '投资', 'founder', '创始人'],
            '教程': ['教程', 'tutorial', '学习', 'learn', 'how to', '指南', 'guide', '课程', 'course'],
            '新闻': ['新闻', 'news', '发布', 'release', '更新', 'update', '公告', 'announcement'],
            '灵感': ['灵感', 'inspiration', '创意', 'idea', '想法', 'thought'],
            '工具': ['工具', 'tool', '软件', 'software', 'app', '应用', 'plugin', '插件'],
            '营销': ['营销', 'marketing', '推广', 'promotion', 'seo', '广告', 'ads'],
            '数据': ['数据', 'data', '统计', 'statistics', '分析', 'analysis', '图表', 'chart'],
            '观点': ['观点', 'opinion', '评论', 'comment', '看法', '认为', 'think'],
            '幽默': ['😂', '😄', '🤣', '哈哈', 'lol', 'funny', '搞笑', '有趣'],
        }

    def generate_tags_rule_based(self, text: str, author_username: str = None) -> List[Tuple[str, float]]:
        """
        基于规则的标签生成

        Args:
            text: 推文文本
            author_username: 作者用户名（可选，用于特定规则）

        Returns:
            [(tag_name, confidence), ...] 标签和置信度列表
        """
        if not text:
            return []

        text_lower = text.lower()
        matched_tags = []

        # 遍历规则，查找匹配的关键词
        for tag_name, keywords in self.keyword_rules.items():
            confidence = 0.0
            match_count = 0

            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in text_lower:
                    match_count += 1
                    # 根据匹配次数和关键词长度计算置信度
                    keyword_confidence = 0.3 + (len(keyword) * 0.02)
                    confidence = max(confidence, keyword_confidence)

            # 如果有多个关键词匹配，提高置信度
            if match_count > 1:
                confidence = min(confidence * (1 + match_count * 0.1), 0.95)

            if confidence > 0:
                matched_tags.append((tag_name, confidence))

        # 按置信度排序
        matched_tags.sort(key=lambda x: x[1], reverse=True)

        # 最多返回5个标签
        return matched_tags[:5]

    def _load_prompt_config(self) -> dict:
        """
        从prompts.ini加载prompt配置

        Returns:
            配置字典
        """
        import configparser
        import os

        config = configparser.ConfigParser()
        prompt_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts.ini')

        if os.path.exists(prompt_file):
            config.read(prompt_file, encoding='utf-8')

        return {
            'prompt': config.get('gemini_tag_generation', 'prompt', fallback=''),
            'model': config.get('gemini_tag_generation', 'model', fallback='models/gemini-2.0-flash-exp')
        }

    def generate_tags_gemini_api(self, text: str, api_key: str = None) -> List[Tuple[str, float]]:
        """
        使用Gemini API生成标签（需要API密钥）

        Args:
            text: 推文文本
            api_key: Google API密钥

        Returns:
            [(tag_name, confidence), ...] 标签和置信度列表
        """
        if not api_key:
            # 如果没有API密钥，降级到规则引擎
            return self.generate_tags_rule_based(text)

        try:
            import google.generativeai as genai

            # 配置Gemini API
            genai.configure(api_key=api_key)

            # 从配置文件加载prompt
            config = self._load_prompt_config()
            prompt_template = config.get('prompt')
            model_name = config.get('model')

            if not prompt_template:
                print("[WARNING] prompts.ini中未找到prompt配置，使用默认prompt")
                prompt_template = """分析以下推文内容，生成3-5个最合适的标签。

推文内容:
{text}

要求:
1. 根据推文内容自动生成最相关的3-5个标签
2. 标签应该简洁、准确，能概括推文的主题、领域或特点
3. 标签名使用中文或英文，纯文本，不要包含emoji或特殊符号
4. 每个标签2-4个字为佳，最多不超过6个字
5. 为每个标签提供0.0-1.0的置信度分数
6. 返回JSON格式: {{"tags": [{{"name": "标签名", "confidence": 0.85}}]}}

请只返回JSON，不要有其他文字。"""

            # 格式化prompt
            prompt = prompt_template.format(text=text)

            # 初始化模型
            model = genai.GenerativeModel(model_name)

            # 生成响应
            response = model.generate_content(prompt)
            response_text = response.text.strip()

            # 解析JSON响应
            try:
                # 提取JSON（可能被markdown代码块包裹）
                if '```json' in response_text:
                    response_text = response_text.split('```json')[1].split('```')[0].strip()
                elif '```' in response_text:
                    response_text = response_text.split('```')[1].split('```')[0].strip()

                result = json.loads(response_text)
                tags = result.get('tags', [])

                # 返回格式: [(name, confidence), ...]
                return [(tag['name'], tag['confidence']) for tag in tags]

            except json.JSONDecodeError as e:
                print(f"[WARNING] Gemini API响应解析失败: {e}")
                print(f"Response: {response_text}")
                # 降级到规则引擎
                return self.generate_tags_rule_based(text)

        except Exception as e:
            print(f"[ERROR] Gemini API调用失败: {e}")
            import traceback
            traceback.print_exc()
            # 降级到规则引擎
            return self.generate_tags_rule_based(text)

    def generate_tags_claude_api(self, text: str, api_key: str = None) -> List[Tuple[str, float]]:
        """
        使用Claude API生成标签（需要API密钥）
        已弃用，建议使用 generate_tags_gemini_api

        Args:
            text: 推文文本
            api_key: Anthropic API密钥

        Returns:
            [(tag_name, confidence), ...] 标签和置信度列表
        """
        # 直接降级到规则引擎
        print("[INFO] Claude API已弃用，使用规则引擎")
        return self.generate_tags_rule_based(text)

    def apply_tags_to_tweet(self, task_id: int, tags: List[Tuple[str, float]], method: str = 'rule_based'):
        """
        将标签应用到推文

        Args:
            task_id: 任务ID
            tags: [(tag_name, confidence), ...] 标签列表
            method: 生成方法 ('rule_based', 'gemini_api', 'manual')
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            for tag_name, confidence in tags:
                # 获取或创建标签
                cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
                result = cursor.fetchone()

                if result:
                    tag_id = result[0]
                else:
                    # 创建新标签（不包含emoji）
                    cursor.execute('''
                        INSERT INTO tags (name, is_auto_generated)
                        VALUES (?, TRUE)
                    ''', (tag_name,))
                    tag_id = cursor.lastrowid

                # 关联标签到推文
                try:
                    cursor.execute('''
                        INSERT INTO tweet_tags (task_id, tag_id, confidence, is_manual)
                        VALUES (?, ?, ?, ?)
                    ''', (task_id, tag_id, confidence, method == 'manual'))

                    # 更新标签使用次数
                    cursor.execute('''
                        UPDATE tags SET usage_count = usage_count + 1
                        WHERE id = ?
                    ''', (tag_id,))

                except sqlite3.IntegrityError:
                    # 标签已存在，更新置信度
                    cursor.execute('''
                        UPDATE tweet_tags
                        SET confidence = ?, is_manual = ?
                        WHERE task_id = ? AND tag_id = ?
                    ''', (confidence, method == 'manual', task_id, tag_id))

            # 记录生成日志
            cursor.execute('''
                INSERT INTO tag_generation_log (task_id, method, generated_tags, confidence_scores)
                VALUES (?, ?, ?, ?)
            ''', (task_id, method, json.dumps([t[0] for t in tags]), json.dumps([t[1] for t in tags])))

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_tags_for_tweet(self, task_id: int) -> List[Dict]:
        """
        获取推文的所有标签

        Args:
            task_id: 任务ID

        Returns:
            标签列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT t.id, t.name, t.emoji, t.color, tt.confidence, tt.is_manual
            FROM tweet_tags tt
            JOIN tags t ON tt.tag_id = t.id
            WHERE tt.task_id = ?
            ORDER BY tt.confidence DESC
        ''', (task_id,))

        tags = []
        for row in cursor.fetchall():
            tags.append({
                'id': row[0],
                'name': row[1],
                'emoji': row[2],
                'color': row[3],
                'confidence': row[4],
                'is_manual': bool(row[5])
            })

        conn.close()
        return tags

    def remove_tag_from_tweet(self, task_id: int, tag_id: int):
        """
        从推文移除标签

        Args:
            task_id: 任务ID
            tag_id: 标签ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM tweet_tags WHERE task_id = ? AND tag_id = ?', (task_id, tag_id))

        # 更新标签使用次数
        cursor.execute('UPDATE tags SET usage_count = usage_count - 1 WHERE id = ?', (tag_id,))

        conn.commit()
        conn.close()

    def get_all_tags(self) -> List[Dict]:
        """获取所有标签"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, emoji, color, description, usage_count
            FROM tags
            ORDER BY usage_count DESC
        ''')

        tags = []
        for row in cursor.fetchall():
            tags.append({
                'id': row[0],
                'name': row[1],
                'emoji': row[2],
                'color': row[3],
                'description': row[4],
                'usage_count': row[5]
            })

        conn.close()
        return tags


# 测试代码
if __name__ == '__main__':
    generator = TagGenerator()

    # 测试规则引擎
    test_text = """
    使用 Claude AI 进行推文分析和自动标签生成。
    这是一个非常有趣的技术项目，结合了 Python 和机器学习。
    """

    tags = generator.generate_tags_rule_based(test_text)
    print("生成的标签:")
    for tag, confidence in tags:
        print(f"  {tag}: {confidence:.2f}")
