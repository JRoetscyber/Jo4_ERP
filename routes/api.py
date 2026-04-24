from flask import Blueprint, jsonify, current_app, request
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from models import db, Ingredient, Product, SalesRecord, RecipeItem, OrderTicket

# Define the Blueprint
api_bp = Blueprint('api', __name__)

def get_currency_info(currency_code):
    rates = {
        'ZAR': {'symbol': 'R', 'rate': 1.0},
        'USD': {'symbol': '$', 'rate': 0.053},
        'EUR': {'symbol': '€', 'rate': 0.049},
        'GBP': {'symbol': '£', 'rate': 0.042},
        'JPY': {'symbol': '¥', 'rate': 8.25},
        'AUD': {'symbol': 'A$', 'rate': 0.082}
    }
    return rates.get(currency_code, rates['ZAR'])

def to_base_currency(amount, currency_code):
    """Converts user input (e.g. USD) to ZAR for the database."""
    info = get_currency_info(currency_code)
    return amount / info['rate']

def from_base_currency(amount, currency_code):
    """Converts database ZAR to user's currency for display."""
    info = get_currency_info(currency_code)
    return amount * info['rate']

def format_currency(amount, currency_code):
    info = get_currency_info(currency_code)
    converted = from_base_currency(amount, currency_code)
    return f"{info['symbol']} {converted:,.2f}"

