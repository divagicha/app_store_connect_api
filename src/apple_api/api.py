import hashlib
import mimetypes
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

    def _api_call(self, uri, method="get", post_data=None, file_meta=None):
        headers = {"Authorization": "Bearer %s" % self.token}
        if self._debug:
            print(uri)
        r = {}

        url = BASE_API + uri if method != 'put' else uri
        if method.lower() == "get":
            r = requests.get(url, headers=headers)
        elif method.lower() == "post":
            headers["Content-Type"] = "application/json"
            r = requests.post(url=url, headers=headers, data=json.dumps(post_data))
        elif method.lower() == "patch":
            headers["Content-Type"] = "application/json"
            r = requests.patch(url=url, headers=headers, data=json.dumps(post_data))
        elif method.lower() == "put":
            headers["Content-Type"] = file_meta['content_type']
            r = requests.put(url=url, headers=headers, data=file_meta['file'])
        elif method.lower() == "delete":
            r = requests.delete(url=url, headers=headers)

        try:
            content_type = r.headers['content-type']
        except KeyError:
            content_type = ''

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

    def create_iap_price_schedule(self, iap_id=None, price_point_id=None, price=None):
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
                                'id': price_point_id,
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

    def get_iap_review_screenshot_request_status(self, creation_id=None):
        if not creation_id:
            raise InvalidParameterException(f"'creation_id' is required for getting status of "
                                            f"your request")

        return self._api_call(f"/v1/inAppPurchaseAppStoreReviewScreenshots/{creation_id}")

    def create_iap_review_screenshot_request(self, iap_id=None, file_path=None):
        if not iap_id or not file_path:
            raise InvalidParameterException(f"'iap_id' and 'file_path' are required for creating "
                                            f"screenshot review request")

        try:
            file_name = os.path.basename(file_path)
            file_size_in_bytes = os.path.getsize(file_path)
        except Exception as exc:
            raise exc

        metadata = {
            'data': {
                'type': 'inAppPurchaseAppStoreReviewScreenshots',
                'attributes': {
                    'fileName': file_name,
                    'fileSize': file_size_in_bytes
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

        res = self._api_call(f"/v1/inAppPurchaseAppStoreReviewScreenshots", method="post", post_data=metadata)

        response_json = res.json()
        creation_id = response_json['data']['id']
        put_url = response_json['data']['attributes']['uploadOperations'][0]['url']

        _ = self._upload_iap_review_screenshot(
            put_url=put_url,
            file_path=file_path
        )

        return self._commit_iap_review_screenshot_request(
            creation_id=creation_id,
            file_path=file_path
        )

    def _upload_iap_review_screenshot(self, put_url=None, file_path=None):
        if not put_url or not file_path:
            raise InvalidParameterException(f"'put_url' and 'file_path' are required "
                                            f"for uploading screenshot file")

        try:
            file_handle = open(file_path, 'rb')
        except Exception as exc:
            raise exc

        return self._api_call(
            put_url,
            method="put",
            file_meta={
                'content_type': mimetypes.MimeTypes().guess_type(file_path)[0],
                'file': file_handle
            }
        )

    def _commit_iap_review_screenshot_request(self, creation_id=None, file_path=None):
        if not creation_id or not file_path:
            raise InvalidParameterException(f"'creation_id' and 'file_path' are required for commiting "
                                            f"screenshot review request")

        try:
            with open(file_path, 'rb') as file:
                file_checksum = hashlib.md5(file.read()).hexdigest()
        except Exception as exc:
            raise exc

        metadata = {
            'data': {
                'id': creation_id,
                'type': 'inAppPurchaseAppStoreReviewScreenshots',
                'attributes': {
                    'sourceFileChecksum': file_checksum,
                    'uploaded': True
                }
            }
        }

        return self._api_call(f"/v1/inAppPurchaseAppStoreReviewScreenshots/{creation_id}", method="patch", post_data=metadata)

    def delete_iap_review_screenshot(self, creation_id=None):
        if not creation_id:
            raise InvalidParameterException(f"'creation_id' is required "
                                            f"for deleting screenshot file")

        return self._api_call(f"/v1/inAppPurchaseAppStoreReviewScreenshots/{creation_id}", method="delete")

    def submit_nr_subscription_for_review(self, iap_id=None):
        if not iap_id:
            raise InvalidParameterException("'iap_id' is mandatory "
                                            "parameter for submitting subscription request")

        metadata = {
            'data': {
                'type': 'inAppPurchaseSubmissions',
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

        return self._api_call(f"/v1/inAppPurchaseSubmissions", method="post", post_data=metadata)

    def list_subscription_groups(self):
        return self._api_call(f"/v1/apps/{os.getenv('APP_ID')}/subscriptionGroups")

    def get_subscription_group(self, sg_id=None):
        if not sg_id:
            raise InvalidParameterException("'sg_id' is mandatory parameter for fetching "
                                            "subscription group info")

        return self._api_call(f"/v1/subscriptionGroups/{sg_id}")

    def create_subscription_group(self, name=None):
        if not name:
            raise InvalidParameterException("'name' is mandatory parameter for creating "
                                            "subscription group")

        metadata = {
            'data': {
                'type': 'subscriptionGroups',
                'attributes': {
                    'referenceName': name
                },
                'relationships': {
                    'app': {
                        'data': {
                            'id': os.getenv('APP_ID'),
                            'type': 'apps'
                        }
                    }
                }
            }
        }

        return self._api_call(f"/v1/subscriptionGroups", method="post", post_data=metadata)

    def delete_subscription_group(self, sg_id=None):
        if not sg_id:
            raise InvalidParameterException("'sg_id' is mandatory parameter for deleting a "
                                            "subscription group")

        return self._api_call(f"/v1/subscriptionGroups/{sg_id}", method="delete")

    def list_subscription_group_localizations(self, sg_id=None):
        if not sg_id:
            raise InvalidParameterException("'sg_id' is mandatory parameter for fetching all "
                                            "localizations for a subscription group")

        return self._api_call(f"/v1/subscriptionGroups/{sg_id}/subscriptionGroupLocalizations")

    def list_subscriptions_in_a_group(self, sg_id=None):
        if not sg_id:
            raise InvalidParameterException("'sg_id' is mandatory parameter for fetching all "
                                            "subscriptions inside a group")

        return self._api_call(f"/v1/subscriptionGroups/{sg_id}/subscriptions")

    def create_ar_subscription(self, sg_id=None, name=None, product_id=None,
                               subscription_period=None, group_level: int = None, review_note=None):
        if not sg_id or not name or not product_id or not subscription_period or not group_level:
            raise InvalidParameterException("'sg_id', 'name', 'product_id', 'subscription_period' "
                                            "and 'group_level' are mandatory parameters for "
                                            "creating an auto-renewable subscription")

        valid_subscription_periods = ['ONE_WEEK', 'ONE_MONTH', 'TWO_MONTHS', 'THREE_MONTHS',
                                      'SIX_MONTHS', 'ONE_YEAR']
        if subscription_period not in valid_subscription_periods:
            raise InvalidParameterException("invalid value provided for parameter "
                                            f"'subscription_period'. Possible values: {valid_subscription_periods}")

        metadata = {
            'data': {
                'type': 'subscriptions',
                'attributes': {
                    'name': name,
                    'productId': product_id,
                    'subscriptionPeriod': subscription_period,
                    # 'groupLevel': group_level,
                    'familySharable': False,
                    'availableInAllTerritories': True,
                    'reviewNote': review_note
                },
                'relationships': {
                    'group': {
                        'data': {
                            'id': sg_id,
                            'type': 'subscriptionGroups'
                        }
                    }
                }
            }
        }

        return self._api_call(f"/v1/subscriptions", method="post", post_data=metadata)

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
