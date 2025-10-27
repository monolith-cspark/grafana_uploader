import os

def normalize_path_for_grafana(absolute_path: str) -> str:
    """
    Windows 절대 경로의 역슬래시(\\)를 Grafana/Linux 표준인 포워드 슬래시(/)로 변환
    """
    if not absolute_path:
        return ""
        
    # 역슬래시를 포워드 슬래시로 변환
    normalized_path = absolute_path.replace('\\', '/')
    
    return normalized_path    