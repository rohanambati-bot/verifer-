"""
Pytest configuration and shared fixtures for VisionClick Agent tests.
"""
import os
import sys
import tempfile
import pytest
import asyncio

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.config import AppConfig, VisionConfig, AgentConfig
from app.vision.mock import MockVisionProvider
from app.reasoning.statement_parser import StatementParser
from app.reasoning.confidence import ConfidenceConfig
from app.decision.classifier import DecisionClassifier
from app.database.database import Database
from app.database.repository import Repository


import pytest_asyncio

@pytest.fixture
def ground_truth_path():
    return os.path.join(PROJECT_ROOT, "demo", "ground_truth", "ground_truth.json")


@pytest.fixture
def mock_vision_provider(ground_truth_path):
    return MockVisionProvider(ground_truth_path=ground_truth_path, noise_level=0.0)


@pytest.fixture
def statement_parser():
    return StatementParser()


@pytest.fixture
def confidence_config():
    return ConfidenceConfig(high_confidence=0.90, review_threshold=0.75)


@pytest.fixture
def decision_classifier(confidence_config):
    return DecisionClassifier(confidence_config=confidence_config)


@pytest_asyncio.fixture
async def test_db():
    temp_db = tempfile.mktemp(suffix=".db")
    db = Database(db_path=temp_db)
    await db.initialize()
    yield db
    await db.close()
    if os.path.exists(temp_db):
        os.remove(temp_db)


@pytest_asyncio.fixture
async def test_repo(test_db):
    return Repository(test_db)

