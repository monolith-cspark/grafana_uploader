import os
import time # 쿨타임 관리를 위해 time 모듈 추가
from PySide6.QtWidgets import ( # 💡 PyQt6 -> PySide6로 변경
    QApplication, QWidget, QPushButton, QVBoxLayout, 
    QHBoxLayout, QLabel, QLineEdit, QGridLayout, QComboBox,
    QGroupBox, QFileDialog, QTextEdit, QMessageBox
)
from PySide6.QtGui import QIcon # PySide6 유지
from PySide6.QtCore import Qt # 💡 PyQt6 -> PySide6로 변경

from datetime import datetime
import shutil
import json
from enum import IntEnum
import uuid

from grafana_api import GrafanaAPI
from config_manager import ConfigManager

from log_analyzer import LogAnalyzer, AnalysisResult, LogEntry, GrSections, MODE_TABLE
import util

# --- 1. 윈도우 크기 매크로(상수) 정의 ---
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 1080
WINDOW_TITLE = 'Grafana Dashboard Uploader'

LOCK_COOLTIME_MS = 1000 


COOLDOWN_SECONDS = 1.0 # 쿨타임 1초 설정

CLICK_LOCK_SECONDS = 0.15 # 0.15 중복 클릭 방지

DELETE_COOLDOWN_SECONDS = 2.0 # Delete 쿨타임 2초 설정

INVALID_RACE_NUM = -1

class UI_State(IntEnum):
    INIT_STATE = 0      # 초기 상태 (로그 분석 필요)
    ANALYZE_STATE = 1   # 로그 분석 완료 상태 (업로드 가능)
    UPLOAD_STATE = 2    # 업로드 완료 상태 (사용하지 않음, 일단 분석 상태로 복귀)

class UI_NotiState(IntEnum):
    NOTI_NONE = 0,            
    NOTI_WARN = 1,
    NOTI_ERR = 2
    NOTI_MAX = 3



