#!/usr/bin/env python3
"""
Twitter内容保存工具 - Web界面
Flask + Bootstrap Web应用
"""

import os
import json
import sqlite3
import threading
import time
import logging
import sys
import io
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, Response, session, flash
from werkzeug.utils import secure_filename
import queue
from collections import deque
from services.config_manager import ConfigManager
from services.twitter_service import TwitterService, TwitterScrapingError
from services.media_downloader import MediaDownloader
from services.file_manager import FileManager
from services.user_manager import UserManager
from utils.url_parser import TwitterURLParser

app = Flask(__name__)

# 使用固定的 secret key 或从环境变量读取
# 这样重启应用后 session 不会失效
SECRET_KEY_FILE = 'secret_key.txt'
if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, 'r') as f:
        app.secret_key = f.read().strip()
else:
    # 首次运行，生成并保存 secret key
    app.secret_key = secrets.token_hex(32)
    with open(SECRET_KEY_FILE, 'w') as f:
        f.write(app.secret_key)

app.permanent_session_lifetime = timedelta(days=1)  # Default 24 hours

# Session 配置 - 确保在 HTTPS 环境下正常工作
app.config['SESSION_COOKIE_SECURE'] = False  # 允许 HTTP 和 HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # 防止 XSS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF 保护

# 配置日志级别，减少Flask的HTTP请求日志
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# 导入实时日志系统
from utils.realtime_logger import log_buffer, log_lock, log, info, error, warning, success

# 添加自定义Jinja2过滤器
@app.template_filter('tojsonpretty')
def to_json_pretty(value):
    """将对象转换为格式化的JSON字符串"""
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)

@app.template_filter('autolink')
def autolink(text):
    """自动将文本中的链接转换为HTML链接"""
    import re

    # 处理 None 或空字符串
    if not text:
        return ''

    # 确保是字符串类型
    text = str(text)

    # URL正则表达式
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'

    # 替换URL为链接
    def replace_url(match):
        url = match.group(0)
        # 截断显示的URL长度
        display_url = url if len(url) <= 50 else url[:47] + '...'
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="text-primary">{display_url}</a>'

    text = re.sub(url_pattern, replace_url, text)

    # 处理@用户名
    mention_pattern = r'@(\w+)'
    def replace_mention(match):
        username = match.group(1)
        return f'<a href="https://twitter.com/{username}" target="_blank" rel="noopener noreferrer" class="text-info">@{username}</a>'

    text = re.sub(mention_pattern, replace_mention, text)

    # 处理#标签
    hashtag_pattern = r'#(\w+)'
    def replace_hashtag(match):
        hashtag = match.group(1)
        return f'<a href="https://twitter.com/hashtag/{hashtag}" target="_blank" rel="noopener noreferrer" class="text-success">#{hashtag}</a>'

    text = re.sub(hashtag_pattern, replace_hashtag, text)

    return text

@app.template_filter('nl2br')
def nl2br(text):
    """将换行符转换为HTML换行"""
    if not text:
        return ''
    return str(text).replace('\n', '<br>')

@app.template_filter('format_datetime')
def format_datetime(datetime_str):
    """格式化日期时间"""
    if not datetime_str:
        return '未知'
    try:
        # 尝试解析ISO格式的日期时间
        if 'T' in datetime_str:
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(datetime_str)
        return dt.strftime('%Y年%m月%d日 %H:%M')
    except:
        return datetime_str

# 添加context processor，自动传递登录状态给所有模板
@app.context_processor
def inject_user_status():
    """注入用户登录状态到所有模板"""
    return {
        'is_logged_in': session.get('logged_in', False),
        'username': session.get('username', None)
    }

# 全局变量
config_manager = None
twitter_service = None
media_downloader = None
file_manager = None
user_manager = UserManager()  # Initialize UserManager
processing_queue = queue.Queue()
is_processing = False
processing_thread = None

# 登录验证装饰器
def login_required(f):
    """
    Decorator to require login for frontend routes
    API routes are exempt from login requirement
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if request is for API endpoint
        if request.path.startswith('/api/'):
            return f(*args, **kwargs)

        # Check if user is logged in
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('login', next=request.url))

        return f(*args, **kwargs)
    return decorated_function

def normalize_path_cross_platform(path):
    """标准化路径以支持跨平台兼容性（Windows <-> Linux）"""
    if not path:
        return path
    
    # 根据当前操作系统标准化路径分隔符
    if os.sep == '/':  # Linux/Unix 系统
        normalized_path = path.replace('\\', '/')
    else:  # Windows 系统
        normalized_path = path.replace('/', '\\')
    
    # 使用 os.path.normpath 进一步标准化路径
    normalized_path = os.path.normpath(normalized_path)
    
    # 如果是相对路径，确保相对于当前工作目录
    if not os.path.isabs(normalized_path):
        normalized_path = os.path.join(os.getcwd(), normalized_path)
        normalized_path = os.path.normpath(normalized_path)
    
    return normalized_path

def find_actual_tweet_directory(expected_path):
    """查找实际存在的推文目录，处理日期不匹配问题"""
    if os.path.exists(expected_path):
        return expected_path
    
    # 如果期望路径不存在，尝试在父目录中查找匹配的目录
    parent_dir = os.path.dirname(expected_path)
    expected_basename = os.path.basename(expected_path)
    
    if not os.path.exists(parent_dir):
        return expected_path  # 返回原路径，调用者可以判断是否存在
    
    try:
        # 提取推文ID（格式通常是 YYYY-MM-DD_tweet_id）
        if '_' in expected_basename:
            date_part, tweet_id = expected_basename.split('_', 1)
            
            # 在父目录中查找包含相同推文ID的目录
            for item in os.listdir(parent_dir):
                item_path = os.path.join(parent_dir, item)
                if os.path.isdir(item_path) and '_' in item:
                    item_date, item_tweet_id = item.split('_', 1)
                    if item_tweet_id == tweet_id:
                        return item_path
        
        # 如果没找到精确匹配，尝试部分匹配
        for item in os.listdir(parent_dir):
            item_path = os.path.join(parent_dir, item)
            if os.path.isdir(item_path) and expected_basename in item:
                return item_path
                
    except Exception as e:
        pass
    
    return expected_path  # 如果找不到，返回原路径

def get_current_time():
    """获取当前时间，使用本地时区但保持一致性"""
    return datetime.now()

def format_time_for_db(dt):
    """格式化时间用于数据库存储"""
    if dt is None:
        return None
    return dt.isoformat()

def parse_time_from_db(time_str):
    """从数据库解析时间字符串"""
    if not time_str:
        return None
    try:
        return datetime.fromisoformat(time_str)
    except:
        # 兼容旧格式
        try:
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except:
            return None

def generate_unique_slug():
    """生成唯一的URL安全的随机字符串用于分享链接"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    max_attempts = 10
    for _ in range(max_attempts):
        # 生成8字符的URL安全随机字符串
        slug = secrets.token_urlsafe(8)
        
        # 检查是否已存在
        existing = cursor.execute(
            'SELECT id FROM tasks WHERE share_slug = ?',
            (slug,)
        ).fetchone()
        
        if not existing:
            conn.close()
            return slug
    
    conn.close()
    # 如果10次都冲突（几乎不可能），使用更长的字符串
    return secrets.token_urlsafe(12)


