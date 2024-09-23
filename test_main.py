import pytest
from fastapi.testclient import TestClient
from .main import app, Base, get_db, SQLALCHEMY_DATABASE_URL
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test database
TEST_DATABASE_URL = SQLALCHEMY_DATABASE_URL

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the database tables
Base.metadata.create_all(bind=engine)

# Create a TestClient for the FastAPI app
client = TestClient(app)

# Dependency override for testing
def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    # Setup before tests
    yield
    # Teardown after tests (optional cleanup)
    Base.metadata.drop_all(bind=engine)

def test_create_product():
    response = client.post("/products/", json={
        "name": "Test Product",
        "price": 10.99,
        "quantity": 100,
        "description": "A test product",
        "category": "Test Category"
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Test Product"

def test_create_product_duplicate_name():
    # Create a product first
    client.post("/products/", json={
        "name": "Duplicate Product",
        "price": 12.99,
        "quantity": 50
    })
    response = client.post("/products/", json={
        "name": "Duplicate Product",
        "price": 15.99,
        "quantity": 60
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Product creation failed due to duplicate name."

def test_get_product():
    # Create a product first
    response = client.post("/products/", json={
        "name": "Another Product",
        "price": 5.99,
        "quantity": 20
    })
    product_id = response.json()["id"]
    
    response = client.get(f"/products/{product_id}")
    assert response.status_code == 200
    assert response.json()["id"] == product_id

def test_get_product_not_found():
    response = client.get("/products/999")  # Non-existent product ID
    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"

def test_delete_product():
    # Create a product first
    response = client.post("/products/", json={
        "name": "To Be Deleted",
        "price": 8.99,
        "quantity": 10
    })
    product_id = response.json()["id"]
    
    response = client.delete(f"/products/{product_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Product deleted successfully"

    # Check if the product is indeed deleted
    response = client.get(f"/products/{product_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"
