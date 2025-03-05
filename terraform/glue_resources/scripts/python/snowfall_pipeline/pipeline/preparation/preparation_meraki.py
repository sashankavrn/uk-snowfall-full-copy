# import boto3
# from snowfall_pipeline.common_utilities.transform_base import TransformBase
# from datetime import datetime


# class PreparationMeraki(TransformBase):

#     def __init__(self, spark, sc, glueContext):
#         super().__init__(spark, sc, glueContext)
#         self.file_path = "meraki"  # JSON files are inside the `meraki/` folder
#         self.s3_client = boto3.client("s3")  # Initialize S3 client

#     def get_data(self):
#         """
#         Reads the most recent Meraki JSON file from the raw bucket.
#         """
#         print(f"[INFO] Reading JSON file from {self.raw_bucket_name}/{self.file_path}/")

#         # List files in the raw bucket with the `meraki/` prefix
#         response = self.s3_client.list_objects_v2(
#             Bucket=self.raw_bucket_name,
#             Prefix=self.file_path
#         )

#         # Check if files exist
#         if 'Contents' not in response:
#             print("[ERROR] No files found in the raw bucket.")
#             return None

#         # Get the most recent file (based on last modified time)
#         files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
#         latest_file = files[0]['Key']

#         print(f"[INFO] Found the latest file: {latest_file}")
#         return latest_file

#     def save_data(self, df):
#         """
#         Copies the most recent Meraki JSON file from raw to processed bucket.
#         """
#         print("[INFO] Copying JSON from Raw to Processed Bucket")

#         # Get the source key (most recent file in raw bucket)
#         source_key = self.get_data()

#         if not source_key:
#             print("[ERROR] No source file found. Skipping file copy.")
#             return

#         # Define the target key (fixed name for testing)
#         target_key = f"{self.file_path}/prepared_data.json"

#         try:
#             # Copy JSON from raw to processed bucket
#             self.s3_client.copy_object(
#                 Bucket=self.processed_bucket_name,  # Destination bucket
#                 CopySource={"Bucket": self.raw_bucket_name, "Key": source_key},
#                 Key=target_key,
#             )
#             print(f"[SUCCESS] Copied JSON from {self.raw_bucket_name}/{source_key} to {self.processed_bucket_name}/{target_key}")

#         except Exception as e:
#             print(f"[ERROR] Failed to copy JSON file: {str(e)}")

#         print("[INFO] File Copy Completed - Test Successful")
