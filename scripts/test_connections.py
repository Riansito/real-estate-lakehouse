"""
Script de validação de conectividade com a infraestrutura (PostgreSQL e S3 Data Lake).
Executa testes de ping, listagem de buckets e verificação de schemas.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carrega o arquivo .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

def test_database():
    print("\n[1/2] Testando conexão com PostgreSQL (Data Warehouse)...")
    import psycopg
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("  ERRO: DATABASE_URL não configurada no .env")
        return False
        
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"  OK: Conectado com sucesso ao PostgreSQL!")
                print(f"  Versão: {version.split()[0]} {version.split()[1]}")
                
                # Cria schema raw se não existir
                cur.execute("CREATE SCHEMA IF NOT EXISTS raw;")
                conn.commit()
                print("  OK: Schema 'raw' validado/criado com sucesso.")
        return True
    except Exception as e:
        print(f"  FALHA na conexão com o banco de dados: {e}")
        return False

def test_datalake():
    print("\n[2/2] Testando conexão com Data Lake (S3-compatible Storage)...")
    import boto3
    
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3")
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    region = os.environ.get("AWS_REGION", "us-east-2")
    target_bucket = os.environ.get("S3_BUCKET_NAME", "raw-imoveis")
    
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        response = s3.list_buckets()
        buckets = [b["Name"] for b in response.get("Buckets", [])]
        print(f"  OK: Conexão S3 autenticada com sucesso!")
        print(f"  Buckets disponíveis: {buckets}")
        
        if target_bucket in buckets:
            print(f"  OK: Bucket alvo '{target_bucket}' encontrado e pronto para uso!")
        else:
            print(f"  Criando bucket alvo '{target_bucket}'...")
            s3.create_bucket(Bucket=target_bucket)
            print(f"  OK: Bucket '{target_bucket}' criado com sucesso!")
            
        # Teste de escrita e leitura de um arquivo de probe
        probe_key = "_healthcheck/probe.txt"
        s3.put_object(Bucket=target_bucket, Key=probe_key, Body=b"healthcheck_ok")
        s3.delete_object(Bucket=target_bucket, Key=probe_key)
        print("  OK: Permissões de escrita e exclusão validadas no bucket!")
        return True
    except Exception as e:
        print(f"  FALHA na conexão com o Data Lake S3: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("VALIDAÇÃO DA INFRAESTRUTURA - REAL ESTATE LAKEHOUSE")
    print("=" * 60)
    
    db_ok = test_database()
    lake_ok = test_datalake()
    
    print("\n" + "=" * 60)
    if db_ok and lake_ok:
        print("RESULTADO: TODOS OS SERVIÇOS ESTÃO OPERACIONAIS E CONECTADOS! ✅")
        print("=" * 60)
        sys.exit(0)
    else:
        print("RESULTADO: HOUVE FALHA EM UM OU MAIS SERVIÇOS. ❌")
        print("=" * 60)
        sys.exit(1)
