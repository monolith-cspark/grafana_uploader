import os
import csv
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple

# --- 상수 및 열거형 정의 ---

class GPS_AREA(IntEnum):
    GPS_INIT = 0
    GPS_TRACKSENSOR_1 = 1
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
    race_times: Dict[int, Dict[str, Optional[str]]] = field(default_factory=dict)
    
    # 섹션 변경 시점의 시간을 기록
    # {race_num: [(section_id_1, time_1), (section_id_2, time_2), ...]}
    # 레이스별 섹션 변경 이벤트(섹션 ID와 시간)를 시간 순서대로 저장
    race_section_changes: Dict[int, List[Tuple[GrSections, str]]] = field(default_factory=dict)

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
        
    def _add_section_change_log(self, time: str, current_area_id: GPS_AREA, section_id: GrSections):
        """
        섹션 변경이 발생했을 때 _add_log에 기록하고 race_section_changes에 항목을 추가합니다.
        """
        # 1. 상세 로그 (res.logs)에 기록
        context = MODE_TABLE.get(section_id, "SECTION_UNKNOWN")
        self._add_log(time, context, "SECTION_CHANGE", current_area_id, section_id)
        self._record_section_change(section_id, time)
            
    def _record_section_change(self, section_id: GrSections, time: str):
        """
        현재 레이스의 섹션 변경 리스트에 (section_id, time)을 중복 없이 기록합니다.
        """
        new_entry = (section_id, time)
        changes_list = self.result.race_section_changes.setdefault(self._race_count, [])
        
        # 마지막 항목과 동일한 (ID, 시간)이면 추가하지 않습니다.
        if not changes_list or changes_list[-1] != new_entry:
            changes_list.append(new_entry)
            
    def analyze(self, csv_path: str) -> AnalysisResult:
        """
        CSV 파일을 분석하고 결과를 AnalysisResult 구조체로 반환합니다.
        Race 0은 SECTION_BOARDINGIC (Race 1의 시작) 이전에 발생하는 모든 로그를 포괄합니다.
        """
        self.result = AnalysisResult()
        self._prev_area = None
        self._prev_section = None
        self._race_count = 0  # Race 0부터 시작

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                reader.fieldnames = [name.strip() for name in reader.fieldnames]

                area_key = next((k for k in reader.fieldnames if k.strip().lower() == "area"), None)
                section_key = next((k for k in reader.fieldnames if k.strip().lower() == "section"), None)

                if not section_key:
                    raise KeyError("CSV에 'section' 열이 없습니다.")

                time = ""
                for i, row in enumerate(reader):
                    time = row["time"].strip()
                    
                    # 1. 섹션 및 영역 ID 파싱 (기존 로직 유지)
                    section_str = row[section_key].strip()
                    section_id = STR_TO_ENUM.get(section_str, GrSections.SECTION_UNKNOWN)
                    current_area_id = GPS_AREA.GPS_UNKNOWN
                    
                    try:
                        if area_key and row[area_key].strip():
                            area_int = int(row[area_key])
                            current_area_id = GPS_AREA(area_int)
                    except (ValueError, KeyError):
                        pass

                    # 2. 첫 번째 로그 초기화 (Race 0 시작)
                    if i == 0:
                        # Race 0 시작. Race가 시작되기 전의 모든 로그를 포함합니다.
                        self._race_count = 0 
                        self.result.first_time = time
                        self.result.race_times[self._race_count] = {"start": time, "end": None}
                        
                        self._add_log(time, f"============== RACE {self._race_count} START ==============", "RACE_INFO", current_area_id, section_id)
                        self._add_section_change_log(time, area_int, section_id)
                        
                        self._prev_area = current_area_id
                        self._prev_section = section_id
                        continue 

                    # 3. Race 종료/시작 (SECTION_BOARDINGIC) 처리
                    is_boarding_ic_start = (
                        section_id == GrSections.SECTION_BOARDINGIC and self._prev_section != GrSections.SECTION_BOARDINGIC
                    )
                    
                    if is_boarding_ic_start:
                        # 이전 레이스 종료 시간 기록 (Race 0 또는 Race N)
                        if self._race_count in self.result.race_times:
                            self.result.race_times[self._race_count]["end"] = time
                        
                        # 이전 레이스의 마지막 event 기록
                        self._add_section_change_log(time, area_int, section_id)
                            
                                            
                        # 새로운 레이스 시작 (Race N+1)
                        self._race_count += 1
                        self._add_log(time, f"============== RACE {self._race_count} START ==============", "RACE_INFO", current_area_id, section_id)
                        self._add_section_change_log(time, area_int, section_id)
                        
                        # 새 레이스 시간/섹션 기록
                        self.result.race_times[self._race_count] = {"start": time, "end": None}
                        
                    # 4. 일반 Section 변경 로그 및 기록
                    elif section_id != self._prev_section:
                        self._add_section_change_log(time, area_int, section_id)

                    # 5. Area 체크 (GPS_RACE_START/END 이벤트) - 주석 처리된 부분 복원
                    # if current_area_id != self._prev_area:
                    #     if current_area_id == GPS_AREA.GPS_RACE_START:
                    #         self._add_log(time, "GPS_RACE_START !!!", "RACE_EVENT", current_area_id, section_id)
                    #     elif current_area_id == GPS_AREA.GPS_RACE_END:
                    #         self._add_log(time, "GPS_RACE_END !!!", "RACE_EVENT", current_area_id, section_id)
                            
                    # 6. 상태 업데이트 (다음 루프를 위해)
                    self._prev_area = current_area_id
                    self._prev_section = section_id

            # ===================================================
            # 7. 최종 상태 기록 (루프 종료 후)
            # ===================================================
            self.result.last_time = time # 전체 로그 최종 시간
            
            # 현재 활성화된 마지막 레이스(Race 0 또는 Race N)의 종료 시간 기록
            if self._race_count in self.result.race_times:
                self.result.race_times[self._race_count]["end"] = time 

            # 최종 섹션 상태를 명시적으로 기록 
            self._add_section_change_log(time, area_int, section_id)

            # total_race_count는 Race 1부터 Race N까지만 세는 것이 일반적이므로, 
            # Race 0을 제외한 레이스 개수를 계산합니다.
            self.result.total_race_count = max(0, self._race_count)

            return self.result

        except KeyError as e:
            raise e
        except Exception as e:
            print(f"로그 분석 중 오류 발생: {e}")
            raise e

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


