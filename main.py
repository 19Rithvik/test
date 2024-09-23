from fastapi import FastAPI, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import Column, Integer, String, Float, create_engine, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
import logging
import sys

# Setup logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPI app
app = FastAPI()

# SQLAlchemy Product Model with Unique Constraint on name
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, nullable=True)

    __table_args__ = (UniqueConstraint('name', name='uq_product_name'),)  # Unique constraint

# Pydantic Model for Product Schema (Create)
class ProductCreate(BaseModel):
    name: str
    price: float = Field(..., gt=0, description="Price must be greater than 0")
    quantity: int = Field(..., ge=0, description="Quantity must be greater than or equal to 0")
    description: str = None
    category: str = None

# Pydantic Model for Product Schema (Response with ID)
class ProductResponse(ProductCreate):
    id: int
    category: str = None

# Pydantic Model for Product Schema (Update)
class ProductUpdate(BaseModel):
    name: str = None
    price: float = Field(None, gt=0)
    quantity: int = Field(None, ge=0)
    description: str = None
    category: str = None

# Initialize database
Base.metadata.create_all(bind=engine)

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create a product with proper error handling
@app.post("/products/", response_model=ProductResponse)
def create_product(product: ProductCreate = Body(...), db: Session = Depends(get_db)):
    try:
        if not product.name:
            raise HTTPException(status_code=400, detail="Product name is required")

        db_product = Product(**product.dict())
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Product creation failed due to duplicate name.")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

# Retrieve a product by id with error handling for non-existent and invalid ids
@app.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid product ID type")

# Update a product and ensure constraints are respected
@app.put("/products/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, product: ProductUpdate, db: Session = Depends(get_db)):
    try:
        db_product = db.query(Product).filter(Product.id == product_id).first()
        if not db_product:
            raise HTTPException(status_code=404, detail="Product not found")

        update_data = product.dict(exclude_unset=True)

        if 'price' in update_data and update_data['price'] <= 0:
            raise HTTPException(status_code=400, detail="Price must be greater than 0")
        if 'quantity' in update_data and update_data['quantity'] < 0:
            raise HTTPException(status_code=400, detail="Quantity must be greater than or equal to 0")

        for key, value in update_data.items():
            setattr(db_product, key, value)

        db.commit()
        db.refresh(db_product)
        return db_product
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Product update failed due to integrity error.")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

# Delete a product with proper error handling for non-existent products
@app.delete("/products/{product_id}", response_model=dict)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    try:
        db_product = db.query(Product).filter(Product.id == product_id).first()
        if not db_product:
            raise HTTPException(status_code=404, detail="Product not found")

        db.delete(db_product)
        db.commit()
        return {"message": "Product deleted successfully"}
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid product ID type")

# List all products with optional price filtering and handling empty list case
@app.get("/products/", response_model=list[ProductResponse])
def list_products(price_gte: float = Query(None, ge=0), db: Session = Depends(get_db)):
    try:
        query = db.query(Product)
        if price_gte is not None:
            query = query.filter(Product.price >= price_gte)
        products = query.all()
        if not products:
            return []  # Empty list if no products found
        return products
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

