"""
장비 사용 데이터를 pickle 파일로 변환하는 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pickle
import gzip
import json
from datetime import datetime
import logging
from src.data.equipment_processors import (
    process_eam_data, process_lams_data, process_mes_data, 
    merge_equipment_data, create_o_tags_from_equipment
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def save_pickle(df, filename):
    """DataFrame을 압축된 pickle 파일로 저장"""
    output_path = f'data/pickles/{filename}'
    with gzip.open(output_path, 'wb') as f:
        pickle.dump(df, f)
    logger.info(f"Pickle 파일 저장: {output_path}")
    return output_path

def update_upload_config(data_type, file_names, row_count):
    """upload_config.json 업데이트"""
    config_path = 'config/upload_config.json'
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # upload_config 섹션에 추가
    if 'upload_config' not in config:
        config['upload_config'] = {}
    
    config['upload_config'][data_type] = {
        "files": [],
        "file_names": file_names,
        "pickle_exists": True,
        "dataframe_name": data_type.lower() + "_data",
        "last_modified": datetime.now().isoformat(),
        "row_count": row_count
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    logger.info(f"upload_config.json 업데이트 완료: {data_type}")

def main():
    """메인 처리 함수"""
    # 타임스탬프 생성
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # EAM 데이터 처리
    logger.info("\n=== EAM 데이터 처리 ===")
    try:
        eam_file = 'data/EAM(안전설비시스템)_로그인 이력_250601~250715.xlsx'
        eam_df = pd.read_excel(eam_file)
        eam_processed = process_eam_data(eam_df)
        
        # Pickle 저장
        eam_pickle = save_pickle(eam_processed, f'eam_data_v{timestamp}.pkl.gz')
        update_upload_config('EAM', [os.path.basename(eam_file)], len(eam_processed))
        
    except Exception as e:
        logger.error(f"EAM 데이터 처리 중 오류: {e}")
        eam_processed = None
    
    # LAMS 데이터 처리
    logger.info("\n=== LAMS 데이터 처리 ===")
    try:
        lams_file = 'data/LAMS(품질시스템) 스케쥴 작성, 수정 이력_2506.xlsx'
        lams_df = pd.read_excel(lams_file)
        lams_processed = process_lams_data(lams_df)
        
        # Pickle 저장
        lams_pickle = save_pickle(lams_processed, f'lams_data_v{timestamp}.pkl.gz')
        update_upload_config('LAMS', [os.path.basename(lams_file)], len(lams_processed))
        
    except Exception as e:
        logger.error(f"LAMS 데이터 처리 중 오류: {e}")
        lams_processed = None
    
    # MES 데이터 처리
    logger.info("\n=== MES 데이터 처리 ===")
    mes_files = [
        'data/MES(생산시스템)_003 로그인 이력_250601~0717.xlsx',
        'data/MES(생산시스템)_005 로그인 이력_250601~0717.xlsx'
    ]
    
    mes_dfs = []
    for mes_file in mes_files:
        try:
            logger.info(f"처리 중: {mes_file}")
            mes_df = pd.read_excel(mes_file)
            mes_processed = process_mes_data(mes_df)
            mes_dfs.append(mes_processed)
        except Exception as e:
            logger.error(f"MES 데이터 처리 중 오류 ({mes_file}): {e}")
    
    if mes_dfs:
        # MES 데이터 통합
        mes_combined = pd.concat(mes_dfs, ignore_index=True)
        logger.info(f"MES 데이터 통합: {len(mes_combined)}개 레코드")
        
        # Pickle 저장
        mes_pickle = save_pickle(mes_combined, f'mes_data_v{timestamp}.pkl.gz')
        update_upload_config('MES', [os.path.basename(f) for f in mes_files], len(mes_combined))
    else:
        mes_combined = None
    
    # 전체 장비 데이터 통합
    logger.info("\n=== 전체 장비 데이터 통합 ===")
    equipment_merged = merge_equipment_data(
        eam_df=eam_processed if eam_processed is not None else None,
        lams_df=lams_processed if lams_processed is not None else None,
        mes_df=mes_combined if mes_combined is not None else None
    )
    
    if len(equipment_merged) > 0:
        # 통합 데이터 Pickle 저장
        equipment_pickle = save_pickle(equipment_merged, f'equipment_data_merged_v{timestamp}.pkl.gz')
        
        # O 태그 생성
        logger.info("\n=== O 태그 생성 ===")
        o_tags = create_o_tags_from_equipment(equipment_merged)
        o_tags_df = pd.DataFrame(o_tags)
        
        if len(o_tags_df) > 0:
            o_tags_pickle = save_pickle(o_tags_df, f'o_tags_equipment_v{timestamp}.pkl.gz')
            logger.info(f"O 태그 데이터 저장 완료: {len(o_tags_df)}개")
        
        # 통계 출력
        logger.info("\n=== 처리 완료 통계 ===")
        logger.info(f"EAM: {len(eam_processed) if eam_processed is not None else 0:,}개")
        logger.info(f"LAMS: {len(lams_processed) if lams_processed is not None else 0:,}개")
        logger.info(f"MES: {len(mes_combined) if mes_combined is not None else 0:,}개")
        logger.info(f"통합: {len(equipment_merged):,}개")
        logger.info(f"O 태그: {len(o_tags_df) if len(o_tags_df) > 0 else 0:,}개")
        
        # metadata 업데이트
        metadata_path = 'data/pickles/metadata.json'
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {"datasets": {}}
        
        metadata['datasets']['equipment_data'] = {
            "timestamp": timestamp,
            "total_records": len(equipment_merged),
            "o_tags_generated": len(o_tags_df) if len(o_tags_df) > 0 else 0,
            "systems": {
                "EAM": len(eam_processed) if eam_processed is not None else 0,
                "LAMS": len(lams_processed) if lams_processed is not None else 0,
                "MES": len(mes_combined) if mes_combined is not None else 0
            }
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

if __name__ == "__main__":
    main()