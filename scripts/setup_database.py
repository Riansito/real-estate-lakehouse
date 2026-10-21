"""
Script de inicialização e aplicação de DDLs no PostgreSQL (Data Warehouse).
Executa as instruções SQL da pasta sql/ddl/ de forma transacional e idempotente.
"""
import os
from pathlib import Path
import sys
from dotenv import load_dotenv
from loguru import logger
import psycopg

# Carrega variáveis de ambiente
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


def apply_ddl(ddl_path: Path) -> bool:
    """Executa um arquivo SQL de DDL no PostgreSQL."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("Variável DATABASE_URL não configurada no arquivo .env.")
        return False

    if not ddl_path.exists():
        logger.error(f"Arquivo DDL não encontrado: {ddl_path}")
        return False

    sql_content = ddl_path.read_text(encoding="utf-8")
    logger.info(f"Aplicando DDL: {ddl_path.name}...")

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql_content)
            conn.commit()
        logger.info(f"DDL '{ddl_path.name}' aplicado com sucesso! ✅")
        return True
    except Exception as err:
        logger.error(f"Erro ao aplicar DDL '{ddl_path.name}': {err}")
        return False


def verify_raw_schema() -> bool:
    """Verifica se o schema e a tabela landing_anuncios foram criados corretamente com seus índices."""
    db_url = os.getenv("DATABASE_URL")
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # 1. Verifica existência da tabela
                cur.execute("""
                    SELECT table_schema, table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'raw' AND table_name = 'landing_anuncios';
                """)
                table = cur.fetchone()
                if not table:
                    logger.error("Tabela raw.landing_anuncios não encontrada.")
                    return False
                logger.info(f"Tabela encontrada: {table[0]}.{table[1]} ✅")

                # 2. Lista as colunas e tipos
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'raw' AND table_name = 'landing_anuncios'
                    ORDER BY ordinal_position;
                """)
                columns = cur.fetchall()
                logger.info("Estrutura das colunas:")
                for col, dtype, nullable in columns:
                    logger.info(f"  - {col} ({dtype}) | Nullable: {nullable}")

                # 3. Lista os índices criados
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'raw' AND tablename = 'landing_anuncios';
                """)
                indexes = cur.fetchall()
                logger.info(f"Índices ativos ({len(indexes)}):")
                for idx_name, _ in indexes:
                    logger.info(f"  - {idx_name}")

        return True
    except Exception as err:
        logger.error(f"Erro na verificação da tabela raw.landing_anuncios: {err}")
        return False


def main():
    logger.info("=" * 60)
    logger.info("INICIALIZAÇÃO DO SCHEMA RAW - DATA LAKEHOUSE")
    logger.info("=" * 60)

    ddl_file = BASE_DIR / "sql" / "ddl" / "01_create_raw_landing_anuncios.sql"
    success = apply_ddl(ddl_file)

    if success:
        verified = verify_raw_schema()
        if verified:
            logger.info("=" * 60)
            logger.info("SCHEMA RAW E TABELA LANDING CONFIGURADOS COM SUCESSO! 🚀")
            logger.info("=" * 60)
            sys.exit(0)

    logger.error("Falha ao configurar schema raw.")
    sys.exit(1)


if __name__ == "__main__":
    main()
