import { ChangeDetectionStrategy, Component, signal, inject, Input, Output, EventEmitter } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpClientModule, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

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

// --- MAIN APP COMPONENT ---

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [FormsModule, HttpClientModule, 'PackageDetailComponent'], // Use string literal for forward reference
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="bg-gray-900 text-gray-200 min-h-screen font-sans antialiased">
      <main class="container mx-auto p-4 sm:p-6 lg:p-8">

        <header class="text-center mb-8">
          <div class="flex items-center justify-center gap-3 mb-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 256 256" class="text-yellow-400"><path fill="currentColor" d="M139.23 219.88a12.12 12.12 0 0 1-13-5.22l-37-64.14a12 12 0 0 1 10.4-18.4l64.09 37a12 12 0 0 1-5.21 23l-3.21.54l-11.89-20.6l10.4-6a12 12 0 0 1 15.21-1.22a12.06 12.06 0 0 1 4 14.61l-24.46 42.37a12 12 0 0 1-5.13 7.06Zm-16.11-99.76l-37-64.14a12 12 0 0 1 10.4-18.4l64.09 37a12 12 0 0 1-5.21 23l-3.21.54l-11.89-20.6l10.4-6a12 12 0 1 1 10.4 20.8l-37 21.36a12 12 0 0 1-15-2.56Z M232 128a104 104 0 1 1-104-104a104.11 104.11 0 0 1 104 104Zm-16 0a88 88 0 1 0-88 88a88.1 88.1 0 0 0 88-88Z"/></svg>
            <h1 class="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-yellow-300 to-blue-400">PAIPI</h1>
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
            />
          } @else {
            <!-- SEARCH VIEW -->
            <form (submit)="onSearch($event)" class="w-full mb-10">
              <div class="relative">
                <input [(ngModel)]="query" name="search-query" type="search" class="w-full pl-12 pr-4 py-3 bg-gray-800 border-2 border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors" placeholder="e.g., terminal text editors, http clients...">
                <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-500"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                </div>
              </div>
            </form>

            @if (isLoading()) {
              <div class="flex flex-col items-center justify-center text-gray-500 mt-12"><svg class="animate-spin h-8 w-8 text-blue-400 mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><p>Searching for '{{ lastQuery() }}'...</p></div>
            }
            @if (error()) {
              <div class="bg-red-900/50 border border-red-700 text-red-300 px-4 py-3 rounded-lg text-center mt-12" role="alert"><strong class="font-bold">An error occurred:</strong><span class="block sm:inline ml-2">{{ error() }}</span></div>
            }
            @if (!isLoading() && !error() && searchPerformed()) {
              @if (searchResults().length > 0) {
                <div class="flex flex-col gap-4">
                  <p class="text-gray-400 mb-2">Showing {{ searchResults().length }} results for "{{ lastQuery() }}"</p>
                  @for (pkg of searchResults(); track pkg.name) {
                    <div (click)="handleSelectPackage(pkg)" class="bg-gray-800 border border-gray-700 rounded-lg p-5 transition-all hover:border-blue-500 hover:shadow-lg cursor-pointer">
                      <div class="flex flex-col sm:flex-row justify-between items-baseline gap-2">
                        <span class="text-xl font-bold" [class.text-red-500]="!pkg.package_exists" [class.text-blue-400]="pkg.package_exists">
                          {{ pkg.name }}
                        </span>
                        <span class="text-xs font-mono bg-gray-700 text-yellow-300 px-2 py-1 rounded-md">{{ pkg.version }}</span>
                      </div>
                      <p class="mt-2 text-gray-300">{{ pkg.summary }}</p>
                    </div>
                  }
                </div>
              } @else {
                <div class="text-center text-gray-500 mt-12"><p class="text-xl mb-2">No results found for "{{ lastQuery() }}".</p><p>Please try a different search query.</p></div>
              }
            } @else if (!isLoading() && !searchPerformed()) {
              <div class="text-center text-gray-500 mt-12"><p>Search for Python packages using AI's knowledge.</p></div>
            }
          }
        </div>
      </main>
    </div>
  `
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

  /**
   * Handles the search form submission.
   * @param event The form submission event.
   */
  async onSearch(event: Event): Promise<void> {
    event.preventDefault();
    const currentQuery = this.query().trim();
    if (!currentQuery) return;

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
      const response = await this.apiSearch(currentQuery);
      this.searchResults.set(response.results); // Use API response directly
    } catch (e: any) {
      console.error('API Error:', e);
      let message = 'Failed to fetch results from the server.';
      if(e instanceof HttpErrorResponse) {
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
}



