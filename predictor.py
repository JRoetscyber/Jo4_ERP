import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from datetime import datetime, timedelta
from models import SalesRecord, Product, RecipeItem, Ingredient
import os
import threading
import warnings

# Suppress sklearn warnings for a cleaner terminal
warnings.filterwarnings("ignore", category=UserWarning)

class StockPredictor:
    def __init__(self, db_uri):
        self.engine = create_engine(db_uri)
        self.Session = sessionmaker(bind=self.engine)
        self.n_estimators = int(os.environ.get("PREDICTOR_ESTIMATORS", "100"))
        self.cache_ttl_seconds = int(os.environ.get("PREDICTOR_CACHE_TTL", "300"))
        self._cache = {}
        self._cache_lock = threading.Lock()

    def _get_cached_prediction(self, user_id):
        if self.cache_ttl_seconds <= 0:
            return None

        with self._cache_lock:
            cached = self._cache.get(user_id)

        if not cached:
            return None

        if datetime.utcnow() >= cached["expires_at"]:
            with self._cache_lock:
                self._cache.pop(user_id, None)
            return None

        return cached["data"]

    def _set_cached_prediction(self, user_id, data):
        if self.cache_ttl_seconds <= 0:
            return

        with self._cache_lock:
            self._cache[user_id] = {
                "data": data,
                "expires_at": datetime.utcnow() + timedelta(seconds=self.cache_ttl_seconds),
            }

    def _get_sales_data(self, user_id):
        session = self.Session()
        try:
            query = session.query(
                SalesRecord.timestamp,
                SalesRecord.quantity_sold,
                Product.name.label('product_name')
            ).join(Product).filter(SalesRecord.user_id == user_id).statement
            df = pd.read_sql(query, self.engine)
            if df.empty:
                return None
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        finally:
            session.close()

    def _get_all_products_and_recipes(self, user_id):
        session = self.Session()
        try:
            products = session.query(Product).filter(Product.user_id == user_id).all()
            recipes = {}
            for p in products:
                recipes[p.name] = {
                    item.ingredient.name: {
                        "quantity": item.quantity_needed,
                        "unit": item.ingredient.unit_of_measure
                    } for item in p.recipe_items
                }
            return products, recipes
        finally:
            session.close()

    def _calculate_requirements(self, predictions, recipes):
        """Helper to convert product predictions into ingredient needs."""
        ingredient_reqs = {}
        for product_name, qty in predictions.items():
            if product_name in recipes and qty > 0:
                for ing_name, details in recipes[product_name].items():
                    if ing_name not in ingredient_reqs:
                        ingredient_reqs[ing_name] = {"quantity": 0, "unit": details["unit"]}
                    ingredient_reqs[ing_name]["quantity"] += qty * details["quantity"]
        
        for ing, details in ingredient_reqs.items():
            details['quantity'] = round(details['quantity'], 2)
            
        return ingredient_reqs

    def predict_sales(self, user_id):
        """
        Predicts sales for 7 days and 30 days simultaneously for a specific user.
        """
        cached_result = self._get_cached_prediction(user_id)
        if cached_result is not None:
            return cached_result

        sales_df = self._get_sales_data(user_id)
        if sales_df is None:
            return {"error": "No sales data available. Start recording sales or upload historical data."}

        products, recipes = self._get_all_products_and_recipes(user_id)
        if not products:
             return {"error": "No products found. Please add products and recipes first."}
        
        # --- THE MASTER CLOCK ---
        # Find the absolute latest date anything was sold in the entire shop.
        # We strip the hours/minutes so it aligns perfectly to midnight.
        global_latest_date = pd.to_datetime(sales_df['timestamp'].dt.date.max())
        
        week_preds = {}
        month_preds = {}

        for product in products:
            product_df = sales_df[sales_df['product_name'] == product.name].copy()
            
            if product_df.empty: 
                week_preds[product.name] = 0
                month_preds[product.name] = 0
                continue

            # 1. Resample to Daily & Fill Missing Days with 0 (Fixes gaps in the middle)
            product_df.set_index('timestamp', inplace=True)
            daily_df = product_df[['quantity_sold']].resample('D').sum().fillna(0)
            
            # --- THE MASTER CLOCK FIX ---
            # Fixes gaps at the END of the timeline. 
            # If this product's last sale was 5 days ago, force the calendar to stretch to today and fill with 0s.
            if daily_df.index.max() < global_latest_date:
                full_calendar = pd.date_range(start=daily_df.index.min(), end=global_latest_date, freq='D')
                daily_df = daily_df.reindex(full_calendar, fill_value=0)
            
            # 2. Advanced AI Feature Engineering
            daily_df['day_of_year'] = daily_df.index.dayofyear
            daily_df['weekday'] = daily_df.index.weekday
            daily_df['is_weekend'] = daily_df.index.weekday.isin([5, 6]).astype(int)
            daily_df['month'] = daily_df.index.month
            
            # 7-day rolling average to catch recent sales momentum
            daily_df['rolling_7d'] = daily_df['quantity_sold'].shift(1).rolling(window=7, min_periods=1).mean().fillna(0)

            X = daily_df[['day_of_year', 'weekday', 'is_weekend', 'month', 'rolling_7d']]
            y = daily_df['quantity_sold']

            model = RandomForestRegressor(
                n_estimators=self.n_estimators,
                random_state=35,
                n_jobs=1,
            )
            model.fit(X, y)

            # 3. Forecast the next 30 days
            last_date = daily_df.index.max()
            future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=30)
            
            future_df = pd.DataFrame({
                'day_of_year': future_dates.dayofyear,
                'weekday': future_dates.weekday,
                'is_weekend': future_dates.weekday.isin([5, 6]).astype(int),
                'month': future_dates.month
            }, index=future_dates)
            
            # Use the last known momentum for the future baseline
            future_df['rolling_7d'] = daily_df['rolling_7d'].iloc[-1] if not daily_df.empty else 0

            # Predict! (Using np.maximum to prevent impossible negative sales)
            daily_predictions = np.maximum(0, model.predict(future_df))
            
            # Split the data into Week (first 7) and Month (all 30)
            week_preds[product.name] = int(sum(daily_predictions[:7]))
            month_preds[product.name] = int(sum(daily_predictions))

        # Return both sets of data to the frontend
        result = {
            "week": {
                "product_predictions": week_preds,
                "ingredient_requirements": self._calculate_requirements(week_preds, recipes)
            },
            "month": {
                "product_predictions": month_preds,
                "ingredient_requirements": self._calculate_requirements(month_preds, recipes)
            }
        }
        self._set_cached_prediction(user_id, result)
        return result
