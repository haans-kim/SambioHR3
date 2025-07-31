#!/usr/bin/env python3
"""
데이터베이스 파일 암호화 및 분할 스크립트
GitHub 업로드를 위해 대용량 DB 파일을 암호화하고 작은 조각으로 분할
"""

import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import getpass
import argparse
import gzip
import json
from datetime import datetime

class DBEncryptor:
    def __init__(self, password: str):
        """암호화 키 생성"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'sambio_hr_salt_2025',  # 실제로는 랜덤 salt 사용 권장
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher = Fernet(key)
    
    def encrypt_and_split(self, db_path: str, chunk_size_mb: int = 50):
        """DB 파일을 암호화하고 분할"""
        db_path = Path(db_path)
        if not db_path.exists():
            raise FileNotFoundError(f"DB 파일을 찾을 수 없습니다: {db_path}")
        
        # 출력 디렉토리 생성
        output_dir = db_path.parent / "encrypted_chunks"
        output_dir.mkdir(exist_ok=True)
        
        # 메타데이터
        metadata = {
            "original_file": db_path.name,
            "created_at": datetime.now().isoformat(),
            "file_size": db_path.stat().st_size,
            "chunks": []
        }
        
        print(f"1. DB 파일 압축 중...")
        # 먼저 압축
        compressed_path = output_dir / f"{db_path.stem}.gz"
        with open(db_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb', compresslevel=9) as f_out:
                f_out.write(f_in.read())
        
        compressed_size = compressed_path.stat().st_size
        print(f"   압축 완료: {db_path.stat().st_size / 1024 / 1024:.1f}MB → {compressed_size / 1024 / 1024:.1f}MB")
        
        print(f"2. 암호화 및 분할 중...")
        chunk_size = chunk_size_mb * 1024 * 1024
        chunk_num = 0
        
        with open(compressed_path, 'rb') as f:
            while True:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break
                
                # 청크 암호화
                encrypted_chunk = self.cipher.encrypt(chunk_data)
                
                # 청크 저장
                chunk_filename = f"{db_path.stem}.enc.{chunk_num:03d}"
                chunk_path = output_dir / chunk_filename
                
                with open(chunk_path, 'wb') as chunk_file:
                    chunk_file.write(encrypted_chunk)
                
                metadata["chunks"].append({
                    "filename": chunk_filename,
                    "size": len(encrypted_chunk),
                    "order": chunk_num
                })
                
                print(f"   청크 {chunk_num} 생성: {chunk_filename} ({len(encrypted_chunk) / 1024 / 1024:.1f}MB)")
                chunk_num += 1
        
        # 압축 파일 삭제
        compressed_path.unlink()
        
        # 메타데이터 저장
        metadata_path = output_dir / f"{db_path.stem}.metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n✅ 암호화 완료!")
        print(f"   총 {chunk_num}개의 청크 생성")
        print(f"   출력 디렉토리: {output_dir}")
        
        return output_dir
    
    def decrypt_and_merge(self, encrypted_dir: str, output_path: str = None):
        """암호화된 청크들을 복호화하고 병합"""
        encrypted_dir = Path(encrypted_dir)
        
        # 메타데이터 로드
        metadata_files = list(encrypted_dir.glob("*.metadata.json"))
        if not metadata_files:
            raise FileNotFoundError("메타데이터 파일을 찾을 수 없습니다")
        
        with open(metadata_files[0], 'r') as f:
            metadata = json.load(f)
        
        if output_path is None:
            output_path = Path.cwd() / metadata["original_file"]
        else:
            output_path = Path(output_path)
        
        print(f"1. 청크 복호화 및 병합 중...")
        temp_path = output_path.with_suffix('.gz')
        
        with open(temp_path, 'wb') as output_file:
            for chunk_info in sorted(metadata["chunks"], key=lambda x: x["order"]):
                chunk_path = encrypted_dir / chunk_info["filename"]
                
                with open(chunk_path, 'rb') as chunk_file:
                    encrypted_data = chunk_file.read()
                    decrypted_data = self.cipher.decrypt(encrypted_data)
                    output_file.write(decrypted_data)
                
                print(f"   청크 {chunk_info['order']} 복호화 완료")
        
        print(f"2. 압축 해제 중...")
        with gzip.open(temp_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                f_out.write(f_in.read())
        
        temp_path.unlink()
        
        print(f"\n✅ 복호화 완료!")
        print(f"   출력 파일: {output_path}")
        print(f"   파일 크기: {output_path.stat().st_size / 1024 / 1024:.1f}MB")

def main():
    parser = argparse.ArgumentParser(description="DB 파일 암호화/복호화 도구")
    parser.add_argument("action", choices=["encrypt", "decrypt"], help="수행할 작업")
    parser.add_argument("--db-path", help="암호화할 DB 파일 경로")
    parser.add_argument("--encrypted-dir", help="암호화된 청크 디렉토리")
    parser.add_argument("--output", help="출력 경로")
    parser.add_argument("--chunk-size", type=int, default=50, help="청크 크기 (MB)")
    parser.add_argument("--password", help="암호화 비밀번호 (미입력시 프롬프트)")
    
    args = parser.parse_args()
    
    # 비밀번호 입력
    if args.password:
        password = args.password
    else:
        password = getpass.getpass("암호화 비밀번호 입력: ")
    
    encryptor = DBEncryptor(password)
    
    if args.action == "encrypt":
        if not args.db_path:
            parser.error("--db-path 필수")
        encryptor.encrypt_and_split(args.db_path, args.chunk_size)
    
    elif args.action == "decrypt":
        if not args.encrypted_dir:
            parser.error("--encrypted-dir 필수")
        encryptor.decrypt_and_merge(args.encrypted_dir, args.output)

if __name__ == "__main__":
    main()