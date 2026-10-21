"""
Testes unitários para a configuração do Apache Airflow no docker-compose.yml (BACK-017).
Valida estrutura YAML, serviços configurados, variáveis de ambiente e diretórios canônicos.
"""
from pathlib import Path
import unittest
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
COMPOSE_FILE = BASE_DIR / "docker-compose.yml"
ENV_EXAMPLE = BASE_DIR / ".env.example"


class TestAirflowSetup(unittest.TestCase):
    """Valida as configurações do Apache Airflow no docker-compose."""

    def test_docker_compose_exists_and_valid_yaml(self):
        """Valida se docker-compose.yml existe e possui sintaxe YAML válida."""
        self.assertTrue(COMPOSE_FILE.exists(), "docker-compose.yml deve existir.")

        with open(COMPOSE_FILE, "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)

        self.assertIn("services", compose)
        self.assertIn("volumes", compose)

    def test_airflow_services_configured(self):
        """Valida presença dos serviços essenciais do Apache Airflow."""
        with open(COMPOSE_FILE, "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)

        services = compose["services"]

        # Serviços obrigatórios
        required_services = [
            "postgres-airflow",
            "airflow-init",
            "airflow-webserver",
            "airflow-scheduler",
        ]
        for s in required_services:
            self.assertIn(s, services, f"Serviço '{s}' deve estar definido no docker-compose.yml.")

    def test_airflow_volumes_and_ports(self):
        """Valida mapeamento de volumes e porta do webserver."""
        with open(COMPOSE_FILE, "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)

        # Checa volumes declarados
        volumes = compose["volumes"]
        self.assertIn("airflow_postgres_data", volumes)

        # Checa porta do webserver
        webserver = compose["services"]["airflow-webserver"]
        self.assertIn("ports", webserver)
        port_mappings = [str(p) for p in webserver["ports"]]
        self.assertTrue(any("8080" in p for p in port_mappings))

    def test_airflow_directories_exist(self):
        """Valida se os diretórios dags/ e plugins/ existem na raiz do projeto."""
        dags_dir = BASE_DIR / "dags"
        plugins_dir = BASE_DIR / "plugins"

        self.assertTrue(dags_dir.exists(), "Diretório dags/ deve existir.")
        self.assertTrue(plugins_dir.exists(), "Diretório plugins/ deve existir.")

    def test_env_example_contains_airflow_vars(self):
        """Valida se .env.example documenta as variáveis de configuração do Airflow."""
        self.assertTrue(ENV_EXAMPLE.exists(), ".env.example deve existir.")
        content = ENV_EXAMPLE.read_text(encoding="utf-8")

        expected_vars = [
            "AIRFLOW_IMAGE_NAME",
            "AIRFLOW_UID",
            "_AIRFLOW_WWW_USER_USERNAME",
            "_AIRFLOW_WWW_USER_PASSWORD",
            "AIRFLOW_WEBSERVER_PORT",
        ]
        for var in expected_vars:
            self.assertIn(var, content, f"Variável '{var}' deve estar documentada em .env.example.")


if __name__ == "__main__":
    unittest.main()
