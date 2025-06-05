import sqlite3
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from contextlib import contextmanager
import uuid

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
DATABASE = "freshfarmer.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def db_connection():
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS farmer_profiles (
                username TEXT PRIMARY KEY,
                name TEXT,
                location TEXT,
                contact TEXT,
                products TEXT,
                FOREIGN KEY (username) REFERENCES users (username)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                farmer TEXT NOT NULL,
                FOREIGN KEY (farmer) REFERENCES users (username)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                client_username TEXT NOT NULL,
                quantity REAL NOT NULL,
                total_price REAL NOT NULL,
                farmer_username TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products (id),
                FOREIGN KEY (client_username) REFERENCES users (username),
                FOREIGN KEY (farmer_username) REFERENCES users (username)
            )
        """)
        conn.commit()

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    role = data.get("role")

    if not username or not password or not role:
        return jsonify({"message": "All fields are required!"}), 400

    if role not in ["farmer", "client"]:
        return jsonify({"message": "Invalid role!"}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
            if role == "farmer":
                cursor.execute("INSERT INTO farmer_profiles (username) VALUES (?)", (username,))
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({"message": "Username already exists!"}), 400

    return jsonify({"message": "User registered successfully!"})

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    role = data.get("role")

    if not username or not password or not role:
        return jsonify({"message": "All fields are required!"}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ? AND role = ?", (username, password, role))
        user = cursor.fetchone()

    if user:
        return jsonify({"message": "Login successful!", "username": username, "role": role})
    else:
        return jsonify({"message": "Invalid credentials!"}), 401

@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    username = data.get("username")
    new_password = data.get("new_password")
    role = data.get("role")

    if not username or not new_password or not role:
        return jsonify({"message": "All fields are required!"}), 400

    if role not in ["farmer", "client"]:
        return jsonify({"message": "Invalid role!"}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND role = ?", (username, role))
        user = cursor.fetchone()

        if not user:
            return jsonify({"message": "User not found!"}), 404

        cursor.execute("UPDATE users SET password = ? WHERE username = ? AND role = ?", (new_password, username, role))
        conn.commit()

    return jsonify({"message": "Password reset successfully!"})

@app.route("/farmer-profile/<username>", methods=["GET"])
def get_farmer_profile(username):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM farmer_profiles WHERE username = ?", (username,))
        profile = cursor.fetchone()

    if profile:
        return jsonify({
            "username": profile[0],
            "name": profile[1],
            "location": profile[2],
            "contact": profile[3],
            "products": profile[4]
        })
    else:
        return jsonify({"message": "Farmer profile not found!"}), 404

@app.route("/farmer-profile/<username>", methods=["PUT"])
def update_farmer_profile(username):
    data = request.get_json()
    name = data.get("name")
    location = data.get("location")
    contact = data.get("contact")
    products = data.get("products")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM farmer_profiles WHERE username = ?", (username,))
        if not cursor.fetchone():
            return jsonify({"message": "Farmer not found!"}), 404

        cursor.execute("""
            UPDATE farmer_profiles
            SET name = ?, location = ?, contact = ?, products = ?
            WHERE username = ?
        """, (name, location, contact, products, username))
        conn.commit()

    return jsonify({"message": "Profile updated successfully!"})

@app.route("/product", methods=["POST"])
def add_product():
    data = request.get_json()
    name = data.get("name")
    quantity = data.get("quantity")
    price = data.get("price")
    farmer = data.get("farmer")

    if not name or not quantity or not price or not farmer:
        return jsonify({"message": "All fields are required!"}), 400

    try:
        quantity = float(quantity)
        price = float(price)
        if quantity <= 0 or price <= 0:
            return jsonify({"message": "Quantity and price must be greater than 0!"}), 400
    except ValueError:
        return jsonify({"message": "Invalid quantity or price!"}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND role = 'farmer'", (farmer,))
        if not cursor.fetchone():
            return jsonify({"message": "Farmer not found!"}), 404

        product_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO products (id, name, quantity, price, farmer) VALUES (?, ?, ?, ?, ?)",
                       (product_id, name, quantity, price, farmer))
        conn.commit()

    return jsonify({"message": "Product added successfully!"})

@app.route("/farmer-products", methods=["GET"])
def get_products():
    farmer = request.args.get("farmer")
    if not farmer:
        return jsonify({"message": "Farmer username is required!"}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE farmer = ?", (farmer,))
        products = cursor.fetchall()

    return jsonify([{
        "id": product[0],
        "name": product[1],
        "quantity": product[2],
        "price": product[3],
        "farmer": product[4]
    } for product in products])

@app.route("/products", methods=["GET"])
def get_all_products():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()

    return jsonify([{
        "id": product[0],
        "name": product[1],
        "quantity": product[2],
        "price": product[3],
        "farmer": product[4]
    } for product in products])

@app.route("/product/<product_id>", methods=["PUT"])
def update_product(product_id):
    data = request.get_json()
    name = data.get("name")
    quantity = data.get("quantity")
    price = data.get("price")
    farmer = data.get("farmer")

    if not name or not quantity or not price or not farmer:
        return jsonify({"message": "All fields are required!"}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ? AND farmer = ?", (product_id, farmer))
        if not cursor.fetchone():
            return jsonify({"message": "Product not found or not authorized!"}), 404

        cursor.execute("""
            UPDATE products
            SET name = ?, quantity = ?, price = ?
            WHERE id = ? AND farmer = ?
        """, (name, quantity, price, product_id, farmer))
        conn.commit()

    return jsonify({"message": "Product updated successfully!"})

@app.route("/product/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()

    return jsonify({"message": "Product deleted successfully!"})

@app.route("/order", methods=["POST"])
def create_order():
    data = request.get_json()
    product_id = data.get("product_id")
    client_username = data.get("client_username")
    quantity = data.get("quantity")

    if not product_id or not client_username or not quantity:
        return jsonify({"message": "All fields are required!"}), 400

    try:
        quantity = float(quantity)
        if quantity <= 0:
            return jsonify({"message": "Quantity must be greater than 0!"}), 400
    except ValueError:
        return jsonify({"message": "Invalid quantity!"}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND role = 'client'", (client_username,))
        if not cursor.fetchone():
            return jsonify({"message": "Client not found!"}), 404

        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        if not product:
            return jsonify({"message": "Product not found!"}), 404

        available_quantity = product[2]
        if quantity > available_quantity:
            return jsonify({"message": f"Only {available_quantity} kg available!"}), 400

        price_per_kg = product[3]
        total_price = quantity * price_per_kg

        order_id = str(uuid.uuid4())
        farmer_username = product[4]
        cursor.execute("""
            INSERT INTO orders (id, product_id, client_username, quantity, total_price, farmer_username, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (order_id, product_id, client_username, quantity, total_price, farmer_username, "pending"))

        new_quantity = available_quantity - quantity
        cursor.execute("""
            UPDATE products
            SET quantity = ?
            WHERE id = ?
        """, (new_quantity, product_id))

        conn.commit()

    return jsonify({"message": "Order placed successfully!", "order_id": order_id})

@app.route("/orders", methods=["GET"])
def get_client_orders():
    client_username = request.args.get("client_username")
    if not client_username:
        return jsonify({"message": "Client username is required!"}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.*, p.name AS product_name
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.client_username = ?
        """, (client_username,))
        orders = cursor.fetchall()

    return jsonify([{
        "id": order[0],
        "product_id": order[1],
        "client_username": order[2],
        "quantity": order[3],
        "total_price": order[4],
        "farmer_username": order[5],
        "status": order[6],
        "product_name": order[7]
    } for order in orders])

if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 8001))
    app.run(host="0.0.0.0", port=port, debug=False)