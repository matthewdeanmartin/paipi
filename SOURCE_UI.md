## Tree for paipi-app
```
├── README.md
└── src/
    ├── app/
    │   ├── app.config.ts
    │   ├── app.css
    │   ├── app.html
    │   ├── app.ts
    │   ├── models.ts
    │   ├── package_page.html
    │   └── package_page.ts
    ├── index.html
    ├── main.ts
    └── styles.css
```

## File: README.md
```markdown
# PAIPI Angular UI

This is the official web frontend for **PAIPI**, the AI-Powered PyPI Search engine. Built with Angular and styled with Tailwind CSS, this single-page application provides a clean and responsive interface to interact with the `paipi` backend, allowing you to search for Python packages, generate detailed README files, and download scaffolded package structures.

## Features

- **AI-Powered Search**: Leverage the knowledge of a Large Language Model to find Python packages based on natural language queries.
- **Package Validation**: Search results are color-coded to indicate whether a package name actually exists on the official PyPI repository.
- **Detailed Package View**: Click on any search result to see a clean, detailed view with metadata, project links, and keywords.
- **On-Demand README Generation**: With a single click, ask the AI to generate a comprehensive `README.md` file based on the package's metadata.
- **Package Scaffolding**: Download a functional, pre-structured `.zip` file for any generated package, complete with a `pyproject.toml` and the generated README.

## Prerequisites

Before you begin, ensure you have the following installed:

1. **Node.js**: A recent LTS version is recommended.
2. **Angular CLI**: Install it globally if you haven't already: `npm install -g @angular/cli`.
3. **Running PAIPI Backend**: This is a frontend application and **requires the Python backend to be running**. By default, it expects the backend to be available at `http://127.0.0.1:8080`.

## Getting Started

Follow these steps to get the application running on your local machine.

1. **Clone the repository:**

   ```bash
   git clone git@github.com:matthewdeanmartin/paipi.git
   cd paipi-app
   ```

2. **Install dependencies:**

   ```bash
   npm install
   ```

3. **Run the application:**

   ```bash
   ng serve
   ```

   Navigate to `http://localhost:4200/` in your browser. The application will automatically reload if you change any of the source files.

## How to Use the Application

1. **Search for Packages**: Use the main search bar to enter a query, like `http clients for python` or `terminal text editors`.
2. **View Results**: The application will display a list of packages found by the AI.
  - Package names in \<span style="color: \#60A5FA;"\>**blue**\</span\> exist on PyPI.
  - Package names in \<span style="color: \#F87171;"\>**red**\</span\> are AI-generated suggestions that do not exist on PyPI.
3. **See Details**: Click on any package to navigate to the detail view. Here you'll find the summary, description, author, license, and relevant links.
4. **Generate a README**: In the detail view, click the **"Generate README.md"** button. The application will send the package metadata to the backend, which uses the AI to generate and return a complete markdown file.
5. **Download the Package**: Once the README has been generated, a **"Download Package"** button will appear. Clicking this will generate and download a `.zip` archive containing a basic Python package structure (`pyproject.toml`, `__init__.py`, etc.) and the newly created README.

## How to Contribute

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

1. **Fork the Project**
2. **Create your Feature Branch**
   ```bash
   git checkout -b feature/AmazingFeature
   ```
3. **Commit your Changes**
   ```bash
   git commit -m 'Add some AmazingFeature'
   ```
4. **Push to the Branch**
   ```bash
   git push origin feature/AmazingFeature
   ```
5. **Open a Pull Request**

Please try to follow the existing code style and Angular best practices.

## License

