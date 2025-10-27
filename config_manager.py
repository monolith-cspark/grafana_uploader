# config_manager.py
import configparser
import os
from typing import Tuple, Optional

class ConfigManager:
    def __init__(self, ini_path='config.ini'):
        self.config = configparser.ConfigParser()
        self.ini_path=ini_path
        if not os.path.exists(ini_path):
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {ini_path}")
        self.config.read(ini_path, encoding='utf-8')

    def get(self, key, section='DEFAULT', fallback=None):
        return self.config[section].get(key, fallback)
    
    def set(self, key: str, value, section: str = 'DEFAULT') -> Tuple[bool, Optional[str]]:
            """
            설정 객체에 값을 설정하고 디스크에 저장합니다.
            성공 시 (True, None), 실패 시 (False, 에러 메시지)를 반환합니다.
            """
            if section not in self.config:
                self.config.add_section(section)
            
            # 값을 문자열로 변환하여 메모리(self.config)에 반영
            self.config.set(section, key, str(value))
            
            # 디스크에 저장하고 결과를 반환
            return self._save_config()
            
    def _save_config(self) -> Tuple[bool, Optional[str]]:
        """
        메모리상의 변경 사항을 디스크의 설정 파일에 저장(쓰기)합니다.
        성공 시 (True, None), 실패 시 (False, 에러 메시지)를 반환합니다.
        """
        try:
            with open(self.ini_path, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)
            
            # 성공 시 (True, None) 반환
            return True, None
            
        except Exception as e:
            error_message = f"설정 파일 저장 중 오류 발생: {e}"
            print(f"{error_message}") 
            
            # 실패 시 (False, 에러 메시지) 반환
            return False, error_message
    
    def reload(self, ini_path='config.ini'):
        """ini 파일 다시 읽기"""
        self.config.read(ini_path, encoding='utf-8')