def check_and_schedule_retry(cursor, task_id, error_message):
    """检查任务是否应该重试，如果是则安排重试"""
    try:
        # 获取当前任务的重试信息
        task = cursor.execute(
            'SELECT retry_count, max_retries FROM tasks WHERE id = ?',
            (task_id,)
        ).fetchone()
        
        if not task:
            return False
        
        retry_count = task['retry_count'] if task['retry_count'] else 0
        max_retries = task['max_retries'] if task['max_retries'] else 3
        
        # 检查是否应该重试的错误类型
        retry_eligible_errors = [
            "Web scraping failed and API is not available",
            "Failed to fetch tweet",
            "Rate limit exceeded",
            "Timeout",
            "Connection error",
            "Request failed"
        ]
        
        should_retry = any(error_pattern in error_message for error_pattern in retry_eligible_errors)
        
        if should_retry and retry_count < max_retries:
            # 计算下次重试时间（指数退避：2^retry_count 分钟）
            delay_minutes = min(2 ** retry_count, 60)  # 最大延迟60分钟
            next_retry_time = get_current_time() + timedelta(minutes=delay_minutes)
            
            # 更新重试信息
            cursor.execute("""
                UPDATE tasks SET 
                    status = 'pending',
                    retry_count = ?,
                    next_retry_time = ?,
                    error_message = ?
                WHERE id = ?
            """, (
                retry_count + 1,
                format_time_for_db(next_retry_time),
                f"Retry {retry_count + 1}/{max_retries}: {error_message}",
                task_id
            ))
            
            print(f"[Task {task_id}] Scheduled for retry {retry_count + 1}/{max_retries} at {next_retry_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return True
        else:
            print(f"[Task {task_id}] Max retries ({max_retries}) reached or error not retry-eligible")
            return False
            
    except Exception as e:
        print(f"Error in check_and_schedule_retry: {e}")
        return False

def check_retry_ready_tasks():
    """检查并将准备重试的任务重新加入队列"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 查找到达重试时间的任务
        current_time = get_current_time()
        cursor.execute("""
            SELECT id, url FROM tasks 
            WHERE status = 'pending' 
            AND next_retry_time IS NOT NULL 
            AND next_retry_time <= ?
            AND retry_count > 0
        """, (format_time_for_db(current_time),))
        
        retry_tasks = cursor.fetchall()
        
        for task in retry_tasks:
            task_id, url = task['id'], task['url']
            info(f"[Retry Queue] Adding retry task {task_id} to queue: {url}")
            processing_queue.put((task_id, url))
            
            # 清除next_retry_time以避免重复加入队列
            cursor.execute(
                "UPDATE tasks SET next_retry_time = NULL WHERE id = ?",
                (task_id,)
            )
        
        if retry_tasks:
            conn.commit()
            info(f"[Retry Queue] Added {len(retry_tasks)} retry tasks to queue")
        
        conn.close()
        
    except Exception as e:
        error(f"Error in check_retry_ready_tasks: {e}")

def check_and_queue_pending_tasks():
    """检查所有pending任务并确保它们在队列中（防止重置后任务丢失）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 查找所有pending状态且没有重试时间的任务（通常是重置后的任务）
        cursor.execute("""
            SELECT id, url FROM tasks 
            WHERE status = 'pending' 
            AND (next_retry_time IS NULL OR (retry_count = 0 AND next_retry_time IS NULL))
        """)
        
        pending_tasks = cursor.fetchall()
        
        if pending_tasks:
            for task in pending_tasks:
                task_id, url = task['id'], task['url']
                processing_queue.put((task_id, url))
                info(f"[Pending Check] Added pending task {task_id} to queue: {url}")
            
            info(f"[Pending Check] Added {len(pending_tasks)} pending tasks to queue")
        
        conn.close()
        
    except Exception as e:
        error(f"Error in check_and_queue_pending_tasks: {e}")

# 数据库初始化
def init_db():
    """初始化数据库"""
    conn = sqlite3.connect('twitter_saver.db')
    cursor = conn.cursor()
    
    # 创建任务表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            tweet_id TEXT,
            author_username TEXT,
            author_name TEXT,
            save_path TEXT,
            error_message TEXT,
            is_thread BOOLEAN DEFAULT FALSE,
            tweet_count INTEGER DEFAULT 0,
            media_count INTEGER DEFAULT 0,
            tweet_text TEXT,
            retry_count INTEGER DEFAULT 0,
            next_retry_time TIMESTAMP,
            max_retries INTEGER DEFAULT 3
        )
    ''')
    
    # 添加新字段（用于已有数据库的升级）
    new_columns = [
        ('tweet_text', 'TEXT'),
        ('retry_count', 'INTEGER DEFAULT 0'),
        ('next_retry_time', 'TIMESTAMP'),
        ('max_retries', 'INTEGER DEFAULT 3'),
        ('share_slug', 'TEXT'),
        ('content_type', "TEXT DEFAULT 'tweet'")
    ]
    
    for column_name, column_def in new_columns:
        try:
            cursor.execute(f'ALTER TABLE tasks ADD COLUMN {column_name} {column_def}')
        except sqlite3.OperationalError:
            # 字段已存在，忽略错误
            pass
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_id ON tasks(tweet_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_author_username ON tasks(author_username)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_author_name ON tasks(author_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_next_retry_time ON tasks(next_retry_time)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_retry_count ON tasks(retry_count)')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_share_slug ON tasks(share_slug)')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect('twitter_saver.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_services():
    """初始化服务"""
    global config_manager, twitter_service, media_downloader, file_manager
    
    try:
        print(f"[init_services] Starting service initialization...")
        print(f"[init_services] Current global variables: config_manager={config_manager}, twitter_service={twitter_service}")
        
        print(f"[init_services] Creating ConfigManager...")
        config_manager = ConfigManager()
        print(f"[init_services] ConfigManager created: {config_manager}")
        
        print(f"[init_services] Validating config...")
        if not config_manager.validate_config():
            print(f"[init_services] Config validation failed!")
            return False
        print(f"[init_services] Config validation passed")
        
        print(f"[init_services] Loading config...")
        config = config_manager.load_config()
        print(f"[init_services] Config loaded successfully")
        
        print(f"[init_services] Creating TwitterService...")
        twitter_service = TwitterService(
            max_retries=config['max_retries'],
            timeout=config['timeout_seconds'],
            use_playwright=config.get('use_playwright', True)
        )
        print(f"[init_services] TwitterService created: {twitter_service}")
        
        print(f"[init_services] Creating MediaDownloader...")
        media_downloader = MediaDownloader(
            max_retries=config['max_retries'],
            timeout=config['timeout_seconds']
        )
        print(f"[init_services] MediaDownloader created: {media_downloader}")
        
        print(f"[init_services] Creating FileManager...")
        file_manager = FileManager(
            base_path=config['save_path'],
            create_date_folders=config['create_date_folders']
        )
        print(f"[init_services] FileManager created: {file_manager}")
        
        print(f"[init_services] All services created successfully!")
        print(f"[init_services] Final global variables: config_manager={config_manager}, twitter_service={twitter_service}")
        return True
    except Exception as e:
        print(f"[init_services] ERROR: Failed to initialize services: {e}")
        import traceback
        traceback.print_exc()
        return False

def auto_generate_tags_for_tweet(task_id: int, tweet_text: str, author_username: str = None):
    """
    自动为新保存的推文生成标签

    Args:
        task_id: 任务ID
        tweet_text: 推文文本
        author_username: 作者用户名
    """
    from services.config_manager import ConfigManager

    # 获取Gemini API密钥（从config.ini）
    config = ConfigManager()
    gemini_api_key = config.get_gemini_api_key()

    # 生成标签
    if gemini_api_key:
        # 优先使用Gemini API
        info(f"[Tag Generator] Using Gemini API for task {task_id}")
        tags = tag_generator.generate_tags_gemini_api(tweet_text, gemini_api_key)
        method = 'gemini_api'
    else:
        # 降级到规则引擎
        info(f"[Tag Generator] Using rule-based engine for task {task_id}")
        tags = tag_generator.generate_tags_rule_based(tweet_text, author_username)
        method = 'rule_based'

    if tags:
        # 应用标签
        tag_generator.apply_tags_to_tweet(task_id, tags, method)
        tag_names = [f"{name}({conf:.2f})" for name, conf in tags]
        success(f"[Tag Generator] Generated {len(tags)} tags for task {task_id}: {', '.join(tag_names)}")
    else:
        info(f"[Tag Generator] No tags matched for task {task_id}")

def process_tweet_task(task_id, url):
    """处理单个推文任务"""
    conn = get_db_connection()
    
    try:
        info(f"[Task {task_id}] Starting processing: {url}")
        update_task_progress(task_id, 'started', f'开始处理任务: {url}')
        
        # 先验证任务状态，确保任务还是pending状态
        task_check = conn.execute(
            'SELECT status FROM tasks WHERE id = ?', (task_id,)
        ).fetchone()
        
        if not task_check or task_check['status'] != 'pending':
            warning(f"[Task {task_id}] Task is not in pending status, skipping...")
            update_task_progress(task_id, 'skipped', '任务状态不是pending，跳过处理')
            conn.close()
            return
        
        # 更新任务状态为处理中
        conn.execute(
            'UPDATE tasks SET status = ?, processed_at = ? WHERE id = ?',
            ('processing', format_time_for_db(get_current_time()), task_id)
        )
        conn.commit()
        info(f"[Task {task_id}] Status updated to processing")
        update_task_progress(task_id, 'processing', '任务状态已更新为处理中')
        
        # 验证URL
        if not TwitterURLParser.is_valid_twitter_url(url):
            raise ValueError(f"Invalid Twitter URL: {url}")
        
        # 提取推文ID
        tweet_id = twitter_service.extract_tweet_id(url)
        info(f"[Task {task_id}] Extracted tweet ID: {tweet_id}")
        
        # 获取推文数据
        try:
            info(f"[Task {task_id}] Calling Twitter service to get tweet...")
            update_task_progress(task_id, 'api_call', f'正在获取推文 {tweet_id}')
            
            # 先尝试获取单个推文，传递完整URL保留用户名信息
            single_tweet = twitter_service.get_tweet(url)
            success(f"[Task {task_id}] Successfully got tweet from @{single_tweet.author_username}")
            update_task_progress(task_id, 'api_success', f'成功获取推文，作者: @{single_tweet.author_username}')
            
            # 检测是否为长文
            is_article = TwitterURLParser.is_article_url(url)
            content_type = 'article' if is_article else 'tweet'
            if is_article:
                info(f"[Task {task_id}] Detected article URL, will scrape full article content")
                update_task_progress(task_id, 'article_detected', '检测到长文链接，将抓取长文内容')

            # 检查是否是推文串的一部分
            if single_tweet.conversation_id != single_tweet.id:
                info(f"[Task {task_id}] Detected thread, getting full conversation...")
                update_task_progress(task_id, 'thread_detected', '检测到推文串，正在获取完整对话...')
                # 这是推文串的一部分，获取完整串
                tweets = twitter_service.get_thread(tweet_id)
                is_thread = True
                success(f"[Task {task_id}] Got {len(tweets)} tweets in thread")
                update_task_progress(task_id, 'thread_complete', f'获取到推文串，共 {len(tweets)} 条推文')
            else:
                tweets = [single_tweet]
                is_thread = False
                info(f"[Task {task_id}] Single tweet, not a thread")
                update_task_progress(task_id, 'single_tweet', '单条推文，非推文串')
                
        except TwitterScrapingError as e:
            error(f"[Task {task_id}] Twitter API Error: {str(e)}")
            if "Rate limit exceeded" in str(e):
                warning(f"[Task {task_id}] Rate limit exceeded, requeueing task...")
                current_time = get_current_time()
                retry_time = current_time.strftime('%H:%M:%S')
                next_retry = (current_time.timestamp() + 60)
                next_retry_str = datetime.fromtimestamp(next_retry).strftime('%H:%M:%S')
                
                update_task_progress(
                    task_id, 
                    'rate_limited', 
                    f'API速率限制，将在 {next_retry_str} 重试',
                    error_message=f'Rate limit exceeded at {retry_time}',
                    retry_time=next_retry_str
                )
                
                # 速率限制，将任务重新放回队列
                conn.execute(
                    'UPDATE tasks SET status = ?, error_message = ? WHERE id = ?',
                    ('pending', f'Rate limit exceeded at {retry_time}, will retry at {next_retry_str}', task_id)
                )
                conn.commit()
                conn.close()
                # 使用定时器延迟重新加入队列，不阻塞当前线程
                info(f"[Task {task_id}] Scheduling retry in 60 seconds...")
                def delayed_requeue():
                    processing_queue.put((task_id, url))
                    info(f"[Task {task_id}] Requeued after rate limit delay")
                
                timer = threading.Timer(60.0, delayed_requeue)
                timer.start()
                return
            else:
                error(f"[Task {task_id}] Non-rate-limit API error: {str(e)}")
                update_task_progress(task_id, 'api_error', f'API调用失败: {str(e)}', error_message=str(e))
                raise e
        
        # 创建保存目录
        save_dir = file_manager.create_save_directory(tweets[0].id, tweets[0].created_at)
        update_task_progress(task_id, 'saving', f'创建保存目录: {save_dir}')
        
        # 统计媒体文件数量
        total_images = sum(len(tweet.get_images()) for tweet in tweets)
        total_videos = sum(len(tweet.get_videos()) for tweet in tweets)
        total_avatars = sum(len(tweet.get_avatars()) for tweet in tweets)
        total_media = total_images + total_videos + total_avatars
        
        if total_media > 0:
            update_task_progress(task_id, 'media_download', f'准备下载 {total_media} 个媒体文件 (图片:{total_images}, 视频:{total_videos}, 头像:{total_avatars})')
        
        # 下载媒体文件
        all_media_files = []
        downloaded_count = 0
        
        for tweet in tweets:
            if tweet.has_media():
                images = tweet.get_images()
                videos = tweet.get_videos()
                avatars = tweet.get_avatars()
                
                if images:
                    update_task_progress(task_id, 'downloading_images', f'正在下载图片 ({len(images)} 个)...')
                    image_files = media_downloader.download_images(images, save_dir)
                    all_media_files.extend(image_files)
                    downloaded_count += len(image_files)
                    update_task_progress(task_id, 'images_done', f'图片下载完成 ({len(image_files)}/{len(images)})')
                
                if videos:
                    update_task_progress(task_id, 'downloading_videos', f'正在下载视频 ({len(videos)} 个)...')
                    video_files = media_downloader.download_videos(videos, save_dir)
                    all_media_files.extend(video_files)
                    downloaded_count += len(video_files)
                    update_task_progress(task_id, 'videos_done', f'视频下载完成 ({len(video_files)}/{len(videos)})')
                
                if avatars:
                    update_task_progress(task_id, 'downloading_avatars', f'正在下载头像 ({len(avatars)} 个)...')
                    avatar_files = media_downloader.download_avatars(avatars, save_dir)
                    all_media_files.extend(avatar_files)
                    downloaded_count += len(avatar_files)
                    update_task_progress(task_id, 'avatars_done', f'头像下载完成 ({len(avatar_files)}/{len(avatars)})')
        
        if total_media > 0:
            update_task_progress(task_id, 'media_complete', f'媒体下载完成: {downloaded_count}/{total_media} 个文件')
        
        # 保存推文内容
        if len(tweets) == 1:
            file_manager.save_tweet_content(tweets[0], save_dir, all_media_files)
        else:
            file_manager.save_thread_content(tweets, save_dir, all_media_files)
        
        # 保存元数据
        file_manager.save_metadata(tweets, save_dir, all_media_files)
        
        # 构建推文文本内容（用于搜索）
        if len(tweets) == 1:
            # 单条推文
            tweet_text = tweets[0].text
        else:
            # 推文串：合并所有推文文本，用双换行分隔
            tweet_text = '\n\n'.join(tweet.text for tweet in tweets)
        
        # 生成唯一的分享slug
        share_slug = generate_unique_slug()
        
        # 更新任务状态为完成
        conn.execute('''
            UPDATE tasks SET 
                status = ?, 
                tweet_id = ?, 
                author_username = ?, 
                author_name = ?, 
                save_path = ?, 
                is_thread = ?, 
                tweet_count = ?, 
                media_count = ?,
                tweet_text = ?,
                share_slug = ?,
                content_type = ?,
                error_message = NULL
            WHERE id = ?
        ''', (
            'completed',
            tweets[0].id,
            tweets[0].author_username,
            tweets[0].author_name,
            save_dir,
            is_thread,
            len(tweets),
            len(all_media_files),
            tweet_text,
            share_slug,
            content_type,
            task_id
        ))
        conn.commit()
        
        info(f"[Task {task_id}] Generated share slug: {share_slug}")


    except Exception as e:
        # 检查是否应该重试
        should_retry = check_and_schedule_retry(conn.cursor(), task_id, str(e))
        if not should_retry:
            # 不重试，更新任务状态为失败
            conn.execute(
                'UPDATE tasks SET status = ?, error_message = ? WHERE id = ?',
                ('failed', str(e), task_id)
            )
        conn.commit()
    
    finally:
        conn.close()

def queue_processor():
    """队列处理器"""
    global is_processing
    
    info("[Queue Processor] Starting queue processor thread...")
    
    while True:
        try:
            # 检查是否有待重试的任务
            check_retry_ready_tasks()
            
            # 检查是否有pending任务需要加入队列（每30秒检查一次）
            import time
            if not hasattr(check_and_queue_pending_tasks, 'last_check'):
                check_and_queue_pending_tasks.last_check = 0
            
            current_time = time.time()
            if current_time - check_and_queue_pending_tasks.last_check > 30:
                check_and_queue_pending_tasks()
                check_and_queue_pending_tasks.last_check = current_time
            
            # 从队列获取任务
            if processing_queue.qsize() > 0:
                info(f"[Queue Processor] Queue has {processing_queue.qsize()} tasks, getting next task...")
            
            task_id, url = processing_queue.get(timeout=5)  # 增加超时时间
            is_processing = True
            
            info(f"[Queue Processor] Got task {task_id}: {url}")
            info(f"[Queue Processor] Starting to process task {task_id}...")
            
            task_success = False
            try:
                process_tweet_task(task_id, url)
                # 检查任务实际状态来确定是否成功
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT status FROM tasks WHERE id = ?', (task_id,))
                result = cursor.fetchone()
                conn.close()
                
                if result and result[0] == 'completed':
                    success(f"[Queue Processor] Successfully processed task {task_id}")
                    task_success = True
                else:
                    warning(f"[Queue Processor] Task {task_id} not completed (status: {result[0] if result else 'unknown'})")
                    
            except Exception as task_error:
                error(f"[Queue Processor] Error processing task {task_id}: {task_error}")
                import traceback
                traceback.print_exc()
                
                # 错误处理现在在process_tweet_task中处理重试逻辑
                warning(f"[Queue Processor] Task {task_id} error handled by process_tweet_task")
            
            processing_queue.task_done()
            is_processing = False
            
            if task_success:
                success(f"[Queue Processor] Completed processing task {task_id}")
            else:
                warning(f"[Queue Processor] Finished processing task {task_id} (may have failed or scheduled for retry)")
            
            # 处理完一个任务后稍作休息
            time.sleep(2)
            
        except queue.Empty:
            is_processing = False
            # 减少日志输出频率 - 只在首次空队列时输出
            continue
        except Exception as e:
            error(f"[Queue Processor] Unexpected error in queue processor: {e}")
            import traceback
            traceback.print_exc()
            is_processing = False
            time.sleep(5)  # 遇到异常时等待5秒再继续

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面和处理"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember_days = request.form.get('remember_days', '1', type=int)

        if not username or not password:
            return render_template('login.html', error='用户名和密码不能为空')

        # 验证用户
        if user_manager.authenticate(username, password):
            # 设置session
            session.permanent = True
            session['logged_in'] = True
            session['username'] = username

            # 设置session有效期
            app.permanent_session_lifetime = timedelta(days=remember_days)

            # 重定向到原页面或主页
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('saved'))
        else:
            return render_template('login.html', error='用户名或密码错误')

    # GET请求，显示登录表单
    return render_template('login.html')

@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """主页 - 重定向到已保存推文页面"""
    return redirect(url_for('saved'))

@app.route('/status')
@login_required
def status_page():
    """状态页面 - 显示系统状态和提交界面"""
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
@login_required
def submit_url():
    """提交URL"""
    url = request.form.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'message': 'URL不能为空'})
    
    if not TwitterURLParser.is_valid_twitter_url(url):
        return jsonify({'success': False, 'message': '无效的Twitter URL'})
    
    # 检查是否已经存在相同的URL
    conn = get_db_connection()
    existing = conn.execute(
        'SELECT id FROM tasks WHERE url = ? AND status != "failed"',
        (url,)
    ).fetchone()
    
    if existing:
        conn.close()
        return jsonify({'success': False, 'message': '该URL已经在处理队列中'})
    
    # 添加到数据库
    cursor = conn.execute(
        'INSERT INTO tasks (url, status) VALUES (?, ?)',
        (url, 'pending')
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # 添加到处理队列
    processing_queue.put((task_id, url))
    info(f"[Submit] Added task {task_id} to queue. Queue size: {processing_queue.qsize()}")
    
    return jsonify({'success': True, 'message': 'URL已添加到处理队列', 'task_id': task_id})

@app.route('/api/status')
def status():
    """获取系统状态"""
    conn = get_db_connection()
    
    # 获取各状态的任务数量
    stats = conn.execute('''
        SELECT status, COUNT(*) as count 
        FROM tasks 
        GROUP BY status
    ''').fetchall()
    
    status_counts = {row['status']: row['count'] for row in stats}
    
    # 获取队列大小 - 统计所有待处理和处理中的任务
    # 这样显示更准确：正在处理的任务也会被计入
    pending_and_processing = conn.execute('''
        SELECT COUNT(*) as count 
        FROM tasks 
        WHERE status IN ('pending', 'processing')
    ''').fetchone()
    queue_size = pending_and_processing['count'] if pending_and_processing else 0
    
    # 获取最近的任务状态
    recent_tasks = conn.execute('''
        SELECT id, url, status, error_message, created_at, processed_at
        FROM tasks 
        ORDER BY created_at DESC 
        LIMIT 5
    ''').fetchall()
    
    recent_tasks_list = []
    for task in recent_tasks:
        task_dict = dict(task)
        if task_dict['created_at']:
            created_time = parse_time_from_db(task_dict['created_at'])
            task_dict['created_at'] = created_time.strftime('%H:%M:%S') if created_time else task_dict['created_at']
        if task_dict['processed_at']:
            processed_time = parse_time_from_db(task_dict['processed_at'])
            task_dict['processed_at'] = processed_time.strftime('%H:%M:%S') if processed_time else task_dict['processed_at']
        recent_tasks_list.append(task_dict)
    
    conn.close()
    
    return jsonify({
        'queue_size': queue_size,
        'is_processing': is_processing,
        'status_counts': status_counts,
        'recent_tasks': recent_tasks_list,
        'processing_thread_alive': processing_thread.is_alive() if processing_thread else False
    })

@app.route('/tasks')
@login_required
def tasks():
    """任务列表页面"""
    return render_template('tasks.html')

@app.route('/api/tasks')
def api_tasks():
    """获取任务列表API"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status', '')
    
    conn = get_db_connection()
    
    # 构建查询
    where_clause = ''
    params = []
    
    if status_filter:
        where_clause = 'WHERE status = ?'
        params.append(status_filter)
    
    # 获取总数
    total_query = f'SELECT COUNT(*) as count FROM tasks {where_clause}'
    total = conn.execute(total_query, params).fetchone()['count']
    
    # 获取分页数据
    offset = (page - 1) * per_page
    tasks_query = f'''
        SELECT * FROM tasks {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    '''
    params.extend([per_page, offset])
    
    tasks = conn.execute(tasks_query, params).fetchall()
    conn.close()
    
    # 转换为字典列表
    tasks_list = []
    for task in tasks:
        task_dict = dict(task)
        # 格式化时间
        if task_dict['created_at']:
            created_time = parse_time_from_db(task_dict['created_at'])
            task_dict['created_at'] = created_time.strftime('%Y-%m-%d %H:%M:%S') if created_time else task_dict['created_at']
        if task_dict['processed_at']:
            processed_time = parse_time_from_db(task_dict['processed_at'])
            task_dict['processed_at'] = processed_time.strftime('%Y-%m-%d %H:%M:%S') if processed_time else task_dict['processed_at']
        tasks_list.append(task_dict)
    
    return jsonify({
        'tasks': tasks_list,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })

@app.route('/saved')
@login_required
def saved():
    """已保存推文列表页面"""
    return render_template('saved.html')


@app.route('/tags')
@login_required
def tags_page():
    """标签管理页面"""
    return render_template('tags.html')

@app.route('/retries')
@login_required
def retries():
    """重试管理页面"""
    return render_template('retries.html')

@app.route('/api/saved')
def api_saved():
    """获取已保存推文列表API，支持搜索功能"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search_query = request.args.get('search', '').strip()
    
    conn = get_db_connection()
    
    # 构建搜索条件
    base_where = "status = 'completed'"
    params = []
    
    if search_query:
        # 搜索推文内容、作者用户名、作者显示名
        search_where = """(
            tweet_text LIKE ? OR 
            author_username LIKE ? OR 
            author_name LIKE ?
        )"""
        where_clause = f"{base_where} AND {search_where}"
        search_param = f'%{search_query}%'
        params = [search_param, search_param, search_param]
    else:
        where_clause = base_where
    
    # 获取已完成的任务
    offset = (page - 1) * per_page
    query = f'''
        SELECT * FROM tasks 
        WHERE {where_clause}
        ORDER BY processed_at DESC
        LIMIT ? OFFSET ?
    '''
    params.extend([per_page, offset])
    tasks = conn.execute(query, params).fetchall()
    
    # 获取总数
    count_params = params[:-2] if search_query else []  # 排除LIMIT和OFFSET参数
    total_query = f"SELECT COUNT(*) as count FROM tasks WHERE {where_clause}"
    total = conn.execute(total_query, count_params).fetchone()['count']
    
    conn.close()
    
    # 转换为字典列表
    saved_list = []
    for task in tasks:
        task_dict = dict(task)
        if task_dict['processed_at']:
            processed_time = parse_time_from_db(task_dict['processed_at'])
            task_dict['processed_at'] = processed_time.strftime('%Y-%m-%d %H:%M:%S') if processed_time else task_dict['processed_at']
        
        # 检查头像文件是否存在
        if task_dict['save_path']:
            # 使用通用函数标准化路径
            raw_path = task_dict['save_path']
            normalized_save_path = normalize_path_cross_platform(raw_path)
            
            # 查找实际存在的目录（处理日期不匹配问题）
            actual_save_path = find_actual_tweet_directory(normalized_save_path)
            
            # 使用实际找到的路径进行文件操作
            avatar_path = os.path.join(actual_save_path, 'avatar.jpg')
            
            if os.path.exists(avatar_path):
                task_dict['has_avatar'] = True
                task_dict['avatar_url'] = f'/media/{task_dict["id"]}/avatar.jpg'
            else:
                task_dict['has_avatar'] = False
                task_dict['avatar_url'] = None
                
            # 检查是否有实际的媒体文件（不包括头像）用于预览
            has_media_preview = False
            
            # 检查是否有视频缩略图
            thumbnails_dir = os.path.join(actual_save_path, 'thumbnails')
            if os.path.exists(thumbnails_dir):
                for filename in os.listdir(thumbnails_dir):
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                        has_media_preview = True
                        break
            
            # 如果没有缩略图，检查是否有图片
            if not has_media_preview:
                images_dir = os.path.join(actual_save_path, 'images')
                if os.path.exists(images_dir):
                    for filename in os.listdir(images_dir):
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                            has_media_preview = True
                            break
            
            # 如果没有图片，检查是否有视频
            if not has_media_preview:
                videos_dir = os.path.join(actual_save_path, 'videos')
                if os.path.exists(videos_dir):
                    for filename in os.listdir(videos_dir):
                        if filename.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
                            has_media_preview = True
                            break
            
            task_dict['has_media_preview'] = has_media_preview
                
            # 读取推文内容用于预览（现在content.txt只包含纯文本）
            content_path = os.path.join(actual_save_path, 'content.txt')
            
            if os.path.exists(content_path):
                try:
                    with open(content_path, 'r', encoding='utf-8') as f:
                        tweet_content = f.read().strip()
                        
                        # 提取前140个字符作为预览
                        if len(tweet_content) > 140:
                            task_dict['preview_text'] = tweet_content[:140] + '...'
                        else:
                            task_dict['preview_text'] = tweet_content
                            
                except Exception as e:
                    task_dict['preview_text'] = f'内容读取失败: {str(e)}'
            else:
                # 添加更详细的错误信息
                task_dict['preview_text'] = f'内容文件不存在: {content_path}'
        else:
            task_dict['has_avatar'] = False
            task_dict['avatar_url'] = None
            task_dict['has_media_preview'] = False
            task_dict['preview_text'] = '保存路径不存在'

        # 获取标签信息
        task_dict['tags'] = tag_generator.get_tags_for_tweet(task_dict['id'])

        saved_list.append(task_dict)

    return jsonify({
        'saved': saved_list,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })



@app.route('/view/<slug>')
def show_tweet(slug):
    """显示推文 - 仅支持随机slug访问 (无需登录，可分享)"""
    # 调试：打印登录状态
    is_logged_in = session.get('logged_in', False)
    print(f"[DEBUG] /view/{slug} - is_logged_in: {is_logged_in}, session: {dict(session)}")

    # 获取任务信息 - 仅通过slug查找，不支持数字ID
    conn = get_db_connection()
    
    task = conn.execute(
        'SELECT * FROM tasks WHERE share_slug = ? AND status = "completed"',
        (slug,)
    ).fetchone()
    
    conn.close()
    
    if not task:
        return "推文未找到", 404
    
    # 获取任务ID用于后续媒体文件访问
    task_id = task['id']
    
    # 扫描媒体文件
    media_files = []
    avatar_file = None
    save_path = task['save_path']
    # 使用通用函数标准化路径
    normalized_save_path = normalize_path_cross_platform(save_path)
    # 查找实际存在的目录
    actual_save_path = find_actual_tweet_directory(normalized_save_path)
    
    
    # 检查头像文件
    avatar_path = os.path.join(actual_save_path, 'avatar.jpg')
    if os.path.exists(avatar_path):
        avatar_file = {
            'filename': 'avatar.jpg',
            'type': 'avatar',
            'url': f'/media/{task_id}/avatar.jpg'
        }
    
    # 扫描images目录
    images_dir = os.path.join(actual_save_path, 'images')
    if os.path.exists(images_dir):
        for filename in os.listdir(images_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                media_files.append({
                    'filename': filename,
                    'type': 'image',
                    'url': f'/media/{task_id}/images/{filename}'
                })
    
    # 扫描videos目录
    videos_dir = os.path.join(actual_save_path, 'videos')
    if os.path.exists(videos_dir):
        for filename in os.listdir(videos_dir):
            if filename.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
                media_files.append({
                    'filename': filename,
                    'type': 'video',
                    'url': f'/media/{task_id}/videos/{filename}'
                })
    
    # 读取推文文本内容
    tweet_text = ""
    content_txt_file = os.path.join(actual_save_path, 'content.txt')
    if os.path.exists(content_txt_file):
        try:
            with open(content_txt_file, 'r', encoding='utf-8') as f:
                tweet_text = f.read().strip()
        except Exception as e:
            print(f"[DEBUG] Failed to read content.txt: {e}")
            tweet_text = ""

    # 读取Reader模式HTML内容
    tweet_html = ""
    content_html_file = os.path.join(actual_save_path, 'content.html')
    if os.path.exists(content_html_file):
        try:
            with open(content_html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
                # 提取HTML文件中的推文内容部分（去掉HTML文档结构）
                import re
                # 提取<div class="reader-content">内的内容
                content_match = re.search(r'<div class="reader-content">(.*?)</div>', html_content, re.DOTALL)
                if content_match:
                    tweet_html = content_match.group(1).strip()
                    print(f"[DEBUG] Successfully loaded Reader mode content, length: {len(tweet_html)}")
                else:
                    # 备用：使用完整的body内容
                    body_match = re.search(r'<body>(.*?)</body>', html_content, re.DOTALL)
                    if body_match:
                        tweet_html = body_match.group(1).strip()
                    else:
                        tweet_html = html_content
                    print(f"[DEBUG] Using fallback HTML content, length: {len(tweet_html)}")
        except Exception as e:
            print(f"[DEBUG] Failed to read HTML file: {e}")
            tweet_html = ""

    # 获取标签
    tags = tag_generator.get_tags_for_tweet(task_id)

    # 构造推文数据
    content_type = 'tweet'
    try:
        content_type = task['content_type'] or 'tweet'
    except (IndexError, KeyError):
        pass

    tweet_data = {
        'id': task['tweet_id'],
        'author_name': task['author_name'],
        'author_username': task['author_username'],
        'url': task['url'],
        'is_thread': task['is_thread'],
        'tweet_count': task['tweet_count'],
        'media_count': len(media_files),
        'processed_at': task['processed_at'],
        'media_files': media_files,
        'avatar_file': avatar_file,
        'text': tweet_text,
        'html_content': tweet_html,
        'tags': tags,
        'content_type': content_type,
        'is_article': content_type == 'article'
    }

    return render_template('tweet_display.html', tweet=tweet_data, task_id=task_id)

@app.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_tweet(task_id):
    """删除已保存的推文"""
    try:
        conn = get_db_connection()
        task = conn.execute(
            'SELECT * FROM tasks WHERE id = ?',
            (task_id,)
        ).fetchone()
        
        if not task:
            conn.close()
            return jsonify({'success': False, 'message': '任务未找到'})
        
        # 删除文件夹
        save_path = task['save_path']
        if save_path:
            # 使用通用函数标准化路径
            normalized_save_path = normalize_path_cross_platform(save_path)
            # 查找实际存在的目录
            actual_save_path = find_actual_tweet_directory(normalized_save_path)
            
            if os.path.exists(actual_save_path):
                import shutil
                shutil.rmtree(actual_save_path)
        
        # 从数据库中删除记录
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '任务已被删除'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})

@app.route('/debug')
@login_required
def debug():
    """调试页面"""
    return render_template('debug.html')

@app.route('/reset_stuck_tasks')
def reset_stuck_tasks():
    """重置卡住的任务"""
    try:
        conn = get_db_connection()
        
        # 获取所有processing任务
        stuck_tasks = conn.execute(
            'SELECT id, url FROM tasks WHERE status = "processing"'
        ).fetchall()
        
        if stuck_tasks:
            print(f"[Reset] Found {len(stuck_tasks)} stuck tasks")
            # 重置为pending
            conn.execute('UPDATE tasks SET status = "pending" WHERE status = "processing"')
            conn.commit()
            
            # 重新加入队列
            for task in stuck_tasks:
                processing_queue.put((task['id'], task['url']))
                print(f"[Reset] Requeued task {task['id']}")
            
            message = f"Reset {len(stuck_tasks)} stuck tasks and requeued them"
        else:
            message = "No stuck tasks found"
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message,
            'queue_size': processing_queue.qsize()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

@app.route('/force_start_queue')
def force_start_queue():
    """强制启动队列处理器"""
    global processing_thread
    
    try:
        print("[Force Start] Force starting queue processor...")
        
        # 检查线程状态
        thread_alive = processing_thread.is_alive() if processing_thread else False
        print(f"[Force Start] Thread alive: {thread_alive}")
        
        # 强制重置所有processing任务为pending
        conn = get_db_connection()
        processing_tasks = conn.execute(
            'SELECT id FROM tasks WHERE status = "processing"'
        ).fetchall()
        
        if processing_tasks:
            print(f"[Force Start] Resetting {len(processing_tasks)} processing tasks to pending...")
            conn.execute('UPDATE tasks SET status = "pending" WHERE status = "processing"')
            conn.commit()
        
        conn.close()
        
        # 重新启动线程（如果需要）
        if not thread_alive:
            print("[Force Start] Starting queue processor thread...")
            start_background_thread()
            
        # 重新加载待处理任务
        print("[Force Start] Reloading pending tasks...")
        load_pending_tasks()
        
        queue_size = processing_queue.qsize()
        print(f"[Force Start] Queue size after reload: {queue_size}")
        
        return jsonify({
            'success': True,
            'message': f'Queue processor restarted. Thread alive: {processing_thread.is_alive() if processing_thread else False}, Queue size: {queue_size}',
            'queue_size': queue_size
        })
    except Exception as e:
        print(f"[Force Start] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

# 全局变量用于跟踪当前处理状态
current_task_status = {
    'task_id': None,
    'status': 'idle',
    'progress': '',
    'start_time': None,
    'last_update': None,
    'retry_time': None,
    'error_message': None
}

def update_task_progress(task_id, status, progress='', error_message=None, retry_time=None):
    """更新任务处理进度"""
    global current_task_status
    current_task_status.update({
        'task_id': task_id,
        'status': status,
        'progress': progress,
        'last_update': get_current_time().strftime('%H:%M:%S'),
        'error_message': error_message,
        'retry_time': retry_time
    })
    if status == 'started':
        current_task_status['start_time'] = get_current_time().strftime('%H:%M:%S')

@app.route('/api/debug')
def api_debug():
    """获取详细的调试信息"""
    conn = get_db_connection()
    
    # 获取所有任务的详细信息
    all_tasks = conn.execute('''
        SELECT * FROM tasks 
        ORDER BY created_at DESC 
        LIMIT 10
    ''').fetchall()
    
    tasks_info = []
    for task in all_tasks:
        task_dict = dict(task)
        if task_dict['created_at']:
            created_time = parse_time_from_db(task_dict['created_at'])
            task_dict['created_at'] = created_time.strftime('%Y-%m-%d %H:%M:%S') if created_time else task_dict['created_at']
        if task_dict['processed_at']:
            processed_time = parse_time_from_db(task_dict['processed_at'])
            task_dict['processed_at'] = processed_time.strftime('%Y-%m-%d %H:%M:%S') if processed_time else task_dict['processed_at']
        tasks_info.append(task_dict)
    
    conn.close()
    
    # 检查服务状态
    services_status = {
        'config_manager': config_manager is not None,
        'twitter_service': twitter_service is not None,
        'media_downloader': media_downloader is not None,
        'file_manager': file_manager is not None,
        'processing_thread_alive': processing_thread.is_alive() if processing_thread else False,
        'processing_thread_exists': processing_thread is not None
    }
    
    # 获取配置信息
    config_info = {}
    if config_manager:
        try:
            config = config_manager.load_config()
            config_info = {
                'scraping_mode': 'Web Scraping (Playwright)',
                'save_path': config.get('save_path'),
                'max_retries': config.get('max_retries'),
                'timeout_seconds': config.get('timeout_seconds'),
                'create_date_folders': config.get('create_date_folders'),
                'use_playwright': config.get('use_playwright'),
                'playwright_headless': config.get('playwright_headless')
            }
        except Exception as e:
            config_info = {'error': str(e)}
    
    return jsonify({
        'queue_size': processing_queue.qsize(),
        'is_processing': is_processing,
        'services_status': services_status,
        'config_info': config_info,
        'recent_tasks': tasks_info,
        'current_time': get_current_time().strftime('%Y-%m-%d %H:%M:%S'),
        'current_task_status': current_task_status
    })

@app.route('/media/<int:task_id>/preview')
def serve_media_preview(task_id):
    """提供媒体预览图（返回第一个媒体文件）"""
    conn = get_db_connection()
    task = conn.execute(
        'SELECT save_path FROM tasks WHERE id = ? AND status = "completed"',
        (task_id,)
    ).fetchone()
    conn.close()
    
    if not task:
        return "任务未找到", 404
    
    save_path = task['save_path']
    # 使用通用函数标准化路径
    normalized_save_path = normalize_path_cross_platform(save_path)
    # 查找实际存在的目录
    actual_save_path = find_actual_tweet_directory(normalized_save_path)
    
    # 查找第一个媒体文件
    # 优先顺序：1) 视频缩略图 2) images目录中的第一个图片 3) videos目录中的第一个视频
    
    # 1. 优先检查视频缩略图
    thumbnails_dir = os.path.join(actual_save_path, 'thumbnails')
    if os.path.exists(thumbnails_dir):
        thumbnail_files = []
        for filename in os.listdir(thumbnails_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                thumbnail_files.append(filename)
        
        if thumbnail_files:
            # 返回第一个缩略图
            first_thumbnail = sorted(thumbnail_files)[0]
            return send_from_directory(thumbnails_dir, first_thumbnail)
    
    # 2. 检查images目录中的图片
    images_dir = os.path.join(actual_save_path, 'images')
    if os.path.exists(images_dir):
        image_files = []
        for filename in os.listdir(images_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                image_files.append(filename)
        
        if image_files:
            # 返回第一个图片
            first_image = sorted(image_files)[0]
            return send_from_directory(images_dir, first_image)
    
    # 3. 如果没有图片和缩略图，返回视频本身（虽然浏览器可能无法预览）
    videos_dir = os.path.join(actual_save_path, 'videos')
    if os.path.exists(videos_dir):
        video_files = []
        for filename in os.listdir(videos_dir):
            if filename.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
                video_files.append(filename)
        
        if video_files:
            # 返回第一个视频文件
            first_video = sorted(video_files)[0]
            return send_from_directory(videos_dir, first_video)
    
    return "无媒体文件", 404

@app.route('/media/<int:task_id>/<path:filename>')
def serve_media(task_id, filename):
    """提供媒体文件"""
    conn = get_db_connection()
    task = conn.execute(
        'SELECT save_path FROM tasks WHERE id = ? AND status = "completed"',
        (task_id,)
    ).fetchone()
    conn.close()
    
    if not task:
        return "任务未找到", 404
    
    save_path = task['save_path']
    # 使用通用函数标准化路径
    normalized_save_path = normalize_path_cross_platform(save_path)
    # 查找实际存在的目录
    actual_save_path = find_actual_tweet_directory(normalized_save_path)
    
    
    # 检查是否为头像文件
    if filename == 'avatar.jpg':
        avatar_path = os.path.join(actual_save_path, 'avatar.jpg')
        if os.path.exists(avatar_path):
            return send_from_directory(actual_save_path, 'avatar.jpg')
    
    # 处理子目录中的文件
    if '/' in filename:
        parts = filename.split('/')
        if len(parts) == 2:
            subdir, actual_filename = parts
            if subdir in ['images', 'videos', 'thumbnails']:
                actual_filename = secure_filename(actual_filename)
                media_dir = os.path.join(actual_save_path, subdir)
                if os.path.exists(os.path.join(media_dir, actual_filename)):
                    return send_from_directory(media_dir, actual_filename)
    
    # 安全检查文件名（用于向后兼容）
    filename = secure_filename(filename)
    
    # 检查文件是否在images、videos或thumbnails目录中
    for subdir in ['images', 'videos', 'thumbnails']:
        media_dir = os.path.join(actual_save_path, subdir)
        if os.path.exists(os.path.join(media_dir, filename)):
            return send_from_directory(media_dir, filename)
    
    return "文件未找到", 404

def task_monitor():
    """任务监控器，定期检查卡住的任务"""
    print("[Task Monitor] Starting task monitor thread...")
    
    while True:
        try:
            time.sleep(300)  # 每5分钟检查一次
            
            conn = get_db_connection()
            
            # 查找处理时间超过10分钟的processing任务
            stuck_tasks = conn.execute('''
                SELECT id, url, processed_at 
                FROM tasks 
                WHERE status = "processing" 
                AND datetime(processed_at) < datetime('now', '-10 minutes')
            ''').fetchall()
            
            if stuck_tasks:
                print(f"[Task Monitor] Found {len(stuck_tasks)} stuck tasks, recovering...")
                
                for task in stuck_tasks:
                    print(f"[Task Monitor] Recovering stuck task {task['id']}")
                    # 重置为pending状态
                    conn.execute(
                        'UPDATE tasks SET status = ?, error_message = ? WHERE id = ?',
                        ('pending', 'Task recovered from stuck state', task['id'])
                    )
                    # 重新加入队列
                    processing_queue.put((task['id'], task['url']))
                
                conn.commit()
                print(f"[Task Monitor] Recovered {len(stuck_tasks)} stuck tasks")
            
            conn.close()
            
        except Exception as e:
            print(f"[Task Monitor] Error in task monitor: {e}")

def start_background_thread():
    """启动后台处理线程"""
    global processing_thread
    if processing_thread is None or not processing_thread.is_alive():
        info("[Main] Starting background processing thread...")
        processing_thread = threading.Thread(target=queue_processor, daemon=True)
        processing_thread.start()
        success(f"[Main] Background thread started: {processing_thread.is_alive()}")
        
        # 启动任务监控线程
        monitor_thread = threading.Thread(target=task_monitor, daemon=True)
        monitor_thread.start()
        success("[Main] Task monitor thread started")

# Flask应用启动时的钩子
@app.before_request
def initialize_app():
    """应用请求前的初始化"""
    if not hasattr(app, '_services_initialized'):
        print("[Flask] First request - initializing services in Flask context...")
        print(f"[Flask] Global variables before init: config_manager={config_manager}, twitter_service={twitter_service}")
        
        result = init_services()
        print(f"[Flask] init_services() returned: {result}")
        print(f"[Flask] Global variables after init: config_manager={config_manager}, twitter_service={twitter_service}")
        
        if not result:
            print("[Flask] Failed to initialize services in Flask context!")
        else:
            print("[Flask] Services initialized successfully in Flask context")
        app._services_initialized = True
    
    if not hasattr(app, '_background_thread_started'):
        print("[Flask] First request - initializing background thread...")
        start_background_thread()
        # 自动检测并修复卡住的任务
        auto_fix_stuck_tasks()
        app._background_thread_started = True

def auto_fix_stuck_tasks():
    """自动修复卡住的任务"""
    try:
        conn = get_db_connection()
        
        # 检查是否有卡住的processing任务
        stuck_tasks = conn.execute(
            'SELECT id, url FROM tasks WHERE status = "processing"'
        ).fetchall()
        
        if stuck_tasks:
            print(f"[Auto Fix] Found {len(stuck_tasks)} stuck tasks, auto-fixing...")
            
            # 重置为pending
            conn.execute('UPDATE tasks SET status = "pending" WHERE status = "processing"')
            conn.commit()
            
            # 重新加入队列
            for task in stuck_tasks:
                processing_queue.put((task['id'], task['url']))
                print(f"[Auto Fix] Requeued task {task['id']}")
            
            print(f"[Auto Fix] Auto-fixed {len(stuck_tasks)} stuck tasks")
        
        conn.close()
        
    except Exception as e:
        print(f"[Auto Fix] Error in auto fix: {e}")

def load_pending_tasks():
    """加载数据库中的待处理任务到队列"""
    conn = get_db_connection()
    
    # 首先，将所有processing状态的任务重置为pending（可能是之前异常退出导致的）
    processing_tasks = conn.execute(
        'SELECT id FROM tasks WHERE status = "processing"'
    ).fetchall()
    
    if processing_tasks:
        print(f"[Startup] Found {len(processing_tasks)} stuck processing tasks, resetting to pending...")
        conn.execute('UPDATE tasks SET status = "pending" WHERE status = "processing"')
        conn.commit()
        print(f"[Startup] Reset {len(processing_tasks)} stuck tasks to pending")
    
    # 加载所有pending任务到队列
    pending_tasks = conn.execute(
        'SELECT id, url FROM tasks WHERE status = "pending" ORDER BY created_at ASC'
    ).fetchall()
    
    for task in pending_tasks:
        processing_queue.put((task['id'], task['url']))
        print(f"[Startup] Loaded pending task {task['id']} into queue")
    
    conn.close()
    
    if pending_tasks:
        print(f"[Startup] Loaded {len(pending_tasks)} pending tasks into queue")
    else:
        print("[Startup] No pending tasks found")

@app.route('/api/retry-tasks')
def api_retry_tasks():
    """获取重试任务列表API"""
    conn = get_db_connection()
    
    # 查询所有有重试记录的任务
    query = """
        SELECT id, url, status, retry_count, max_retries, next_retry_time, 
               error_message, created_at, processed_at, author_username, tweet_id
        FROM tasks 
        WHERE retry_count > 0 
        ORDER BY next_retry_time ASC, created_at DESC
    """
    
    tasks = conn.execute(query).fetchall()
    conn.close()
    
    # 转换为字典列表并添加状态信息
    retry_list = []
    for task in tasks:
        task_dict = dict(task)
        
        # 计算重试状态
        if task_dict['next_retry_time']:
            next_retry = parse_time_from_db(task_dict['next_retry_time'])
            now = get_current_time()
            
            if task_dict['status'] == 'pending' and next_retry <= now:
                task_dict['retry_status'] = 'ready'
                task_dict['retry_status_text'] = '准备重试'
            elif task_dict['status'] == 'pending':
                remaining = next_retry - now
                minutes = int(remaining.total_seconds() / 60)
                task_dict['retry_status'] = 'waiting'
                task_dict['retry_status_text'] = f'{minutes}分钟后重试'
            else:
                task_dict['retry_status'] = task_dict['status']
                task_dict['retry_status_text'] = task_dict['status']
        else:
            task_dict['retry_status'] = task_dict['status']
            task_dict['retry_status_text'] = task_dict['status']
        
        # 格式化时间
        if task_dict['created_at']:
            created_time = parse_time_from_db(task_dict['created_at'])
            task_dict['created_at'] = created_time.strftime('%Y-%m-%d %H:%M:%S') if created_time else task_dict['created_at']
        if task_dict['next_retry_time']:
            retry_time = parse_time_from_db(task_dict['next_retry_time'])
            task_dict['next_retry_time'] = retry_time.strftime('%Y-%m-%d %H:%M:%S') if retry_time else task_dict['next_retry_time']
        
        retry_list.append(task_dict)
    
    return jsonify({
        'retry_tasks': retry_list,
        'total': len(retry_list)
    })

@app.route('/api/retry-now/<int:task_id>', methods=['POST'])
def api_retry_now(task_id):
    """立即重试指定任务"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查任务是否存在且可以重试
        task = cursor.execute(
            'SELECT id, url, retry_count, max_retries, status FROM tasks WHERE id = ?',
            (task_id,)
        ).fetchone()
        
        if not task:
            return jsonify({'success': False, 'message': '任务不存在'})
        
        if task['status'] not in ['pending', 'failed']:
            return jsonify({'success': False, 'message': '任务状态不允许重试'})
        
        retry_count = task['retry_count'] if task['retry_count'] else 0
        max_retries = task['max_retries'] if task['max_retries'] else 3
        
        if retry_count >= max_retries:
            return jsonify({'success': False, 'message': '已达到最大重试次数'})
        
        # 清除重试时间并设置为pending
        cursor.execute("""
            UPDATE tasks SET 
                status = 'pending',
                next_retry_time = NULL,
                error_message = ?
            WHERE id = ?
        """, (f'Manual retry {retry_count + 1}/{max_retries}', task_id))
        
        # 添加到处理队列
        processing_queue.put((task_id, task['url']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '任务已添加到重试队列'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'重试失败: {str(e)}'})

@app.route('/api/reset-retries/<int:task_id>', methods=['POST'])
def api_reset_retries(task_id):
    """重置任务的重试计数"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 首先获取任务URL
        task = cursor.execute(
            'SELECT url FROM tasks WHERE id = ?', (task_id,)
        ).fetchone()
        
        if not task:
            return jsonify({'success': False, 'message': '任务不存在'})
        
        task_url = task['url']
        
        # 重置重试相关字段
        cursor.execute("""
            UPDATE tasks SET 
                retry_count = 0,
                next_retry_time = NULL,
                status = 'pending',
                error_message = 'Retry count reset, ready for new attempt'
            WHERE id = ?
        """, (task_id,))
        
        conn.commit()
        conn.close()
        
        # 将任务加入处理队列
        processing_queue.put((task_id, task_url))
        info(f"[Reset Retries] Task {task_id} reset and added to queue: {task_url}")
        
        return jsonify({'success': True, 'message': '重试计数已重置，任务已重新加入队列'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'重置失败: {str(e)}'})

@app.route('/api/delete-retry-task/<int:task_id>', methods=['POST'])
def api_delete_retry_task(task_id):
    """删除重试任务"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 首先获取任务信息
        task = cursor.execute(
            'SELECT url, status, retry_count FROM tasks WHERE id = ?', (task_id,)
        ).fetchone()
        
        if not task:
            return jsonify({'success': False, 'message': '任务不存在'})
        
        task_url = task['url']
        task_status = task['status']
        retry_count = task['retry_count']
        
        # 删除任务记录
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        
        conn.commit()
        conn.close()
        
        info(f"[Delete Retry Task] Task {task_id} deleted: {task_url} (status: {task_status}, retries: {retry_count})")
        
        return jsonify({'success': True, 'message': '重试任务已删除'})
        
    except Exception as e:
        error(f"[Delete Retry Task] Failed to delete task {task_id}: {str(e)}")
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})

@app.route('/api/submit', methods=['POST'])
def api_submit():
    """API方式提交推文URL进行下载
    
    支持的请求格式:
    1. JSON: {"url": "https://twitter.com/user/status/123456"}
    2. Form: url=https://twitter.com/user/status/123456
    3. Text: 直接在body中放置URL
    """
    try:
        # 尝试多种方式获取URL
        url = None
        
        # 方式1: JSON格式
        if request.is_json:
            data = request.get_json()
            url = data.get('url') if data else None
        
        # 方式2: Form格式
        if not url and request.form:
            url = request.form.get('url')
        
        # 方式3: 纯文本格式
        if not url and request.data:
            text_data = request.data.decode('utf-8').strip()
            # 检查是否是有效的Twitter URL
            if TwitterURLParser.is_valid_twitter_url(text_data):
                url = text_data
        
        # 方式4: URL参数
        if not url:
            url = request.args.get('url')
        
        if not url:
            return jsonify({
                'success': False,
                'error': 'URL is required',
                'message': '请提供Twitter URL',
                'supported_formats': [
                    'JSON: {"url": "https://twitter.com/user/status/123456"}',
                    'Form: url=https://twitter.com/user/status/123456',
                    'Text: 直接在body中放置URL',
                    'Query: ?url=https://twitter.com/user/status/123456'
                ]
            }), 400
        
        # 验证URL格式
        if not TwitterURLParser.is_valid_twitter_url(url):
            return jsonify({
                'success': False,
                'error': 'Invalid Twitter URL',
                'message': f'无效的Twitter URL: {url}',
                'url': url
            }), 400
        
        # 检查URL是否已存在
        conn = get_db_connection()
        existing_task = conn.execute(
            'SELECT id, status FROM tasks WHERE url = ?', (url,)
        ).fetchone()
        
        if existing_task:
            task_id = existing_task['id']
            status = existing_task['status']
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'任务已存在 (状态: {status})',
                'task_id': task_id,
                'url': url,
                'status': status,
                'duplicate': True
            }), 200
        
        # 创建新任务
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO tasks (url, status, created_at) VALUES (?, ?, ?)',
            (url, 'pending', format_time_for_db(get_current_time()))
        )
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 添加到处理队列
        processing_queue.put((task_id, url))
        info(f"[API Submit] Added task {task_id} to queue. Queue size: {processing_queue.qsize()}")
        
        return jsonify({
            'success': True,
            'message': '任务已添加到队列',
            'task_id': task_id,
            'url': url,
            'status': 'pending',
            'queue_size': processing_queue.qsize()
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/status/<int:task_id>')
def api_task_status(task_id):
    """获取任务状态"""
    try:
        conn = get_db_connection()
        task = conn.execute(
            'SELECT * FROM tasks WHERE id = ?', (task_id,)
        ).fetchone()
        conn.close()
        
        if not task:
            return jsonify({
                'success': False,
                'error': 'Task not found',
                'message': '任务不存在'
            }), 404
        
        task_data = dict(task)
        
        # 格式化时间
        if task_data['created_at']:
            created_time = parse_time_from_db(task_data['created_at'])
            task_data['created_at'] = created_time.strftime('%Y-%m-%d %H:%M:%S') if created_time else task_data['created_at']
        if task_data['processed_at']:
            processed_time = parse_time_from_db(task_data['processed_at'])
            task_data['processed_at'] = processed_time.strftime('%Y-%m-%d %H:%M:%S') if processed_time else task_data['processed_at']
        if task_data['next_retry_time']:
            retry_time = parse_time_from_db(task_data['next_retry_time'])
            task_data['next_retry_time'] = retry_time.strftime('%Y-%m-%d %H:%M:%S') if retry_time else task_data['next_retry_time']
        
        return jsonify({
            'success': True,
            'task': task_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/logs/stream')
def stream_logs():
    """实时日志流 - Server-Sent Events"""
    def generate():
        # 发送已有的日志
        with log_lock:
            for log_entry in log_buffer:
                yield f"data: {log_entry}\n\n"
        
        # 实时推送新日志
        last_count = len(log_buffer)
        while True:
            try:
                with log_lock:
                    current_count = len(log_buffer)
                    if current_count > last_count:
                        # 发送新增的日志
                        new_logs = list(log_buffer)[last_count:]
                        for log_entry in new_logs:
                            yield f"data: {log_entry}\n\n"
                        last_count = current_count
                
                time.sleep(0.5)  # 每0.5秒检查一次新日志
            except GeneratorExit:
                break
            except Exception as e:
                yield f"data: [ERROR] 日志流错误: {str(e)}\n\n"
                break
    
    return Response(generate(), mimetype='text/plain', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*'
    })

@app.route('/api/logs/recent')
def get_recent_logs():
    """获取最近的日志（用于初始化）"""
    with log_lock:
        logs = list(log_buffer)
    return jsonify({
        'success': True,
        'logs': logs
    })

@app.route('/api/logs/test')
def test_logs():
    """测试日志捕获系统"""
    from utils.realtime_logger import info, error, warning, success
    
    info("[TEST] This is a test log message from /api/logs/test endpoint")
    error("[TEST] Testing log capture system - ERROR test")
    warning("[TEST] Warning message test")
    info("[TEST] Multiple line test")
    info("[TEST] 中文测试日志")
    success("[TEST] Test completed successfully")
    
    with log_lock:
        buffer_size = len(log_buffer)
        latest_logs = list(log_buffer)[-5:] if log_buffer else []
    
    return jsonify({
        'success': True,
        'message': 'Test logs generated',
        'buffer_size': buffer_size,
        'latest_logs': latest_logs
    })


# ==================== 标签系统 API ====================

from services.tag_generator import TagGenerator

tag_generator = TagGenerator()

@app.route('/api/tags/all')
def api_get_all_tags():
    """获取所有标签及使用统计"""
    try:
        conn = get_db_connection()

        # 查询所有标签及其使用次数
        query = '''
            SELECT
                t.id,
                t.name,
                t.emoji,
                t.color,
                t.usage_count,
                t.is_auto_generated,
                COUNT(DISTINCT tt.task_id) as tweet_count
            FROM tags t
            LEFT JOIN tweet_tags tt ON t.id = tt.tag_id
            LEFT JOIN tasks tk ON tt.task_id = tk.id AND tk.status = 'completed'
            GROUP BY t.id
            ORDER BY tweet_count DESC, t.name ASC
        '''

        tags = conn.execute(query).fetchall()
        conn.close()

        # 转换为字典列表
        tags_list = []
        for tag in tags:
            tags_list.append({
                'id': tag['id'],
                'name': tag['name'],
                'emoji': tag['emoji'],
                'color': tag['color'],
                'usage_count': tag['usage_count'],
                'tweet_count': tag['tweet_count'],
                'is_auto_generated': bool(tag['is_auto_generated'])
            })

        return jsonify({
            'success': True,
            'tags': tags_list,
            'total': len(tags_list)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tags/generate/<int:task_id>', methods=['POST'])
@login_required
def api_generate_tags(task_id):
    """为指定推文生成标签"""
    try:
        # 获取推文内容
        conn = get_db_connection()
        task = conn.execute('SELECT tweet_text, author_username FROM tasks WHERE id = ?', (task_id,)).fetchone()
        conn.close()

        if not task:
            return jsonify({'success': False, 'error': '推文不存在'}), 404

        tweet_text = task['tweet_text']
        author_username = task['author_username']

        # 获取请求参数
        data = request.get_json() or {}
        method = data.get('method', 'rule_based')  # 'rule_based', 'gemini_api', or 'claude_api'
        api_key = data.get('api_key', None)

        # 如果没有提供API密钥，尝试从config.ini获取
        if not api_key and method == 'gemini_api':
            from services.config_manager import ConfigManager
            config = ConfigManager()
            api_key = config.get_gemini_api_key()

        # 生成标签
        if method == 'gemini_api' and api_key:
            tags = tag_generator.generate_tags_gemini_api(tweet_text, api_key)
        elif method == 'claude_api' and api_key:
            tags = tag_generator.generate_tags_claude_api(tweet_text, api_key)
        else:
            tags = tag_generator.generate_tags_rule_based(tweet_text, author_username)

        if not tags:
            return jsonify({
                'success': True,
                'message': '未匹配到合适的标签',
                'tags': []
            })

        # 应用标签
        tag_generator.apply_tags_to_tweet(task_id, tags, method)

        # 返回生成的标签
        applied_tags = tag_generator.get_tags_for_tweet(task_id)

        return jsonify({
            'success': True,
            'message': f'成功生成 {len(applied_tags)} 个标签',
            'tags': applied_tags
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tags/tweet/<int:task_id>')
def api_get_tweet_tags(task_id):
    """获取推文的所有标签"""
    try:
        tags = tag_generator.get_tags_for_tweet(task_id)
        return jsonify({
            'success': True,
            'tags': tags
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tags/add', methods=['POST'])
@login_required
def api_add_tag_to_tweet():
    """手动添加标签到推文"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        tag_name = data.get('tag_name')

        if not task_id or not tag_name:
            return jsonify({'success': False, 'error': '缺少参数'}), 400

        # 添加标签
        tag_generator.apply_tags_to_tweet(task_id, [(tag_name, 1.0)], 'manual')

        return jsonify({
            'success': True,
            'message': f'标签 "{tag_name}" 已添加'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tags/remove', methods=['POST'])
@login_required
def api_remove_tag_from_tweet():
    """从推文移除标签"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        tag_id = data.get('tag_id')

        if not task_id or not tag_id:
            return jsonify({'success': False, 'error': '缺少参数'}), 400

        tag_generator.remove_tag_from_tweet(task_id, tag_id)

        return jsonify({
            'success': True,
            'message': '标签已移除'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/saved/by-tag')
def api_saved_by_tag():
    """按标签筛选已保存推文"""
    tag_name = request.args.get('tag', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    if not tag_name:
        return jsonify({'success': False, 'error': '未指定标签'}), 400

    conn = get_db_connection()

    # 先查找标签ID
    tag_result = conn.execute('SELECT id FROM tags WHERE name = ?', (tag_name,)).fetchone()
    if not tag_result:
        conn.close()
        return jsonify({
            'saved': [],
            'total': 0,
            'page': page,
            'per_page': per_page,
            'pages': 0
        })

    tag_id = tag_result['id']
    offset = (page - 1) * per_page

    # 查询包含指定标签的推文
    query = '''
        SELECT DISTINCT t.* FROM tasks t
        JOIN tweet_tags tt ON t.id = tt.task_id
        WHERE tt.tag_id = ?
        AND t.status = 'completed'
        ORDER BY t.processed_at DESC
        LIMIT ? OFFSET ?
    '''

    tasks = conn.execute(query, [tag_id, per_page, offset]).fetchall()

    # 获取总数
    count_query = '''
        SELECT COUNT(DISTINCT t.id) as count FROM tasks t
        JOIN tweet_tags tt ON t.id = tt.task_id
        WHERE tt.tag_id = ?
        AND t.status = 'completed'
    '''
    total = conn.execute(count_query, [tag_id]).fetchone()['count']

    # 转换为字典列表（复用 api_saved 的处理逻辑）
    saved_list = []
    for task in tasks:
        task_dict = dict(task)
        if task_dict['processed_at']:
            processed_time = parse_time_from_db(task_dict['processed_at'])
            task_dict['processed_at'] = processed_time.strftime('%Y-%m-%d %H:%M:%S') if processed_time else task_dict['processed_at']

        # 检查头像文件是否存在
        if task_dict['save_path']:
            raw_path = task_dict['save_path']
            normalized_save_path = normalize_path_cross_platform(raw_path)
            actual_save_path = find_actual_tweet_directory(normalized_save_path)
            avatar_path = os.path.join(actual_save_path, 'avatar.jpg')

            if os.path.exists(avatar_path):
                task_dict['has_avatar'] = True
                task_dict['avatar_url'] = f'/media/{task_dict["id"]}/avatar.jpg'
            else:
                task_dict['has_avatar'] = False
                task_dict['avatar_url'] = None

            # 检查是否有实际的媒体文件用于预览
            has_media_preview = False
            thumbnails_dir = os.path.join(actual_save_path, 'thumbnails')
            if os.path.exists(thumbnails_dir):
                for filename in os.listdir(thumbnails_dir):
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                        has_media_preview = True
                        break

            if not has_media_preview:
                images_dir = os.path.join(actual_save_path, 'images')
                if os.path.exists(images_dir):
                    for filename in os.listdir(images_dir):
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                            has_media_preview = True
                            break

            if not has_media_preview:
                videos_dir = os.path.join(actual_save_path, 'videos')
                if os.path.exists(videos_dir):
                    for filename in os.listdir(videos_dir):
                        if filename.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
                            has_media_preview = True
                            break

            task_dict['has_media_preview'] = has_media_preview

            # 读取推文内容用于预览
            content_path = os.path.join(actual_save_path, 'content.txt')
            if os.path.exists(content_path):
                try:
                    with open(content_path, 'r', encoding='utf-8') as f:
                        tweet_content = f.read().strip()
                        if len(tweet_content) > 140:
                            task_dict['preview_text'] = tweet_content[:140] + '...'
                        else:
                            task_dict['preview_text'] = tweet_content
                except Exception as e:
                    task_dict['preview_text'] = f'内容读取失败: {str(e)}'
            else:
                task_dict['preview_text'] = f'内容文件不存在: {content_path}'
        else:
            task_dict['has_avatar'] = False
            task_dict['avatar_url'] = None
            task_dict['has_media_preview'] = False
            task_dict['preview_text'] = '保存路径不存在'

        # 获取标签信息
        task_dict['tags'] = tag_generator.get_tags_for_tweet(task_dict['id'])

        saved_list.append(task_dict)

    conn.close()

    return jsonify({
        'saved': saved_list,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })


if __name__ == '__main__':
    # 初始化数据库
    init_db()
    
    # 初始化服务
    if not init_services():
        print("Failed to initialize services. Please check your configuration.")
        exit(1)
    
    # 启动队列处理线程
    start_background_thread()
    
    # 加载待处理任务
    load_pending_tasks()
    
    print("Twitter Saver Web App starting...")
    print("Access the application at: http://localhost:6201")

    app.run(debug=False, host='0.0.0.0', port=6201)