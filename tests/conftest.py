import pytest


@pytest.fixture
def docs_fonte(tmp_path):
    caminho = tmp_path / "docs-fonte"
    caminho.mkdir()
    return caminho


@pytest.fixture
def docs_normalizado(tmp_path):
    caminho = tmp_path / "docs-normalizado"
    caminho.mkdir()
    return caminho