Distributed under the MIT License. See `LICENSE` file for more information.
```
## File: src\index.html
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>PaipiApp</title>
  <base href="/">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/x-icon" href="favicon.ico">
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body>
  <app-root></app-root>
</body>
</html>
```
## File: src\main.ts
```typescript
import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { App } from './app/app';

bootstrapApplication(App, appConfig)
  .catch((err) => console.error(err));
```
## File: src\styles.css
```css
/* You can add global styles to this file, and also import other style files */
@tailwind base;
@tailwind components;
@tailwind utilities;
```
## File: src\app\app.config.ts
```typescript
import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    
  ]
};
```
## File: src\app\app.html
```html
<!-- Main Application Container -->
<div class="bg-gray-900 text-gray-200 min-h-screen font-sans antialiased">
  <main class="container mx-auto p-4 sm:p-6 lg:p-8">

    <!-- Header Section -->
    <header class="text-center mb-8">
      <div class="flex items-center justify-center gap-3 mb-2">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 256 256"
             class="text-yellow-400">
          <path fill="currentColor"
                d="M139.23 219.88a12.12 12.12 0 0 1-13-5.22l-37-64.14a12 12 0 0 1 10.4-18.4l64.09 37a12 12 0 0 1-5.21 23l-3.21.54l-11.89-20.6l10.4-6a12 12 0 0 1 15.21-1.22a12.06 12.06 0 0 1 4 14.61l-24.46 42.37a12 12 0 0 1-5.13 7.06Zm-16.11-99.76l-37-64.14a12 12 0 0 1 10.4-18.4l64.09 37a12 12 0 0 1-5.21 23l-3.21.54l-11.89-20.6l10.4-6a12 12 0 1 1 10.4 20.8l-37 21.36a12 12 0 0 1-15-2.56Z M232 128a104 104 0 1 1-104-104a104.11 104.11 0 0 1 104 104Zm-16 0a88 88 0 1 0-88 88a88.1 88.1 0 0 0 88-88Z"/>
        </svg>
        <h1
          class="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-yellow-300 to-blue-400">
          PAIPI
        </h1>
      </div>
      <p class="text-md text-gray-400">AI-Powered PyPI Search</p>
    </header>

    <!-- VIEW CONTAINER -->
    <div class="max-w-4xl mx-auto">
      @if (selectedPackage()) {
        <!-- DETAIL VIEW -->
        <app-package-detail
          [package]="selectedPackage()!"
          (close)="handleCloseDetailView()"
          (readmeGenerated)="handleReadmeGenerated($event)"
        />
      } @else {
        <!-- SEARCH VIEW -->
        <form (submit)="onSearch($event)" class="w-full mb-10">
          <div class="relative">
            <input [(ngModel)]="query" name="search-query" type="search"
                   class="w-full pl-12 pr-4 py-3 bg-gray-800 border-2 border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                   placeholder="e.g., terminal text editors, http clients...">
            <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                   class="text-gray-500">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
            </div>
          </div>
        </form>

        @if (isLoading()) {
          <div class="flex flex-col items-center justify-center text-gray-500 mt-12">
            <svg class="animate-spin h-8 w-8 text-blue-400 mb-3" xmlns="http://www.w3.org/2000/svg" fill="none"
                 viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p>Searching for '{{ lastQuery() }}'...</p></div>
        }
        @if (error()) {
          <div class="bg-red-900/50 border border-red-700 text-red-300 px-4 py-3 rounded-lg text-center mt-12"
               role="alert"><strong class="font-bold">An error occurred:</strong><span
            class="block sm:inline ml-2">{{ error() }}</span></div>
        }
        @if (!isLoading() && !error() && searchPerformed()) {
          @if (searchResults().length > 0) {
            <div class="flex flex-col gap-4">
              <p class="text-gray-400 mb-2">Showing {{ searchResults().length }} results for "{{ lastQuery() }}"</p>
              @for (pkg of searchResults(); track pkg.name) {
                <div (click)="handleSelectPackage(pkg)"
                     class="bg-gray-800 border border-gray-700 rounded-lg p-5 transition-all hover:border-blue-500 hover:shadow-lg cursor-pointer">
                  <div class="flex flex-col sm:flex-row justify-between items-baseline gap-2">
                        <span class="text-xl font-bold" [class.text-red-500]="!pkg.package_exists"
                              [class.text-blue-400]="pkg.package_exists">
                          {{ pkg.name }}
                        </span>
                    <span
                      class="text-xs font-mono bg-gray-700 text-yellow-300 px-2 py-1 rounded-md">{{ pkg.version }}</span>
                  </div>
                  <p class="mt-2 text-gray-300">{{ pkg.summary }}</p>
                </div>
              }
            </div>
          } @else {
            <!-- No Results State -->
            <div class="text-center text-gray-500 mt-12">
              <p class="text-xl mb-2">No results found for "{{ lastQuery() }}".</p>
              <p>Please try a different search query.</p>
            </div>
          }
        } @else if (!isLoading() && !searchPerformed()) {
          <!-- Initial Welcome State -->
          <div class="text-center text-gray-500 mt-12">
            <p>Search for Python packages using AI's knowledge.</p>
          </div>
        }
      }
    </div>
  </main>
</div>
```
## File: src\app\app.ts
```typescript
import {ChangeDetectionStrategy, Component, signal, inject, effect} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {HttpClient, HttpClientModule, HttpErrorResponse} from '@angular/common/http';
import {firstValueFrom} from 'rxjs';
import {PackageDetailComponent} from './package_page';



// --- MAIN APP COMPONENT ---

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [FormsModule, HttpClientModule, PackageDetailComponent], // Use string literal for forward reference
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
})
export class App {
  // --- INJECTIONS & API CONFIG ---
  private http = inject(HttpClient);
  private readonly apiUrl = 'http://127.0.0.1:8080';

  // --- STATE MANAGEMENT WITH SIGNALS ---
  query = signal<string>('');
  lastQuery = signal<string>('');
  searchResults = signal<SearchResult[]>([]);
  isLoading = signal<boolean>(false);
  error = signal<string | null>(null);
  searchPerformed = signal<boolean>(false);
  selectedPackage = signal<SearchResult | null>(null);

  // --- NEW: Powerful Debugging with effect() ---
  // This will run whenever the signals it reads inside have changed.
  constructor() {
    effect(() => {
      const pkg = this.selectedPackage();
      if (pkg) {
        console.log(`%c[EFFECT] selectedPackage changed to: ${pkg.name} (readme_cached: ${pkg.readme_cached})`, 'color: #7DF9FF');
      } else {
        console.log(`%c[EFFECT] selectedPackage changed to: null`, 'color: #7DF9FF');
      }
    });
  }

  // --- MODIFIED: The corrected handler ---
  handleReadmeGenerated(packageName: string): void {
    console.log(`[App] Received readmeGenerated event for '${packageName}'.`);

    // 1. Update the main search results array
    this.searchResults.update(currentResults =>
      currentResults.map(pkg =>
        pkg.name === packageName ? { ...pkg, readme_cached: true } : pkg
      )
    );

    // 2. IMPORTANT: Also update the currently selected package signal
    // This ensures the state is consistent everywhere, immediately.
    const currentSelected = this.selectedPackage();
    if (currentSelected && currentSelected.name === packageName) {
      console.log(`[App] Updating selectedPackage signal for '${packageName}' to set readme_cached = true.`);
      this.selectedPackage.set({ ...currentSelected, readme_cached: true });
    }
  }

  // --- (No other changes needed in this file) ---

  /**
   * Handles the search form submission.
   * @param event The form submission event.
   */
  async onSearch(event: Event): Promise<void> {
    event.preventDefault();
    const currentQuery = this.query().trim();
    // if (!currentQuery) {
    //   return;
    // }

    // Set loading state
    this.isLoading.set(true);
    this.searchPerformed.set(true);
    this.lastQuery.set(currentQuery);
    this.error.set(null);
    this.searchResults.set([]);
    this.selectedPackage.set(null); // Reset detail view on new search

    try {
      // Fetch results from the mock API
      // const response = await this.mockApiSearch(currentQuery);
      const response = await this.apiSearch(currentQuery)
      this.searchResults.set(response.results);
    } catch (e: any) {
      console.error('API Error:', e);
      let message = 'Failed to fetch results from the server.';
      if (e instanceof HttpErrorResponse) {
        message = `Error ${e.status}: ${e.statusText}`;
      } else if (e.message) {
        message = e.message;
      }
      this.error.set(message);
    } finally {
      // Unset loading state
      this.isLoading.set(false);
    }
  }

  /**
   * A utility function to split a comma-or-space-separated string of keywords into an array.
   * @param keywords The keyword string.
   * @returns An array of trimmed keywords.
   */
  splitKeywords(keywords: string | null | undefined): string[] {
    if (!keywords) {
      return [];
    }
    // Handles both comma-separated and space-separated keywords
    return keywords.split(/, | |,\s*/).map(k => k.trim()).filter(Boolean);
  }

  /**
   * Sets the selected package to show the detail view.
   */
  handleSelectPackage(pkg: SearchResult): void {
    this.selectedPackage.set(pkg);
  }

  /**
   * Clears the selected package to return to the search results.
   */
  handleCloseDetailView(): void {
    this.selectedPackage.set(null);
  }

  /**
   * Fetches search results from the live backend API.
   * @param q The search query string.
   * @returns A Promise that resolves to a SearchResponse.
   */
  private apiSearch(q: string): Promise<SearchResponse> {
    const searchUrl = `${this.apiUrl}/search?q=${encodeURIComponent(q)}&size=20`;
    console.log(`Fetching from API: ${searchUrl}`);
    return firstValueFrom(this.http.get<SearchResponse>(searchUrl));
  }

  /**
   * Mocks the backend API call to search for packages.
   * This simulates network latency and returns different results based on the query.
   * @param q The search query string.
   * @returns A Promise that resolves to a SearchResponse.
   */
  private async mockApiSearch(q: string): Promise<SearchResponse> {
    console.log(`Simulating API search for: "${q}"`);
    await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 500)); // Simulate delay

    const lowerCaseQuery = q.toLowerCase();

    // Simulate an error response
    if (lowerCaseQuery.includes('error')) {
      throw new Error('Failed to connect to the PAIPI server.');
    }

    // Simulate an empty response
    if (lowerCaseQuery.includes('empty') || lowerCaseQuery.includes('unfindable package name')) {
      return {
        info: {query: q, count: 0},
        results: [],
      };
    }

    // Return the example response for the specific query
    if (lowerCaseQuery.includes('terminal text editor')) {
      return {
        info: {query: q, count: 2},
        results: [
          {
            name: "prompt-toolkit",
            version: "3.0.43",
            description: "Library for building powerful interactive command line applications in Python",
            summary: "Library for building powerful interactive command line applications",
            author: "Jonathan Slenders",
            author_email: "jonathan@slenders.be",
            home_page: "https://github.com/prompt-toolkit/python-prompt-toolkit",
            package_url: "https://pypi.org/project/prompt-toolkit/",
            keywords: "cli, terminal, editor, interactive, command-line",
            license: "BSD-3-Clause",
            classifiers: ["Development Status :: 5 - Production/Stable", "Programming Language :: Python :: 3"],
            requires_python: ">=3.7",
            project_urls: {Homepage: "https://github.com/prompt-toolkit/python-prompt-toolkit"},
            package_exists: true,

            readme_cached: false,
            package_cached: false
          },
          {
            name: "textual",
            version: "0.52.1",
            description: "Modern Text User Interface framework for Python using Rich as the renderer",
            summary: "Text User Interface framework for Python",
            author: "Will McGugan",
            author_email: "willmcgugan@gmail.com",
            home_page: "https://github.com/Textualize/textual",
            package_url: "https://pypi.org/project/textual/",
            keywords: "tui, terminal, interface, rich, text editor",
            license: "MIT",
            classifiers: ["Development Status :: 4 - Beta", "Programming Language :: Python :: 3"],
            requires_python: ">=3.7",
            project_urls: {Homepage: "https://github.com/Textualize/textual"},
            package_exists: true,

            readme_cached: false,
            package_cached: false
          }
        ]
      };
    }

    // Default mock response for any other query
    return {
      info: {query: q, count: 3},
      results: [
        {
          name: "requests",
          version: "2.31.0",
          summary: "A simple, yet elegant, HTTP library.",
          home_page: "https://requests.readthedocs.io/",
          package_url: "https://pypi.org/project/requests/",
          keywords: "http, web, client, api",
          license: "Apache 2.0",
          requires_python: ">=3.7",
          package_exists: true,

          readme_cached: false,
          package_cached: false
        },
        {
          name: "fastapi",
          version: "0.109.2",
          summary: "A modern, fast (high-performance), web framework for building APIs with Python.",
          home_page: "https://fastapi.tiangolo.com/",
          package_url: "https://pypi.org/project/fastapi/",
          keywords: "api, web, framework, rest",
          license: "MIT",
          requires_python: ">=3.8",
          package_exists: true,
          readme_cached: false,
          package_cached: false
        },
        {
          name: "pandas",
          version: "2.2.0",
          summary: "Powerful data structures for data analysis, time series, and statistics.",
          home_page: "https://pandas.pydata.org",
          package_url: "https://pypi.org/project/pandas/",
          keywords: "data analysis, dataframe, statistics",
          license: "BSD 3-Clause",
          requires_python: ">=3.9",
          package_exists: true,
          readme_cached: false,
          package_cached: false
        }
      ]
    };
  }
}
```
## File: src\app\models.ts
```typescript
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
 * Represents the response from the /availability endpoint.
 */
interface AvailabilityResponse {
  name: string;
  readme_cached: boolean;
  package_cached: boolean;
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
```
## File: src\app\package_page.html
```html
<div class="bg-gray-800 border border-gray-700 rounded-lg p-6 animate-fade-in">
      <!-- Back Button -->
      <button (click)="close.emit()"
              class="mb-6 bg-gray-700 hover:bg-gray-600 text-gray-200 px-4 py-2 rounded-lg transition-colors flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"></line>
          <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
        Back to Search
      </button>

      <!-- Header -->
      <div class="flex flex-col sm:flex-row justify-between items-start gap-4 mb-4">
        <div>
          <h2 class="text-3xl font-bold" [class.text-red-500]="!package.package_exists"
              [class.text-blue-400]="package.package_exists">
            {{ package.name }}
            @if (!package.package_exists) {
              <span class="text-sm align-middle">(Package not found on PyPI)</span>
            }
          </h2>
          <p class="text-gray-400 mt-1">{{ package.summary }}</p>
        </div>
        <span
          class="text-sm font-mono bg-gray-700 text-yellow-300 px-3 py-1 rounded-md flex-shrink-0">{{ package.version }}</span>
      </div>

<!--      <p class="text-gray-300 mb-6">{{ package.description }}</p>-->

      <!-- Metadata Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-gray-700 pt-6">
        <div>
          <h3 class="text-lg font-semibold text-gray-200 mb-3">Details</h3>
          <dl class="space-y-2 text-sm">
            @if (package.author) {
              <div class="grid grid-cols-3 gap-1">
                <dt class="text-gray-500">Author</dt>
                <dd class="col-span-2 text-gray-300">{{ package.author }}</dd>
              </div>
            }
            @if (package.license) {
              <div class="grid grid-cols-3 gap-1">
                <dt class="text-gray-500">License</dt>
                <dd class="col-span-2 text-gray-300">{{ package.license }}</dd>
              </div>
            }
            @if (package.requires_python) {
              <div class="grid grid-cols-3 gap-1">
                <dt class="text-gray-500">Requires</dt>
                <dd class="col-span-2 text-gray-300">Python {{ package.requires_python }}</dd>
              </div>
            }
          </dl>
        </div>
        <div>
          <h3 class="text-lg font-semibold text-gray-200 mb-3">Links</h3>
          <div class="flex flex-col space-y-2 text-sm">
            @if (package.home_page) {
              <a [href]="package.home_page" target="_blank" rel="noopener noreferrer"
                 class="text-blue-400 hover:underline">Homepage</a>
            }
            @if (package.package_url) {
              <a [href]="package.package_url" target="_blank" rel="noopener noreferrer"
                 class="text-blue-400 hover:underline">PyPI Package URL</a>
            }
            @if (package.project_urls?.['Documentation']) {
              <a [href]="package.project_urls?.['Documentation']" target="_blank" rel="noopener noreferrer"
                 class="text-blue-400 hover:underline">Documentation</a>
            }
          </div>
        </div>
      </div>

      <!-- Keywords -->
      @if (splitKeywords(package.keywords).length > 0) {
        <div class="mt-6 pt-6 border-t border-gray-700">
          <h3 class="text-lg font-semibold text-gray-200 mb-3">Keywords</h3>
          <div class="flex flex-wrap gap-2">
            @for (keyword of splitKeywords(package.keywords); track $index) {
              <span class="text-xs bg-blue-900/50 text-blue-300 px-2 py-1 rounded-full">{{ keyword }}</span>
            }
          </div>
        </div>
      }

      <!-- README Generation -->
      <div class="mt-6 pt-6 border-t border-gray-700">
        <h3 class="text-lg font-semibold text-gray-200 mb-3">README.md</h3>

        @if (readmeIsLoading()) {
          <div class="flex items-center gap-3 text-gray-400 p-4 bg-gray-800 rounded-md">
            <svg class="animate-spin h-5 w-5 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none"
                 viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Generating README with AI...</span>
          </div>
        } @else if (safeReadmeHtml()) {
          <div class="prose prose-sm prose-invert bg-gray-900/50 p-4 rounded-md border border-gray-600 max-w-none">
            <div [innerHTML]="safeReadmeHtml()"></div>
          </div>
          <div class="mt-6 flex gap-4">
            <button (click)="onDownloadPackage()" [disabled]="packageIsLoading()"
                    class="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-4 rounded-lg transition-colors flex items-center justify-center w-48 disabled:opacity-50 disabled:cursor-not-allowed">
              @if (packageIsLoading()) {
                <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              } @else {
                <span>Download Package</span>
              }
            </button>
            <button (click)="resetReadme()"
                    class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-2 px-4 rounded-lg transition-colors">
              Regenerate
            </button>
          </div>
        } @else {
          <p class="text-gray-400 text-sm mb-4">Click the button below to generate a README.md file for this
            package.</p>
          <button (click)="onGenerateReadme()"
                  class="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded-lg transition-colors">
            Generate README.md
          </button>
          @if (readmeError()) {
            <p class="text-red-400 mt-2">{{ readmeError() }}</p>
          }
        }
      </div>
    </div>
```
## File: src\app\package_page.ts
```typescript
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  EventEmitter,
  inject,
  Input,
  OnInit,
  Output, // <-- Import Output
  signal
} from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { firstValueFrom } from 'rxjs';

@Component({
  selector: 'app-package-detail',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './package_page.html', // We'll use a separate template file for clarity
  styles: [`
    .animate-fade-in {
      animation: fadeIn 0.5s ease-in-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
  `]
})
// Implement the OnInit interface
export class PackageDetailComponent implements OnInit {
  @Input({ required: true }) package!: SearchResult;
  @Output() close = new EventEmitter<void>();
  // --- NEW: Event emitter to notify the parent component ---
  @Output() readmeGenerated = new EventEmitter<string>();

  private http = inject(HttpClient);
  private sanitizer = inject(DomSanitizer);
  private readonly apiUrl = 'http://127.0.0.1:8080';

  readmeContent = signal<string | null>(null);
  readmeIsLoading = signal<boolean>(false);
  packageIsLoading = signal<boolean>(false);
  readmeError = signal<string | null>(null);

  safeReadmeHtml = computed<SafeHtml | null>(() => {
    const markdown = this.readmeContent();
    if (markdown && (window as any).marked) {
      const html = (window as any).marked.parse(markdown);
      return this.sanitizer.bypassSecurityTrustHtml(html);
    }
    return null;
  });

  // --- NEW: ngOnInit Lifecycle Hook ---
  ngOnInit(): void {
    console.log(`[PackageDetail] ngOnInit for '${this.package.name}'. Checking live availability from server...`);
    this.checkAndLoadCachedReadme();
  }

  async checkAndLoadCachedReadme(): Promise<void> {
    this.readmeIsLoading.set(true);
    this.readmeError.set(null);
    this.readmeContent.set(null);

    try {
      const availabilityUrl = `${this.apiUrl}/availability?name=${encodeURIComponent(this.package.name)}`;
      console.log(`[PackageDetail] Checking availability at: ${availabilityUrl}`);
      const availability = await firstValueFrom(this.http.get<AvailabilityResponse>(availabilityUrl));

      if (availability.readme_cached) {
        console.log(`[PackageDetail] README is cached on server. Fetching content...`);
        const readmeUrl = `${this.apiUrl}/readme/by-name/${encodeURIComponent(this.package.name)}`;
        const markdown = await firstValueFrom(this.http.get(readmeUrl, { responseType: 'text' }));
        this.readmeContent.set(markdown);
      } else {
        console.log(`[PackageDetail] README is not cached on server. Waiting for user to generate.`);
      }
    } catch (err: any) {
      console.error("Failed to check/load cached README:", err);
      this.readmeError.set(err.error?.detail || err.message || 'Could not check for cached README.');
    } finally {
      this.readmeIsLoading.set(false);
    }
  }

  async onGenerateReadme(): Promise<void> {
    // --- NEW: Add logging for debugging ---
    console.log(`[PackageDetail] Generating new README for '${this.package.name}'...`);

    this.readmeIsLoading.set(true);
    this.readmeError.set(null);
    this.readmeContent.set(null);

    const payload: ReadmeRequest = {
      name: this.package.name,
      summary: this.package.summary,
      description: this.package.description,
      license: this.package.license,
      homepage: this.package.home_page,
      documentation_url: this.package.project_urls?.['Documentation'],
      python_requires: this.package.requires_python,
    };

    try {
      const markdown = await firstValueFrom(this.http.post(`${this.apiUrl}/readme`, payload, { responseType: 'text' }));
      this.readmeContent.set(markdown);

      // --- NEW: Emit event to parent on success ---
      console.log(`[PackageDetail] Emitting readmeGenerated event for '${this.package.name}'`);
      this.readmeGenerated.emit(this.package.name);

    } catch (err: any) {
      console.error("README Generation Error:", err);
      this.readmeError.set(err.error?.detail || err.message || 'Failed to generate README.');
    } finally {
      this.readmeIsLoading.set(false);
    }
  }

  async onDownloadPackage(): Promise<void> {
    const markdown = this.readmeContent();
    if (!markdown) return;

    this.packageIsLoading.set(true);
    const payload: PackageGenerateRequest = {
      readme_markdown: markdown,
      metadata: { ...this.package }
    };

    try {
      const blob = await firstValueFrom(this.http.post(`${this.apiUrl}/generate_package`, payload, { responseType: 'blob' }));
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${this.package.name.replace(/[^a-z0-9]/gi, '_')}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 501) {
        alert('The package generation feature is not yet implemented on the server.');
      } else {
        console.error("Package Download Error:", err);
        alert('An error occurred while trying to generate the package.');
      }
    } finally {
      this.packageIsLoading.set(false);
    }
  }

  resetReadme(): void {
    this.readmeContent.set(null);
    this.readmeError.set(null);
  }

  /**
   * Utility to split keywords for display.
   */
  splitKeywords(keywords: string | null | undefined): string[] {
    if (!keywords) return [];
    return keywords.split(/, | |,\s*/).map(k => k.trim()).filter(Boolean);
  }
}
```
