import logging
import sys
from typing import Any, Dict, Optional, Tuple

from azure.cosmos import CosmosClient, DatabaseProxy
from azure.cosmos.exceptions import CosmosResourceExistsError
from azure.identity import AzureCliCredential
from azure.mgmt.cosmosdb import CosmosDBManagementClient
from azure.mgmt.cosmosdb.models import BackupPolicy, ConsistencyPolicy, DatabaseAccountCreateUpdateParameters, Location

COSMOSDB_DB_NAME = "iot"
MSG_CONTAINER_PART_KEY = "/deviceId"
# Make sure the vendor names are known to `IoTHub_EventHub` Azure function.
VENDOR_NAMES: Tuple[str, ...] = ("vemcon", "mts_smart", "exelonix", "test_vendor")
LATEST_MSG_CONTAINER_TEMPLATE = "_latest_{}"
LEASES_CONTAINER_TEMPLATE = "_leases_{}"
LATEST_MSG_CONTAINER_PART_KEY = "/id"
MSG_CONTAINER_DEFAULT_TTL = 15768000  # in seconds (6 months)


class Provisioner:
    def __init__(
        self,
        credential: AzureCliCredential,
        azure_subscription_id: str,
        resource_group_name: str,
        cosmosdb_name: str,
        location: str,
        logger: logging.Logger,
    ):
        self._credential = credential
        self._azure_subscription_id = azure_subscription_id
        self._resource_group_name = resource_group_name
        self._cosmosdb_name = cosmosdb_name
        self._location = location
        self._logger = logger

        self._cosmosdb_client = CosmosDBManagementClient(self._credential, self._azure_subscription_id)

    def provision(self):
        if self._cosmosdb_name not in {
            desc_list_res.name
            for desc_list_res in self._cosmosdb_client.database_accounts.list_by_resource_group(self._resource_group_name)
        }:
            if self._cosmosdb_client.database_accounts.check_name_exists(self._cosmosdb_name):
                self._logger.error(f"Cosmos DB name '{self._cosmosdb_name}' is not available")
                sys.exit(1)
            upd_params = DatabaseAccountCreateUpdateParameters(
                locations=[Location(location_name=self._location, failover_priority=0)],
                location=self._location,
                kind="GlobalDocumentDB",
                consistency_policy=ConsistencyPolicy(default_consistency_level="Session"),
                is_virtual_network_filter_enabled=False,
                enable_automatic_failover=True,
                enable_multiple_write_locations=False,
                disable_key_based_metadata_write_access=False,
                default_identity="FirstPartyIdentity",
                public_network_access="Enabled",
                enable_free_tier=True,
                enable_analytical_storage=False,
                backup_policy=BackupPolicy(type="Periodic"),
                network_acl_bypass="None",
                network_acl_bypass_resource_ids=[],
            )
            poller = self._cosmosdb_client.database_accounts.begin_create_or_update(
                self._resource_group_name, self._cosmosdb_name, upd_params
            )
            cosmosdb_res = poller.result()
            self._logger.info(f"Provisioned Cosmos DB '{cosmosdb_res.name}'")
        else:
            self._logger.info(f"Cosmos DB '{self._cosmosdb_name}' is already provisioned")

        # Initialize the Cosmos DB with a database named "iot" and
        # 2 collections named "messages" and "latest_messages"
        self._initialize_db()

    def _initialize_db(self):
        keys = self._cosmosdb_client.database_accounts.list_keys(self._resource_group_name, self._cosmosdb_name)
        acc_res = self._cosmosdb_client.database_accounts.get(self._resource_group_name, self._cosmosdb_name)
        cosmos_client = CosmosClient(acc_res.document_endpoint, keys.secondary_master_key)
        try:
            cosmos_client.create_database(COSMOSDB_DB_NAME, populate_query_metrics=True, offer_throughput=400)
            self._logger.info(f"'{COSMOSDB_DB_NAME}' database is created in Cosmos DB")
        except CosmosResourceExistsError:
            self._logger.info(f"Cosmos DB already has '{COSMOSDB_DB_NAME}' database")

        db_proxy = cosmos_client.get_database_client(COSMOSDB_DB_NAME)
        for vendor_name in VENDOR_NAMES:
            self._create_vendor_containers(db_proxy, vendor_name)

    def _create_vendor_containers(self, db_proxy: DatabaseProxy, vendor_name: str):
        # https://docs.microsoft.com/en-us/rest/api/cosmos-db-resource-provider/2021-03-15/sqlresources/createupdatesqlcontainer#sqlcontainerresource
        self._create_container(
            db_proxy,
            vendor_name,
            {"paths": [MSG_CONTAINER_PART_KEY]},
            {"automatic": True},
            MSG_CONTAINER_DEFAULT_TTL,
            True,
        )
        self._create_container(
            db_proxy,
            LATEST_MSG_CONTAINER_TEMPLATE.format(vendor_name),
            {"paths": [LATEST_MSG_CONTAINER_PART_KEY]},
            {"automatic": True},
            None,
            True,
            {"paths": [LATEST_MSG_CONTAINER_PART_KEY]},
        )

    def _create_container(
        self,
        db_proxy: DatabaseProxy,
        id: str,
        partition_key: str,
        indexing_policy: Dict[str, Any],
        default_ttl: Optional[int] = None,
        populate_query_metrics: bool = True,
        unique_key_policy: Dict[str, Any] = None,
    ):
        # https://docs.microsoft.com/en-us/rest/api/cosmos-db-resource-provider/2021-03-15/sqlresources/createupdatesqlcontainer#sqlcontainerresource
        try:
            db_proxy.create_container(
                id=id,
                partition_key=partition_key,
                indexing_policy=indexing_policy,
                default_ttl=default_ttl,
                populate_query_metrics=populate_query_metrics,
                unique_key_policy=unique_key_policy,
            )
            self._logger.info("Collection '{}' is created in '{}' database".format(id, db_proxy.id))
        except CosmosResourceExistsError:
            self._logger.info("Collection '{}' already exists in '{}' database".format(id, db_proxy.id))
