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

