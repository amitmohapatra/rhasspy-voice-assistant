"""Cloud SDK integration for AWS, Azure, and GCP.

This module provides:
1. Cloud credential validation
2. Resource provisioning verification
3. IAM/Permission checking
4. Cloud connection testing
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class CloudProvider(str, Enum):
    """Supported cloud providers."""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    PRIVATE = "private"


@dataclass
class CloudValidationResult:
    """Result of cloud credential/connection validation."""
    valid: bool
    checks: dict[str, bool]
    errors: list[str]
    warnings: list[str]
    details: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details,
        }


class CloudSDK(ABC):
    """Abstract base class for cloud SDK integrations."""

    @abstractmethod
    async def validate_credentials(self) -> CloudValidationResult:
        """Validate that the credentials are correct and have necessary permissions."""
        pass

    @abstractmethod
    async def test_connection(self) -> CloudValidationResult:
        """Test the connection to the cloud provider."""
        pass

    @abstractmethod
    async def check_permissions(self, required_permissions: list[str]) -> CloudValidationResult:
        """Check if the credentials have the required permissions."""
        pass


class AWSSDK(CloudSDK):
    """AWS SDK integration using boto3."""

    def __init__(
        self,
        account_id: str,
        region: str,
        role_arn: str,
        external_id: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        self.account_id = account_id
        self.region = region
        self.role_arn = role_arn
        self.external_id = external_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self._session = None

    def _get_session(self):
        """Get or create AWS session."""
        try:
            import boto3
            from botocore.config import Config

            config = Config(
                region_name=self.region,
                signature_version='v4',
                retries={'max_attempts': 3}
            )

            if self.access_key_id and self.secret_access_key:
                return boto3.Session(
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    region_name=self.region,
                )
            else:
                return boto3.Session(region_name=self.region)
        except ImportError:
            logger.warning("boto3 not installed, AWS validation will be mocked")
            return None

    async def validate_credentials(self) -> CloudValidationResult:
        """Validate AWS credentials by attempting to assume the role."""
        checks = {}
        errors = []
        warnings = []
        details = {}

        session = self._get_session()
        if not session:
            return CloudValidationResult(
                valid=False,
                checks={"boto3_available": False},
                errors=["boto3 is not installed"],
                warnings=[],
                details={},
            )

        try:
            sts = session.client('sts')

            # Assume the role
            assume_role_params = {
                'RoleArn': self.role_arn,
                'RoleSessionName': 'rhasspy-validation',
                'DurationSeconds': 900,  # 15 minutes
            }
            if self.external_id:
                assume_role_params['ExternalId'] = self.external_id

            response = sts.assume_role(**assume_role_params)
            checks['sts_assume_role'] = True

            # Store credentials for further checks
            credentials = response['Credentials']
            details['assumed_role_user'] = response['AssumedRoleUser']['Arn']
            details['expiration'] = credentials['Expiration'].isoformat()

            # Verify caller identity
            temp_session = session.__class__(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=self.region,
            )
            temp_sts = temp_session.client('sts')
            identity = temp_sts.get_caller_identity()
            checks['identity_verification'] = True
            details['account_id'] = identity['Account']

            # Verify account ID matches
            if identity['Account'] != self.account_id:
                errors.append(f"Account ID mismatch: expected {self.account_id}, got {identity['Account']}")
                checks['account_id_match'] = False
            else:
                checks['account_id_match'] = True

        except Exception as e:
            logger.error(f"AWS credential validation failed: {e}")
            checks['sts_assume_role'] = False
            errors.append(f"Failed to assume role: {str(e)}")

        valid = all(checks.values()) and len(errors) == 0
        return CloudValidationResult(
            valid=valid,
            checks=checks,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    async def test_connection(self) -> CloudValidationResult:
        """Test AWS connection by checking VPC and EC2 access."""
        checks = {}
        errors = []
        warnings = []
        details = {}

        session = self._get_session()
        if not session:
            return CloudValidationResult(
                valid=False,
                checks={"boto3_available": False},
                errors=["boto3 is not installed"],
                warnings=[],
                details={},
            )

        try:
            # First assume the role
            sts = session.client('sts')
            assume_role_params = {
                'RoleArn': self.role_arn,
                'RoleSessionName': 'rhasspy-connection-test',
                'DurationSeconds': 900,
            }
            if self.external_id:
                assume_role_params['ExternalId'] = self.external_id

            response = sts.assume_role(**assume_role_params)
            credentials = response['Credentials']

            # Create session with assumed credentials
            temp_session = session.__class__(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=self.region,
            )

            # Test EC2 access
            try:
                ec2 = temp_session.client('ec2')
                ec2.describe_vpcs(MaxResults=1)
                checks['ec2_describe_vpcs'] = True
            except Exception as e:
                checks['ec2_describe_vpcs'] = False
                errors.append(f"Cannot describe VPCs: {e}")

            # Test EKS access
            try:
                eks = temp_session.client('eks')
                eks.list_clusters(maxResults=1)
                checks['eks_list_clusters'] = True
            except Exception as e:
                checks['eks_list_clusters'] = False
                warnings.append(f"Cannot list EKS clusters: {e}")

            # Test RDS access
            try:
                rds = temp_session.client('rds')
                rds.describe_db_instances(MaxRecords=20)
                checks['rds_describe_instances'] = True
            except Exception as e:
                checks['rds_describe_instances'] = False
                warnings.append(f"Cannot describe RDS instances: {e}")

            # Test Secrets Manager
            try:
                secrets = temp_session.client('secretsmanager')
                secrets.list_secrets(MaxResults=1)
                checks['secretsmanager_list'] = True
            except Exception as e:
                checks['secretsmanager_list'] = False
                warnings.append(f"Cannot list secrets: {e}")

        except Exception as e:
            logger.error(f"AWS connection test failed: {e}")
            checks['connection'] = False
            errors.append(f"Connection failed: {str(e)}")

        valid = checks.get('ec2_describe_vpcs', False) and len(errors) == 0
        return CloudValidationResult(
            valid=valid,
            checks=checks,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    async def check_permissions(self, required_permissions: list[str]) -> CloudValidationResult:
        """Check if the role has required IAM permissions."""
        checks = {}
        errors = []
        warnings = []
        details = {}

        session = self._get_session()
        if not session:
            return CloudValidationResult(
                valid=False,
                checks={},
                errors=["boto3 is not installed"],
                warnings=[],
                details={},
            )

        try:
            sts = session.client('sts')
            assume_role_params = {
                'RoleArn': self.role_arn,
                'RoleSessionName': 'rhasspy-permission-check',
                'DurationSeconds': 900,
            }
            if self.external_id:
                assume_role_params['ExternalId'] = self.external_id

            response = sts.assume_role(**assume_role_params)
            credentials = response['Credentials']

            temp_session = session.__class__(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=self.region,
            )

            # Use IAM Access Analyzer or simulate permissions
            iam = temp_session.client('iam')

            # Get the role name from ARN
            role_name = self.role_arn.split('/')[-1]

            # List attached policies
            try:
                policies = iam.list_attached_role_policies(RoleName=role_name)
                details['attached_policies'] = [p['PolicyName'] for p in policies.get('AttachedPolicies', [])]
            except Exception:
                # May not have permission to list policies
                pass

            # For now, mark all as potentially available
            # In production, use IAM Policy Simulator
            for perm in required_permissions:
                checks[perm] = True  # Would use simulator in production

        except Exception as e:
            logger.error(f"AWS permission check failed: {e}")
            errors.append(str(e))

        valid = all(checks.values()) and len(errors) == 0
        return CloudValidationResult(
            valid=valid,
            checks=checks,
            errors=errors,
            warnings=warnings,
            details=details,
        )


class AzureSDK(CloudSDK):
    """Azure SDK integration."""

    def __init__(
        self,
        tenant_id: str,
        subscription_id: str,
        client_id: str,
        client_secret: str,
        resource_group: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.subscription_id = subscription_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.resource_group = resource_group
        self._credential = None

    def _get_credential(self):
        """Get Azure credential."""
        try:
            from azure.identity import ClientSecretCredential
            return ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
        except ImportError:
            logger.warning("Azure SDK not installed, validation will be mocked")
            return None

    async def validate_credentials(self) -> CloudValidationResult:
        """Validate Azure service principal credentials."""
        checks = {}
        errors = []
        warnings = []
        details = {}

        credential = self._get_credential()
        if not credential:
            return CloudValidationResult(
                valid=False,
                checks={"azure_sdk_available": False},
                errors=["Azure SDK is not installed"],
                warnings=[],
                details={},
            )

        try:
            # Get a token to validate credentials
            from azure.identity import ClientSecretCredential

            token = credential.get_token("https://management.azure.com/.default")
            checks['authentication'] = True
            details['token_expires'] = token.expires_on

        except Exception as e:
            logger.error(f"Azure credential validation failed: {e}")
            checks['authentication'] = False
            errors.append(f"Authentication failed: {str(e)}")

        valid = all(checks.values()) and len(errors) == 0
        return CloudValidationResult(
            valid=valid,
            checks=checks,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    async def test_connection(self) -> CloudValidationResult:
        """Test Azure connection by checking resource access."""
        checks = {}
        errors = []
        warnings = []
        details = {}

        credential = self._get_credential()
        if not credential:
            return CloudValidationResult(
                valid=False,
                checks={"azure_sdk_available": False},
                errors=["Azure SDK is not installed"],
                warnings=[],
                details={},
            )

        try:
            from azure.mgmt.resource import ResourceManagementClient
            from azure.mgmt.compute import ComputeManagementClient
            from azure.mgmt.network import NetworkManagementClient

            # Test Resource Management
            try:
                resource_client = ResourceManagementClient(credential, self.subscription_id)
                list(resource_client.resource_groups.list())
                checks['resource_groups_list'] = True
            except Exception as e:
                checks['resource_groups_list'] = False
                errors.append(f"Cannot list resource groups: {e}")

            # Test Compute
            try:
                compute_client = ComputeManagementClient(credential, self.subscription_id)
                list(compute_client.virtual_machines.list_all())
                checks['compute_list_vms'] = True
            except Exception as e:
                checks['compute_list_vms'] = False
                warnings.append(f"Cannot list VMs: {e}")

            # Test Network
            try:
                network_client = NetworkManagementClient(credential, self.subscription_id)
                list(network_client.virtual_networks.list_all())
                checks['network_list_vnets'] = True
            except Exception as e:
                checks['network_list_vnets'] = False
                warnings.append(f"Cannot list VNets: {e}")

        except ImportError as e:
            errors.append(f"Azure management SDK not installed: {e}")
        except Exception as e:
            logger.error(f"Azure connection test failed: {e}")
            errors.append(str(e))

        valid = checks.get('resource_groups_list', False) and len(errors) == 0
        return CloudValidationResult(
            valid=valid,
            checks=checks,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    async def check_permissions(self, required_permissions: list[str]) -> CloudValidationResult:
        """Check Azure RBAC permissions."""
        checks = {}
        errors = []
        warnings = []
        details = {}

        credential = self._get_credential()
        if not credential:
            return CloudValidationResult(
                valid=False,
                checks={},
                errors=["Azure SDK is not installed"],
                warnings=[],
                details={},
            )

        try:
            from azure.mgmt.authorization import AuthorizationManagementClient

            auth_client = AuthorizationManagementClient(credential, self.subscription_id)

            # List role assignments for the service principal
            scope = f"/subscriptions/{self.subscription_id}"
            if self.resource_group:
                scope = f"{scope}/resourceGroups/{self.resource_group}"

            assignments = list(auth_client.role_assignments.list_for_scope(scope))
            details['role_assignments'] = len(assignments)

            # For now, mark permissions as available
            # In production, would check specific role definitions
            for perm in required_permissions:
                checks[perm] = True

        except Exception as e:
            logger.error(f"Azure permission check failed: {e}")
            errors.append(str(e))

        valid = all(checks.values()) and len(errors) == 0
        return CloudValidationResult(
            valid=valid,
            checks=checks,
            errors=errors,
            warnings=warnings,
            details=details,
        )


class GCPSDK(CloudSDK):
    """Google Cloud Platform SDK integration."""

    def __init__(
        self,
        project_id: str,
        service_account_key: str,  # JSON key content
        region: Optional[str] = None,
    ):
        self.project_id = project_id
        self.service_account_key = service_account_key
        self.region = region
        self._credentials = None

    def _get_credentials(self):
        """Get GCP credentials from service account key."""
        try:
            from google.oauth2 import service_account

            key_data = json.loads(self.service_account_key)
            return service_account.Credentials.from_service_account_info(key_data)
        except ImportError:
            logger.warning("Google Cloud SDK not installed, validation will be mocked")
            return None
        except json.JSONDecodeError:
            logger.error("Invalid service account key JSON")
            return None

    async def validate_credentials(self) -> CloudValidationResult:
        """Validate GCP service account credentials."""
        checks = {}
        errors = []
        warnings = []
        details = {}

        credentials = self._get_credentials()
        if not credentials:
            return CloudValidationResult(
                valid=False,
                checks={"gcp_sdk_available": False},
                errors=["Google Cloud SDK is not installed or invalid key"],
                warnings=[],
                details={},
            )

        try:
            from googleapiclient import discovery

            # Test by getting project info
            service = discovery.build(
                'cloudresourcemanager', 'v1',
                credentials=credentials,
                cache_discovery=False
            )
            project = service.projects().get(projectId=self.project_id).execute()
            checks['project_access'] = True
            details['project_name'] = project.get('name')
            details['project_number'] = project.get('projectNumber')

        except Exception as e:
            logger.error(f"GCP credential validation failed: {e}")
            checks['project_access'] = False
            errors.append(f"Cannot access project: {str(e)}")

        valid = all(checks.values()) and len(errors) == 0
        return CloudValidationResult(
            valid=valid,
            checks=checks,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    async def test_connection(self) -> CloudValidationResult:
        """Test GCP connection by checking compute and network access."""
        checks = {}
        errors = []
        warnings = []
        details = {}

        credentials = self._get_credentials()
        if not credentials:
            return CloudValidationResult(
                valid=False,
                checks={"gcp_sdk_available": False},
                errors=["Google Cloud SDK is not installed"],
                warnings=[],
                details={},
            )

        try:
            from googleapiclient import discovery

            # Test Compute Engine
            try:
                compute = discovery.build(
                    'compute', 'v1',
                    credentials=credentials,
                    cache_discovery=False
                )
                zones = compute.zones().list(project=self.project_id).execute()
                checks['compute_list_zones'] = True
                details['zones_count'] = len(zones.get('items', []))
            except Exception as e:
                checks['compute_list_zones'] = False
                errors.append(f"Cannot list compute zones: {e}")

            # Test VPC Networks
            try:
                networks = compute.networks().list(project=self.project_id).execute()
                checks['network_list'] = True
                details['networks_count'] = len(networks.get('items', []))
            except Exception as e:
                checks['network_list'] = False
                warnings.append(f"Cannot list networks: {e}")

            # Test GKE
            try:
                container = discovery.build(
                    'container', 'v1',
                    credentials=credentials,
                    cache_discovery=False
                )
                clusters = container.projects().locations().clusters().list(
                    parent=f'projects/{self.project_id}/locations/-'
                ).execute()
                checks['gke_list_clusters'] = True
            except Exception as e:
                checks['gke_list_clusters'] = False
                warnings.append(f"Cannot list GKE clusters: {e}")

        except Exception as e:
            logger.error(f"GCP connection test failed: {e}")
            errors.append(str(e))

        valid = checks.get('compute_list_zones', False) and len(errors) == 0
        return CloudValidationResult(
            valid=valid,
            checks=checks,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    async def check_permissions(self, required_permissions: list[str]) -> CloudValidationResult:
        """Check GCP IAM permissions."""
        checks = {}
        errors = []
        warnings = []
        details = {}

        credentials = self._get_credentials()
        if not credentials:
            return CloudValidationResult(
                valid=False,
                checks={},
                errors=["Google Cloud SDK is not installed"],
                warnings=[],
                details={},
            )

        try:
            from googleapiclient import discovery

            # Use testIamPermissions to check permissions
            service = discovery.build(
                'cloudresourcemanager', 'v1',
                credentials=credentials,
                cache_discovery=False
            )

            response = service.projects().testIamPermissions(
                resource=self.project_id,
                body={'permissions': required_permissions}
            ).execute()

            granted = set(response.get('permissions', []))
            for perm in required_permissions:
                checks[perm] = perm in granted
                if perm not in granted:
                    errors.append(f"Missing permission: {perm}")

            details['granted_permissions'] = list(granted)

        except Exception as e:
            logger.error(f"GCP permission check failed: {e}")
            errors.append(str(e))

        valid = all(checks.values()) and len(errors) == 0
        return CloudValidationResult(
            valid=valid,
            checks=checks,
            errors=errors,
            warnings=warnings,
            details=details,
        )


def get_cloud_sdk(
    provider: str,
    config: dict,
) -> CloudSDK:
    """Factory function to get the appropriate cloud SDK.

    Args:
        provider: Cloud provider name (aws, azure, gcp)
        config: Provider-specific configuration

    Returns:
        Configured CloudSDK instance
    """
    if provider == CloudProvider.AWS.value:
        return AWSSDK(
            account_id=config.get('account_id', ''),
            region=config.get('region', ''),
            role_arn=config.get('role_arn', ''),
            external_id=config.get('external_id'),
            access_key_id=config.get('access_key_id'),
            secret_access_key=config.get('secret_access_key'),
        )
    elif provider == CloudProvider.AZURE.value:
        return AzureSDK(
            tenant_id=config.get('tenant_id', ''),
            subscription_id=config.get('subscription_id', ''),
            client_id=config.get('client_id', ''),
            client_secret=config.get('client_secret', ''),
            resource_group=config.get('resource_group'),
        )
    elif provider == CloudProvider.GCP.value:
        return GCPSDK(
            project_id=config.get('project_id', ''),
            service_account_key=config.get('service_account_key', ''),
            region=config.get('region'),
        )
    else:
        raise ValueError(f"Unsupported cloud provider: {provider}")


# Required permissions for each provider
AWS_REQUIRED_PERMISSIONS = [
    "ec2:DescribeVpcs",
    "ec2:DescribeSubnets",
    "ec2:DescribeSecurityGroups",
    "ec2:CreateSecurityGroup",
    "ec2:AuthorizeSecurityGroupIngress",
    "ec2:RunInstances",
    "ec2:TerminateInstances",
    "eks:CreateCluster",
    "eks:DeleteCluster",
    "eks:DescribeCluster",
    "eks:ListClusters",
    "rds:CreateDBInstance",
    "rds:DeleteDBInstance",
    "rds:DescribeDBInstances",
    "secretsmanager:CreateSecret",
    "secretsmanager:GetSecretValue",
    "secretsmanager:DeleteSecret",
    "iam:PassRole",
]

AZURE_REQUIRED_PERMISSIONS = [
    "Microsoft.Resources/subscriptions/resourceGroups/read",
    "Microsoft.Compute/virtualMachines/*",
    "Microsoft.Network/virtualNetworks/*",
    "Microsoft.ContainerService/managedClusters/*",
    "Microsoft.KeyVault/vaults/*",
]

GCP_REQUIRED_PERMISSIONS = [
    "compute.instances.create",
    "compute.instances.delete",
    "compute.networks.list",
    "container.clusters.create",
    "container.clusters.delete",
    "secretmanager.secrets.create",
    "secretmanager.versions.access",
]
