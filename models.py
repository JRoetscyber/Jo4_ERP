import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
Base = declarative_base()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    currency = db.Column(db.String(10), default='ZAR') # Added currency preference
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    ingredients = db.relationship('Ingredient', back_populates='user', cascade="all, delete-orphan")
    products = db.relationship('Product', back_populates='user', cascade="all, delete-orphan")
    order_tickets = db.relationship('OrderTicket', back_populates='user', cascade="all, delete-orphan")
    sales_records = db.relationship('SalesRecord', back_populates='user', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Ingredient(db.Model):
    __tablename__ = 'ingredients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False) 
    current_stock = db.Column(db.Float, nullable=False, default=0)
    unit_of_measure = db.Column(db.String(50), nullable=False)
    unit_cost = db.Column(db.Float, nullable=False, default=0) 

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    user = db.relationship('User', back_populates='ingredients')

    def __repr__(self):
        return f'<Ingredient {self.name}>'

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float, nullable=True, default=0)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    user = db.relationship('User', back_populates='products')

    recipe_items = db.relationship('RecipeItem', back_populates='product', cascade="all, delete-orphan")
    sales_records = db.relationship('SalesRecord', back_populates='product', cascade="all, delete-orphan")

    def calculate_cost(self):
        """Calculates total cost from ingredients."""
        total = 0
        for item in self.recipe_items:
            total += (item.quantity_needed * item.ingredient.unit_cost)
        return total

    def __repr__(self):
        return f'<Product {self.name}>'

class RecipeItem(db.Model):
    __tablename__ = 'recipe_items'
    id = db.Column(db.Integer, primary_key=True)
    quantity_needed = db.Column(db.Float, nullable=False)

    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False, index=True)

    product = db.relationship('Product', back_populates='recipe_items')
    ingredient = db.relationship('Ingredient')

    def __repr__(self):
        return f'<RecipeItem for {self.product.name} - {self.ingredient.name}>'

class SalesRecord(db.Model):
    __tablename__ = 'sales_records'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    quantity_sold = db.Column(db.Integer, nullable=False)
    unit_cost_at_sale = db.Column(db.Float, nullable=False, default=0) 

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    user = db.relationship('User', back_populates='sales_records')

    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    product = db.relationship('Product', back_populates='sales_records')

    def __repr__(self):
        return f'<SalesRecord {self.product.name} - {self.quantity_sold} @ {self.timestamp}>'

def setup_database(app):
    with app.app_context():
        db.init_app(app)
        db.create_all()
        
        # Data Migration: Fix existing data that might have null user_id
        from models import User, Ingredient, Product, OrderTicket, SalesRecord
        first_user = User.query.first()
        if first_user:
            # Assign any orphaned items to the first user so they don't crash the app
            unowned_ing = Ingredient.query.filter(Ingredient.user_id == None).all()
            for item in unowned_ing: item.user_id = first_user.id
            
            unowned_prod = Product.query.filter(Product.user_id == None).all()
            for item in unowned_prod: item.user_id = first_user.id
            
            unowned_sales = SalesRecord.query.filter(SalesRecord.user_id == None).all()
            for item in unowned_sales: item.user_id = first_user.id

            unowned_tickets = OrderTicket.query.filter(OrderTicket.user_id == None).all()
            for item in unowned_tickets: item.user_id = first_user.id
            
            if unowned_ing or unowned_prod or unowned_sales or unowned_tickets:
                db.session.commit()
                print("Migration: Assigned legacy data to first user.")

def get_session(app):
    engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    Session = sessionmaker(bind=engine)
    return Session()

class OrderTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    status = db.Column(db.String(20), default='Pending', index=True) 
    items = db.Column(db.JSON, nullable=False)

    # Payment Details for Auditing
    payment_method = db.Column(db.String(20), default='card') # 'card' or 'cash'
    total_in_zar = db.Column(db.Float, nullable=False, default=0)
    amount_tendered = db.Column(db.Float, nullable=True) # Stored in user's currency at time of sale
    currency_at_sale = db.Column(db.String(10), default='ZAR')

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    user = db.relationship('User', back_populates='order_tickets')