// --- TYPE DEFINITIONS BASED ON OPENAPI SCHEMA ---

/**
 * Represents a single package search result, matching the PyPI format.
 */
interface SearchResult {
  name: string;
  version: string;
  package_exists: boolean; // New field from the API
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

/**
 * Represents the top-level response from the search API.
 */
interface SearchResponse {
  info: {
    query: string;
    count: number;
  };
  results: SearchResult[];
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

