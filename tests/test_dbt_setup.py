"""
Testes unitários para a configuração inicial do projeto dbt_imoveis.
Valida arquivos de configuração, sintaxe YAML e caminhos do projeto.
"""
from pathlib import Path
import unittest
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = BASE_DIR / "dbt_imoveis"


class TestDbtSetup(unittest.TestCase):
    """Valida a estrutura e configurações do projeto dbt."""

    def test_dbt_project_yml(self):
        """Valida se dbt_project.yml existe e possui configurações de schemas."""
        project_file = DBT_DIR / "dbt_project.yml"
        self.assertTrue(project_file.exists(), "dbt_project.yml deve existir.")

        with open(project_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.assertEqual(data.get("name"), "dbt_imoveis")
        self.assertEqual(data.get("profile"), "dbt_imoveis")
        self.assertIn("models", data)
        self.assertIn("snapshots", data)

        # Checa configurações de schemas das camadas
        models_cfg = data["models"]["dbt_imoveis"]
        self.assertEqual(models_cfg["staging"]["+schema"], "staging")
        self.assertEqual(models_cfg["intermediate"]["+schema"], "silver")
        self.assertEqual(models_cfg["marts"]["+schema"], "gold")

    def test_profiles_yml(self):
        """Valida se profiles.yml existe e está parametrizado com env_var."""
        profiles_file = DBT_DIR / "profiles.yml"
        self.assertTrue(profiles_file.exists(), "profiles.yml deve existir.")

        content = profiles_file.read_text(encoding="utf-8")
        self.assertIn("dbt_imoveis:", content)
        self.assertIn("type: postgres", content)
        self.assertIn("env_var('POSTGRES_HOST')", content)
        self.assertIn("env_var('POSTGRES_USER')", content)

    def test_macro_generate_schema_name(self):
        """Valida se a macro de custom schema name foi implementada."""
        macro_file = DBT_DIR / "macros" / "generate_schema_name.sql"
        self.assertTrue(macro_file.exists(), "macros/generate_schema_name.sql deve existir.")
        content = macro_file.read_text(encoding="utf-8")
        self.assertIn("macro generate_schema_name", content)

    def test_dbt_directories_exist(self):
        """Valida se os diretórios canônicos do dbt foram criados."""
        required_dirs = ["models/staging", "models/intermediate", "models/marts", "snapshots", "macros", "tests"]
        for d in required_dirs:
            p = DBT_DIR / d
            self.assertTrue(p.exists(), f"Diretório dbt_imoveis/{d} deve existir.")


if __name__ == "__main__":
    unittest.main()
