import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Product, Ingredient, OrderTicket, RecipeItem, SalesRecord
from routes.api import to_base_currency, from_base_currency, get_currency_info

# Define the Blueprint
ui_bp = Blueprint('ui', __name__)

@ui_bp.context_processor
def inject_currency():
    """Makes currency info available to all templates automatically."""
    if current_user.is_authenticated:
        return {'curr': get_currency_info(current_user.currency)}
    return {'curr': get_currency_info('ZAR')}

def process_detailed_sales(df):
    """Processes the CSV, creates missing products, and logs sales."""
    rows_added = 0
    user_curr = current_user.currency
    for index, row in df.iterrows():
        product_name = str(row['product_name']).strip()
        if not product_name or pd.isna(product_name) or 'average' in product_name.lower():
            continue
            
        # 1. Check if product exists FOR THIS USER
        product = Product.query.filter_by(name=product_name, user_id=current_user.id).first()
        
        price_in_user_curr = 0.0
        if 'price' in df.columns:
            try:
                price_val = str(row['price']).replace('R', '').replace('$', '').replace(',', '').strip()
                price_in_user_curr = float(price_val)
            except (ValueError, TypeError):
                pass
        
        # Convert user's upload price to ZAR for storage
        price_in_zar = to_base_currency(price_in_user_curr, user_curr)

        if not product:
            product = Product(
                name=product_name, 
                selling_price=price_in_zar,
                user_id=current_user.id
            )
            db.session.add(product)
            db.session.flush() 
        elif price_in_user_curr > 0:
            product.selling_price = price_in_zar
            
        try:
            timestamp = pd.to_datetime(row['timestamp'], errors='coerce')
            if pd.isna(timestamp): continue
            quantity = int(row['quantity_sold'])
        except Exception: continue 
            
        record = SalesRecord(
            timestamp=timestamp,
            quantity_sold=quantity,
            product_id=product.id,
            user_id=current_user.id,
            unit_cost_at_sale=product.calculate_cost() # Already in ZAR
        )
        db.session.add(record)
        rows_added += 1
        
    db.session.commit()
    return rows_added

def process_daily_summary(df):
    # Placeholder for daily summary format
    return 0

# --- Routes ---

@ui_bp.route('/')
def index():
    return render_template('index.html')

@ui_bp.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')

@ui_bp.route('/predictions')
@login_required
def predictions():
    return render_template('predictions.html')

@ui_bp.route('/transactions')
@login_required
def transactions():
    orders = OrderTicket.query.filter_by(user_id=current_user.id).order_by(OrderTicket.timestamp.desc()).all()
    return render_template('transactions.html', orders=orders)

@ui_bp.route('/kitchen')
@login_required
def kitchen():
    active_orders = OrderTicket.query.filter_by(user_id=current_user.id, status='Pending').order_by(OrderTicket.timestamp.asc()).all()
    return render_template('kitchen.html', orders=active_orders)

@ui_bp.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    if request.method == 'POST':
        raw_name = request.form.get('name', '').strip()
        unit = request.form.get('unit', '').strip()
        cost_in_user_curr = request.form.get('unit_cost', type=float) or 0.0

        if not raw_name or not unit:
            flash('Ingredient name and unit are required.', 'error')
            return redirect(url_for('ui.inventory'))
        
        # Normalize input cost to ZAR
        cost_in_zar = to_base_currency(cost_in_user_curr, current_user.currency)

        # The Duplicate Catcher: Filter by user_id
        existing = Ingredient.query.filter(
            Ingredient.user_id == current_user.id,
            db.func.lower(Ingredient.name) == raw_name.lower()
        ).first()

        if existing:
            flash(f"Ingredient '{existing.name}' already exists in your inventory!", 'error')
        else:
            new_ingredient = Ingredient(
                name=raw_name.title(), 
                unit_of_measure=unit, 
                unit_cost=cost_in_zar,
                current_stock=0.0,
                user_id=current_user.id
            )
            db.session.add(new_ingredient)
            db.session.commit()
            flash(f"Added {new_ingredient.name} to inventory!", 'success')

        return redirect(url_for('ui.inventory'))

    ingredients = Ingredient.query.filter_by(user_id=current_user.id).order_by(Ingredient.name).all()
    return render_template('inventory.html', ingredients=ingredients)

