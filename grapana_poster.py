import json
import requests

class GrafanaPoster:
    """Grafana API를 통해 대시보드를 POST하는 클래스"""
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.dashboard_endpoint = f"{self.base_url}/api/dashboards/db"

    def post_dashboard(self, file_path, uid_placeholder, target_uid):
        """
        JSON 파일을 읽고 UID를 교체한 후 Grafana에 POST 요청을 보냅니다.
        """
        try:
            # 1. JSON 파일 읽기
            with open(file_path, 'r') as f:
                content = f.read()

            # 2. 올바른 UID로 교체
            content = content.replace(uid_placeholder, target_uid)

            # 3. JSON 파싱
            dashboard_data = json.loads(content)

            # 4. API 요청
            response = requests.post(
                self.dashboard_endpoint,
                headers=self.headers,
                json=dashboard_data,
                timeout=10 # 타임아웃 설정
            )
            
            # 응답 처리
            response_json = response.json()
            
            # 성공/실패 여부 출력
            if response.status_code == 200:
                result_message = f"POST Success\n"
                result_message += f"대시보드 UID: {response_json.get('uid')}\n"
                result_message += f"버전: {response_json.get('version')}"
            else:
                result_message = f"POST Failed (HTTP {response.status_code})\n"
                result_message += f"Error: {response_json.get('message', '알 수 없는 에러')}"

            return result_message, dashboard_data

        except FileNotFoundError:
            return f"Error: 대시보드 파일 경로를 찾을 수 없습니다: {file_path}", None
        except json.JSONDecodeError:
            return f"Error: JSON 파일 파싱에 실패했습니다. 파일 형식을 확인하세요.", None
        except requests.exceptions.RequestException as e:
            return f"Error: API 요청 중 에러 발생: {e}", None
        except Exception as e:
            return f"Error: 알 수 없는 오류 발생: {e}", None

