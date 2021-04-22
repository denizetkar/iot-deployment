import argparse
import random

# Import the needed management objects from the libraries. The azure.common library
# is installed automatically with the other libraries.
from azure.identity import AzureCliCredential

from services import cosmosdb, iot_devices, iot_hub, resource_group

# Constants we need in multiple places: the resource group name and the region
# in which we provision resources. You can change these values however you want.
DEFAULT_RESOURCE_GROUP_NAME = "IoT-project"
DEFAULT_IOT_HUB_NAME = f"iot-hub-materialfluss{random.randint(1,100000):05}"
DEFAULT_COSMOSDB_NAME = f"cosmosdb-materialfluss{random.randint(1,100000):05}"
DEFAULT_LOCATION = "North Europe"


def main(args: argparse.Namespace):
    # Acquire a credential object using CLI-based authentication.
    credential = AzureCliCredential()

    # Step 1: Provision the resource group.
    resource_group.provision(
        credential, args.azure_subscription_id, args.resource_group_name, args.location
    )

    # Step 2: Provision the IotHub.
    iot_hub.provision(
        credential,
        args.azure_subscription_id,
        args.resource_group_name,
        args.iot_hub_name,
        args.location,
    )

    # Step 3: Onboard & provision default IoT devices.
    iot_devices.provision(
        credential,
        args.azure_subscription_id,
        args.resource_group_name,
        args.iot_hub_name,
        args.device_ids_file_path,
    )

    # Step 4: Provision the CosmosDB and initialize it.
    cosmosdb.Provisioner(
        credential,
        args.azure_subscription_id,
        args.resource_group_name,
        args.cosmosdb_name,
        args.location,
    ).provision()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "azure_subscription_id", type=str, help="Azure subscription ID."
    )
    parser.add_argument(
        "--resource-group-name",
        type=str,
        default=DEFAULT_RESOURCE_GROUP_NAME,
        help="Resource group name for the deployment.",
    )
    parser.add_argument(
        "--iot-hub-name",
        type=str,
        default=DEFAULT_IOT_HUB_NAME,
        help="IotHub name for deployment.",
    )
    parser.add_argument(
        "--device-ids-file-path",
        type=str,
        default="",
        help="Path of the text file containing 1 "
        "device id per line to be registered in IotHub.",
    )
    parser.add_argument(
        "--cosmosdb-name",
        type=str,
        default=DEFAULT_COSMOSDB_NAME,
        help="CosmosDB name for the deployment.",
    )
    parser.add_argument(
        "--location",
        type=str,
        default=DEFAULT_LOCATION,
        help="Location of the Azure datacenter to deploy.",
    )
    main(parser.parse_args())
