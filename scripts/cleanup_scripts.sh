#!/bin/bash
# 스크립트 정리 작업

echo "스크립트 정리를 시작합니다..."

# 1. Debug 스크립트 이동
echo "Debug 스크립트 이동 중..."
mv scripts/check_*.py scripts/debug/ 2>/dev/null
mv scripts/debug_*.py scripts/debug/ 2>/dev/null
mv scripts/read_transition_probabilities.py scripts/debug/ 2>/dev/null

# 2. Archive 스크립트 이동
echo "구버전 및 일회성 스크립트 Archive로 이동 중..."
mv scripts/upload_tag_location_master.py scripts/archive/ 2>/dev/null
mv scripts/upload_tag_location_master_v2.py scripts/archive/ 2>/dev/null
mv scripts/fix_tag_mapping.py scripts/archive/ 2>/dev/null
mv scripts/generate_o_tags.py scripts/archive/ 2>/dev/null
mv scripts/fix_gate_tags.py scripts/archive/ 2>/dev/null
mv scripts/convert_hmm_rules.py scripts/archive/ 2>/dev/null
mv scripts/extract_transition_data.py scripts/archive/ 2>/dev/null
mv scripts/load_existing_tag_mapping.py scripts/archive/ 2>/dev/null

# 3. Active 스크립트 이동
echo "Active 스크립트 이동 중..."
mv scripts/process_equipment_data.py scripts/active/ 2>/dev/null
mv scripts/generate_o_tags_fast.py scripts/active/ 2>/dev/null
mv scripts/map_locations_to_tags.py scripts/active/ 2>/dev/null
mv scripts/upload_tag_location_master_v3.py scripts/active/ 2>/dev/null
mv scripts/create_tag_tables.py scripts/active/ 2>/dev/null
mv scripts/initialize_transition_rules.py scripts/active/ 2>/dev/null
mv scripts/fix_tag_mapping_v2.py scripts/active/ 2>/dev/null
mv scripts/analyze_individual_with_tags.py scripts/active/ 2>/dev/null
mv scripts/analyze_duration.py scripts/active/ 2>/dev/null
mv scripts/analyze_work_status.py scripts/active/ 2>/dev/null
mv scripts/compare_systems.py scripts/active/ 2>/dev/null

# track_changes.py는 scripts 루트에 유지 (특수 용도)

echo "정리 완료!"
echo ""
echo "결과:"
echo "- Active 스크립트: $(ls scripts/active/*.py 2>/dev/null | wc -l)개"
echo "- Debug 스크립트: $(ls scripts/debug/*.py 2>/dev/null | wc -l)개"
echo "- Archive 스크립트: $(ls scripts/archive/*.py 2>/dev/null | wc -l)개"
echo ""
echo "남은 파일:"
ls scripts/*.py scripts/*.sh scripts/*.txt scripts/*.csv 2>/dev/null