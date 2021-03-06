import logging

from azure.identity import AzureCliCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import ResourceGroup

RESOURCE_MGMT_API_VER = "2021-04-01"


def provision(
    credential: AzureCliCredential,
    azure_subscription_id: str,
    resource_group_name: str,
    location: str,
    logger: logging.Logger,
):
    resource_client = ResourceManagementClient(credential, azure_subscription_id, api_version=RESOURCE_MGMT_API_VER)
    if not resource_client.resource_groups.check_existence(resource_group_name):
        # https://docs.microsoft.com/en-us/python/api/azure-mgmt-resource/azure.mgmt.resource.resources.v2021_04_01.operations.resourcegroupsoperations?view=azure-python#create-or-update-resource-group-name--parameters----kwargs-
        rg_result = resource_client.resource_groups.create_or_update(resource_group_name, ResourceGroup(location=location))
        logger.info(f"Provisioned resource group '{rg_result.name}'")
    else:
        logger.info(f"Resource group '{resource_group_name}' is already provisioned")
