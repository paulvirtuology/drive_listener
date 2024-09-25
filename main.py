from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import pickle
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Scopes for the Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']

# Folder ID for the specific folder to monitor
FOLDER_ID = '1zxrkg0Ug5po-njoqu9ULiJuDMT7PXUg-'

# Set to keep track of processed file IDs
processed_file_ids = set()

def authenticate():
    logging.info("Authenticating...")
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            logging.info("No valid credentials found. Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('drive', 'v3', credentials=creds)

def is_in_folder(service, file_id, target_folder_id):
    """Check if the file is in the specified folder or its subfolders."""
    try:
        file_metadata = service.files().get(fileId=file_id, fields='id, parents').execute()
        parents = file_metadata.get('parents', [])
        if target_folder_id in parents:
            return True
        for parent_id in parents:
            if is_in_folder(service, parent_id, target_folder_id):
                return True
        return False
    except Exception as e:
        logging.error(f"Error checking folder hierarchy: {e}")
        return False

def check_file_exists(service, folder_id, file_name):
    """Check if a file with the same name exists in the specified folder."""
    query = f"name='{file_name}' and '{folder_id}' in parents"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    return len(items) > 0  # Returns True if duplicates exist

def check_file_ownership(service, file_id, user_email):
    """Check if the file is owned by the specified user."""
    try:
        file_metadata = service.files().get(fileId=file_id, fields='owners').execute()
        owners = file_metadata.get('owners', [])
        for owner in owners:
            if owner.get('emailAddress') == user_email:
                return True  # The user is an owner of the file
    except Exception as e:
        logging.error(f"Error checking file ownership: {e}")
    return False  # The user is not an owner

def copy_and_remove_file(service, file_id, file_name, user_email):
    try:
        # Check if this file has already been processed
        if file_id in processed_file_ids:
            logging.info(f"File {file_name} (ID: {file_id}) has already been processed. Skipping.")
            return
        
        # Check if the owner of the file is this user
        if check_file_ownership(service, file_id, user_email):
            logging.info(f"You are the owner of {file_name}. Skipping copy.")
            return
        
        # Check if a file with the same name already exists in the target folder
        if check_file_exists(service, FOLDER_ID, file_name):
            logging.info(f"Duplicate file {file_name} already exists. Skipping copy.")
            return
        
        logging.info(f"Copying file: {file_name} (ID: {file_id})")
        copied_file = service.files().copy(fileId=file_id, body={'name': file_name}).execute()
        logging.info(f"Copied file: {file_name} with new ID: {copied_file['id']}")
        
        # Mark this file ID as processed
        processed_file_ids.add(file_id)

        # Delete original only after successful copy
        service.files().delete(fileId=file_id).execute()
        logging.info(f"Deleted original file: {file_name}.")
        
    except Exception as e:
        logging.error(f"Error copying and removing file: {e}")

def list_changes(service, start_page_token, user_email):
    try:
        logging.info("Fetching changes...")
        results = service.changes().list(
            pageToken=start_page_token,
            spaces='drive',
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute()
        
        changes = results.get('changes', [])
        
        if changes:
            logging.info(f"{len(changes)} change(s) detected.")
            for change in changes:
                if 'file' in change:
                    file_id = change['file']['id']
                    file_info = service.files().get(fileId=file_id, fields='id, name, parents').execute()
                    if is_in_folder(service, file_id, FOLDER_ID):
                        copy_and_remove_file(service, file_id, file_info['name'], user_email)
                    else:
                        logging.info(f"File {file_info['name']} is not in the specified folder. Skipping...")
        
        else:
            logging.info('No changes found.')
        
        return results.get('newStartPageToken')
    
    except Exception as e:
        logging.error(f"Error fetching changes: {e}")
        return start_page_token

def main():
    service = authenticate()
    response = service.changes().getStartPageToken().execute()
    start_page_token = response.get('startPageToken')
    
    user_email = 'YOUR_EMAIL@example.com'  # Replace with your email address
    
    while True:
        try:
            new_start_page_token = list_changes(service, start_page_token, user_email)
            if new_start_page_token:
                start_page_token = new_start_page_token
            
            time.sleep(10)  # Sleep to avoid rapid polling
            
        except Exception as error:
            logging.error(f'Error in main loop: {error}')
            time.sleep(10)

if __name__ == '__main__':
    main()