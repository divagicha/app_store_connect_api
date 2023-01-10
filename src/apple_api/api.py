import os
import requests
import jwt
import gzip
from datetime import datetime, timedelta
import time
import json
import base64

from .exceptions import *

ALGORITHM = 'ES256'
BASE_API = "https://api.appstoreconnect.apple.com"
APP_ID = os.getenv('APP_ID', '')


class AppStoreConnect:
    def __init__(self, key_id, key_file, issuer_id):
        self._token = None
        self.token_gen_date = None
        self.exp = None
        self.key_id = key_id
        self.key_file = key_file
        self.issuer_id = issuer_id
        self._debug = False
        token = self.token  # generate first token

    @property
    def token(self):
        # generate a new token every 15 minutes
        if not self._token or self.token_gen_date + timedelta(minutes=15) < datetime.now():
            self._token = self._generate_token()

        return self._token

    def _generate_token(self):
        key = open(self.key_file, 'r').read()
        self.token_gen_date = datetime.now()
        exp = int(time.mktime((self.token_gen_date + timedelta(minutes=20)).timetuple()))
        return jwt.encode({'iss': self.issuer_id, 'exp': exp, 'aud': 'appstoreconnect-v1'}, key,
                          headers={'kid': self.key_id, 'typ': 'JWT'}, algorithm=ALGORITHM).decode(
            'ascii')

    def _api_call(self, uri, method="get", post_data=None):
        if method not in ["get", "post", "patch"]:
            raise MethodNotAllowedException(f"allowed values are: ['get', 'post', 'patch']")

        headers = {"Authorization": "Bearer %s" % self.token}
        if self._debug:
            print(uri)
        r = {}

        url = BASE_API + uri
        if method.lower() == "get":
            r = requests.get(url, headers=headers)
        elif method.lower() == "post":
            headers["Content-Type"] = "application/json"
            r = requests.post(url=url, headers=headers, data=json.dumps(post_data))
        elif method.lower() == "patch":
            headers["Content-Type"] = "application/json"
            r = requests.patch(url=url, headers=headers, data=json.dumps(post_data))

        content_type = r.headers['content-type']

        if content_type == 'application/a-gzip':
            # TODO implement stream decompress
            data_gz = b""
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    data_gz = data_gz + chunk

            data = gzip.decompress(data_gz)
            return data.decode("utf-8")
        else:
            return r

    def fetch(self, uri, method="get", post_data=None):
        return self._api_call(uri, method, post_data)

    def list_apps(self):
        return self._api_call("/v1/apps")

    def list_builds(self):
        return self._api_call("/v1/builds")

    def list_bundle_ids(self):
        return self._api_call("/v1/bundleIds")

    def list_certificates(self):
        return self._api_call("/v1/certificates")

    def download_certificate(self, certificatID=None, saveFolderPath=None):
        try:
            r = self._api_call("/v1/certificates/" + certificatID)
            r = r.json()
            attributes = r["data"]["attributes"]
            certificateContent = attributes["certificateContent"]
            name = attributes["name"]
            saveFilePath = name + ".cer"
            f = open(saveFilePath, "w")
            f.write(base64.b64decode(certificateContent))
            f.close()
            return "success"
        except FileNotFoundError:
            return "failure"

    def list_devices(self):
        return self._api_call("/v1/devices")

    def list_in_app_purchases(self, app_id=None):
        if not app_id:
            raise InvalidParameterException(f"'app_id' is required for this endpoint")

        return self._api_call(f"/v1/apps/{app_id}/inAppPurchasesV2")

    def create_iap_nr_subscription(self, name=None, product_id=None, review_note=None):
        if not name or not product_id:
            raise InvalidParameterException("'name' and 'product_id' are mandatory parameters for creating a non-renewing subscription")

        metadata = {
            'data': {
                'type': 'inAppPurchases',
                'attributes': {
                    'name': name,
                    'productId': product_id,
                    'inAppPurchaseType': 'NON_RENEWING_SUBSCRIPTION',
                    'familySharable': False,
                    'availableInAllTerritories': True,
                    'reviewNote': review_note
                },
                'relationships': {
                    'app': {
                        'data': {
                            'id': APP_ID,
                            'type': 'apps'
                        }
                    }
                }
            }
        }

        return self._api_call("/v2/inAppPurchases", method="post", post_data=metadata)

    def get_iap_purchase_localizations(self, iap_id=None):
        if not iap_id:
            raise InvalidParameterException(f"'iap_id' is required for listing price localizations")

        return self._api_call(f"/v2/inAppPurchases/{iap_id}/inAppPurchaseLocalizations")

    def create_iap_purchase_localization(self, iap_id=None, name=None, locale=None, description=None):
        if not iap_id or not name or not locale:
            raise InvalidParameterException("'iap_id', 'name' and 'locale' are mandatory "
                                            "parameters for creating localization")

        metadata = {
            'data': {
                'type': 'inAppPurchaseLocalizations',
                'attributes': {
                    'name': name,
                    'locale': locale,
                    'description': description
                },
                'relationships': {
                    'inAppPurchaseV2': {
                        'data': {
                            'id': iap_id,
                            'type': 'inAppPurchases'
                        }
                    }
                }
            }
        }

        return self._api_call(f"/v1/inAppPurchaseLocalizations", method="post", post_data=metadata)

    def get_iap_price_points(self, iap_id=None):
        if not iap_id:
            raise InvalidParameterException(f"'iap_id' is required for listing price points")

        return self._api_call(f"/v2/inAppPurchases/{iap_id}/pricePoints")

    def get_iap_price_schedules(self, iap_id=None):
        if not iap_id:
            raise InvalidParameterException(f"'iap_id' is required for listing price schedules")

        return self._api_call(f"/v1/inAppPurchasePriceSchedules/{iap_id}")

    def create_iap_price_schedule(self, iap_id=None, price=None):
        if not iap_id:
            raise InvalidParameterException(f"'iap_id' is required for listing price schedules")

        metadata = {
            'data': {
                # 'id': iap_id,
                'type': 'inAppPurchasePriceSchedules',
                # 'attributes': {},
                'relationships': {
                    'inAppPurchase': {
                        'data': {
                            'id': iap_id,
                            'type': 'inAppPurchases'
                        }
                    },
                    'manualPrices': {
                        'data': [
                            {
                                'id': f"${price}",
                                'type': 'inAppPurchasePrices'
                            }
                        ]
                    }
                }
            },
            'included': [
                {
                    'id': f"${price}",
                    'type': 'inAppPurchasePrices',
                    'attributes': {
                        'startDate': None,
                    },
                    'relationships': {
                        'inAppPurchasePricePoint': {
                            'data': {
                                'id': "eyJzIjoiNjQ0NTM1MDg1NyIsInQiOiJBRkciLCJwIjoiNTkwIn0",    # 4.99
                                'type': 'inAppPurchasePricePoints'
                            }
                        },
                        'inAppPurchaseV2': {
                            'data': {
                                'id': iap_id,
                                'type': 'inAppPurchases'
                            }
                        }
                    }
                }
            ]
        }

        return self._api_call(f"/v1/inAppPurchasePriceSchedules", method="post", post_data=metadata)

    def get_iap_manual_prices(self, iap_id=None):
        if not iap_id:
            raise InvalidParameterException(f"'iap_id' is required for listing manual price")

        return self._api_call(f"/v1/inAppPurchasePriceSchedules/{iap_id}/manualPrices")

    def list_profiles(self):
        return self._api_call("/v1/profiles")

    def download_profile(self, profileID=None, saveFolderPath=None):
        try:
            r = self._api_call("/v1/profiles/" + profileID)
            r = r.json()
            attributes = r["data"]["attributes"]
            profileContent = attributes["profileContent"]
            name = attributes["uuid"]
            saveFilePath = saveFolderPath + "/" + name + ".mobileprovision"
            f = open(saveFilePath, "w")
            f.write(base64.b64decode(profileContent))
            f.close()
            return "success"
        except FileNotFoundError:
            return "failure"

    def list_users(self):
        return self._api_call("/v1/userInvitations")