@ui_bp.route('/inventory/update', methods=['POST'])
@login_required
def update_stock():
    try:
        ingredient_id = request.form.get('ingredient_id')
        amount = request.form.get('amount', type=float)
        action = request.form.get('action') 
        input_unit = request.form.get('input_unit') 

        if ingredient_id and amount is not None:
            if amount <= 0:
                flash("Stock amount must be greater than zero.", "error")
                return redirect(url_for('ui.inventory'))

            # Secure by user_id
            ingredient = Ingredient.query.filter_by(id=int(ingredient_id), user_id=current_user.id).first()
            if ingredient:
                actual_amount = amount

                # --- AUTO-CONVERSION LOGIC ---
                # Weight conversions (if tracking in grams)
                if ingredient.unit_of_measure == 'g' and input_unit == 'kg':
                    actual_amount = amount * 1000
                elif ingredient.unit_of_measure == 'kg' and input_unit == 'g':
                    actual_amount = amount / 1000

                # Volume conversions (if tracking in ml)
                elif ingredient.unit_of_measure == 'ml' and input_unit == 'L':
                    actual_amount = amount * 1000
                elif ingredient.unit_of_measure == 'L' and input_unit == 'ml':
                    actual_amount = amount / 1000

                # --- YIELD CONVERSIONS (The "Pump/Shot" Math) ---
                # If the master ingredient is tracked in 'pumps', but the user enters a bulk liquid amount:
                if ingredient.unit_of_measure == 'pumps':
                    # Convert to raw ML first
                    total_ml_received = amount
                    if input_unit in ['L', 'L_to_pump_15', 'L_to_pump_10', 'L_to_pump_7_5', 'L_to_pump_30', 'L_to_pump_5']:
                        total_ml_received = amount * 1000

                    # Divide by the pump size
                    if 'pump_15' in input_unit or input_unit == 'ml_to_pump_15':
                        actual_amount = total_ml_received / 15
                    elif 'pump_10' in input_unit or input_unit == 'ml_to_pump_10':
                        actual_amount = total_ml_received / 10
                    elif 'pump_7_5' in input_unit or input_unit == 'ml_to_pump_7_5':
                        actual_amount = total_ml_received / 7.5
                    elif 'pump_30' in input_unit or input_unit == 'ml_to_pump_30':
                        actual_amount = total_ml_received / 30
                    elif 'pump_5' in input_unit or input_unit == 'ml_to_pump_5':
                        actual_amount = total_ml_received / 5
                    elif input_unit == 'pumps':
                        actual_amount = amount # User entered exactly the number of pumps

                # --- APPLY THE ACTION (+ OR -) ---
                if action == 'remove':
                    ingredient.current_stock -= actual_amount
                    flash(f"Corrected: Removed {actual_amount:.2f} {ingredient.unit_of_measure} from {ingredient.name}.", 'success')
                else:
                    ingredient.current_stock += actual_amount
                    flash(f"Delivery: Added {actual_amount:.2f} {ingredient.unit_of_measure} to {ingredient.name}!", 'success')

                db.session.commit()
            else:
                flash("Ingredient not found.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating stock: {e}", "error")

    return redirect(url_for('ui.inventory'))

