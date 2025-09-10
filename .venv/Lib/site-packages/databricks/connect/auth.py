#
# DATABRICKS CONFIDENTIAL & PROPRIETARY
# __________________
#
# Copyright 2020-present Databricks, Inc.
# All Rights Reserved.
#
# NOTICE:  All information contained herein is, and remains the property of Databricks, Inc.
# and its suppliers, if any.  The intellectual and technical concepts contained herein are
# proprietary to Databricks, Inc. and its suppliers and may be covered by U.S. and foreign Patents,
# patents in process, and are protected by trade secret and/or copyright law. Dissemination, use,
# or reproduction of this information is strictly forbidden unless prior written permission is
# obtained from Databricks, Inc.
#
# If you view or obtain a copy of this information and believe Databricks, Inc. may not have
# intended it to be made available, please promptly report it to Databricks Legal Department
# @ legal@databricks.com.
#

from typing import Any, List, Optional, Tuple

import grpc
import urllib.parse

from databricks.sdk.core import Config
from pyspark.sql.connect.client import ChannelBuilder


MAX_MESSAGE_LENGTH = 128 * 1024 * 1024

GRPC_DEFAULT_OPTIONS = [
    ("grpc.max_send_message_length", MAX_MESSAGE_LENGTH),
    ("grpc.max_receive_message_length", MAX_MESSAGE_LENGTH),
]


class DatabricksChannelBuilder(ChannelBuilder):
    def __init__(
        self, config: Config,
        user_agent: str = "",
        channelOptions: Optional[List[Tuple[str, Any]]] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        self._config = config
        self.url = urllib.parse.urlparse(config.host)
        super()._extract_attributes()
        # We assume that cluster ID is validated by DatabricksSession
        self.params = {
            "x-databricks-cluster-id": self._config.cluster_id,
            ChannelBuilder.PARAM_USER_AGENT: user_agent,
        }

        if headers is not None:
            self.params.update(headers)

            # Transitional behavior, session_id overrides cluster_id
            if "x-databricks-session-id" in headers:
                del self.params['x-databricks-cluster-id']

        if channelOptions is None:
            self._channel_options = GRPC_DEFAULT_OPTIONS
        else:
            self._channel_options = GRPC_DEFAULT_OPTIONS + channelOptions

    def toChannel(self) -> grpc.Channel:
        """This method creates secure channel with :class:DatabricksAuthMetadataPlugin
        enabled, which handles refresh of HTTP headers for OAuth, like U2M flow and
        Service Principal flows."""
        from grpc import _plugin_wrapping  # pylint: disable=cyclic-import

        ssl_creds = grpc.ssl_channel_credentials()
        databricks_creds = _plugin_wrapping.metadata_plugin_call_credentials(
            UnifiedAuthMetadata(self._config), None
        )

        composite_creds = grpc.composite_channel_credentials(
            ssl_creds, databricks_creds
        )

        destination = f"{self._config.hostname}:443"
        return grpc.secure_channel(destination, composite_creds, self._channel_options)


class UnifiedAuthMetadata(grpc.AuthMetadataPlugin):
    def __init__(self, config: Config):
        self._config = config

    def __call__(
        self,
        context: grpc.AuthMetadataContext,
        callback: grpc.AuthMetadataPluginCallback,
    ) -> None:
        try:
            headers = self._config.authenticate()
            metadata = ()
            # these are HTTP headers returned by Databricks SDK
            for k, v in headers.items():
                # gRPC requires headers to be lower-cased
                metadata += ((k.lower(), v),)
            callback(metadata, None)
        except Exception as e:
            # We have to include the 'failed to connect to all addresses' string, because that
            # is the current way to propagate a terminal error when the client cannot connect
            # to any endpoint and thus cannot be retried.
            #
            # See pyspark.sql.connect.client.SparkConnectClient.retry_exception
            msg = f"failed to connect to all addresses using {self._config.auth_type} auth: {e}"

            # Add debug information from SDK Config to the end of the error message.
            msg = self._config.wrap_debug_info(msg)
            callback((), ValueError(msg))
