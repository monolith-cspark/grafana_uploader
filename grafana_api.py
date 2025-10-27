import json
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple

def to_utc_iso8601(time_str: str) -> str:
    """
    'YYYY-MM-DD HH:MM:SS.sss' → UTC ISO 8601 문자열
    밀리초까지 포함
    """
    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")
    dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat(timespec='milliseconds').replace("+00:00", "Z")


def to_korea_iso8601(time_str: str) -> str:
    """
    'YYYY-MM-DD HH:MM:SS.sss' → 한국 시간 ISO 8601 문자열
    """
    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")
    # 시간대 정보를 한국 시간으로 설정
    korea_tz = timezone(timedelta(hours=9))
    dt = dt.replace(tzinfo=korea_tz)
    return dt.isoformat(timespec='milliseconds')


class GrafanaAPI:
    """Grafana API"""
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.dashboard_endpoint = f"{self.base_url}/api/dashboards/db"
        self.search_endpoint = f"{self.base_url}/api/search"
        self.delete_endpoint = f"{self.base_url}/api/dashboards/uid"
        self.datasource_endpoint = f"{self.base_url}/api/datasources"


    def check_connection(self) -> tuple[bool, str]:
        """
        Grafana 서버와의 연결 및 API Key의 유효성을 확인합니다.
        성공 시 (True, 메시지), 실패 시 (False, 상세 오류 메시지)를 반환합니다.
        """
        user_endpoint = f"{self.base_url}/api/user"
        
        try:
            # GET 요청을 보내 연결 상태와 인증 유효성을 동시에 확인
            response = requests.get(user_endpoint, headers=self.headers, timeout=10)
            
            # HTTP 200 (OK) 코드는 연결 성공 및 유효한 인증을 의미합니다.
            if response.status_code == 200:
                # 응답에 사용자 정보가 포함되어 있다면 인증 성공
                return True, "Grafana 서버 연결 성공 및 API Key 인증 유효."
            
            elif response.status_code == 401:
                # 401 Unauthorized는 API Key가 유효하지 않거나 권한이 없음을 의미
                error_msg = "인증 실패: API Key가 유효하지 않거나 접근 권한이 부족합니다. (HTTP 401)"
                return False, error_msg
                
            elif response.status_code == 404:
                # 404 Not Found는 API URL이 잘못되었거나 엔드포인트를 찾을 수 없음을 의미
                error_msg = f"연결 실패: API URL이 잘못되었거나 Grafana 인스턴스가 응답하지 않습니다. (HTTP 404)"
                return False, error_msg
                
            else:
                # 기타 오류 처리
                response.raise_for_status() # 4xx 또는 5xx 오류 시 Exception 발생
                error_msg = f"기타 HTTP 오류 발생: {response.status_code} - {response.reason}"
                return False, error_msg
            
        except requests.exceptions.Timeout:
            return False, "연결 시간 초과: Grafana 서버가 지정된 시간(10초) 내에 응답하지 않았습니다."
            
        except requests.exceptions.ConnectionError:
            return False, "연결 오류: Grafana 서버에 연결할 수 없습니다. URL 또는 네트워크 상태를 확인하세요."
            
        except requests.exceptions.RequestException as e:
            # 위에서 잡지 못한 모든 requests 관련 오류
            return False, f"일반 요청 오류 발생: {e}"

    # GrafanaPoster 클래스 내부에 구현되어야 할 함수 예시
    def create_csv_datasource(self, name, csv_path):
        """
        marcusolsson-csv-datasource 타입의 데이터 소스를 생성하고 성공 시 UID를 반환합니다.
        Storage Location을 'Local'로 설정하고, 'Path'에 CSV 경로를 입력합니다.
        """
        url = f"{self.base_url}/api/datasources"
        
        payload = {
            "name": name,
            "type": "marcusolsson-csv-datasource", 
            "access": "proxy", 
            "url": csv_path,    # url에도 csv 경로를 넣어줘야 동작
            "isDefault": False, 
            "jsonData": {
                "storage": "local",  
                "pdcInjected" : False,
                #"path": csv_path,        # csv 경로
                #"maxLines": 1000000,
                "delimiter": ","
            }
        }
 
        try:
            response = requests.post(url, headers=self.headers, data=json.dumps(payload))
            response.raise_for_status()
            
            # 성공 시 응답에는 ID와 UID가 포함됩니다.
            ds_data = response.json()
            print(f"데이터 소스 생성 성공: UID={ds_data.get('datasource', {}).get('uid', 'N/A')}")
            return ds_data.get('datasource', {}).get('uid')
            
        except requests.exceptions.RequestException as e:
            # 실패 시 응답 내용도 함께 출력하여 디버깅에 도움
            error_detail = response.text if 'response' in locals() else str(e)
            print(f"데이터 소스 생성 실패: {error_detail}")
            # self.last_response = response # 디버깅을 위해 저장
            return None

    def get_all_datasources(self):
        """모든 데이터 소스 목록 조회 (ID와 NAME 포함)"""
        url = f"{self.base_url}/api/datasources"
        # GET http://localhost:3000/api/datasources
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"데이터 소스 목록 조회 실패: {e}")
            return []

    def get_datasource_details(self, ds_id):
        """특정 데이터 소스의 상세 설정(JSON) 조회"""
        url = f"{self.base_url}/api/datasources/{ds_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # 401, 403 에러 등 민감한 정보는 숨김 처리
            print(f"데이터 소스 ID {ds_id}의 상세 조회 실패 (Status: {response.status_code if 'response' in locals() else 'N/A'})")
            return None


    def find_datasource_by_csv_path(self, csv_file_path):
        """
        주어진 CSV 경로와 일치하는 데이터 소스(UID)를 찾습니다.
        marcusolsson-csv-datasource 플러그인
        """
        print(f"CSV 경로로 데이터 소스 검색 중: '{csv_file_path}'")
        
        all_datasources = self.get_all_datasources()
        
        if not all_datasources:
            print("조회된 데이터 소스가 없습니다.")
            return None

        for ds_summary in all_datasources:
            ds_id = ds_summary.get('id')
            ds_uid = ds_summary.get('uid')
            ds_name = ds_summary.get('name')
            ds_type = ds_summary.get('type') # 플러그인 타입 (예: 'marcusolsson-csv-datasource')

            # CSV 데이터 소스 플러그인만 필터링 (선택 사항)
            # if ds_type != "marcusolsson-csv-datasource": 
            #     continue 

            ds_details = self.get_datasource_details(ds_id)
            
            if ds_details is None:
                continue

            # 여기서 'path' 키에 CSV 경로
            config_path = ds_details.get('jsonData', {}).get('path')
            
            if config_path and config_path == csv_file_path:
                print(f"일치하는 데이터 소스 발견! 이름: {ds_name}, UID: {ds_uid}, 경로: {config_path}")
                return ds_uid # 일치하는 데이터 소스의 UID 반환

        print(f"주어진 CSV 경로 '{csv_file_path}'에 해당하는 데이터 소스를 찾을 수 없습니다.")
        return None


    def get_all_dashboards(self):
        """모든 대시보드 목록 조회"""
        url = f"{self.base_url}/api/search"
        params = {
            'query': '',
            'type': 'dash-db'
        }
        
        try:
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"대시보드 목록 조회 실패: {e}")
            return []

    def find_dashboard_by_title(self, title):
        """제목으로 대시보드 찾기"""
        print(f"대시보드 검색 중: '{title}'")
        
        # 1. 전체 목록에서 필터링
        all_dashboards = self.get_all_dashboards()
        
        for dashboard in all_dashboards:
            if dashboard['title'] == title:
                print(f"{title} 제목의 대시보드 발견: UID={dashboard['uid']}")
                return dashboard['uid']
        
        # 못 찾은 경우 검색 쿼리 사용
        url = f"{self.base_url}/api/search"
        params = {
            'query': title,
            'type': 'dash-db'
        }
        
        try:
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            dashboards = response.json()
            
            for dashboard in dashboards:
                if dashboard['title'] == title:
                    print(f"{title} 제목의 대시보드 발견: UID={dashboard['uid']}")
                    return dashboard['uid']
            
            print(f"대시보드를 찾을 수 없음: '{title}'")
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"검색 실패: {e}")
            return None

    def delete_dashboard(self, uid: str) -> bool:
        """
        UID로 대시보드를 삭제합니다.
        """
        try:
            response = requests.delete(
                f"{self.delete_endpoint}/{uid}",
                headers=self.headers,
                timeout=10
            )
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"Error during delete API request: {e}")
            return False

    def _get_items_for_deletion(self, search_url: str, item_type: str) -> List[Dict[str, Any]]:
        """
        삭제할 항목(대시보드 또는 데이터 소스)의 목록을 가져옵니다.
        """
        print(f"[{item_type}] 목록을 가져오는 중...")
        try:
            response = requests.get(
                search_url,
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting {item_type} list. Status: {response.status_code}, Response: {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"Error during GET API request for {item_type}: {e}")
            return []

    def delete_all_dashboards(self) -> Tuple[bool, List[str]]:
        """
        Grafana에 있는 모든 대시보드를 삭제합니다. (bool, List[str]) 반환
        - bool: 전체 작업 성공 여부
        - List[str]: 작업 로그 메시지 리스트
        """
        messages: List[str] = []
        
        search_url = f"{self.search_endpoint}?type=dash-db"
        dashboards = self._get_items_for_deletion(search_url, "Dashboard")
        
        if not dashboards:
            messages.append("삭제할 대시보드가 없습니다. (작업 성공)")
            return True, messages
        
        messages.append(f"총 {len(dashboards)}개의 대시보드 삭제를 시작합니다.")
        
        success_count = 0
        fail_count = 0
        
        for db in dashboards:
            # 대시보드 검색 API 결과는 UID 필드를 가집니다.
            uid = db.get('uid')
            title = db.get('title')
            
            log_msg = f"  -> 대시보드 삭제 중: Title='{title}', UID='{uid}'"
            
            if not uid:
                msg = f"경고: Title '{title}'의 UID가 없어 건너뜁니다."
                messages.append(msg)
                fail_count += 1
                continue
                
            
            # self.delete_endpoint는 대시보드 삭제 API의 기본 URL이어야 합니다.
            if self.delete_dashboard(uid): 
                messages.append(f"{log_msg} Success")
                success_count += 1
            else:
                messages.append(f"{log_msg} Failed (delete_dashboard 함수 실패)")
                fail_count += 1
                
        final_msg = f"\n대시보드 삭제 완료. 성공: {success_count}개, 실패: {fail_count}개."
        messages.append(final_msg)
        
        overall_success = fail_count == 0
        return overall_success, messages

    # --------------------------------------------------------------------------------

    def delete_all_datasources(self) -> Tuple[bool, List[str]]:
        """
        Grafana에 있는 모든 데이터 소스를 삭제합니다. (bool, List[str]) 반환
        - bool: 전체 작업 성공 여부
        - List[str]: 작업 로그 메시지 리스트
        """
        messages: List[str] = []
        
        # 데이터 소스 목록 API URL
        search_url = self.datasource_endpoint
        datasources = self._get_items_for_deletion(search_url, "Datasource")
        
        if not datasources:
            messages.append("삭제할 데이터 소스가 없습니다. (작업 성공)")
            return True, messages

        messages.append(f"총 {len(datasources)}개의 데이터 소스 삭제를 시작합니다.")
        
        success_count = 0
        fail_count = 0
        
        for ds in datasources:
            # 데이터 소스 API 결과는 ID 필드를 가집니다.
            ds_id = ds.get('id')
            ds_name = ds.get('name')
            
            log_msg = f"  -> 데이터 소스 삭제 중: Name='{ds_name}', ID='{ds_id}'"
            
            if not ds_id:
                msg = f"경고: Name '{ds_name}'의 ID가 없어 건너뜁니다."
                messages.append(msg)
                fail_count += 1
                continue

            # 데이터 소스 삭제 엔드포인트: /api/datasources/{id}
            delete_ds_url = f"{self.datasource_endpoint}/{ds_id}" 
            
            try:
                response = requests.delete(
                    delete_ds_url,
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    messages.append(f"{log_msg} Success")
                    success_count += 1
                else:
                    messages.append(f"{log_msg} Failed (Status: {response.status_code}, Response: {response.text})")
                    fail_count += 1
                    
            except requests.exceptions.RequestException as e:
                messages.append(f"{log_msg} Failed (Error: {e})")
                fail_count += 1
                
        final_msg = f"\n데이터 소스 삭제 완료. 성공: {success_count}개, 실패: {fail_count}개."
        messages.append(final_msg)
        
        overall_success = fail_count == 0
        return overall_success, messages


    def post_dashboard(self, dashboard_data: dict, target_uid: str, start_time: str, end_time: str, overwrite=False):
        """
        대시보드 데이터를 Grafana에 POST/PUT 합니다.
        :param dashboard_data: 수정된 대시보드 JSON 딕셔너리
        :param uid_placeholder: 데이터소스 UID 플레이스홀더 문자열
        :param target_uid: 실제 데이터소스 UID
        :param start_time: 로그 분석 시작 시간 ('YYYY-MM-DD HH:MM:SS.sss' 형식)
        :param end_time: 로그 분석 종료 시간 ('YYYY-MM-DD HH:MM:SS.sss' 형식)
        :param overwrite: 덮어쓰기 여부 (True로 설정하여 안정적인 업데이트 유도)
        """
        try:
            # UID 치환 (템플릿 변수 내에서만 치환)
            content_str = json.dumps(dashboard_data)
            content_str = content_str.replace("${DS_MARCUSOLSSON-CSV-DATASOURCE}", target_uid)
            
            # Grafana 대시보드 시간 범위 설정 (KST ISO 8601로 변환하여 적용)
            start_iso = to_korea_iso8601(start_time)
            end_iso   = to_korea_iso8601(end_time)
            
            # JSON에서 시간 범위 설정: 이 부분이 1970년 문제의 핵심 해결책입니다.
            # 대시보드 최상위 필드 'time' 및 'timeFrom', 'timeTo'를 UTC 시간으로 명시적으로 설정합니다.
            dashboard_data = json.loads(content_str) # 치환된 문자열로 다시 파싱

            # 대시보드 JSON의 시간 범위를 강제 설정
            if 'dashboard' in dashboard_data:
                db = dashboard_data['dashboard']
            else: # 기존 대시보드 JSON이 최상위 레벨에 dashboard 키를 포함하지 않는 경우를 대비
                 db = dashboard_data

            db['time']['from'] = start_iso
            db['time']['to'] = end_iso
            db['timeFrom'] = start_iso
            db['timeTo'] = end_iso
            #db['timezone'] = 'utc' # kst임!!!
            
            db['refresh'] = False
            
            
            # API 요청 페이로드 준비
            payload = {
                "dashboard": db,
                "folderId": 0, # 기본 폴더
                "overwrite": overwrite
            }

            response = requests.post(
                self.dashboard_endpoint,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            response_json = response.json()
            
            if response.status_code == 200:
                result_message = "POST success !!!\n"
                result_message += f"대시보드 UID: {response_json.get('uid')}\n"
                result_message += f"버전: {response_json.get('version')}\n"
                result_message += f"Grafana 설정 시간대: KST\n"
                result_message += f"대시보드 범위: {start_iso} ~ {end_iso}"
                
                return result_message, response_json

            else:
                result_message = f"POST 실패 (HTTP {response.status_code})\n"
                result_message += f"에러 메시지: {response_json.get('message', '알 수 없는 에러')}"
                return result_message, None

        except requests.exceptions.RequestException as e:
            return f"API 요청 중 에러 발생: {e}", None
        except Exception as e:
            return f"알 수 없는 오류 발생: {e}", None
