 🔄 백업 프로세스 상세 설명

  1. 암호화 스크립트 실행 시 (encrypt_db.py)

  python scripts/encrypt_db.py encrypt --db-path data/sambio_human.db --chunk-size 50

  실행 과정:
  1. 비밀번호 입력 프롬프트 표시
  2. 640MB DB 파일을 gzip으로 압축 (→ 약 300-400MB)
  3. 압축된 파일을 50MB 단위로 암호화하여 분할
  4. 결과물:
  data/encrypted_chunks/
  ├── sambio_human.enc.000  (50MB)
  ├── sambio_human.enc.001  (50MB)
  ├── sambio_human.enc.002  (50MB)
  ├── ...
  ├── sambio_human.enc.007  (약 40MB)
  └── sambio_human.metadata.json

  2. 백업 스크립트 실행 시 (backup_db.sh)

  ./scripts/backup_db.sh

  실행 과정:
  1. 암호화: encrypt_db.py 자동 실행
  2. Git 브랜치 생성: db-backup 브랜치로 전환
  3. 파일 추가:
  git add data/encrypted_chunks/
  git commit -m "🔐 Encrypted DB backup - 20250131_120000"
  4. GitHub 푸시:
  git push origin db-backup
  5. 정리: 로컬 암호화 파일 삭제 여부 확인
  6. 복귀: main 브랜치로 돌아감

  3. GitHub 저장소 구조

  GitHub Repository
  ├── main branch (코드만)
  │   ├── src/
  │   ├── scripts/
  │   └── (DB 파일 없음)
  │
  └── db-backup branch (암호화된 백업)
      └── data/encrypted_chunks/
          ├── sambio_human.enc.000
          ├── sambio_human.enc.001
          ├── ...
          └── sambio_human.metadata.json

  ⚠️ 실행 전 준비사항

  1. 필요한 패키지 설치

  pip install cryptography

  2. Git 설정 확인

  # 현재 브랜치 확인
  git branch

  # 변경사항 커밋
  git add .
  git commit -m "작업 저장"

  3. 첫 실행 예시

  # 1. 테스트로 암호화만 해보기
  python scripts/encrypt_db.py encrypt --db-path data/sambio_human.db
  # 비밀번호 입력: ********

  # 2. 결과 확인
  ls -lah data/encrypted_chunks/

  # 3. 전체 백업 프로세스 실행
  ./scripts/backup_db.sh

  🔑 복원 방법

  # 1. 백업 브랜치에서 파일 가져오기
  git checkout db-backup
  git pull origin db-backup

  # 2. 복호화
  python scripts/encrypt_db.py decrypt --encrypted-dir data/encrypted_chunks
  # 동일한 비밀번호 입력

  # 3. 복원된 파일 확인
  ls -lah sambio_human_restored.db

  💡 주의사항

  1. 비밀번호 관리:
    - 암호화 비밀번호를 안전하게 보관
    - 비밀번호 분실 시 복원 불가
  2. 브랜치 전략:
    - main: 코드만
    - db-backup: 암호화된 DB 백업
  3. 저장 공간:
    - 각 백업마다 새로운 커밋 생성
    - 주기적으로 오래된 백업 정리 필요

  이렇게 하면 GitHub의 100MB 제한을 우회하면서도 안전하게 DB를 백업할 수 있습니다!