import pandas as pd
import statsmodels.api as sm
from django.utils import timezone
import warnings

# Ignore warnings from statsmodels for cleaner output
warnings.filterwarnings("ignore")

class SpendingForecaster:
        def __init__(self, transactions_queryset):
            """
            Initializes the forecaster with the user's transaction data.
            'transactions_queryset' should be a queryset of the user's Transaction objects.
            """
            # We only care about expenses for forecasting spending
            self.expenses = transactions_queryset.filter(transaction_type='expense').order_by('date')

        def _prepare_daily_data(self):
            """
            Transforms the raw transaction data into a daily spending time series using pandas.
            """
            if not self.expenses.exists():
                return None

            # Convert queryset to a pandas DataFrame
            df = pd.DataFrame(list(self.expenses.values('date', 'amount')))
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # Ensure amounts are float for numpy/statsmodels numerical routines
            # Resample the data into daily totals. 'D' means daily frequency.
            daily_spending = df['amount'].astype(float).resample('D').sum().fillna(0)
            
            return daily_spending

        def forecast_next_30_days(self):
            """
            Forecasts the total spending for the next 30 days.
            Returns a single number (the forecasted total) or None if not possible.
            """
            daily_data = self._prepare_daily_data()

            # --- Edge Case Handling ---
            # We need enough data to make a meaningful forecast.
            # If we have less than 30 days of data, fallback to average daily spending * 30.
            if daily_data is None or len(daily_data) < 30:
                if daily_data is not None and len(daily_data) > 0:
                    avg_daily_spend = float(daily_data.mean())
                    return avg_daily_spend * 30
                return None # Not enough data to calculate an average

            try:
                # --- The Time Series Model (SARIMA) ---
                model = sm.tsa.statespace.SARIMAX(daily_data,
                                                  order=(1, 1, 1),
                                                  seasonal_order=(1, 1, 0, 7),
                                                  enforce_stationarity=False,
                                                  enforce_invertibility=False)
                
                results = model.fit(disp=False)
                
                # --- Prediction ---
                forecast = results.get_forecast(steps=30)
                
                # Non-negative spending values
                predicted_spending = forecast.predicted_mean.copy()
                predicted_spending[predicted_spending < 0] = 0
                
                return float(predicted_spending.sum())

            except Exception as e:
                # Fallback to mean daily spend if model fitting encounters numerical convergence issues
                if daily_data is not None and len(daily_data) > 0:
                    return float(daily_data.mean()) * 30
                return None
    
