import os
import csv
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# --- 상수 및 열거형 정의 ---

class GPS_AREA(IntEnum):
    GPS_INIT = 0
    GPS_TRACKSENSOR_1 = 1
    # ... (생략된 GPS_TRACKSENSOR 2-9)
    GPS_TRACKSENSOR_2 = 2
    GPS_TRACKSENSOR_3 = 3
    GPS_TRACKSENSOR_4 = 4
    GPS_TRACKSENSOR_5 = 5
    GPS_TRACKSENSOR_6 = 6
    GPS_TRACKSENSOR_7 = 7
    GPS_TRACKSENSOR_8 = 8
    GPS_TRACKSENSOR_9 = 9
    GPS_RACE_START = 10
    GPS_RACE_END = 11
    GPS_UNKNOWN = 99

class GrSections(IntEnum):
    SECTION_ENTERING = 0
    SECTION_DOWNHILL = 1
    SECTION_UPHILLSTANDBY = 2
    SECTION_UPHILL = 3
    SECTION_UPHILLSLOWDOWN = 4
    SECTION_LANDINGIC = 5
    SECTION_LANDING = 6
    SECTION_GARAGE = 7
    SECTION_BOARDINGIC = 8
    SECTION_BOARDING = 9
    SECTION_UNKNOWN = 99

# --- 매핑 테이블 ---

MODE_TABLE: Dict[GrSections, str] = {
    GrSections.SECTION_ENTERING: "ENTERING",
    GrSections.SECTION_DOWNHILL: "DOWNHILL",
    GrSections.SECTION_UPHILLSTANDBY: "UPHILL_STANDBY",
    GrSections.SECTION_UPHILL: "UPHILL",
    GrSections.SECTION_UPHILLSLOWDOWN: "UPHILL_SLOWDOWN",
    GrSections.SECTION_LANDINGIC: "LANDING_IC",
    GrSections.SECTION_LANDING: "LANDING",
    GrSections.SECTION_GARAGE: "GARAGE",
    GrSections.SECTION_BOARDING: "BOARDING",
    GrSections.SECTION_BOARDINGIC: "BOARDING_IC"
}

STR_TO_ENUM: Dict[str, GrSections] = {v: k for k, v in MODE_TABLE.items()}

# --- 데이터 구조체 (UI 사용을 위한 로그 엔트리) ---

@dataclass
class LogEntry:
    """
    분석된 단일 로그 엔트리 구조체.
    UI에서 사용할 시간, 컨텍스트 및 원본 정보를 포함합니다.
    """
    time: str
    context: str  # 로그에 출력될 주 내용 (예: SECTION_DOWNHILL, GPS_RACE_START!!!)
    log_type: str # 로그 유형 (예: "SECTION_CHANGE", "RACE_EVENT", "INFO")
    area_id: Optional[GPS_AREA] = None  # 해당 시점의 GPS_AREA (UI 표시용)
    section_id: Optional[GrSections] = None # 해당 시점의 GrSections (UI 표시용)

@dataclass
class AnalysisResult:
    """
    전체 분석 결과를 담는 구조체.
    """
    first_time: Optional[str] = None
    last_time: Optional[str] = None
    total_race_count: int = 0
    logs: List[LogEntry] = field(default_factory=list)