@ui_bp.route('/inventory/<int:ingredient_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_ingredient(ingredient_id):
    ingredient = Ingredient.query.filter_by(id=ingredient_id, user_id=current_user.id).first()
    if not ingredient:
        flash("Ingredient not found.", "error")
        return redirect(url_for('ui.inventory'))

    if request.method == 'POST':
        try:
            ingredient.name = request.form.get('name', '').strip().title()
            ingredient.unit_of_measure = request.form.get('unit', '').strip()
            
            cost_in_user_curr = request.form.get('unit_cost', type=float) or 0.0
            if not ingredient.name or not ingredient.unit_of_measure:
                flash("Ingredient name and unit are required.", "error")
                return redirect(url_for('ui.edit_ingredient', ingredient_id=ingredient.id))
            ingredient.unit_cost = to_base_currency(cost_in_user_curr, current_user.currency)
            
            db.session.commit()
            flash(f"Ingredient updated to {ingredient.name} ({ingredient.unit_of_measure}).", "success")
            return redirect(url_for('ui.inventory'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating ingredient: {e}", "error")

    return render_template('edit_ingredient.html', ingredient=ingredient)

@ui_bp.route('/inventory/<int:ingredient_id>/delete', methods=['POST'])
@login_required
def delete_ingredient(ingredient_id):
    ingredient = Ingredient.query.filter_by(id=ingredient_id, user_id=current_user.id).first()
    if ingredient:
        try:
            db.session.delete(ingredient)
            db.session.commit()
            flash(f"Successfully deleted {ingredient.name} from the master list.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Cannot delete {ingredient.name}! It is currently being used in a Recipe.", "error")

    return redirect(url_for('ui.inventory'))

@ui_bp.route('/recipes')
@login_required
def recipes():
    products = Product.query.filter_by(user_id=current_user.id).options(
        db.joinedload(Product.recipe_items).joinedload(RecipeItem.ingredient)
    ).order_by(Product.name).all()
    return render_template('recipes.html', products=products)

@ui_bp.route('/pos')
@login_required
def pos():
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.name).all()
    return render_template('pos.html', products=products)

# --- Recipe CRUD ---
@ui_bp.route('/recipe/new', methods=['GET', 'POST'])
@login_required
def recipe_form():
    if request.method == 'POST':
        try:
            user_curr = current_user.currency
            manual_cost_input = request.form.get('cost_price')
            selling_price_input = float(request.form['selling_price'])
            
            # Normalize to ZAR
            selling_price_zar = to_base_currency(selling_price_input, user_curr)
            manual_cost_zar = to_base_currency(float(manual_cost_input), user_curr) if manual_cost_input else 0

            new_product = Product(
                name=request.form['name'],
                selling_price=selling_price_zar,
                cost_price=manual_cost_zar,
                user_id=current_user.id
            )
            db.session.add(new_product)
            db.session.flush() 

            ingredient_ids = request.form.getlist('ingredient_id')
            quantities = request.form.getlist('quantity_needed')

            for i in range(len(ingredient_ids)):
                if ingredient_ids[i] and quantities[i]:
                    recipe_item = RecipeItem(
                        product_id=new_product.id,
                        ingredient_id=int(ingredient_ids[i]),
                        quantity_needed=float(quantities[i])
                    )
                    db.session.add(recipe_item)

            # If no manual cost was provided, auto-calculate
            if not manual_cost_input:
                new_product.cost_price = new_product.calculate_cost()

            db.session.commit()

            flash(f'Recipe for {new_product.name} created successfully!', 'success')
            return redirect(url_for('ui.recipes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating recipe: {e}', 'error')

    all_ingredients = Ingredient.query.filter_by(user_id=current_user.id).order_by(Ingredient.name).all()
    return render_template('recipe_form.html', all_ingredients=all_ingredients)

@ui_bp.route('/recipe/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_recipe_form(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        try:
            user_curr = current_user.currency
            manual_cost_input = request.form.get('cost_price')
            selling_price_input = float(request.form['selling_price'])
            
            # Normalize to ZAR
            selling_price_zar = to_base_currency(selling_price_input, user_curr)
            manual_cost_zar = to_base_currency(float(manual_cost_input), user_curr) if manual_cost_input else 0

            product.name = request.form['name']
            product.selling_price = selling_price_zar
            product.cost_price = manual_cost_zar

            RecipeItem.query.filter_by(product_id=product.id).delete()

            ingredient_ids = request.form.getlist('ingredient_id')
            quantities = request.form.getlist('quantity_needed')

            for i in range(len(ingredient_ids)):
                if ingredient_ids[i] and quantities[i]:
                    recipe_item = RecipeItem(
                        product_id=product.id,
                        ingredient_id=int(ingredient_ids[i]),
                        quantity_needed=float(quantities[i])
                    )
                    db.session.add(recipe_item)

            # If no manual cost was provided, auto-calculate
            if not manual_cost_input:
                product.cost_price = product.calculate_cost()

            db.session.commit()
            flash(f'Recipe for {product.name} updated successfully!', 'success')
            return redirect(url_for('ui.recipes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating recipe: {e}', 'error')

    all_ingredients = Ingredient.query.filter_by(user_id=current_user.id).order_by(Ingredient.name).all()
    return render_template('recipe_form.html', product=product, all_ingredients=all_ingredients)

@ui_bp.route('/recipe/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_recipe(product_id):
    try:
        product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
        db.session.delete(product)
        db.session.commit()
        flash(f'Recipe for {product.name} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting recipe: {e}', 'error')
    return redirect(url_for('ui.recipes'))


@ui_bp.route('/wipe-data', methods=['POST'])
@login_required
def wipe_data():
    try:
        # 1. Delete Sales & Tickets (Directly linked to User)
        SalesRecord.query.filter_by(user_id=current_user.id).delete()
        OrderTicket.query.filter_by(user_id=current_user.id).delete()
        
        # 2. Delete Recipe Items (Linked via Product)
        # We find product IDs first to avoid the forbidden 'join' in delete()
        user_product_ids = [p.id for p in Product.query.filter_by(user_id=current_user.id).all()]
        if user_product_ids:
            RecipeItem.query.filter(RecipeItem.product_id.in_(user_product_ids)).delete(synchronize_session='fetch')
        
        # 3. Delete Products & Ingredients
        Product.query.filter_by(user_id=current_user.id).delete()
        Ingredient.query.filter_by(user_id=current_user.id).delete()
        
        db.session.commit()
        flash('All your data has been successfully wiped.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error wiping data: {e}', 'error')
    
    return redirect(url_for('ui.upload_form'))

@ui_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_form():
    if request.method == 'GET':
        return render_template('upload.html')

    if 'csv_file' not in request.files:
        flash('No file part', 'error')
        return redirect(request.url)

    file = request.files['csv_file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(request.url)

    if file and file.filename.endswith('.csv'):
        try:
            # Handle BOM and standard reading
            df = pd.read_csv(file, sep=None, engine='python', encoding='utf-8-sig')

            # Normalize columns
            df.columns = df.columns.str.replace('\ufeff', '').str.strip().str.lower().str.replace(' ', '_')

            # Rename plural to singular
            df.rename(columns={'timestamps': 'timestamp'}, inplace=True)

            # Check for detailed format (now allowing 'price' as an optional extra)
            required_detailed = ['timestamp', 'product_name', 'quantity_sold']
            required_daily = ['date', 'net_sales']

            if all(col in df.columns for col in required_detailed):
                count = process_detailed_sales(df)
                flash(f'Success! Processed {count} sales records and updated your product list.', 'success')
            elif all(col in df.columns for col in required_daily):
                count = process_daily_summary(df)
                flash(f'Success! Processed {count} daily summaries.', 'success')
            else:
                flash(f"CSV format not recognized. Columns found: {', '.join(df.columns)}", 'error')
                return redirect(request.url)

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during processing: {e}', 'error')
            return redirect(request.url)

        return redirect(url_for('ui.index'))

    flash('Invalid file type. Please upload a CSV.', 'error')
    return redirect(request.url)
