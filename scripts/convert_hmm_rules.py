#!/usr/bin/env python3
"""
HMM 도메인 지식 기반 전이 확률을 JSON 규칙으로 변환하는 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.hmm import HMMModel
from src.hmm.rule_converter import HMMRuleConverter
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """메인 함수"""
    try:
        # HMM 모델 생성 및 초기화
        logger.info("HMM 모델 생성 중...")
        hmm_model = HMMModel("sambio_work_activity_hmm")
        hmm_model.initialize_parameters("domain_knowledge")
        
        # 규칙 변환기 생성
        logger.info("규칙 변환 시작...")
        converter = HMMRuleConverter(hmm_model)
        
        # 규칙 추출 및 저장
        output_path = converter.save_rules_to_file()
        logger.info(f"규칙이 저장되었습니다: {output_path}")
        
        # 기존 규칙과 병합 (옵션)
        existing_rules_path = "config/rules/transition_rules.json"
        if Path(existing_rules_path).exists():
            logger.info("기존 규칙과 병합 중...")
            merged_path = converter.merge_with_existing_rules(
                existing_rules_path,
                "config/rules/merged_transition_rules.json"
            )
            logger.info(f"병합된 규칙이 저장되었습니다: {merged_path}")
        
        logger.info("변환 완료!")
        
    except Exception as e:
        logger.error(f"오류 발생: {e}")
        raise

if __name__ == "__main__":
    main()