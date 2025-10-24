
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, 
    QHBoxLayout, QLabel, QLineEdit, QGridLayout, QComboBox,
    QGroupBox, QScrollArea, QFrame # 결과 섹션 구분을 위해 추가
)
from PyQt6.QtCore import Qt

from grapana_poster import GrafanaPoster
from config_manager import ConfigManager

from log_analyzer import LogAnalyzer, AnalysisResult, LogEntry

# --- 1. 윈도우 크기 매크로(상수) 정의 ---
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800
WINDOW_TITLE = 'Grafana Dashboard Uploader'


class SimpleTool(QWidget):
    def __init__(self):
        super().__init__()

        self.config = ConfigManager()

        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(100, 100, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.init_ui()

    def init_ui(self):
        # 메인 레이아웃 (세로)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # ----------------------------------------------------
        # 1. 입력 필드 그룹 (GridLayout)
        # ----------------------------------------------------
        input_group = QGroupBox("대시보드 및 로그 경로 설정")
        input_layout = QGridLayout(input_group)
        input_layout.setHorizontalSpacing(15)
        input_layout.setVerticalSpacing(10)
        
        # 라벨 및 입력 필드 정의
        self.title_input = self._create_input_field(input_layout, 0, 'Title')
        self.title_input.setText(self.config.get('DEFAULT_DASHBOARD_NAME')) 

        self.json_path_input = self._create_input_field(input_layout, 1, 'json Path')
        self.json_path_input.setText(self.config.get('DEFAULT_DASHBOARD_JSON_PATH')) 

        self.csv_path_input = self._create_input_field(input_layout, 2, 'csv Path')
        self.csv_path_input.setText(self.config.get('DEFAULT_LOG_CSV_NAME')) 
        
        main_layout.addWidget(input_group) 
        
        # ----------------------------------------------------
        # 2. 버튼 그룹 (HorizontalLayout)
        # ----------------------------------------------------
        button_group = QHBoxLayout()
        
        self.analyze_button = QPushButton('1. 로그 분석')
        self.run_button = QPushButton('2. 대시보드 실행/업로드')
        self.clear_button = QPushButton('초기화 (Clear)')
        
        # 버튼에 기능 연결
        self.analyze_button.clicked.connect(self.analyze_log)
        self.run_button.clicked.connect(self.run_task)
        self.clear_button.clicked.connect(self.clear_fields)
        
        button_group.addWidget(self.analyze_button)
        button_group.addWidget(self.run_button)
        button_group.addWidget(self.clear_button)
        
        main_layout.addLayout(button_group)
        
        # ----------------------------------------------------
        # 3. 로그 분석 결과 그룹 (GridLayout)
        # ----------------------------------------------------
        result_group = QGroupBox("로그 분석 결과")
        result_layout = QGridLayout(result_group)

        # 시작 시간
        result_layout.addWidget(QLabel('최초 시작 시간:'), 0, 0)
        self.start_time_label = QLabel('N/A')
        self.start_time_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        result_layout.addWidget(self.start_time_label, 0, 1)

        # 마지막 시간
        result_layout.addWidget(QLabel('마지막 시간:'), 1, 0)
        self.end_time_label = QLabel('N/A')
        self.end_time_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        result_layout.addWidget(self.end_time_label, 1, 1)

        # 총 Race Count
        result_layout.addWidget(QLabel('총 Race 횟수:'), 0, 2)
        self.race_count_label = QLabel('N/A')
        result_layout.addWidget(self.race_count_label, 0, 3)

        # Race 선택 ComboBox
        result_layout.addWidget(QLabel('Race 선택:'), 1, 2)
        self.race_selector = QComboBox()
        self.race_selector.addItem("분석 후 선택 가능")
        self.race_selector.setEnabled(False)
        result_layout.addWidget(self.race_selector, 1, 3)
        
        main_layout.addWidget(result_group)

        # ----------------------------------------------------
        # 4. 실행/업로드 결과 라벨
        # ----------------------------------------------------
        self.result_label = QLabel('실행 전: 로그 분석 또는 모든 필드를 채우고 "실행" 버튼을 누르세요.')
        self.result_label.setStyleSheet("padding: 10px; border: 1px solid #ccc; background-color: #f0f0f0; min-height: 100px;")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        
        main_layout.addWidget(self.result_label)
        
        # 레이아웃 최종 설정
        self.setLayout(main_layout)

    def _create_input_field(self, layout, row, label_text):
        """라벨과 QLineEdit을 격자 레이아웃에 추가하고 QLineEdit 객체를 반환합니다."""
        label = QLabel(f'{label_text}:')
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(f'{label_text}을(를) 입력하세요.')
        
        layout.addWidget(label, row, 0)
        layout.addWidget(line_edit, row, 1)
        
        return line_edit

    def run_task(self):
        """
        '실행' 버튼이 눌렸을 때 실행되는 핵심 로직 함수입니다.
        입력된 데이터를 읽고 결과 라벨을 업데이트합니다.
        """
        title = self.title_input.text()
        json_path = self.json_path_input.text()
        csv_path = self.csv_path_input.text()

        if not all([title, json_path, csv_path]):
            self.result_label.setText('모든 필드를 채워야 합니다.')
            self.result_label.setStyleSheet("padding: 10px; border: 1px solid red; background-color: #ffebeb;")
            return

        poster = GrafanaPoster(api_key=self.config.get(section='SETTINGS', key='API_KEY'), base_url=self.config.get(section='SETTINGS', key='SERVER_URL'))

        result_message, dashboard_data = poster.post_dashboard(
            file_path=json_path,
            uid_placeholder="${DS_MARCUSOLSSON-CSV-DATASOURCE}",
            target_uid=self.config.get('DEFAULT_DATASOURCE_UID')
        )
        
        # 3. 결과 라벨 업데이트
        output = f"--- 실행 결과 ({title}) ---\n{result_message}"
        self.result_label.setText(output)

        if dashboard_data and '✅' in result_message:
            self.result_label.setStyleSheet("padding: 10px; border: 1px solid green; background-color: #ebfff0; min-height: 100px;")
        else:
            self.result_label.setStyleSheet("padding: 10px; border: 1px solid red; background-color: #ffebeb; min-height: 100px;")



    def clear_fields(self):
        """
        '초기화' 버튼이 눌렸을 때 모든 입력 필드를 비웁니다.
        """
        self.title_input.clear()
        self.path_input.clear()
        self.string_input.clear()
        self.result_label.setText('실행 전: 모든 필드를 채우고 "실행" 버튼을 누르세요.')
        self.result_label.setStyleSheet("padding: 10px; border: 1px solid #ccc; background-color: #f0f0f0;")

    def analyze_log(self):
        """
        '로그 분석' 버튼이 눌렸을 때 실행됩니다.
        CSV 파일을 분석하고 결과를 UI에 표시합니다.
        """

        log_analyzer = LogAnalyzer()
        csv_path = self.csv_path_input.text()

        if not csv_path:
            self.result_label.setText('CSV Path 필드를 채워야 로그 분석이 가능합니다.')
            self.result_label.setStyleSheet("padding: 10px; border: 1px solid orange; background-color: #fff8eb;")
            return

        try:
            # log_analyzer는 analyze() 메서드를 통해 AnalysisResult를 반환해야 합니다.
            self.analysis_result = log_analyzer.analyze(csv_path)

            # UI 업데이트
            result = self.analysis_result
            self.start_time_label.setText(result.first_time or 'N/A')
            self.end_time_label.setText(result.last_time or 'N/A')
            self.race_count_label.setText(str(result.total_race_count))

            # Race Selector 업데이트
            self.race_selector.clear()
            if result.total_race_count > 0:
                self.race_selector.addItem("전체 레이스")
                for i in range(1, result.total_race_count + 1):
                    self.race_selector.addItem(f"Race {i}")
                self.race_selector.setEnabled(True)
                
                self.result_label.setText(f'로그 분석 성공: 총 {result.total_race_count}개의 레이스가 발견되었습니다.')
                self.result_label.setStyleSheet("padding: 10px; border: 1px solid green; background-color: #ebfff0; min-height: 100px;")
            else:
                self.race_selector.addItem("레이스 없음")
                self.race_selector.setEnabled(False)
                self.result_label.setText('로그 분석 성공: 레이스가 발견되지 않았습니다.')
                self.result_label.setStyleSheet("padding: 10px; border: 1px solid orange; background-color: #fff8eb; min-height: 100px;")


        except Exception as e:
            self.analysis_result = None
            # 분석 결과 UI 초기화
            self.start_time_label.setText('N/A')
            self.end_time_label.setText('N/A')
            self.race_count_label.setText('N/A')
            self.race_selector.clear()
            self.race_selector.addItem("분석 실패")
            self.race_selector.setEnabled(False)

            self.result_label.setText(f'로그 분석 오류: {e}')
            self.result_label.setStyleSheet("padding: 10px; border: 1px solid red; background-color: #ffebeb; min-height: 100px;")


