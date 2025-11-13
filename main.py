import os
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bson import ObjectId

from database import db, create_document

app = FastAPI(title="E-Commerce Template API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------
# Helpers
# ------------------------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    out = {**doc}
    if out.get("_id") is not None:
        out["id"] = str(out.pop("_id"))
    # convert nested ObjectIds if any
    for k, v in list(out.items()):
        if isinstance(v, ObjectId):
            out[k] = str(v)
    return out


# ------------------------
# Schemas
# ------------------------
class ProductCreate(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category: str
    in_stock: bool = True
    image: Optional[str] = None
    rating: Optional[float] = Field(default=4.5, ge=0, le=5)


class ProductOut(ProductCreate):
    id: str


# ------------------------
# Seed sample data (on first run)
# ------------------------
@app.on_event("startup")
async def seed_products():
    if db is None:
        return
    try:
        count = db["product"].count_documents({})
        if count == 0:
            sample_products = [
                {
                    "title": "Wireless Headphones",
                    "description": "Noise-cancelling over-ear headphones with 30h battery.",
                    "price": 129.99,
                    "category": "Electronics",
                    "in_stock": True,
                    "image": "https://images.unsplash.com/photo-1518445077100-1be42e41a1b7?w=800&q=80",
                    "rating": 4.6,
                },
                {
                    "title": "Smart Watch",
                    "description": "Fitness tracking, heart-rate monitor, and notifications.",
                    "price": 89.0,
                    "category": "Electronics",
                    "in_stock": True,
                    "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800&q=80",
                    "rating": 4.4,
                },
                {
                    "title": "Minimalist Sneakers",
                    "description": "Lightweight, breathable everyday sneakers.",
                    "price": 59.99,
                    "category": "Fashion",
                    "in_stock": True,
                    "image": "https://images.unsplash.com/photo-1528701800489-20be0b1c7e82?w=800&q=80",
                    "rating": 4.2,
                },
                {
                    "title": "Ceramic Mug",
                    "description": "Matte finish mug for your daily coffee ritual.",
                    "price": 14.5,
                    "category": "Home & Kitchen",
                    "in_stock": True,
                    "image": "https://images.unsplash.com/photo-1517686469429-8bdb88b9f907?w=800&q=80",
                    "rating": 4.8,
                },
                {
                    "title": "Standing Desk",
                    "description": "Adjustable height desk for ergonomic work.",
                    "price": 279.0,
                    "category": "Office",
                    "in_stock": True,
                    "image": "https://images.unsplash.com/photo-1517084166765-7f75a9966ace?w=800&q=80",
                    "rating": 4.7,
                },
                {
                    "title": "Cotton T-Shirt",
                    "description": "Soft, breathable cotton tee in multiple colors.",
                    "price": 19.99,
                    "category": "Fashion",
                    "in_stock": True,
                    "image": "https://images.unsplash.com/photo-1520975916090-3105956dac38?w=800&q=80",
                    "rating": 4.1,
                },
            ]
            for p in sample_products:
                create_document("product", p)
    except Exception:
        # Ignore seeding errors in template context
        pass


# ------------------------
# Routes
# ------------------------
@app.get("/")
def root():
    return {"message": "E-Commerce Template API"}


@app.get("/api/products", response_model=List[ProductOut])
def list_products(
    q: Optional[str] = Query(default=None, description="Search query"),
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    sort: Optional[str] = Query(default=None, description="price_asc | price_desc | rating_desc"),
):
    if db is None:
        return []
    filter_doc: Dict[str, Any] = {}
    if q:
        filter_doc["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    if category:
        filter_doc["category"] = category

    cursor = db["product"].find(filter_doc)

    if sort == "price_asc":
        cursor = cursor.sort("price", 1)
    elif sort == "price_desc":
        cursor = cursor.sort("price", -1)
    elif sort == "rating_desc":
        cursor = cursor.sort("rating", -1)

    cursor = cursor.limit(limit)
    return [serialize_doc(d) for d in cursor]


@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        oid = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")
    doc = db["product"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_doc(doc)


@app.get("/api/categories", response_model=List[str])
def categories():
    if db is None:
        return []
    cats = db["product"].distinct("category")
    return sorted([c for c in cats if c])


@app.post("/api/products", response_model=ProductOut)
def create_product(payload: ProductCreate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    product_id = create_document("product", payload.model_dump())
    doc = db["product"].find_one({"_id": ObjectId(product_id)})
    return serialize_doc(doc)


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
