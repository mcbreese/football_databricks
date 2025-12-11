import sys
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit
# Note: We still import types, but they are not used in this version.
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, LongType, DateType, TimestampType

# --- Configuration ---
# NOTE: In a real environment, these configs would be loaded from a config file (e.g., config/paths.json)
# Base path where your raw CSV files are stored
RAW_FILES_BASE_PATH = "/Volumes/learning_catalog/raw_data/landing/"
CATALOG_NAME = "learning_catalog"
SCHEMA_NAME = "football_raw"
TARGET_DATABASE = f"{CATALOG_NAME}.{SCHEMA_NAME}"

# ----------------------------------------------------------------------------------
# !!! TECHNICAL DEBT ALERT !!!
# 
# The SCHEMAS dictionary has been removed, and the job is now relying on 
# 'inferSchema: true'. This is a fast but unsafe practice for production.
# 
# ACTION REQUIRED: In the future, please define and reinstate the SCHEMAS dictionary 
# and switch 'inferSchema' back to 'false' for reliable type handling.
# 
# ----------------------------------------------------------------------------------
SCHEMAS = {} # Removed content for this temporary approach


def create_database(spark: SparkSession):
    """Creates the target database if it does not exist."""
    print(f"Ensuring target database '{TARGET_DATABASE}' exists...")
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {TARGET_DATABASE}")


def get_file_list(spark: SparkSession) -> list:
    """
    Lists the CSV files in the base path.
    Uses dbutils if available (in Databricks environment),
    otherwise uses standard Spark file listing for general Spark environments.
    """
    try:
        # Check if dbutils is available (Databricks specific)
        from pyspark.sql import SparkSession
        dbutils = SparkSession.builder.getOrCreate().dbutils
        print(f"Listing files in Databricks path: {RAW_FILES_BASE_PATH}")
        # Filter for only CSV files and return the path and name
        return [(f.path, os.path.splitext(f.name)[0]) for f in dbutils.fs.ls(RAW_FILES_BASE_PATH) if f.name.endswith('.csv')]
    except (ImportError, AttributeError):
        # Fallback for local testing or non-Databricks Spark
        print(f"Listing files in local path: {RAW_FILES_BASE_PATH}")
        # Use Spark to list files, which is safer than os.listdir for distributed filesystems
        files = spark.sparkContext.wholeTextFiles(f"{RAW_FILES_BASE_PATH}*.csv").keys().collect()
        return [(f, os.path.splitext(os.path.basename(f))[0]) for f in files]


def process_file(spark: SparkSession, file_path: str, table_name: str):
    """
    Reads a single CSV file, applies schema inference, adds metadata, and writes to a Delta table.
    """
    try:
        # NOTE: Schema definition check is skipped here due to inferSchema=true
        
        # 1. Read the CSV file with schema inference enabled
        df = spark.read.format("csv") \
            .option("header", "true") \
            .option("inferSchema", "true") \
            .load(file_path)
            
        # 2. Add metadata columns (Source and Load Timestamp)
        df_processed = df.withColumn("source_file", lit(os.path.basename(file_path))) \
                         .withColumn("loaded_timestamp", current_timestamp())
        
        # 3. Define the target table name and write the data
        full_table_name = f"{TARGET_DATABASE}.{table_name}"
        
        df_processed.write.format("delta") \
            .mode("overwrite") \
            .option("mergeSchema", "true") \
            .saveAsTable(full_table_name)
            
        print(f"Successfully loaded {df_processed.count()} rows into raw table '{full_table_name}' using schema inference.")

    except Exception as e:
        print(f"Error processing {table_name} from {file_path}: {e}")
        raise e


def main():
    """Main execution function for the PySpark job."""
    
    # 1. Initialize Spark Session
    # Use getOrCreate() for execution on Databricks/Spark clusters
    spark = SparkSession.builder.appName("FootballBronzeIngestion") \
        .getOrCreate()
    
    print("--- Starting raw data ingestion ---")
    
    # 2. Ensure the Target Database Exists
    create_database(spark)
    
    # 3. Get list of files to process
    file_list = get_file_list(spark)
    
    # 4. Process each file
    for file_path, table_name in file_list:
        print(f"\n--- Processing {table_name}.csv ---")
        process_file(spark, file_path, table_name)
        
    print("\nIngestion process complete!")
    spark.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Job failed during main execution: {e}")
        sys.exit(1)