if __name__ == '__main__':
    # LogAnalyzer 인스턴스 생성
    logger = LogAnalyzer()
    
    try:
        res = logger.analyze("./csv/log_out.csv")

        # 1. 전체 요약 정보 출력
        print(f"전체 시간대: {res.first_time} - {res.last_time}")
        print(f"총 레이스 횟수 (Race 1~N): {res.total_race_count}")
                
        for log_entry in res.logs:
                    # log_entry 객체의 속성을 직접 참조하여 출력합니다.
                    # (GrSections를 문자열 이름으로 변환하는 MODE_TABLE 사용)
                    
                    # 섹션 이름을 문자열로 변환 (MODE_TABLE 사용 가정)
                    section_name = MODE_TABLE.get(log_entry.section_id, str(log_entry.section_id))
                    
                    # 출력 형식에 맞게 문자열 포매팅
                    print(
                        f"{log_entry.time:<25} | "
                        f"{section_name:<15} | "
                        f"{log_entry.context}"
                    )
        
        
    except KeyError as e:
        print(f"\n[오류] CSV 파일에 필수 열이 없습니다: {e}")
    except FileNotFoundError:
        print(f"\n[오류] 파일을 찾을 수 없습니다. 경로를 확인해주세요: './csv/log_out.csv'")
    except Exception as e:
        print(f"\n[오류] 분석 중 예기치 않은 오류 발생: {e}")