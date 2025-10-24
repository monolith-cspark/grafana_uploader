# config_manager.py
import configparser
import os

class ConfigManager:
    def __init__(self, ini_path='config.ini'):
        self.config = configparser.ConfigParser()
        if not os.path.exists(ini_path):
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {ini_path}")
        self.config.read(ini_path, encoding='utf-8')

    def get(self, key, section='DEFAULT', fallback=None):
        return self.config[section].get(key, fallback)
    
    def reload(self, ini_path='config.ini'):
        """ini 파일 다시 읽기"""
        self.config.read(ini_path, encoding='utf-8')
