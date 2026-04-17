// --- TYPE DEFINITIONS BASED ON OPENAPI SCHEMA ---

/**
 * Represents a single package search result, matching the PyPI format.
 */
interface SearchResult {
  name: string;
  version: string;
  package_exists: boolean;
  readme_cached: boolean;   // <-- ADD THIS
  package_cached: boolean;  // <-- ADD THIS
  search_model?: string | null;
  readme_model?: string | null;
  package_model?: string | null;
  description?: string | null;
  summary?: string | null;
  author?: string | null;
  author_email?: string | null;
  maintainer?: string | null;
  maintainer_email?: string | null;
  home_page?: string | null;
  package_url?: string | null;
  release_url?: string | null;
  docs_url?: string | null;
  download_url?: string | null;
  bugtrack_url?: string | null;
  keywords?: string | null;
  license?: string | null;
  classifiers?: string[];
  platform?: string | null;
  requires_python?: string | null;
  project_urls?: { [key: string]: string };
}

interface SearchInfo {
  query: string;
  count: number;
  model_used?: string | null;
  models_tried?: string[];
  metadata_models_used?: string[];
}

/**
 * Represents the top-level response from the search API.
 */
interface SearchResponse {
  info: SearchInfo;
  results: SearchResult[];
}

/**
 * Represents the response from the /availability endpoint.
 */
interface AvailabilityResponse {
  name: string;
  readme_cached: boolean;
  package_cached: boolean;
  readme_model?: string | null;
  package_model?: string | null;
}

/**
 * Input metadata to draft a README.
 */
interface ReadmeRequest {
  name: string;
  summary?: string | null;
  description?: string | null;
  license?: string | null;
  homepage?: string | null;
  documentation_url?: string | null;
  python_requires?: string | null;
}

/**
 * Payload to generate a package.
 */
interface PackageGenerateRequest {
  readme_markdown: string;
  metadata: object;
}

