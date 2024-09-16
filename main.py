from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import pickle
import time

# Scopes for the Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']

# Folder ID for the specific folder to monitor
FOLDER_ID = '1zxrkg0Ug5po-njoqu9ULiJuDMT7PXUg-'

# Authenticate and build the Drive API service
def authenticate():
    print("Authenticating...")
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
        print("Loaded existing credentials.")
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("No valid credentials found. Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        print("New credentials saved.")
    return build('drive', 'v3', credentials=creds)

def is_in_folder(service, file_id, target_folder_id):
    """Check if the file is in the specified folder or its subfolders."""
    try:
        # Get file metadata, including parents
        file_metadata = service.files().get(fileId=file_id, fields='id, parents').execute()
        parents = file_metadata.get('parents', [])
        
        # Directly check if one of the parents is the target folder
        if target_folder_id in parents:
            return True
        
        # Recursively check parent folders if not a direct child
        for parent_id in parents:
            if is_in_folder(service, parent_id, target_folder_id):
                return True

        return False
    except Exception as e:
        print(f"An error occurred while checking folder hierarchy: {e}")
        return False

def copy_and_remove_file(service, file_id, file_name):
    try:
        print(f"Attempting to copy file: {file_name} (ID: {file_id})")
        copied_file = service.files().copy(fileId=file_id, body={'name': file_name}).execute()
        print(f"Copied file: {file_name} with new ID: {copied_file['id']}")
        print(f"Attempting to delete original file: {file_name} (ID: {file_id})")
        service.files().delete(fileId=file_id).execute()
        print(f"Original file {file_name} deleted.")
    except Exception as e:
        print(f"An error occurred while copying and removing the file: {e}")

def list_changes(service, start_page_token):
    try:
        print("Fetching changes...")
        results = service.changes().list(
            pageToken=start_page_token, spaces='drive', 
            includeItemsFromAllDrives=True, supportsAllDrives=True
        ).execute()
        changes = results.get('changes', [])
        
        if changes:
            print(f"{len(changes)} change(s) detected.")
            for change in changes:
                if 'file' in change:
                    file_id = change['file']['id']
                    file_info = service.files().get(fileId=file_id, fields='id, name, parents').execute()
                    
                    print(f"Detected change - File ID: {file_id}, File Name: {file_info['name']}, Parents: {file_info.get('parents')}")
                    
                    # Check if the file is in the specified folder or its subfolders
                    if is_in_folder(service, file_id, FOLDER_ID):
                        print(f"File {file_info['name']} is in the specified folder. Processing...")
                        copy_and_remove_file(service, file_id, file_info['name'])
                    else:
                        print(f"File {file_info['name']} is not in the specified folder. Skipping...")
        else:
            print('No changes found.')
        
        return results.get('newStartPageToken')
    
    except Exception as e:
        print(f"An error occurred while fetching changes: {e}")
        return start_page_token

def main():
    print("Starting the Google Drive change listener...")
    service = authenticate()
    response = service.changes().getStartPageToken().execute()
    start_page_token = response.get('startPageToken')
    print(f'Start page token: {start_page_token}')

    while True:
        try:
            new_start_page_token = list_changes(service, start_page_token)
            if new_start_page_token:
                start_page_token = new_start_page_token
            
            print("Sleeping for 10 seconds...")
            time.sleep(10)
        except Exception as error:
            print(f'An error occurred in the main loop: {error}')
            print("Retrying in 10 seconds...")
            time.sleep(10)

if __name__ == '__main__':
    main()
