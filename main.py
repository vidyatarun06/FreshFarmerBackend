from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import jwt
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import smtplib

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rest of your code...
# JWT settings
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

# In-memory database (temporary)
users = [
    {"name": "Vidya", "email": "vidya123@gmail.com", "password": "pass123", "role": "farmer"},
    {"name": "Client", "email": "client@test.com", "password": "pass123", "role": "client"},
    {"name": "Test User", "email": "testuser123", "password": "testpass123", "role": "farmer"},
    {"name": "Vidya Tarun", "email": "vidyatarun06@gmail.com", "password": "newpass123", "role": "farmer"},
    {"name": "Test User 12", "email": "testuser12@gmail.com", "password": "testpass12", "role": "farmer"}
]
crops = []
orders = []

# Pydantic models
class User(BaseModel):
    name: str
    email: str
    password: str
    role: str

class LoginRequest(BaseModel):
    email: str
    password: str
    role: str

class Crop(BaseModel):
    name: str
    quantity: float
    price: float
    farmer_email: str

class Order(BaseModel):
    crop_name: str
    quantity: float
    price: float
    client_email: str

class ResetRequest(BaseModel):
    email: str

# JWT token creation
def create_jwt_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Middleware to verify token
def verify_token(authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

# Register endpoint
@app.post("/register")
async def register(user: User):
    if any(u["email"] == user.email for u in users):
        raise HTTPException(status_code=400, detail="Email already registered")
    users.append(user.dict())
    return {"message": "User registered successfully"}

# Login endpoint
@app.post("/login")
async def login(request: LoginRequest):
    user = next((u for u in users if u["email"] == request.email and u["password"] == request.password and u["role"] == request.role), None)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt_token({"email": user["email"], "role": user["role"]})
    return {"token": token, "message": "Login successful"}

# Add crop endpoint
@app.post("/add-crop")
async def add_crop(crop: Crop, authorization: str = Header(...)):
    payload = verify_token(authorization)
    if payload["role"] != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can add crops")
    crop.farmer_email = payload["email"]
    crops.append(crop.dict())
    return {"message": "Crop added successfully"}

# Get all crops endpoint
@app.get("/crops", response_model=List[Crop])
async def get_crops():
    return crops

# Buy crop endpoint
@app.post("/buy-crop")
async def buy_crop(order: Order, authorization: str = Header(...)):
    payload = verify_token(authorization)
    if payload["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can buy crops")
    crop = next((c for c in crops if c["name"] == order.crop_name and c["quantity"] >= order.quantity), None)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found or insufficient quantity")
    crop["quantity"] -= order.quantity
    if crop["quantity"] == 0:
        crops.remove(crop)
    order.client_email = payload["email"]
    orders.append(order.dict())
    return {"message": "Purchase successful"}

# Get orders endpoint
@app.get("/orders/{client_email}", response_model=List[Order])
async def get_orders(client_email: str):
    return [order for order in orders if order["client_email"] == client_email]

# Reset password endpoint
@app.post("/reset-password")
async def reset_password(request: ResetRequest):
    print(f"Received reset request for email: {request.email}")
    user = next((u for u in users if u["email"] == request.email), None)
    if not user:
        print(f"Email not found: {request.email}")
        return {"message": "Email not found"}
    
    sender_email = "vidyatarun06@gmail.com"
    sender_password = "puib hlyx rmkd nrhc"  # Replace with your new App Password
    reset_link = f"http://localhost:8000/reset-password.html?email={request.email}"
    
    msg = MIMEText(f"Hello,\n\nClick the following link to reset your FreshFarmer password:\n{reset_link}\n\nIf you didn't request this, ignore this email.\n\nBest,\nFreshFarmer Team")
    msg["Subject"] = "FreshFarmer Password Reset"
    msg["From"] = sender_email
    msg["To"] = request.email

    try:
        print(f"Sending email to: {request.email}")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.set_debuglevel(1)
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, request.email, msg.as_string())
        print("Email sent successfully!")
        return {"message": "Reset link sent to your email"}
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return {"message": f"Failed to send email: {str(e)}"}

# Reset database endpoint
@app.post("/reset")
async def reset():
    global users, crops, orders
    users = []
    crops = []
    orders = []
    return {"message": "Database reset successful"}

# Update profile endpoint
@app.put("/update-profile")
async def update_profile(user: User, authorization: str = Header(...)):
    payload = verify_token(authorization)
    for u in users:
        if u["email"] == payload["email"]:
            u["name"] = user.name if user.name else u["name"]
            u["email"] = user.email if user.email else u["email"]
            u["password"] = user.password if user.password else u["password"]
            return {"message": "Profile updated successfully", "user": u}
    raise HTTPException(status_code=404, detail="User not found")

# Delete crop endpoint
@app.delete("/delete-crop/{crop_name}")
async def delete_crop(crop_name: str, authorization: str = Header(...)):
    global crops
    payload = verify_token(authorization)
    crops = [crop for crop in crops if crop["name"] != crop_name or crop["farmer_email"] != payload["email"]]
    return {"message": "Crop deleted successfully"}