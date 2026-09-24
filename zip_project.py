import zipfile
import os

zip_filename = 'pulsar_auto.zip'
exclude_dirs = {'audio', '__pycache__', 'error_logs', '.git', '.vscode'}
# local_secrets.json holds credentials (see secrets_loader.py) -- never ship it.
exclude_files = {zip_filename, 'app_err.log', 'app_out.log', 'local_secrets.json'}

with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk('.'):
        # modify dirs in place to skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file in exclude_files:
                continue
            # .bak files are stale source copies that can carry old hardcoded credentials
            if file.endswith('.wav') or file.endswith('.mp3') or file.endswith('.bak'):
                continue
            
            file_path = os.path.join(root, file)
            # Make the path relative to the root of the project
            arcname = os.path.relpath(file_path, '.')
            zipf.write(file_path, arcname)
            print(f"Added {arcname}")

print(f"\nSuccessfully created {zip_filename}")
