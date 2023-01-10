## Sample Usage

### Steps to follow:
1. `cd` into your project directory
2. clone this git repo `git clone https://github.com/divagicha/app_store_connect_api.git`
3. activate your virtual environment
4. run command `pip install -e .`
5. create a python file `main.py`
6. add following code to it 
    ```
    import os
    from os.path import join
    import json
    from dotenv import load_dotenv
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(join(BASE_DIR, '.env'))
    
    from apple_api import AppStoreConnect
    
    api = AppStoreConnect(os.getenv('KEY_ID'), os.getenv('KEY_FILE'), os.getenv('ISSUER_ID'))
    
    # list all apps
    res = api.list_apps()
    print(res.json())
    ```
7. create a `.env` file in current directory
8. add following keys to env file
   ```commandline
    KEY_ID=key_id
    ISSUER_ID=issuer_id
    KEY_FILE=path_to_key_file
    APP_ID=app_id
    ```
9. run your python file `python main.py`