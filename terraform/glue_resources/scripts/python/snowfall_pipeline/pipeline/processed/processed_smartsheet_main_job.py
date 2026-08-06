
from snowfall_pipeline.common_utilities.transform_base import TransformBase
import boto3
import time


class ProcessedSmartsheetMainJob(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)

        self.bucket_name = self.raw_bucket_name
        self.prefix = "smartsheet/"
        self.main_job_name = "uk-snowfall-main-script-runner"  # Main Glue job name

        self.s3_client = boto3.client('s3')
        self.glue_client = boto3.client('glue')

    def get_data(self):
        """
        List subfolders and trigger the worker Glue job with DATASET and EXTENSION.
        Then monitor all jobs and fail if any job fails.
        """
        self.logger.info(f"Scanning bucket: {self.bucket_name}, prefix: {self.prefix}")

        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            subfolders = []
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix, Delimiter='/'):
                for prefix_info in page.get('CommonPrefixes', []):
                    subfolders.append(prefix_info['Prefix'].split('/')[-2])

            if not subfolders:
                self.logger.warning("No subfolders found.")
                return

            self.logger.info(f"Found subfolders: {subfolders}")

            glue_jobs = []

            for subfolder in subfolders:
                folder_prefix = f"{self.prefix}{subfolder}/"
                self.logger.info(f"Checking files in subfolder: {folder_prefix}")

                #use paginator for files listing ---
                files_paginator = self.s3_client.get_paginator('list_objects_v2')
                extension = 'unknown'
                found = False

                for files_page in files_paginator.paginate(Bucket=self.bucket_name, Prefix=folder_prefix):
                    for obj in files_page.get('Contents', []):
                        key = obj['Key']
                        filename = key.split('/')[-1]
                        if '.' in filename:  # Ensure it's a file
                            extension = filename.split('.')[-1].lower()
                            found = True
                            break
                    if found:
                        break
                
                # Stop workflow if no file found in a subfolder
                if not found:
                    self.logger.warning(f"No files found inside subfolder '{subfolder}'. Skipping Glue job for this subfolder.")
                    continue


                self.logger.info(f"Extension for {subfolder}: {extension}")

                # Trigger Glue job with DATASET and EXTENSION
                glue_job = self.glue_client.start_job_run(
                    JobName=self.main_job_name,
                    Arguments={
                        '--GROUP': 'preparation',
                        '--DATASET': 'smartsheet_worker_job',
                        '--SUB_DATASET': subfolder,
                        '--EXTENSION': extension
                    }
                )

                glue_jobs.append((subfolder, glue_job['JobRunId']))
                self.logger.info(f"Worker job triggered for {subfolder}, JobRunId: {glue_job['JobRunId']}")

            # Monitor jobs concurrently
            self._monitor_jobs(glue_jobs)

        except Exception as e:
            self.logger.error(f"Error triggering worker job: {str(e)}")
            raise

        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')

    def _monitor_jobs(self, glue_jobs, poll_interval=30):
        """
        Concurrently wait for all jobs to complete. Collect failed jobs and raise error if any fail.
        """
        failed_jobs = []
        # Track running jobs: run_id -> subfolder
        running = {run_id: subfolder for subfolder, run_id in glue_jobs}

        while running:
            to_remove = []

            for run_id, subfolder in running.items():
                # --- FIX: correct API call to get job status ---
                resp = self.glue_client.get_job_run(JobName=self.main_job_name, RunId=run_id)
                glue_job = resp['JobRun']
                state = glue_job.get('JobRunState')

                if state == 'SUCCEEDED':
                    self.logger.info(f"Job for {subfolder} succeeded. JobRunId: {run_id}")
                    to_remove.append(run_id)
                elif state in ('FAILED', 'ERROR', 'TIMEOUT', 'STOPPED'):
                    error_message = glue_job.get('ErrorMessage', 'No ErrorMessage returned')
                    self.logger.error(
                        f"Job for {subfolder} failed. JobRunId: {run_id}, "
                        f"state: {state}, error: {error_message}"
                    )
                    failed_jobs.append((subfolder, run_id, state, error_message))
                    to_remove.append(run_id)
                else:
                    # Still running/starting/etc.
                    self.logger.debug(f"Job for {subfolder} status: {state}. JobRunId: {run_id}")

            # Remove finished/failed jobs
            for run_id in to_remove:
                running.pop(run_id, None)

            # Sleep before next polling round if any job remains
            if running:
                time.sleep(poll_interval)

        if failed_jobs:
            details = "; ".join(
                f"{subfolder} (JobRunId={run_id}, state={state}, error={err})"
                for subfolder, run_id, state, err in failed_jobs
            )
            error_msg = f"Worker jobs failed: {details}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
