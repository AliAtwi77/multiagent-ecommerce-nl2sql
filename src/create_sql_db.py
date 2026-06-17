from pathlib import Path
import sqlite3
import pandas as pd

# Project Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data folder containing the CSV files
DATA_DIR = PROJECT_ROOT / "data"

# Database folder and database file
DB_DIR = PROJECT_ROOT / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "ecommerce.db"

# Create Fresh Database
# Remove existing database if it already exists
if DB_PATH.exists():
    DB_PATH.unlink()

# Create SQLite connection
con = sqlite3.connect(DB_PATH)

#load the csv files from the data folder and convert them into sql tables
def load_df_to_sql(df_name:str, con, data_dir:str = "../data")-> None:
    """
    Load a CSV file into the database.

    Args:
        df_name (str): Name of the CSV file.
        conn: Database connection object.
        data_dir (str, optional): Directory where CSV files are stored.
    """
    # Build file path safely
    file_path = Path(data_dir) / df_name

    # Read CSV file
    df = pd.read_csv(file_path)

    # Generate clean table name
    table_name = (
        df_name
        .removeprefix("olist_")
        .removesuffix("_dataset.csv")
        .removesuffix(".csv")
    )

    #load into SQL
    df.to_sql(name=table_name, con= con, index=False, if_exists='replace')
    
    print(
        f"Loaded '{df_name}' → table '{table_name}' "
        f"({df.shape[0]} rows × {df.shape[1]} columns)"
    )

load_df_to_sql("olist_customers_dataset.csv", con)
load_df_to_sql("olist_geolocation_dataset.csv", con)
load_df_to_sql("olist_products_dataset.csv", con)
load_df_to_sql("olist_sellers_dataset.csv", con)
load_df_to_sql("olist_orders_dataset.csv", con)
load_df_to_sql("olist_order_items_dataset.csv", con)
load_df_to_sql("olist_order_payments_dataset.csv", con)
load_df_to_sql("olist_order_reviews_dataset.csv", con)
load_df_to_sql("product_category_name_translation.csv", con)

# Close Connection
con.close()
print(f"\nDatabase successfully created: {DB_PATH}")