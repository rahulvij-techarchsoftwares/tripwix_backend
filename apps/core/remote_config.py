#!/usr/bin/python
# -*- coding: utf-8 -*-

import base64
import json
import logging
import os

import boto3
from botocore.exceptions import ClientError


class ConfigHelper(object):
    @classmethod
    def get(cls, param_name=None, default_value=None):
        return cls.get_config_value(param_name=param_name, default_value=default_value)

    @classmethod
    def get_config_value(cls, param_name=None, default_value=None):
        remote_config = get_remote_config()
        value = os.getenv(param_name, default_value)
        if remote_config and param_name in remote_config:
            value = remote_config.get(param_name)
        return value


class __RemoteConfigSingleton(object):
    def __init__(self):
        keyname = os.getenv('REMOTE_CONFIG_KEYNAME', None)
        region = os.getenv('AWS_REGION', None)

        # disable remote config by env var
        is_disabled = os.getenv('REMOTE_CONFIG_DISABLED', False)
        if is_disabled:
            self.remote_config = None
            return

        if not keyname:
            logging.warning('REMOTE_CONFIG_KEYNAME env var is not configured, using environ instead')
            self.remote_config = None
            return

        if not region:
            raise Exception('AWS_REGION env var is not configured')

        remote_config_text = self._get_secret(keyname, region=region)
        if remote_config_text:
            try:
                self.remote_config = json.loads(remote_config_text)
                logging.warning("Config was fetched from remote")
            except Exception as ex:
                logging.error(ex, exc_info=True)

    def _get_secret(self, secret_key, region):
        # Create a Secrets Manager client
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region)

        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_key)
        except ClientError as e:
            if e.response['Error']['Code'] == 'DecryptionFailureException':
                # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
                # Deal with the exception here, and/or rethrow at your discretion.
                raise e
            elif e.response['Error']['Code'] == 'InternalServiceErrorException':
                # An error occurred on the server side.
                # Deal with the exception here, and/or rethrow at your discretion.
                raise e
            elif e.response['Error']['Code'] == 'InvalidParameterException':
                # You provided an invalid value for a parameter.
                # Deal with the exception here, and/or rethrow at your discretion.
                raise e
            elif e.response['Error']['Code'] == 'InvalidRequestException':
                # You provided a parameter value that is not valid for the current state of the resource.
                # Deal with the exception here, and/or rethrow at your discretion.
                raise e
            elif e.response['Error']['Code'] == 'ResourceNotFoundException':
                # We can't find the resource that you asked for.
                # Deal with the exception here, and/or rethrow at your discretion.
                raise e
        else:
            # Decrypts secret using the associated KMS CMK.
            # Depending on whether the secret is a string or binary, one of these fields will be populated.
            if 'SecretString' in get_secret_value_response:
                secret = get_secret_value_response['SecretString']
            else:
                secret = base64.b64decode(get_secret_value_response['SecretBinary'])

            return secret


__redis = __RemoteConfigSingleton()


def get_remote_config():
    return __redis.remote_config
