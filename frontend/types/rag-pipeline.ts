/**
 * RAG Pipeline TypeScript Types
 *
 * The RAG pipeline is fully automated - all components are fixed to
 * best-in-class open-source models with no user-configurable fields.
 * This file contains supporting types for secrets, REST API config,
 * testing, and pipeline info display.
 */

// ============================================================================
// SECRET REFERENCE - Universal secret source configuration
// ============================================================================

export type SecretSource =
  | 'direct'           // Encrypted in DB
  | 'env'              // Environment variable
  | 'aws_secrets'      // AWS Secrets Manager
  | 'azure_keyvault'   // Azure Key Vault
  | 'gcp_secrets'      // Google Cloud Secret Manager
  | 'hashicorp_vault'  // HashiCorp Vault
  | 'platform_default'; // Platform-level setting

export interface AWSSecretsConfig {
  region: string;
  secret_name: string;
  secret_key?: string;
  auth_type: 'iam_role' | 'access_keys';
  access_key_id?: string;
  secret_access_key?: SecretReference;
}

export interface AzureKeyVaultConfig {
  vault_url: string;
  secret_name: string;
  auth_type: 'managed_identity' | 'service_principal';
  tenant_id?: string;
  client_id?: string;
  client_secret?: SecretReference;
}

export interface GCPSecretsConfig {
  project_id: string;
  secret_name: string;
  version: string;
  auth_type: 'default' | 'service_account';
  service_account_json?: string;
}

export interface HashiCorpVaultConfig {
  vault_url: string;
  path: string;
  key: string;
  mount_point: string;
  auth_method: 'token' | 'approle' | 'kubernetes' | 'aws' | 'ldap';
  token?: string;
  role_id?: string;
  secret_id?: SecretReference;
  kubernetes_role?: string;
}

export interface SecretReference {
  source: SecretSource;
  value?: string;
  env_var?: string;
  aws?: AWSSecretsConfig;
  azure?: AzureKeyVaultConfig;
  gcp?: GCPSecretsConfig;
  hashicorp?: HashiCorpVaultConfig;
  platform_key?: string;
}

// ============================================================================
// HEADER CONFIGURATION - For REST API calls
// ============================================================================

export interface HeaderConfig {
  key: string;
  value: string | SecretReference;
  is_secret: boolean;
}

// ============================================================================
// REST API CONFIGURATION - Universal for any API
// ============================================================================

export type ContentType =
  | 'application/json'
  | 'multipart/form-data'
  | 'application/x-www-form-urlencoded'
  | 'text/plain'
  | 'application/octet-stream';

export type InputFormat = 'base64' | 'binary' | 'url' | 'text';
export type ResponseType = 'json' | 'text' | 'binary';
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface RestApiConfig {
  name: string;
  enabled: boolean;
  endpoint_url: string;
  method: HttpMethod;
  headers: HeaderConfig[];
  content_type: ContentType;
  input_format: InputFormat;
  request_body_template?: string;
  response_type: ResponseType;
  output_extraction?: string;
  timeout_seconds: number;
  retry_count: number;
  max_file_size_mb: number;
}

// ============================================================================
// DOCUMENT PROCESSING CONFIGURATION
// ============================================================================

export interface DocumentProcessingConfig {
  describe_images: boolean;
  interpret_charts: boolean;
}

// ============================================================================
// PIPELINE INFO - Automated pipeline component descriptions
// ============================================================================

export interface PipelineInfo {
  chunking: string;
  contextual_enrichment: string;
  parent_child_retrieval: string;
  embedding: string;
  retrieval: string;
  reranker: string;
  vector_store: string;
  cache: string;
}

// ============================================================================
// API RESPONSE TYPES
// ============================================================================

export interface TestRestApiResponse {
  success: boolean;
  message: string;
  status_code?: number;
  output_preview?: string;
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
  details?: Record<string, unknown>;
}

export interface TestPipelineResult {
  content: string;
  score: number;
  element_type: string;
  page_number?: number;
  metadata: Record<string, unknown>;
}

export interface TestPipelineResponse {
  success: boolean;
  document_name?: string;
  query?: string;
  chunks_created?: number;
  results?: TestPipelineResult[];
  timings?: Record<string, number>;
  components?: Record<string, string>;
  error?: string;
}

// ============================================================================
// POWERED BY INFO - Fixed components
// ============================================================================

export interface PoweredByComponent {
  name: string;
  description: string;
  badge_color: string;
}

export const POWERED_BY: PoweredByComponent[] = [
  { name: 'Docling', description: 'Universal document parser', badge_color: 'blue' },
  { name: 'BGE-M3', description: 'Triple embeddings (1024d)', badge_color: 'purple' },
  { name: '3-Way Hybrid', description: 'Dense + Sparse + BM25', badge_color: 'emerald' },
  { name: 'BGE-reranker-v2-m3', description: 'Cross-encoder reranking', badge_color: 'orange' },
  { name: 'Qdrant', description: 'Named vectors', badge_color: 'cyan' },
  { name: 'Redis', description: 'Semantic cache', badge_color: 'red' },
];

// ============================================================================
// SECRET SOURCE LABELS - Display names for UI
// ============================================================================

export const SECRET_SOURCE_LABELS: Record<SecretSource, string> = {
  direct: 'Direct Input (Encrypted)',
  env: 'Environment Variable',
  aws_secrets: 'AWS Secrets Manager',
  azure_keyvault: 'Azure Key Vault',
  gcp_secrets: 'Google Cloud Secret Manager',
  hashicorp_vault: 'HashiCorp Vault',
  platform_default: 'Platform Default',
};