# --- 메인 분석 클래스 ---
class LogAnalyzer:
    def __init__(self):
        """
        분석기 초기화.
        """
        self.result = AnalysisResult()
        self._prev_area: Optional[GPS_AREA] = None
        self._prev_section: Optional[GrSections] = None
        self._race_count: int = 0

    def _add_log(self, time: str, context: str, log_type: str, area_id: Optional[GPS_AREA] = None, section_id: Optional[GrSections] = None):
        """
        AnalysisResult의 logs 리스트에 LogEntry를 추가합니다.
        """
        self.result.logs.append(LogEntry(
            time=time,
            context=context,
            log_type=log_type,
            area_id=area_id,
            section_id=section_id
        ))

    def analyze(self, csv_path: str) -> AnalysisResult:
        """
        CSV 파일을 분석하고 결과를 AnalysisResult 구조체로 반환합니다.
        """
        self.result = AnalysisResult()
        self._prev_area = None
        self._prev_section = None
        self._race_count = 0

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # 필드명 공백 제거
            reader.fieldnames = [name.strip() for name in reader.fieldnames]

            area_key = next((k for k in reader.fieldnames if k.strip().lower() == "area"), None)
            section_key = next((k for k in reader.fieldnames if k.strip().lower() == "section"), None)

            if not section_key:
                raise KeyError("CSV에 'section' 열이 없습니다.")

            for i, row in enumerate(reader):
                time = row["time"].strip()
                if i == 0:
                    self.result.first_time = time
                self.result.last_time = time

                # section 값 처리
                section_str = row[section_key].strip()
                section_id = STR_TO_ENUM.get(section_str, GrSections.SECTION_UNKNOWN)

                # area 값 처리
                current_area_id = GPS_AREA.GPS_UNKNOWN
                try:
                    if area_key and row[area_key].strip():
                        area_int = int(row[area_key])
                        current_area_id = GPS_AREA(area_int)
                except (ValueError, KeyError):
                    pass # current_area_id는 GPS_UNKNOWN 유지

                # race_count 증가: SECTION_BOARDINGIC 진입 시
                if section_id == GrSections.SECTION_BOARDINGIC and self._prev_section != GrSections.SECTION_BOARDINGIC:
                    self._race_count += 1
                    # 레이스 시작 마커 로그 추가
                    self._add_log(time, f"============== RACE {self._race_count} START ==============", "RACE_INFO", current_area_id, section_id)


                # section 변경 로그
                if self._prev_section is not None and section_id != self._prev_section:
                    context = MODE_TABLE.get(section_id, "SECTION_UNKNOWN")
                    self._add_log(time, context, "SECTION_CHANGE", current_area_id, section_id)

                # area 체크 (레이스 시작/종료 이벤트)
                if current_area_id == GPS_AREA.GPS_RACE_START and self._prev_area != current_area_id:
                    self._add_log(time, "GPS_RACE_START!!!", "RACE_EVENT", current_area_id, section_id)
                
                if current_area_id == GPS_AREA.GPS_RACE_END and self._prev_area != current_area_id:
                    self._add_log(time, "GPS_RACE_END!!!", "RACE_EVENT", current_area_id, section_id)

                # 상태 업데이트
                self._prev_area = current_area_id
                self._prev_section = section_id

        self.result.total_race_count = self._race_count
        return self.result

    def save_logs_to_txt(self, result: AnalysisResult, output_dir: str = "."):
        """
        AnalysisResult 구조체를 기반으로 원본과 동일한 포맷의 텍스트 파일을 생성합니다.
        """
        if not result.first_time or not result.last_time:
             print("분석 결과가 비어있어 파일을 저장할 수 없습니다.")
             return

        # 파일명에 시간대 사용 (':' -> '_' 변환)
        file_name = f"{result.first_time.replace(':', '_')}~{result.last_time.replace(':', '_')}.txt"
        file_path = os.path.join(output_dir, file_name)

        os.makedirs(output_dir, exist_ok=True)
        
        output_lines = []
        
        # 헤더 정보 추가
        output_lines.append(f"전체 시간대: {result.first_time} - {result.last_time}\n")
        output_lines.append(f"총 레이스 횟수: {result.total_race_count}\n\n")

        # 로그 엔트리 추가
        for entry in result.logs:
            if entry.log_type == "RACE_INFO":
                # 레이스 구분선은 별도 포맷으로 출력
                output_lines.append(f"\n{entry.context}\n")
            else:
                # 일반 로그 포맷: [time]     context
                output_lines.append(f"[{entry.time}]     {entry.context}\n")

        with open(file_path, "w", encoding="utf-8") as f_out:
            f_out.writelines(output_lines)

        print(f"로그가 저장되었습니다: {file_path}")