class UI_Tool(QWidget):
    def __init__(self):
        super().__init__()
        
        ICON_PATH = 'assets/app.ico' 
        app_icon = QIcon(ICON_PATH)
        if app_icon.isNull():
            print(f"경고: 아이콘 파일 '{ICON_PATH}'을 로드할 수 없습니다.")
        else:
            self.setWindowIcon(app_icon)


        self.config = ConfigManager()
        self.analysis_result = None
        
        
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(
            100,
            100,
            int(self.config.get(key="WINDOW_WIDTH", section='DEFAULT')),
            int(self.config.get(key="WINDOW_HEIGHT", section='DEFAULT'))
        )

        api_key = self.config.get(section='API', key="api_key")
        server_url = self.config.get(section='API', key="server_url")
        
        if not api_key or not server_url:
            error_msg = (
                "오류: API 설정이 누락되었습니다.\n\n"
                f"- server_url: {'OK' if server_url else 'X (누락)'}\n"
                f"- api_key: {'OK' if api_key else 'X (누락)'}\n\n"
                "config.ini 파일의 [API] 섹션을 확인하여 입력"
            )
            print(error_msg)
            # 사용자에게 오류 메시지 표시
            QMessageBox.critical(self, "설정 오류", error_msg)
            
            # 유효하지 않으면 API 객체를 초기화하지 않고 종료 준비
            self.api = None 
            self._is_config_valid = False
            return 
        else:
            self.api = GrafanaAPI(base_url=server_url, api_key=api_key)
            self._is_config_valid = True
            print("INFO: API 설정 확인 완료. Grafana API 객체 초기화 성공.")
        
        
        # 상태 및 쿨타임 관리 변수
        self.current_state = UI_State.INIT_STATE
        self.last_action_time = 0.0 # 마지막 액션 시간 (쿨타임 체크용)
        self.start_time = ""
        self.end_time = ""
        
        self.btn_lock = False
        self.selected_race = INVALID_RACE_NUM
        
        # 초기 입력값 설정
        self.last_title = self.config.get('DEFAULT_DASHBOARD_NAME')
        self.last_gr_name = ""
        self.last_csv_path = self._get_csv_dir()
        
        self._init_ui()
        
        # ini save (ui init 이후에 실행 : noti window)
        self._save_initial_csv_path()
        
        self.click_clearbtn()
        
            
    def _init_ui(self):
        # 메인 레이아웃 (세로)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # ================== 1. 상단: 입력 및 버튼 그룹 ==================
        
        # 입력 그룹 (기존 로직 유지)
        input_group = QGroupBox("대시보드 및 로그 경로 설정")
        input_layout = QGridLayout(input_group)
        input_layout.setHorizontalSpacing(15)
        input_layout.setVerticalSpacing(10)
        
        # Title/GR ID 입력 필드 (기존 로직 유지)
        self.title_input = self._create_input_field(input_layout, 0, 'Title')
        self.title_input.setText(self.last_title) 
        self.gr_name_input = self._create_input_field(input_layout, 1, 'GR ID')
        self.gr_name_input.setText(self.last_gr_name) 

        # csv Path (기존 로직 유지)
        input_layout.addWidget(QLabel('csv Path:'), 2, 0)
        csv_h_layout = QHBoxLayout()
        self.csv_path_input = QLineEdit()
        self.csv_path_input.setText(self.last_csv_path)
        self.csv_browse_button = QPushButton('find csv')
        self.csv_browse_button.setFixedWidth(80)
        self.csv_browse_button.clicked.connect(self._select_csv_path)
        csv_h_layout.addWidget(self.csv_path_input)
        csv_h_layout.addWidget(self.csv_browse_button)
        input_layout.addLayout(csv_h_layout, 2, 1, 1, -1)
        
        main_layout.addWidget(input_group) 
        
        # 버튼 그룹 (기존 로직 유지)
        button_group = QHBoxLayout()
        self.analyze_button = QPushButton('1. 로그 분석')
        self.upload_button = QPushButton('2. 대시보드 업로드')
        self.clear_button = QPushButton('초기화 (Clear)')
        self.analyze_button.clicked.connect(self.click_analyze)
        self.upload_button.clicked.connect(self.click_upload)
        self.clear_button.clicked.connect(self.click_clearbtn)
        button_group.addWidget(self.analyze_button)
        button_group.addWidget(self.upload_button)
        button_group.addWidget(self.clear_button)
        main_layout.addLayout(button_group)
        
        # ================== 2. 중간: 로그 분석 결과 및 설정 그룹 ==================
        # 기존 result_group을 중간에 배치합니다.
        result_group = QGroupBox("로그 분석 결과 및 설정")
        result_layout = QGridLayout(result_group)
        
        # Row 0: 로그 데이터 범위
        result_layout.addWidget(QLabel('로그 데이터 범위:'), 0, 0)
        self.log_data_range_label = QLabel('N/A | N/A')
        self.log_data_range_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        result_layout.addWidget(self.log_data_range_label, 0, 1, 1, 3) 

        # Row 1: Dashboard 설정 범위
        result_layout.addWidget(QLabel('Dashboard 설정 범위:'), 1, 0)
        self.dashboard_setting_range_label = QLabel('N/A | N/A')
        self.dashboard_setting_range_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        result_layout.addWidget(self.dashboard_setting_range_label, 1, 1, 1, 3)

        # Row 2: 총 Race Count 및 Race 선택 ComboBox
        result_layout.addWidget(QLabel('총 Race 횟수:'), 2, 0)
        self.race_count_label = QLabel('N/A')
        result_layout.addWidget(self.race_count_label, 2, 1)

        result_layout.addWidget(QLabel('Race 선택:'), 2, 2)
        self.race_selector = QComboBox()
        self.race_selector.addItem("분석 후 선택 가능")
        self.race_selector.setEnabled(False)
        self.race_selector.currentIndexChanged.connect(self.select_race_selector) 
        result_layout.addWidget(self.race_selector, 2, 3)
        
        # Row 3 & 4: start, end Combobox
        result_layout.addWidget(QLabel('Race-Start:'), 3, 0)
        result_layout.addWidget(QLabel('Race-End:'), 3, 2)
        
        self.start_selector = QComboBox()
        self.start_selector.addItem("분석 후 선택 가능")
        self.start_selector.setEnabled(False)
        self.start_selector.currentIndexChanged.connect(self.select_start_selector) 
        result_layout.addWidget(self.start_selector, 4, 0, 1, 2)
        
        self.end_selector = QComboBox()
        self.end_selector.addItem("분석 후 선택 가능")
        self.end_selector.setEnabled(False)
        self.end_selector.currentIndexChanged.connect(self.select_end_selector) 
        result_layout.addWidget(self.end_selector, 4, 2, 1, 2)
        
        main_layout.addWidget(result_group)

        # ================== 3. 하단: 로그 뷰어 및 상태 알림 (가장 넓은 공간 할당) ==================
        
        # 하단 좌/우 영역을 담는 수평 레이아웃
        bottom_h_layout = QHBoxLayout()
        
        # ------------------ 좌측: CSV 상세 로그 뷰어 ------------------
        csv_log_label_group = QGroupBox("csv 로그 분석")
        csv_log_label_layout = QVBoxLayout(csv_log_label_group)
        
        self.csv_log_label = QTextEdit()
        self.csv_log_label.setReadOnly(True)
        self.csv_log_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border: none;")
        self.csv_log_label.setText("")
        
        csv_log_label_layout.addWidget(self.csv_log_label)
        bottom_h_layout.addWidget(csv_log_label_group, 3)

        # ------------------ 우측: 상세 로그 이벤트 및 상태 알림 ------------------
        right_panel_v_layout = QVBoxLayout()
        
        event_log_group = QGroupBox("상세 로그 이벤트")
        event_log_layout = QVBoxLayout(event_log_group)
        
        self.event_label = QTextEdit()
        self.event_label.setReadOnly(True)
        self.event_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border: none;")
        self.event_label.setText("")
        
        event_log_layout.addWidget(self.event_label)
        right_panel_v_layout.addWidget(event_log_group, 5)
        
        bottom_h_layout.addLayout(right_panel_v_layout, 3)
        
        
        
        main_layout.addLayout(bottom_h_layout, 3)
        
        # ================== 4. 최하단: Delete 버튼 ==================
        
        delete_button_layout = QHBoxLayout()
        delete_button_layout.addStretch(1) 
        
        self.delete_all_button = QPushButton('Delete All Dashboard, DS')
        self.delete_all_button.clicked.connect(self.click_delete_all_btn) 
        
        delete_button_layout.addWidget(self.delete_all_button)
        
        main_layout.addLayout(delete_button_layout)
        
        # 레이아웃 최종 설정
        self.setLayout(main_layout)
        

            
            
        
    def _save_initial_csv_path(self):
        """
        마지막 설정한 CSV 유효성을 검증하여 self.last_csv_path에 설정
        """
        success, error_msg = self.config.set(key="LAST_CSV_PATH", value=self.last_csv_path, section='DEFAULT')
        
        if not success:
            # 설정 저장 실패
            self._show_messagebox(UI_NotiState.NOTI_ERR, f"설정 파일 저장 실패: {error_msg}")

    def _create_input_field(self, layout, row, label_text):
        """라벨과 QLineEdit을 격자 레이아웃에 추가하고 QLineEdit 객체를 반환합니다."""
        label = QLabel(f'{label_text}:')
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(f'{label_text}을(를) 입력하세요.')
        
        layout.addWidget(label, row, 0)
        layout.addWidget(line_edit, row, 1)
        
        return line_edit

    def _get_csv_dir(self):
        """
        설정에서 마지막 CSV 경로를 읽어와 유효성을 검증하고, 
        유효하지 않으면 상위 디렉터리를 탐색하여 유효한 디렉터리를 결정합니다.
        모든 경로는 절대 경로로 처리됩니다.
        """
        last_path = self.config.get(section='DEFAULT', key="LAST_CSV_PATH")
            
        # 현재 작업 디렉터리의 절대 경로를
        default_abs_path = os.path.abspath(os.getcwd())

        if last_path is None:
            # 경로 설정된 게 없으므로 현재 경로
            return default_abs_path

        # 저장된 경로를 즉시 절대 경로로 변환하여 처리 시작
        last_abs_path = os.path.abspath(last_path)

        if os.path.isfile(last_abs_path):
            # csv 파일이면 파일반환, 아니라면 디렉토리 반환
            if last_abs_path.lower().endswith('.csv'):
                return last_abs_path
            else:
                return os.path.dirname(last_abs_path)
        elif os.path.isdir(last_abs_path):
            # 디렉터리가 존재
            return last_abs_path
        else:
            # 파일도 디렉터리도 존재하지 않는 경우, 저장된 경로의 부모 디렉터리 탐색
            current_dir = os.path.dirname(last_abs_path)
        
        # 상위 디렉터리 탐색
        MAX_SEARCH_DEPTH = 3
        
        for _ in range(MAX_SEARCH_DEPTH):
            # 현재 경로가 유효한 디렉터리인지 확인
            if os.path.isdir(current_dir):
                return current_dir
            
            # 상위 디렉터리로 이동
            parent_dir = os.path.dirname(current_dir)
            
            # 최상위 디렉터리이거나, 경로가 더 이상 줄어들지 않으면 탐색 중지
            if parent_dir == current_dir:
                break
            current_dir = parent_dir
        
        # 탐색 실패 시 현재 작업 디렉토리로 
        return default_abs_path


    def _check_lock(self):
        """중복 클릭 방지 체크"""
        return self.btn_lock
    
    def _unlock_click(self):
        """중복 클릭 방지 언락 """
        self.btn_lock = False
        
    def _lock_click(self):
        """중복 클릭 방지 락 """
        self.btn_lock = True
        
    
    def _check_input(self):
        """ input text 입력했는지 체크 """
        title = self.title_input.text()
        gr_name = self.gr_name_input.text()
        csv_path = self.csv_path_input.text()

        if not all([title, gr_name, csv_path]):
            msg = '모든 필드를 채워야 합니다.'
            self._show_messagebox(UI_NotiState.NOTI_ERR, msg)
            return False
        
        return True
    
    def _select_csv_path(self):
        """
        파일 탐색기를 열어 CSV 파일 경로를 선택하고 입력 필드에 설정합니다.
        마지막 사용 경로를 config에 저장
        """
        # 초기 디렉터리 로드
        last_dir = self._get_csv_dir()
        
        # 2. 파일 탐색기 대화 상자 생성
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "CSV 파일 선택", 
            last_dir,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            # 선택된 csv 파일을 input에 입력 및 ini 경로에서 저장
            self.csv_path_input.setText(file_path)
            self.last_csv_path = file_path
            self._save_initial_csv_path()
        
        
    
    def _show_messagebox(self, noti: UI_NotiState, msg):
        """메시지 박스 출력 """
        match noti:
                case UI_NotiState.NOTI_NONE:
                    QMessageBox.information(self, "Notice", msg)
                case UI_NotiState.NOTI_WARN:
                    QMessageBox.warning(self, "Warning", msg)
                case UI_NotiState.NOTI_ERR:
                    QMessageBox.critical(self, "Error", msg)
                case _:  # Default case 
                    QMessageBox.information(self, "Notice", msg)
        
    def click_analyze(self):
        """
        로그 분석 버튼 클릭 함수
        """
        if self._check_lock():
            return

        csv_path = self.csv_path_input.text()

        if not csv_path:
            msg = 'CSV Path를 입력해야 분석이 가능'
            self._show_messagebox(UI_NotiState.NOTI_ERR, msg)
            return

        log_analyzer = LogAnalyzer()

        try:
            # 버튼 비활성화
            self._set_button_states(False)
            self.refresh_ui()
            
            # cvs 분석
            self.analysis_result = log_analyzer.analyze(csv_path)

            result = self.analysis_result
            
            # 최초 로그 분석에는 전체 범위 설정
            log_range = f"{result.first_time or 'N/A'} ~ {result.last_time or 'N/A'}"
            self.log_data_range_label.setText(log_range)

            self.update_log_and_dashboard_range(
                self.analysis_result.first_time or "N/A",
                self.analysis_result.last_time or "N/A"
            )

            self.race_count_label.setText(str(result.total_race_count))


            # Selector 업데이트
            self.race_selector.clear()
            self.start_selector.clear()
            self.end_selector.clear()
            
            self.race_selector.setEnabled(False)
            self.start_selector.setEnabled(False)
            self.end_selector.setEnabled(False)
            
            if result.total_race_count >= 0:
                self.race_selector.addItem("전체 레이스")
                for i in range(0, result.total_race_count + 1):
                    self.race_selector.addItem(f"Race {i}")
                self.race_selector.setEnabled(True)
                
                # start, end selector 설정
                self.start_selector.addItem("전체 로그 시작")
                self.end_selector.addItem("전체 로그 종료")
                
                lines = []
                lines.append(f"전체 시간대: {result.first_time} - {result.last_time}")
                lines.append(f"총 레이스 횟수: {result.total_race_count}\n")

                for entry in result.logs:
                    if entry.log_type == "RACE_INFO":
                        lines.append(f"\n{entry.context}\n")
                    else:
                        lines.append(f"{entry.time}    {entry.context}") 
                        
                self.csv_log_label.setText("\n".join(lines))    
                self.csv_log_label.setStyleSheet("padding: 10px; border: 1px solid green; background-color: #ebfff0;")
                
                # 상태 변경 to 분석 성공 단계
                self.current_state = UI_State.ANALYZE_STATE
            else:
                self.race_selector.addItem("레이스 없음")
                self.race_selector.setEnabled(False)
                self.csv_log_label.setText('로그 분석 성공: 레이스가 발견되지 않았습니다. 업로드를 진행할 수 없습니다.')
                self.csv_log_label.setStyleSheet("padding: 10px; border: 1px solid orange; background-color: #fff8eb;")
            
            time.sleep(COOLDOWN_SECONDS)
            self._set_button_states(True)

        except Exception as e:
            self.analysis_result = None
            
            # 분석 결과 UI 초기화
            self.log_data_range_label.setText('N/A | N/A')
            self.dashboard_setting_range_label.setText('N/A | N/A')
            self.race_count_label.setText('N/A')
            self.race_selector.clear()
            self.race_selector.addItem("분석 실패")
            self.race_selector.setEnabled(False)

            self.csv_log_label.setText(f'로그 분석 오류: {e}')
            self.csv_log_label.setStyleSheet("padding: 10px; border: 1px solid red; background-color: #ffebeb;")
            
            # 상태 변경 to 초기 단계 ( 분석 이전 )
            self.current_state = UI_State.INIT_STATE
            self._set_button_states(True)
            
    def click_upload(self):
        """
        대쉬보드 업로드 버튼 클릭 함수
        """
        if self._check_lock():
            return
        
        # 버튼 비활성화
        self._set_button_states(False)
        
        if self.current_state != UI_State.ANALYZE_STATE:
            msg = '먼저 로그 분석 성공적으로 완료하세요'
            self._show_messagebox(UI_NotiState.NOTI_ERR, msg)
            self._set_button_states(True)
            return
        
        json_path = self.config.get('DEFAULT_DASHBOARD_JSON_PATH')

        gr_name = self.gr_name_input.text().upper() # 대문자
        title = f'[{gr_name}]_{self.title_input.text()}' # [GR_ID]_Title
        original_csv_path = self.csv_path_input.text()

        # csv 저장 경로 
        csv_savedir = os.path.join(os.getcwd(), "csv")
        os.makedirs(csv_savedir, exist_ok=True)

        # 로그 시작시간 문자열
        time_str = self.analysis_result.first_time  # "2025-10-23 15:39:31.065"

        # datetime 객체로 변환
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")

        # 파일명용 문자열로 변환 (밀리초 버림)
        file_name_time = dt.strftime("%Y-%m-%d_%H%M")

        # 복사할 파일명
        copy_csv_path = os.path.join(csv_savedir, f"{title}_{file_name_time}.csv")

        try:
            shutil.copy(original_csv_path, copy_csv_path)
        except Exception as e:
            self._show_messagebox(UI_NotiState.NOTI_ERR, f"CSV 파일 복사 실패: {e}")
            self._set_button_states(True)
            return
        
        csv_path = util.normalize_path_for_grafana(absolute_path=copy_csv_path)

        if not self._check_input():
            self._set_button_states(True)
            return
            
        # 시간 범위 유효성 체크 및 대시보드 업로드
        if not self.start_time or not self.end_time:
            msg = '대시보드 시간 설정 범위 체크필요'
            self._show_messagebox(UI_NotiState.NOTI_ERR, msg)
            self._set_button_states(True)
            return
        
        # 출력 메시지 누적을 위한 변수
        output_messages = []
        
        def update_output(message):
            """출력을 누적해서 업데이트"""
            output_messages.append(message)
            full_output = "\n".join(output_messages)
            self.event_label.setText(full_output)
            # UI 즉시 업데이트
            QApplication.processEvents()


        update_output("그라파나 서버와 연결을 시도합니다...")

        is_connected, message = self.api.check_connection()
        self.api.check_connection()
        
        if is_connected:
            update_output("그라파나 서버 연결 성공")
            update_output(message)
        else:
            self.event_label.setStyleSheet("padding: 10px; border: 1px solid red; background-color: #ffebeb;")
            update_output("오류: Grafana 서버 연결 또는 인증 실패")
            update_output(message)
            QMessageBox.critical(self, "API 연결 오류", message)
            self._set_button_states(True)
            return

        update_output("대시보드 업로드를 시작합니다...")
        update_output(f"제목: {title}")
        update_output(f"GR: {gr_name}")
        update_output(f"JSON 파일: {json_path}")
        update_output(f"CSV 파일: {csv_path}")
        update_output(f"시간 범위: {self.start_time} ~ {self.end_time}")
        
        
        
        
        # json 파일 로드
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                dashboard_payload = json.load(f)
            dashboard_payload['timezone'] = "Asia/Seoul"
            update_output("JSON 파일 로드 완료")
            
        except FileNotFoundError:
            update_output(f'오류: 대시보드 JSON 파일 경로를 찾을 수 없습니다: {json_path}')
            self.event_label.setStyleSheet("padding: 10px; border: 1px solid red; background-color: #ffebeb;")
            self._set_button_states(True)
            return
        except json.JSONDecodeError:
            update_output(f'오류: 대시보드 JSON 파일 형식이 올바르지 않습니다: {json_path}')
            self.event_label.setStyleSheet("padding: 10px; border: 1px solid red; background-color: #ffebeb;")
            self._set_button_states(True)   
            return


        
        # 기존 data source 확인 
        update_output(f"\n기존 datasource 확인...")
        existing_ds_uid = self.api.find_datasource_by_csv_path(csv_file_path=csv_path)
        
        if existing_ds_uid:
            update_output(f"기존 데이터 소스 발견 (UID: {existing_ds_uid})")
            target_ds_uid = existing_ds_uid
        else:
            update_output("새로운 데이터 소스를 생성합니다...")
        
            new_ds_uid = self.api.create_csv_datasource(
                name=f"{gr_name}_{self.analysis_result.first_time}_{uuid.uuid4().hex[:6]}",
                csv_path=csv_path
            )
            
            if new_ds_uid:
                update_output(f"새로운 데이터 소스 생성 완료! (UID: {new_ds_uid})")
                target_ds_uid = new_ds_uid
            else:
                error_message = f"오류: 데이터 소스 생성에 실패했습니다. (경로: {csv_path})"
                update_output(error_message)
                self.event_label.setStyleSheet("padding: 10px; border: 1px solid red; background-color: #ffebeb;")
                self._set_button_states(True)   
                return 
            
        
        # 기존 대시보드 확인
        update_output(f"\n기존 대쉬보드 확인...")
        existing_uid = self.api.find_dashboard_by_title(title)
        
        overwrite_flag = False
        if existing_uid:
            update_output(f"기존 대시보드 발견 (UID: {existing_uid})")
            
            # UID 설정
            if 'dashboard' in dashboard_payload:
                dashboard_payload['dashboard']['uid'] = existing_uid
                dashboard_payload['dashboard']['title'] = title  # 제목도 명시적으로 설정
            else:
                dashboard_payload['uid'] = existing_uid
                dashboard_payload['title'] = title  # 제목도 명시적으로 설정
                
            overwrite_flag = True
            update_output("덮어쓰기(Overwrite) 모드로 진행합니다.")
        else:
            update_output("새로운 대시보드를 생성합니다.")
            
            # 새로 생성 시 UID 제거하고 제목 설정
            if 'dashboard' in dashboard_payload:
                if 'uid' in dashboard_payload['dashboard']:
                    del dashboard_payload['dashboard']['uid']
                dashboard_payload['dashboard']['title'] = title  # 제목 설정
            else:
                dashboard_payload.pop('uid', None)  # 안전하게 UID 제거
                dashboard_payload['title'] = title  # 제목 설정
                
            update_output("UID 초기화 및 제목 설정 완료")

        
        # 대시보드 업로드
        update_output(f"\n대시보드 업로드 중...")
        result_message, dashboard_data = self.api.post_dashboard(
            dashboard_data=dashboard_payload,
            target_uid=target_ds_uid,
            start_time=self.start_time,
            end_time=self.end_time,
            overwrite=overwrite_flag
        )
        
        # result_message를 라인별로 분리하여 출력 (가독성 향상)
        if result_message:
            message_lines = result_message.split('\n')
            for line in message_lines:
                if line.strip():  # 빈 줄이 아닌 경우만 출력
                    update_output(line)
        
        # 성공/실패 판단
        success_indicators = ['성공', 'success']
        is_success = dashboard_data and any(indicator in result_message for indicator in success_indicators)
        
        if is_success:
            update_output("대시보드 업로드 완료!")
            update_output(f"대시보드 제목: {title}")
            
            # 생성된 대시보드 정보 출력
            if isinstance(dashboard_data, dict):
                if 'uid' in dashboard_data:
                    update_output(f"대시보드 UID: {dashboard_data['uid']}")
                if 'url' in dashboard_data:
                    update_output(f"대시보드 URL: {dashboard_data['url']}")
            
            # last input 갱신
            self.last_title = self.title_input.text()
            self.last_gr_name = self.gr_name_input.text()
            self.event_label.setStyleSheet("padding: 10px; border: 2px solid green; background-color: #f0fff0; min-height: 100px; font-family: monospace;")
            update_output("대시보드 업로드 완료!!!")
            
        else:
            # 실패 시 추가 디버깅 정보
            if hasattr(self.api, 'last_response'):
                update_output(f"HTTP 상태 코드: {self.api.last_response.status_code}")
                if hasattr(self.api.last_response, 'text'):
                    update_output(f"응답 내용: {self.api.last_response.text[:200]}...")
            
            self.event_label.setStyleSheet("padding: 10px; border: 2px solid red; background-color: #fff0f0; min-height: 100px; font-family: monospace;")
            
            update_output("대시보드 업로드 실패!!!")
            


        self.event_label.ensureCursorVisible()
        time.sleep(COOLDOWN_SECONDS)
        self._set_button_states(True)
        self.refresh_ui()
        
        

    def click_clearbtn(self):
        """
        '초기화' 버튼이 눌렸을 때 모든 입력 필드를 초기화
        """
        if self._check_lock():
            return
        
        # 상태 초기화
        self.selected_race = INVALID_RACE_NUM
        self.current_state = UI_State.INIT_STATE
        self._set_button_states(False)
        self.refresh_ui()
        
        # 1. 입력 필드 초기화 및 기본값 복원
        self.title_input.setText(self.last_title)
        self.gr_name_input.setText(self.last_gr_name)
        self.csv_path_input.setText(self.last_csv_path)
        
        # 2. 로그 분석 결과 영역 초기화
        self.log_data_range_label.setText('N/A | N/A')
        self.dashboard_setting_range_label.setText('N/A | N/A')
        self.race_count_label.setText('N/A')
        
        # Race Selector 초기화
        self.race_selector.clear()
        self.race_selector.addItem("분석 후 선택 가능")
        self.race_selector.setEnabled(False)
        
        self.start_selector.clear()
        self.start_selector.addItem("분석 후 선택 가능")
        self.start_selector.setEnabled(False)
        
        self.end_selector.clear()
        self.end_selector.addItem("분석 후 선택 가능")
        self.end_selector.setEnabled(False)

        # csv log 라벨 초기화 및 스타일 복원
        self.csv_log_label.setText('csv 파일을 선택 후 로그분석을 하시오')
        self.csv_log_label.setStyleSheet("padding: 10px; background-color: #f0f0f0;") # 스크롤 영역에 테두리가 적용되므로 라벨의 min-height 및 border 제거
        
        self.event_label.setText('사용 TIP \n\n 동일한 이름으로 업로드하면 기존 board에서 덮어씀\n\n\
덮어쓰는 경우 해당 보드를 켜놓고 업로드하면 시간이 꼬임\n\n \
시간이 꼬였다면 보드에서 뒤로가기 한 후 다시 업로드 (시간 재설정)\n\n \
csv는 경로나 이름을 다르게 하면 여러개 업로드 가능\n\n \
all delete 버튼은 그라파나의 dash board, data source (csv 목록)을 모두 삭제함 \
    ')
        self.event_label.setStyleSheet("padding: 10px; background-color: #f0f0f0;") # 스크롤 영역에 테두리가 적용되므로 라벨의 min-height 및 border 제거
        
        time.sleep(COOLDOWN_SECONDS)
        self._set_button_states(True)
        
        
    def refresh_ui(self):
        QApplication.processEvents()

    def select_race_selector(self, index):
        """
        Race 선택 ComboBox의 값이 변경될 때 호출됩니다.
        선택된 Race에 따라 Dashboard 설정 범위를 업데이트합니다.
        :param index: ComboBox에서 선택된 항목의 인덱스
        """
        if index < 0 or not self.race_selector.isEnabled():
            return
        
        # 분석 완료 상태가 아니거나 유효하지 않은 인덱스(-1)일 경우 무시
        if self.current_state != UI_State.ANALYZE_STATE or not self.analysis_result:
            return

        selected_text = self.race_selector.currentText()
        
        # start/end selector 초기화
        self.start_selector.clear()
        self.end_selector.clear()
        self.start_selector.setEnabled(False)
        self.end_selector.setEnabled(False)
        
        self.selected_race = INVALID_RACE_NUM
        if selected_text == "전체 레이스":
            # 전체 레이스 선택 시 로그 데이터 범위 선택
            self.update_log_and_dashboard_range(
                self.analysis_result.first_time or "N/A",
                self.analysis_result.last_time or "N/A"
            )
            self.start_selector.addItem("전체 로그 시작")
            self.end_selector.addItem("전체 로그 종료")
            self.start_selector.setEnabled(False)
            self.end_selector.setEnabled(False)
             
        elif selected_text.startswith("Race"):
            try:
                race_number = int(selected_text.split(' ')[1])
            except (IndexError, ValueError):
                self.event_label.setText("Race 선택 오류: 잘못된 형식입니다.")
                
            # Race의 기본 시간 범위 설정
            race_info = self.analysis_result.race_times.get(race_number)
            if not race_info:
                self.event_label.setText(f"Race 선택 오류: {race_number}번 레이스 정보가 없습니다.")
                return
            
            start_time = race_info.get("start") or "N/A"
            end_time = race_info.get("end") or "N/A"
            self.update_log_and_dashboard_range(start_time, end_time)


            # 섹션 변경 리스트 가져오기
            section_changes_list = self.analysis_result.race_section_changes.get(race_number, [])
            if not section_changes_list:
                self.start_selector.addItem("섹션 변경 없음")
                self.end_selector.addItem("섹션 변경 없음")
                return
            
            # 섹션 변경 이벤트 항목 추가
            for section_id, time in section_changes_list:
                section_name = MODE_TABLE.get(section_id, f"UNKNOWN_{section_id.value}")
                item_text = f"[{section_name}] ({time})"
                
                # start, end추가
                self.start_selector.addItem(item_text)
                self.end_selector.addItem(item_text)
            
            # end_selector는 마지막 인덱스로 설정
            last_index = len(section_changes_list) - 1
            if last_index >= 0:
                self.end_selector.setCurrentIndex(last_index)
            
            # 활성화
            self.start_selector.setEnabled(True)
            self.end_selector.setEnabled(True)
            
            self.selected_race = race_number
                
        else:
            race_info = self.analysis_result.race_times.get(race_number)
            if not race_info:
                self.event_label.setText(f"Race 선택 오류: {race_number}번 레이스 정보가 없습니다.")
            else:
                start_time = race_info.get("start") or "N/A"
                end_time = race_info.get("end") or "N/A"
                self.update_log_and_dashboard_range(start_time, end_time)

    def select_start_selector(self, index):
        """
        시작 시간(start_selector)이 변경될 때 호출됩니다.
        선택된 시작 시간을 적용하고, 시간이 끝 시간보다 늦으면 오류를 표시합니다.
        """
        if index < 0 or not self.start_selector.isEnabled() or self.analysis_result is None:
            return
                
        # 분석 완료 상태가 아니거나 유효하지 않은 인덱스(-1)일 경우 무시
        if self.current_state != UI_State.ANALYZE_STATE or not self.analysis_result.race_section_changes:
            return
        
        race_number = self.selected_race
        section_changes_list = self.analysis_result.race_section_changes.get(race_number, [])
        
        if index >= len(section_changes_list):
            self._show_messagebox(UI_NotiState.NOTI_ERR, "R유효하지 않은 인덱스")
            return

        # 선택된 인덱스에서 시간 추출
        new_start_time = section_changes_list[index][1] # (section_id, time) 튜플의 [1]번째 요소
        
        # 현재 끝 시간 
        self.end_time
        if not new_start_time or not self.end_time:
            self._show_messagebox(UI_NotiState.NOTI_ERR, "Race 데이터에 시간이 누락")
            return

        # 시간 비교
        if new_start_time >= self.end_time:
            self._show_messagebox(UI_NotiState.NOTI_ERR, "시작 시간은 종료 시간보다 빨라야 합니다")
            return
        
        self.update_log_and_dashboard_range(new_start_time, self.end_time)


    def select_end_selector(self, index):
        """
        끝 시간(end_selector)이 변경될 때 호출됩니다.
        선택된 끝 시간을 적용하고, 시간이 시작 시간보다 빠르면 오류를 표시합니다.
        """
        # 기본 유효성 검사
        if index < 0 or not self.end_selector.isEnabled() or self.analysis_result is None:
            return
                
        # 분석 완료 상태 및 데이터 존재 여부 확인
        if self.current_state != UI_State.ANALYZE_STATE or not self.analysis_result.race_section_changes:
            return
        
        race_number = self.selected_race
        section_changes_list = self.analysis_result.race_section_changes.get(race_number, [])
        
        if index >= len(section_changes_list):
            self._show_messagebox(UI_NotiState.NOTI_ERR, "R유효하지 않은 인덱스")
            return

        # 선택된 인덱스에서 시간 추출
        # (section_id, time) 튜플의 [1]번째 요소
        new_end_time = section_changes_list[index][1] 
        
        if not new_end_time or not self.start_time:
            self._show_messagebox(UI_NotiState.NOTI_ERR, "Race 데이터에 시간이 누락")
            return

        # 시간 비교
        # 종료 시간이 시작 시간보다 늦어야 합니다.
        if new_end_time <= self.start_time:
            self._show_messagebox(UI_NotiState.NOTI_ERR, "종료 시간은 시작 시간보다 늦어야 합니다")
            return
        
        self.update_log_and_dashboard_range(self.start_time, new_end_time)

    def update_log_and_dashboard_range(self, start_time, end_time):
        # 범위
        log_range = f"{start_time or 'N/A'} ~ {end_time or 'N/A'}"
        
        # 라벨 업데이트
        self.dashboard_setting_range_label.setText(log_range)
        
        # 내부 시간 저장
        self.start_time = start_time
        self.end_time = end_time
        
    def click_delete_all_btn(self):
        
        reply = QMessageBox.question(
            self,
            "삭제 확인",
            "대시보드와 데이터 소스를 모두 삭제합니다.\n정말 진행하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._check_lock():
            return
        
        self._set_button_states(False)
        self.event_label.clear()
        self.refresh_ui()
        
        try:
            self.event_label.append("dash board 및 data source 삭제 시작")
            
            # dash board 삭제
            is_db_success, db_messages = self.api.delete_all_dashboards()
            self.event_label.append("\n[대시보드 삭제 결과]")
            for msg in db_messages:
                self.event_label.append(msg)
            
            db_status = "SUCCESS" if is_db_success else "FAILED"
            self.event_label.append(f"최종 대시보드 삭제 상태: {db_status}")
            
            # data source 삭제
            is_ds_success, ds_messages = self.api.delete_all_datasources()
            self.event_label.append("\n[데이터 소스 삭제 결과]")
            for msg in ds_messages:
                self.event_label.append(msg)
                
            ds_status = "SUCCESS" if is_ds_success else "FAILED"
            self.event_label.append(f"최종 데이터 소스 삭제 상태: {ds_status}")

            overall_success = is_db_success and is_ds_success
            if overall_success:
                final_status = "모든 항목을 삭제했습니다" 
                self.event_label.setStyleSheet("padding: 10px; border: 1px solid green; background-color: #ebfff0;")
                
            else:
                final_status = "일부 삭제 작업에 실패"
                self.event_label.setStyleSheet("padding: 10px; border: 1px solid red; background-color: #ffebeb;")
                
            self.event_label.append(f"\n=== 최종 삭제 작업 요약: {final_status} ===")

        except Exception as e:
            error_msg = f"API 인스턴스 생성 또는 실행 중 예상치 못한 오류 발생: {e}"
            self.event_label.append(f"ERROR: {error_msg}")
            self.event_label.setStyleSheet("padding: 10px; border: 1px solid red; background-color: #ffebeb;")
            
            
        # UI 스크롤을 맨 아래로 이동
        self.event_label.ensureCursorVisible()

        time.sleep(COOLDOWN_SECONDS)
        self._set_button_states(True)
        self.refresh_ui()
        
    
    def _set_button_states(self, enable: bool):
        """
        주요 버튼들의 활성화/비활성화 상태를 일괄 설정합니다.
        """
        # 모든 버튼을 일괄적으로 설정
        if enable:
            # 활성화
            self.analyze_button.setEnabled(enable)
            self.csv_browse_button.setEnabled(enable)
            self.delete_all_button.setEnabled(enable)
            self.clear_button.setEnabled(enable)
            
            if self.current_state != UI_State.INIT_STATE:
                self.upload_button.setEnabled(enable)
            
        else: # 비활성화
            self.analyze_button.setEnabled(enable)
            self.upload_button.setEnabled(enable)
            self.clear_button.setEnabled(enable)
            self.delete_all_button.setEnabled(enable)
            self.csv_browse_button.setEnabled(enable)
            

import sys

if __name__ == '__main__':
    app = QApplication(sys.argv)

    tool = UI_Tool()
    tool.show()

    sys.exit(app.exec())
