import functools
import urllib3
import requests
import json
from fadcclient.api.exceptions import *
from fadcclient.utils.logging import get_logger

class FortiAdcApiClient(object):

    def __init__(self, base_url: str, username: str, password: str, verify_ssl: bool = False, verbosity: int = 4) -> None:
        self.base_url = base_url
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.verbosity = verbosity
        self.logger = get_logger(name="ADC", verbosity=self.verbosity, with_threads=False)
        self.logger.info(msg="Initializing FortiADC API Client")
        self.session = None

    def initialize(self):
        if not self.verify_ssl:
            self.logger.debug(msg="Disabling warnings for urllib3")
            urllib3.disable_warnings()
        self.session = requests.Session()
        if self.verify_ssl is False:
            self.session.verify = False
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Cache-Control": "no-cache"
            }
        )
        self.authenticate()

    def authenticate(self):
        try:
            auth_response = self.session.post(
                url=f"{self.base_url}/api/user/login",
                data=json.dumps({
                    "username": self.username,
                    "password": self.password
                })
            )
            if auth_response.status_code == 200:
                self.logger.info("Authentication Successful.")
                token = auth_response.json()['token']
                self.logger.debug(msg=f"Received Authentication Bearer Token")
                self.session.headers.update({"Authorization": f"Bearer {token}"})
            if auth_response.status_code == 401:
                self.logger.error("Authentication Error. Check username and password.")
                raise AuthenticationFailed()
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection Error. Cannot connect to {self.base_url}. Exception: {repr(e)}")
            raise
        except AuthenticationFailed as e:
            self.logger.error(f"Authentication Error. Cannot authenticate to {self.base_url}. Exception: {repr(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Encountered unhandled exception: {repr(e)}")
            raise
    
    def retry(count=1):
        def inner(func):
            def wrapper(self, *args, **kwargs):
                retries = 0
                response: requests.Response = func(self, *args, **kwargs)
                while response.status_code == 401 and retries <= count:
                    retries += 1
                    self.logger.info("Unauthorized - Retrying")
                    try:
                        self.authenticate()
                    except AuthenticationFailed as e:
                        return response
                    response: requests.Response = func(self, *args, **kwargs)
                return response
            return wrapper
        return inner
    
    def get(self, path, params: dict = None) -> requests.Response:
        response = self.session.get(
            url=self.base_url + path, 
            params=params
        )
        return response

    def post(self, path, params: dict = None, data: dict = None) -> requests.Response:
        if isinstance(data, dict):
            data = json.dumps(data)
        response = self.session.post(
            url=self.base_url + path, 
            params=params,
            data=data
        )
        return response

    def put(self, path, params: dict = None, data: dict = None) -> requests.Response:
        if isinstance(data, dict):
            data = json.dumps(data)
        response = self.session.put(
            url=self.base_url + path, 
            params=params,
            data=data
        )
        return response

    def delete(self, path, params: dict = None) -> requests.Response:
        response = self.session.delete(
            url=self.base_url + path, 
            params=params,
        )
        return response
    
    @retry()
    def send_request(self, method: str, path: str, params: dict = None, data: dict = None) -> requests.Response:
        response = None
        try:
            if method.lower() == 'get':
                self.logger.debug(msg=f"{method.upper()} {path} Params:{params}")
                response = self.get(path=path, params=params)
            elif method.lower() == 'post':
                self.logger.debug(msg=f"{method.upper()} {path} Params:{params} Data: '{data}'")
                response = self.post(path=path, params=params, data=data)
            elif method.lower() == 'put':
                self.logger.debug(msg=f"{method.upper()} {path} Params:{params} Data: '{data}'")
                response = self.put(path=path, params=params, data=data)
            elif method.lower() == 'delete':
                self.logger.debug(msg=f"{method.upper()} {path} Params:{params}")
                response = self.delete(path=path, params=params)
            else:
                msg = f"Unsupported method: {method}"
                self.logger.error(msg=msg)
                raise ValueError(msg)
            if response.status_code == 404:
                self.logger.warning(msg=f"Got 404 on {path} with {params}")
        except Exception as e:
            self.logger.error(f"Encountered unhandled exception: {repr(e)}")
            raise
        finally:
            return response
        
    def handle_response(self, response: requests.Response):
        is_error, error, data = (None, None, None)
        response_data = response.json()
        if 'payload' not in response_data.keys():
            is_error = True
        else:
            data = response_data['payload']
            if isinstance(data, int) and data < 0:
                is_error = True
                error = get_err_msg(connection=self, err_id=data)
                self.logger.error(msg=f"Error Response: Code: {data} Msg: {error}")
            else:
                is_error = False
        return is_error, error, data

        

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
        self.logger.info("Session closed.")


    def __str__(self) -> str:
        return f"[{self.__class__.__name__}-{self.base_url}]"

    def __repr__(self) -> str:
        return self.__str__()

    




@functools.lru_cache
def _get_error_codes(connection):
    response = connection.send_request(method='GET', path='/api/platform/errMsg')
    is_error, error, data = connection.handle_response(response=response)
    if is_error:
        data = dict()
    return data

@functools.lru_cache
def get_err_msg(connection, err_id):
    error_codes = _get_error_codes(connection=connection)
    if str(err_id) in error_codes.keys():
        err_msg = error_codes[str(err_id)]
    else:
        err_msg = f"Error code: {str(err_id)}"
    return err_msg


