import os
import configparser
from typing import Dict, Any, Optional


class ConfigManager:
    """Configuration manager for handling config files"""

    def __init__(self, config_file: str = "config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config_file()
    
    def _load_config_file(self):
        """Load configuration file"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file, encoding='utf-8')
        else:
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration file"""
        self.config['storage'] = {
            'base_path': '/mnt/nas/saved_tweets',
            'create_date_folders': 'true'
        }
        self.config['download'] = {
            'max_retries': '3',
            'timeout_seconds': '30'
        }
        self.config['scraper'] = {
            'use_playwright': 'true',
            'headless': 'true',
            'debug_mode': 'false'
        }
        self.config['ai'] = {
            'gemini_api_key': ''
        }

        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_save_path(self) -> str:
        """Get save path"""
        return self.config.get('storage', 'base_path', fallback='/mnt/nas/saved_tweets')
    
    def get_create_date_folders(self) -> bool:
        """Whether to create date folders"""
        return self.config.getboolean('storage', 'create_date_folders', fallback=True)
    
    def get_max_retries(self) -> int:
        """Get maximum retry attempts"""
        return self.config.getint('download', 'max_retries', fallback=3)
    
    def get_timeout_seconds(self) -> int:
        """Get timeout (seconds)"""
        return self.config.getint('download', 'timeout_seconds', fallback=30)
    
    def get_use_playwright(self) -> bool:
        """Get whether to use Playwright"""
        return self.config.getboolean('scraper', 'use_playwright', fallback=True)
    
    def get_playwright_headless(self) -> bool:
        """Get whether Playwright uses headless mode"""
        return self.config.getboolean('scraper', 'headless', fallback=True)
    
    def get_playwright_debug(self) -> bool:
        """Get whether Playwright enables debug mode"""
        return self.config.getboolean('scraper', 'debug_mode', fallback=False)

    def get_gemini_api_key(self) -> Optional[str]:
        """Get Gemini API key"""
        api_key = self.config.get('ai', 'gemini_api_key', fallback='')
        return api_key if api_key else None

    def load_config(self) -> Dict[str, Any]:
        """Load all configuration and return dictionary"""
        return {
            'save_path': self.get_save_path(),
            'create_date_folders': self.get_create_date_folders(),
            'max_retries': self.get_max_retries(),
            'timeout_seconds': self.get_timeout_seconds(),
            'use_playwright': self.get_use_playwright(),
            'playwright_headless': self.get_playwright_headless(),
            'playwright_debug': self.get_playwright_debug()
        }
    
    def validate_config(self) -> bool:
        """Validate if configuration is valid"""
        try:
            # Check if save path is writable
            save_path = self.get_save_path()
            os.makedirs(save_path, exist_ok=True)
            test_file = os.path.join(save_path, '.test_write')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except (OSError, IOError) as e:
                raise ValueError(f"Cannot write to save path {save_path}: {e}")

            print(f"[Config] Using web scraping mode (Playwright browser automation)")

            return True
        except ValueError as e:
            print(f"Configuration error: {e}")
            return False