import sys
import logging

# It's better to get the logger from the calling module or configure a new one
# For now, let's create a simple logger for this module.
log = logging.getLogger("fixarc.deadline")
if not log.handlers: # Avoid adding multiple handlers if already configured
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s [%(levelname)-7s] [%(name)s]: %(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.INFO) # Default level

# Import Deadline configuration from constants
try:
    from . import constants as fixarc_constants # deadline.py and constants.py are in the same fixarc/ directory
except ImportError:
    # Fallback for cases where relative import might fail (e.g., running script directly)
    # This assumes constants.py is in the same directory or PYTHONPATH.
    try:
        import constants as fixarc_constants
        log.info("Imported fixarc_constants directly.")
    except ImportError:
        log.error("Failed to import fixarc_constants. Deadline configuration will be missing.")
        # Define fallbacks or raise an error if constants are critical
        class MockConstants:
            DEADLINE_SERVER_ADDRESS = "localhost"
            DEADLINE_SERVER_PORT = 8081
            DEADLINE_USER = "unknown"
            DEADLINE_PASSWORD = ""
        fixarc_constants = MockConstants()

# Configuration for Deadline connection (ideally, these would be configurable)
DEADLINE_SERVER_ADDRESS = getattr(fixarc_constants, 'DEADLINE_SERVER_ADDRESS', "192.168.14.230")
DEADLINE_SERVER_PORT = getattr(fixarc_constants, 'DEADLINE_SERVER_PORT', 8081)
DEADLINE_USER = getattr(fixarc_constants, 'DEADLINE_USER', "fixrs-001")
DEADLINE_PASSWORD = getattr(fixarc_constants, 'DEADLINE_PASSWORD', "")

def submit_deadline_job(job_info, plugin_info=None, aux_files=None):
    """
    Submits a job to Deadline.

    Args:
        job_info (dict): A dictionary containing the job information.
                         Example keys: "Plugin", "Name", "Comment", "UserName",
                                       "Frames", "Executable", "Arguments".
        plugin_info (dict, optional): A dictionary containing plugin-specific information.
                                      Defaults to an empty dict.
        aux_files (list, optional): A list of auxiliary files to submit with the job.
                                   Defaults to an empty list.

    Returns:
        str: The Deadline job ID if submission is successful, None otherwise.
    """
    if plugin_info is None:
        plugin_info = {}
    if aux_files is None:
        aux_files = []

    log.info(f"Attempting to submit job '{job_info.get('Name', 'Unnamed Job')}' to Deadline.")

    try:
        from Deadline.api.Deadline import DeadlineConnect as Connect
    except ImportError as e:
        log.error("Failed to import DeadlineConnect. Ensure Deadline.api is in your PYTHONPATH.")
        log.error(f"Import error: {e}")
        return None


    deadline_connection = None
    try:
        log.debug(f"Connecting to Deadline at {DEADLINE_SERVER_ADDRESS}:{DEADLINE_SERVER_PORT}")
        deadline_connection = Connect.DeadlineCon(DEADLINE_SERVER_ADDRESS, DEADLINE_SERVER_PORT)

        if DEADLINE_USER: # Only enable authentication if a user is specified
            log.debug(f"Enabling Deadline authentication for user: {DEADLINE_USER}")
            auth_enabled = deadline_connection.EnableAuthentication(True)
            if not auth_enabled:
                log.warning("Failed to enable Deadline authentication. Check server settings.")
                # Depending on server config, this might not be a fatal error.
            
            # Set credentials whether auth was successfully enabled or not,
            # as some servers might require it even if EnableAuthentication returns False.
            creds_set = deadline_connection.SetAuthenticationCredentials(DEADLINE_USER, DEADLINE_PASSWORD)
            if not creds_set:
                log.warning(f"Failed to set Deadline authentication credentials for user '{DEADLINE_USER}'.")
                # This could be a problem.

        deadline_job_submission = {
            "JobInfo": job_info,
            "PluginInfo": plugin_info,
            "AuxFiles": aux_files
        }
        
        log.info(f"Submitting job with info: {job_info}")
        log.debug(f"Full submission object: {deadline_job_submission}")

        # SubmitJobs expects a list of jobs
        job_ids = deadline_connection.Jobs.SubmitJobs([deadline_job_submission])
        
        if job_ids and len(job_ids) > 0:
            job_id = job_ids[0] # Assuming one job submitted, get its ID
            log.info(f"Successfully submitted job to Deadline. Job ID: {job_id}")
            return job_id
        else:
            log.error("Failed to submit job to Deadline. No Job ID returned or empty list.")
            # Try to get more error info if possible
            error_report = deadline_connection.Jobs.GetJobErrorReports(job_ids if job_ids else []) # This might be incorrect API usage
            if error_report:
                log.error(f"Deadline error reports: {error_report}")
            return None

    except Exception as e:
        log.error(f"An error occurred during Deadline job submission: {e}", exc_info=True)
        return None
    finally:
        if deadline_connection:
            # DeadlineCon does not have an explicit close/disconnect method in the typical API examples.
            # Connection might be managed internally or be stateless per call after auth.
            log.debug("Deadline connection handling complete (no explicit disconnect needed).")

if __name__ == '__main__':
    # Example usage (for testing this module directly)
    # Ensure Deadline.api is in PYTHONPATH or adjust sys.path here for testing.
    # e.g. sys.path.append("/path/to/parent/of/Deadline")
    
    log.setLevel(logging.DEBUG)
    log.info("Testing Deadline submission module...")

    # Check if Deadline API can be imported
    try:
        from Deadline.api.Deadline import DeadlineConnect as Connect
        log.info("DeadlineConnect imported successfully for test.")
    except ImportError:
        log.error("Cannot import DeadlineConnect for testing. Ensure Deadline.api is in PYTHONPATH.")
        sys.exit(1)

    test_job_info = {
        "Plugin": "CommandLine",
        "Name": "Test CommandLine Job from Python",
        "Comment": "Test job submitted via fixarc.deadline module",
        "UserName": "test_user", # Or use DEADLINE_USER
        "Frames": "0",
        "Executable": "python" if sys.platform != "win32" else "python.exe",
        "Arguments": "-c \"import time; print('Hello from Deadline test job'); time.sleep(5)\""
    }
    
    # Optional: Set specific pool, group, priority
    # test_job_info["Pool"] = "none" # Example
    # test_job_info["Priority"] = 75 # Example

    job_id = submit_deadline_job(test_job_info)

    if job_id:
        log.info(f"Test job submitted. Job ID: {job_id}")
    else:
        log.error("Test job submission failed.")