@api_bp.route('/dashboard_kpis')
@login_required
def api_dashboard_kpis():
    try:
        user_currency = current_user.currency
        
        # Filter all by user_id
        total_revenue = db.session.query(
            func.sum(SalesRecord.quantity_sold * Product.selling_price)
        ).join(Product).filter(SalesRecord.user_id == current_user.id).scalar() or 0

        total_cost = db.session.query(
            func.sum(SalesRecord.quantity_sold * SalesRecord.unit_cost_at_sale)
        ).filter(SalesRecord.user_id == current_user.id).scalar() or 0

        total_items_sold = db.session.query(func.sum(SalesRecord.quantity_sold)).filter(SalesRecord.user_id == current_user.id).scalar() or 0
        
        # Advanced Analytics Calculations
        total_tickets = OrderTicket.query.filter_by(user_id=current_user.id).count()
        avg_ticket_value = total_revenue / total_tickets if total_tickets > 0 else 0
        
        best_seller_query = db.session.query(
            Product.name,
            func.sum(SalesRecord.quantity_sold).label('total_sold')
        ).join(SalesRecord).filter(Product.user_id == current_user.id).group_by(Product.name).order_by(desc('total_sold')).first()

        low_stock_ingredients = Ingredient.query.filter_by(user_id=current_user.id).order_by(Ingredient.current_stock).limit(3).all()

        gross_profit = total_revenue - total_cost
        margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

        return jsonify({
            'total_revenue': format_currency(total_revenue, user_currency),
            'total_cost': format_currency(total_cost, user_currency),
            'gross_profit': format_currency(gross_profit, user_currency),
            'avg_ticket_value': format_currency(avg_ticket_value, user_currency),
            'profit_margin': f'{margin:.1f}%',
            'total_items_sold': total_items_sold,
            'best_selling_product': best_seller_query.name if best_seller_query else 'N/A',
            'low_stock_ingredients': [
                {'name': i.name, 'stock': i.current_stock, 'unit': i.unit_of_measure} for i in low_stock_ingredients
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/production_capacity')
@login_required
def api_production_capacity():
    try:
        products = Product.query.filter_by(user_id=current_user.id).all()
        capacity = []
        for p in products:
            if not p.recipe_items:
                continue

            possible_units = []
            for item in p.recipe_items:
                stock = item.ingredient.current_stock
                needed = item.quantity_needed
                if needed > 0:
                    possible_units.append(stock // needed)

            capacity.append({
                'name': p.name,
                'can_make': min(possible_units) if possible_units else 0
            })

        return jsonify({
            'labels': [c['name'] for c in capacity],
            'values': [c['can_make'] for c in capacity]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/sales_trend')
@login_required
def api_sales_trend():
    try:
        # Group revenue and cost by month
        revenue_records = db.session.query(
            func.strftime('%Y-%m', SalesRecord.timestamp).label('month'),
            func.sum(SalesRecord.quantity_sold * Product.selling_price).label('revenue'),
            func.sum(SalesRecord.quantity_sold * SalesRecord.unit_cost_at_sale).label('cost')
        ).join(Product).filter(SalesRecord.user_id == current_user.id).group_by('month').order_by('month').all()

        return jsonify({
            'labels': [r.month for r in revenue_records],
            'revenue': [r.revenue for r in revenue_records],
            'cost': [r.cost for r in revenue_records]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/product_profitability')
@login_required
def api_product_profitability():
    try:
        # Profitability per product
        profit_query = db.session.query(
            Product.name,
            func.sum(SalesRecord.quantity_sold * (Product.selling_price - SalesRecord.unit_cost_at_sale)).label('profit')
        ).join(SalesRecord).filter(Product.user_id == current_user.id).group_by(Product.name).order_by(desc('profit')).all()

        return jsonify({
            'labels': [r.name for r in profit_query],
            'values': [r.profit for r in profit_query]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/predict')
@login_required
def api_predict():
    try:
        predictions = current_app.predictor.predict_sales(current_user.id)
        return jsonify(predictions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/currency_info')
@login_required
def api_currency_info():
    return jsonify(get_currency_info(current_user.currency))

@api_bp.route('/advanced_analytics')
@login_required
def api_advanced_analytics():
    try:
        # Peak Hours Analysis
        peak_hours_query = db.session.query(
            func.strftime('%H', SalesRecord.timestamp).label('hour'),
            func.sum(SalesRecord.quantity_sold).label('total_sales')
        ).filter(SalesRecord.user_id == current_user.id).group_by('hour').order_by('hour').all()
        
        # Day of Week Analysis
        weekday_query = db.session.query(
            func.strftime('%w', SalesRecord.timestamp).label('weekday'), # 0=Sunday
            func.sum(SalesRecord.quantity_sold).label('total_sales')
        ).filter(SalesRecord.user_id == current_user.id).group_by('weekday').order_by('weekday').all()
        
        # Map weekday numbers to names
        weekday_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        
        return jsonify({
            'peak_hours': {
                'labels': [f"{r.hour}:00" for r in peak_hours_query],
                'values': [r.total_sales for r in peak_hours_query]
            },
            'weekdays': {
                'labels': [weekday_names[int(r.weekday)] for r in weekday_query],
                'values': [r.total_sales for r in weekday_query]
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/checkout', methods=['POST'])
@login_required
def api_checkout():
    try:
        data = request.json
        cart = data.get('cart', [])
        payment_method = data.get('payment_method', 'card')
        tendered = data.get('tendered', 0)
        user_currency = current_user.currency

        if not cart:
            return jsonify({'error': 'Cart is empty'}), 400

        ticket_items = []
        total_zar = 0

        for item in cart:
            product_id = item['product_id']
            quantity = item['quantity']

            if quantity <= 0:
                return jsonify({'error': 'Quantity must be greater than zero'}), 400

            product = Product.query.filter_by(id=product_id, user_id=current_user.id).first()
            if not product: continue

            # Track total for the ticket
            total_zar += (product.selling_price * quantity)

            # Calculate cost snapshot
            cost_snapshot = product.cost_price if (product.cost_price and product.cost_price > 0) else product.calculate_cost()

            # Record the Sale
            sale = SalesRecord(
                timestamp=datetime.utcnow(),
                quantity_sold=quantity,
                product_id=product_id,
                user_id=current_user.id,
                unit_cost_at_sale=cost_snapshot
            )
            db.session.add(sale)

            # Deduct ingredients
            if product.recipe_items:
                for recipe in product.recipe_items:
                    ingredient = db.session.get(Ingredient, recipe.ingredient_id)
                    if ingredient:
                        ingredient.current_stock -= (recipe.quantity_needed * quantity)

            ticket_items.append({"product_name": product.name, "quantity": quantity})

        # Create detailed ticket
        new_ticket = OrderTicket(
            timestamp=datetime.utcnow(),
            status='Pending',
            items=ticket_items,
            user_id=current_user.id,
            payment_method=payment_method,
            total_in_zar=total_zar,
            amount_tendered=tendered,
            currency_at_sale=user_currency
        )
        db.session.add(new_ticket)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Sale completed and ticket sent to Kitchen!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/refund/<int:order_id>', methods=['POST'])
@login_required
def api_refund(order_id):
    try:
        order = OrderTicket.query.filter_by(id=order_id, user_id=current_user.id).first()
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        if order.status == 'Refunded':
            return jsonify({'error': 'Order already refunded'}), 400

        # 1. Restore Inventory
        # For each item in the ticket, find the product and add back ingredients
        for item in order.items:
            product_name = item['product_name']
            qty = item['quantity']
            
            product = Product.query.filter_by(name=product_name, user_id=current_user.id).first()
            if product and product.recipe_items:
                for recipe in product.recipe_items:
                    ingredient = db.session.get(Ingredient, recipe.ingredient_id)
                    if ingredient:
                        # Add back what was deducted during sale
                        ingredient.current_stock += (recipe.quantity_needed * qty)

        # 2. Mark Order as Refunded
        order.status = 'Refunded'

        # 3. Handle SalesRecords (Delete them so analytics update correctly)
        # Match by exact timestamp if possible, or just by order ID if we had linked them
        # Since we didn't link directly, we filter by user, timestamp (close), and products
        # A better way is to delete records within a 2-second window of the order timestamp
        time_window_start = order.timestamp - timedelta(seconds=5)
        time_window_end = order.timestamp + timedelta(seconds=5)
        
        SalesRecord.query.filter(
            SalesRecord.user_id == current_user.id,
            SalesRecord.timestamp >= time_window_start,
            SalesRecord.timestamp <= time_window_end
        ).delete(synchronize_session=False)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Order successfully refunded and inventory restored.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/kitchen/orders', methods=['GET'])
@login_required
def get_live_orders():
    active_orders = OrderTicket.query.filter_by(user_id=current_user.id, status='Pending').order_by(OrderTicket.timestamp.asc()).all()

    orders_data = []
    for order in active_orders:
        orders_data.append({
            'id': order.id,
            'timestamp': order.timestamp.strftime('%H:%M'),
            'items': order.items
        })

    return jsonify(orders_data)

@api_bp.route('/kitchen/orders/<int:order_id>/complete', methods=['POST'])
@login_required
def complete_order(order_id):
    order = OrderTicket.query.filter_by(id=order_id, user_id=current_user.id).first()
    if order:
        order.status = 'Completed'
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Order not found'}), 404
